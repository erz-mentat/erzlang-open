from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from ir.models import Event, Rule
from runtime.errors import ERROR_ENVELOPE_FIELD_ORDER, build_error_envelope, render_error_envelope_json
from runtime.eval import eval_policies, eval_policies_envelope, validate_trace, validate_trace_step


ROOT = Path(__file__).resolve().parents[1]
ERROR_FIXTURES = ROOT / "tests" / "fixtures" / "errors"


class RuntimeEvalTests(unittest.TestCase):
    def _read_error_snapshot(self, name: str) -> str:
        return (ERROR_FIXTURES / name).read_text(encoding="utf-8")

    def test_eval_is_deterministic_for_same_inputs(self) -> None:
        event = {
            "type": "ingest",
            "payload": {
                "timestamp": "2026-02-24T17:00:00Z",
                "seed": 7,
                "z": 2,
                "a": {"b": 1, "a": 0},
            },
        }
        rules = [
            {
                "id": "r2",
                "when": ["event_type_present"],
                "then": [{"kind": "act", "params": {"z": 2, "a": 1}}],
            },
            {
                "id": "r1",
                "when": ["event_type_present", "event_type_equals:ingest", "payload_has:a"],
                "then": [{"kind": "notify", "params": {"z": 9, "a": {"b": 2, "a": 1}}}],
            },
        ]

        first_actions, first_trace = eval_policies(event, rules)
        second_actions, second_trace = eval_policies(event, rules)

        self.assertEqual(first_actions, second_actions)
        self.assertEqual(first_trace, second_trace)

        # Runtime sorts by priority descending, then rule_id, for deterministic ordering.
        self.assertEqual([step["rule_id"] for step in first_trace], ["r1", "r2"])

        self.assertEqual(first_actions[0]["params"], {"a": {"a": 1, "b": 2}, "z": 9})
        self.assertEqual(first_actions[1]["params"], {"a": 1, "z": 2})

    def test_rule_priority_overrides_rule_id_order_and_uses_rule_id_as_tiebreaker(self) -> None:
        event = {"type": "priority_demo", "payload": {"source": "fixture"}}
        rules = [
            {
                "id": "route_default",
                "when": ["event_type_present", "event_type_equals:priority_demo"],
                "then": [{"kind": "route", "params": {"target": "default"}}],
            },
            {
                "id": "route_urgent_b",
                "priority": 100,
                "when": ["event_type_present", "event_type_equals:priority_demo"],
                "then": [{"kind": "route", "params": {"target": "urgent-b"}}],
            },
            {
                "id": "route_urgent_a",
                "priority": 100,
                "when": ["event_type_present", "event_type_equals:priority_demo"],
                "then": [{"kind": "route", "params": {"target": "urgent-a"}}],
            },
        ]

        actions, trace = eval_policies(event, rules)

        self.assertEqual(
            [action["params"]["target"] for action in actions],
            ["urgent-a", "urgent-b", "default"],
        )
        self.assertEqual(
            [step["rule_id"] for step in trace],
            ["route_urgent_a", "route_urgent_b", "route_default"],
        )

    def test_rule_priority_must_be_integer_when_present(self) -> None:
        event = {"type": "ingest", "payload": {"x": 1}}

        for raw_priority in (True, 1.5, "10"):
            with self.subTest(priority=raw_priority):
                with self.assertRaisesRegex(TypeError, "rule.priority must be an integer"):
                    eval_policies(
                        event,
                        [
                            {
                                "id": "r1",
                                "priority": raw_priority,
                                "when": ["event_type_present"],
                                "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                            }
                        ],
                    )

    def test_trace_contract_has_required_fields_and_optional_score(self) -> None:
        actions, trace = eval_policies(
            event={"type": "ingest", "payload": {"x": 1}},
            rules=[
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                },
                {
                    "id": "r2",
                    "when": ["payload_has:y"],
                    "then": [{"kind": "act", "params": {"rule_id": "r2"}}],
                },
            ],
            now=1700000000,
            seed="deterministic-seed",
            include_score=False,
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(len(trace), 1)

        step = trace[0]
        self.assertIn("rule_id", step)
        self.assertIn("matched_clauses", step)
        self.assertNotIn("score", step)
        self.assertNotIn("calibrated_probability", step)
        self.assertEqual(step["timestamp"], 1700000000)
        self.assertEqual(step["seed"], "deterministic-seed")

    def test_eval_policies_envelope_success_omits_error_field(self) -> None:
        payload = eval_policies_envelope(
            event={"type": "ingest", "payload": {"x": 1}},
            rules=[
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                }
            ],
            include_score=False,
        )

        self.assertEqual(list(payload.keys()), ["actions", "trace"])
        self.assertEqual(payload["actions"], [{"kind": "act", "params": {"rule_id": "r1"}}])
        self.assertEqual(payload["trace"], [{"rule_id": "r1", "matched_clauses": ["event_type_present"]}])
        self.assertNotIn("error", payload)

    def test_eval_policies_envelope_value_failure_returns_runtime_error_envelope_parity_snapshot(self) -> None:
        failing_inputs = {
            "event": {"type": "ingest", "payload": {"x": 1}},
            "rules": [
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                }
            ],
            "calibration": {"points": [{"raw_score": 0.0, "probability": 0.1}]},
        }

        payload = eval_policies_envelope(**failing_inputs)
        repeated_payload = eval_policies_envelope(**failing_inputs)

        self.assertEqual(payload, repeated_payload)
        self.assertEqual(list(payload.keys()), ["actions", "trace", "error"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["trace"], [])

        error = payload["error"]
        self.assertEqual(list(error.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
        self.assertEqual(error["code"], "ERZ_RUNTIME_VALUE")
        self.assertEqual(error["stage"], "runtime")
        self.assertEqual(error["details"]["command"], "eval")
        self.assertEqual(error["details"]["error_type"], "ValueError")

        with self.assertRaises(ValueError) as value_ctx:
            eval_policies(**failing_inputs)

        expected_error = build_error_envelope(value_ctx.exception, stage="runtime", command="eval")
        self.assertEqual(error, expected_error)

        rendered = render_error_envelope_json(error) + "\n"
        self.assertEqual(rendered, self._read_error_snapshot("runtime_value.stderr"))

    def test_eval_policies_envelope_type_failure_returns_runtime_error_envelope(self) -> None:
        failing_inputs = {
            "event": {"type": "ingest", "payload": {"x": 1}},
            "rules": [
                {
                    "id": "r1",
                    "when": "event_type_present",
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                }
            ],
        }

        payload = eval_policies_envelope(**failing_inputs)

        self.assertEqual(list(payload.keys()), ["actions", "trace", "error"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["trace"], [])

        error = payload["error"]
        self.assertEqual(error["code"], "ERZ_RUNTIME_CONTRACT")
        self.assertEqual(error["stage"], "runtime")
        self.assertEqual(error["details"]["command"], "eval")
        self.assertEqual(error["details"]["error_type"], "TypeError")

        with self.assertRaises(TypeError) as type_ctx:
            eval_policies(**failing_inputs)

        expected_error = build_error_envelope(type_ctx.exception, stage="runtime", command="eval")
        self.assertEqual(error, expected_error)

    def test_runtime_error_envelope_rendering_parity_for_contract_and_value_failures(self) -> None:
        with self.assertRaises(TypeError) as contract_ctx:
            validate_trace_step({"rule_id": "r1", "matched_clauses": []})

        with self.assertRaises(ValueError) as value_ctx:
            eval_policies(
                event={"type": "ingest", "payload": {"x": 1}},
                rules=[
                    {
                        "id": "r1",
                        "when": ["event_type_present"],
                        "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                    }
                ],
                calibration={"points": [{"raw_score": 0.0, "probability": 0.1}]},
            )

        cases = [
            {
                "name": "runtime_contract",
                "exc": contract_ctx.exception,
                "snapshot": "runtime_contract.stderr",
                "expected_code": "ERZ_RUNTIME_CONTRACT",
                "expected_error_type": "TypeError",
            },
            {
                "name": "runtime_value",
                "exc": value_ctx.exception,
                "snapshot": "runtime_value.stderr",
                "expected_code": "ERZ_RUNTIME_VALUE",
                "expected_error_type": "ValueError",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                envelope = build_error_envelope(case["exc"], stage="runtime", command="eval")
                self.assertEqual(list(envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
                self.assertEqual(list(envelope["details"].keys()), ["error_type", "command"])
                self.assertEqual(envelope["code"], case["expected_code"])
                self.assertEqual(envelope["details"]["error_type"], case["expected_error_type"])
                self.assertEqual(envelope["details"]["command"], "eval")

                rendered = render_error_envelope_json(envelope) + "\n"
                self.assertEqual(rendered, self._read_error_snapshot(case["snapshot"]))

    def test_eval_policies_envelope_runtime_error_code_mapping_triad_canary(self) -> None:
        base_inputs = {
            "event": {"type": "ingest", "payload": {"x": 1}},
            "rules": [
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                }
            ],
        }

        cases = [
            {
                "name": "runtime_contract_type_error",
                "inputs": {
                    "event": base_inputs["event"],
                    "rules": [
                        {
                            "id": "r1",
                            "when": "event_type_present",
                            "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                        }
                    ],
                },
                "expected_code": "ERZ_RUNTIME_CONTRACT",
                "expected_error_type": "TypeError",
            },
            {
                "name": "runtime_value_error",
                "inputs": {
                    **base_inputs,
                    "calibration": {"points": [{"raw_score": 0.0, "probability": 0.1}]},
                },
                "expected_code": "ERZ_RUNTIME_VALUE",
                "expected_error_type": "ValueError",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                payload = eval_policies_envelope(**case["inputs"])
                self.assertEqual(list(payload.keys()), ["actions", "trace", "error"])
                self.assertEqual(payload["actions"], [])
                self.assertEqual(payload["trace"], [])
                self.assertEqual(payload["error"]["code"], case["expected_code"])
                self.assertEqual(payload["error"]["stage"], "runtime")
                self.assertEqual(payload["error"]["details"]["command"], "eval")
                self.assertEqual(payload["error"]["details"]["error_type"], case["expected_error_type"])

        with patch("runtime.eval.map_raw_score_to_probability", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                eval_policies_envelope(
                    **base_inputs,
                    include_score=False,
                    calibration={
                        "points": [
                            {"raw_score": 0.0, "probability": 0.1},
                            {"raw_score": 1.0, "probability": 0.9},
                        ]
                    },
                )

    def test_runtime_envelope_stage_command_matrix_parity_canary(self) -> None:
        cases = [
            {
                "name": "runtime_contract",
                "inputs": {
                    "event": {"type": "ingest", "payload": {"x": 1}},
                    "rules": [
                        {
                            "id": "r1",
                            "when": "event_type_present",
                            "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                        }
                    ],
                },
                "expected_exc": TypeError,
                "expected_error_type": "TypeError",
            },
            {
                "name": "runtime_value",
                "inputs": {
                    "event": {"type": "ingest", "payload": {"x": 1}},
                    "rules": [
                        {
                            "id": "r1",
                            "when": ["event_type_present"],
                            "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                        }
                    ],
                    "calibration": {"points": [{"raw_score": 0.0, "probability": 0.1}]},
                },
                "expected_exc": ValueError,
                "expected_error_type": "ValueError",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                payload = eval_policies_envelope(**case["inputs"])
                self.assertEqual(list(payload.keys()), ["actions", "trace", "error"])
                self.assertEqual(payload["actions"], [])
                self.assertEqual(payload["trace"], [])

                adapter_error = payload["error"]
                self.assertEqual(adapter_error["stage"], "runtime")
                self.assertEqual(adapter_error["details"]["command"], "eval")

                with self.assertRaises(case["expected_exc"]) as exc_ctx:
                    eval_policies(**case["inputs"])

                direct_error = build_error_envelope(exc_ctx.exception, stage="runtime", command="eval")
                self.assertEqual(adapter_error, direct_error)
                self.assertEqual(adapter_error["stage"], direct_error["stage"])
                self.assertEqual(
                    adapter_error["details"]["command"],
                    direct_error["details"]["command"],
                )

                expected_detail_items = [
                    ("error_type", case["expected_error_type"]),
                    ("command", "eval"),
                ]
                self.assertEqual(list(adapter_error["details"].items()), expected_detail_items)
                self.assertEqual(list(direct_error["details"].items()), expected_detail_items)

                rendered_adapter = render_error_envelope_json(adapter_error) + "\n"
                rendered_direct = render_error_envelope_json(direct_error) + "\n"
                self.assertEqual(rendered_adapter, rendered_direct)

    def test_eval_policies_envelope_non_contract_internal_failure_propagates(self) -> None:
        with patch("runtime.eval.map_raw_score_to_probability", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                eval_policies_envelope(
                    event={"type": "ingest", "payload": {"x": 1}},
                    rules=[
                        {
                            "id": "r1",
                            "when": ["event_type_present"],
                            "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                        }
                    ],
                    include_score=False,
                    calibration={
                        "points": [
                            {"raw_score": 0.0, "probability": 0.1},
                            {"raw_score": 1.0, "probability": 0.9},
                        ]
                    },
                )

    def test_trace_includes_calibrated_probability_when_calibration_is_provided(self) -> None:
        _, trace = eval_policies(
            event={"type": "ingest", "payload": {"x": 1}},
            rules=[
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                }
            ],
            include_score=False,
            calibration={
                "points": [
                    {"raw_score": 0.0, "probability": 0.1},
                    {"raw_score": 1.0, "probability": 0.9},
                ]
            },
        )

        self.assertEqual(len(trace), 1)
        self.assertNotIn("score", trace[0])
        self.assertEqual(trace[0]["calibrated_probability"], 0.9)
        self.assertEqual(validate_trace_step(trace[0]), trace[0])

    def test_every_fired_rule_yields_conforming_trace_step(self) -> None:
        _, trace = eval_policies(
            event={"type": "ingest", "payload": {"a": 1}},
            rules=[
                {
                    "id": "r2",
                    "when": ["payload_has:missing"],
                    "then": [{"kind": "act", "params": {"rule_id": "r2"}}],
                },
                {
                    "id": "r1",
                    "when": ["event_type_present", "payload_has:a"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                },
                {
                    "id": "r3",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r3"}}],
                },
            ],
            now="2026-02-25T15:00:00Z",
            seed=7,
        )

        self.assertEqual([step["rule_id"] for step in trace], ["r1", "r3"])
        self.assertEqual(trace[0]["matched_clauses"], ["event_type_present", "payload_has:a"])

        fired_rule_ids = [step["rule_id"] for step in trace]
        self.assertEqual(validate_trace(trace, fired_rule_ids=fired_rule_ids), trace)

        for step in trace:
            self.assertEqual(validate_trace_step(step), step)

    def test_validate_trace_step_rejects_malformed_records(self) -> None:
        malformed_steps = [
            ({"matched_clauses": ["event_type_present"]}, "missing required field"),
            (
                {
                    "rule_id": "r1",
                    "matched_clauses": ["event_type_present"],
                    "unexpected": 1,
                },
                "unknown field",
            ),
            ({"rule_id": "r1", "matched_clauses": []}, "non-empty list"),
            (
                {
                    "rule_id": "r1",
                    "matched_clauses": ["event_type_present"],
                    "score": 1,
                },
                "finite float",
            ),
            (
                {
                    "rule_id": "r1",
                    "matched_clauses": ["event_type_present"],
                    "calibrated_probability": 1,
                },
                "calibrated_probability",
            ),
            (
                {
                    "rule_id": "r1",
                    "matched_clauses": ["event_type_present"],
                    "calibrated_probability": 1.2,
                },
                r"\[0.0, 1.0\]",
            ),
            (
                {
                    "rule_id": "r1",
                    "matched_clauses": ["event_type_present"],
                    "timestamp": True,
                },
                "timestamp",
            ),
            (
                {
                    "rule_id": "r1",
                    "matched_clauses": ["event_type_present"],
                    "seed": True,
                },
                "seed",
            ),
        ]

        for malformed, expected_message in malformed_steps:
            with self.subTest(step=malformed):
                with self.assertRaisesRegex(TypeError, expected_message):
                    validate_trace_step(malformed)

    def test_validate_trace_rejects_fired_rule_sequence_mismatch(self) -> None:
        with self.assertRaisesRegex(TypeError, "does not match fired rule sequence"):
            validate_trace(
                [{"rule_id": "r1", "matched_clauses": ["event_type_present"], "score": 1.0}],
                fired_rule_ids=["r2"],
            )

    def test_rule_fires_only_when_all_clauses_match(self) -> None:
        actions, trace = eval_policies(
            event={"type": "alert", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r1",
                    "when": [
                        "event_type_present",
                        "event_type_equals:alert",
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "ops"}}])
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r1",
                    "matched_clauses": [
                        "event_type_present",
                        "event_type_equals:alert",
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                }
            ],
        )

    def test_rule_does_not_fire_when_any_clause_fails(self) -> None:
        actions, trace = eval_policies(
            event={"type": "alert", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r1",
                    "when": [
                        "event_type_present",
                        "event_type_equals:alert",
                        "payload_has:confidence",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops"}}],
                }
            ],
        )

        self.assertEqual(actions, [])
        self.assertEqual(trace, [])

    def test_event_type_in_preserves_string_literal_members_for_csv_and_json_lists(self) -> None:
        actions, trace = eval_policies(
            event={"type": "null", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r-csv",
                    "when": [
                        "event_type_in:true,null",
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "csv_lane"}}],
                },
                {
                    "id": "r-json",
                    "when": [
                        'event_type_in:["00", "null"]',
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "json_lane"}}],
                },
            ],
        )

        self.assertEqual(
            actions,
            [
                {"kind": "route", "params": {"target": "csv_lane"}},
                {"kind": "route", "params": {"target": "json_lane"}},
            ],
        )
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r-csv",
                    "matched_clauses": [
                        "event_type_in:true,null",
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                },
                {
                    "rule_id": "r-json",
                    "matched_clauses": [
                        'event_type_in:["00", "null"]',
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                },
            ],
        )

    def test_event_type_not_in_matches_present_event_types_outside_blocked_sets(self) -> None:
        actions, trace = eval_policies(
            event={"type": "alert", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r1",
                    "when": [
                        "event_type_present",
                        "event_type_not_in:heartbeat,debug",
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "ops"}}])
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r1",
                    "matched_clauses": [
                        "event_type_present",
                        "event_type_not_in:heartbeat,debug",
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                }
            ],
        )

    def test_event_type_not_in_fails_cleanly_for_blocked_missing_and_empty_event_types(self) -> None:
        cases = [
            {
                "name": "blocked_type",
                "event": {"type": "heartbeat", "payload": {"severity": 0.1}},
                "clause": "event_type_not_in:heartbeat,debug",
            },
            {
                "name": "missing_type",
                "event": {"payload": {"severity": 0.1}},
                "clause": "event_type_not_in:heartbeat,debug",
            },
            {
                "name": "empty_type",
                "event": {"type": "", "payload": {"severity": 0.1}},
                "clause": "event_type_not_in:heartbeat,debug",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_event_type_case_insensitive_exact_and_set_predicates_match_mixed_case_event_types(
        self,
    ) -> None:
        actions, trace = eval_policies(
            event={"type": "Alert", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r1",
                    "when": [
                        "event_type_present",
                        "event_type_equals_ci:ALERT",
                        "event_type_in_ci:incident_candidate,alert",
                        "event_type_not_in_ci:heartbeat,debug",
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "ops"}}])
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r1",
                    "matched_clauses": [
                        "event_type_present",
                        "event_type_equals_ci:ALERT",
                        "event_type_in_ci:incident_candidate,alert",
                        "event_type_not_in_ci:heartbeat,debug",
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                }
            ],
        )

    def test_event_type_in_ci_preserves_string_literal_members_for_csv_and_json_lists(self) -> None:
        actions, trace = eval_policies(
            event={"type": "Null", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r-csv",
                    "when": [
                        "event_type_in_ci:TRUE,NULL",
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "csv_lane"}}],
                },
                {
                    "id": "r-json",
                    "when": [
                        'event_type_in_ci:["00", "NuLl"]',
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "json_lane"}}],
                },
            ],
        )

        self.assertEqual(
            actions,
            [
                {"kind": "route", "params": {"target": "csv_lane"}},
                {"kind": "route", "params": {"target": "json_lane"}},
            ],
        )
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r-csv",
                    "matched_clauses": [
                        "event_type_in_ci:TRUE,NULL",
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                },
                {
                    "rule_id": "r-json",
                    "matched_clauses": [
                        'event_type_in_ci:["00", "NuLl"]',
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                },
            ],
        )

    def test_event_type_case_insensitive_predicates_fail_cleanly_for_missing_empty_and_membership_hits(
        self,
    ) -> None:
        cases = [
            {
                "name": "equals_miss",
                "event": {"type": "heartbeat", "payload": {"severity": 0.1}},
                "clause": "event_type_equals_ci:alert",
            },
            {
                "name": "member_miss_in_ci",
                "event": {"type": "ticket", "payload": {"severity": 0.1}},
                "clause": "event_type_in_ci:alert,incident_candidate",
            },
            {
                "name": "member_hit_not_in_ci",
                "event": {"type": "Debug", "payload": {"severity": 0.1}},
                "clause": "event_type_not_in_ci:heartbeat,debug",
            },
            {
                "name": "missing_type",
                "event": {"payload": {"severity": 0.1}},
                "clause": "event_type_in_ci:alert,incident_candidate",
            },
            {
                "name": "empty_type",
                "event": {"type": "", "payload": {"severity": 0.1}},
                "clause": "event_type_not_in_ci:heartbeat,debug",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_event_type_string_predicates_match_namespaced_event_types(self) -> None:
        actions, trace = eval_policies(
            event={"type": "ops.incident_candidate.alert", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r1",
                    "when": [
                        "event_type_present",
                        "event_type_startswith:ops.",
                        "event_type_contains:incident_candidate",
                        "event_type_endswith:.alert",
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "ops"}}])
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r1",
                    "matched_clauses": [
                        "event_type_present",
                        "event_type_startswith:ops.",
                        "event_type_contains:incident_candidate",
                        "event_type_endswith:.alert",
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                }
            ],
        )

    def test_event_type_string_predicates_fail_cleanly_for_missing_empty_and_nonmatching_event_types(
        self,
    ) -> None:
        cases = [
            {
                "name": "prefix_miss",
                "event": {"type": "audit.incident_candidate.alert", "payload": {"severity": 0.1}},
                "clause": "event_type_startswith:ops.",
            },
            {
                "name": "contains_miss",
                "event": {"type": "ops.heartbeat.debug", "payload": {"severity": 0.1}},
                "clause": "event_type_contains:incident_candidate",
            },
            {
                "name": "suffix_miss",
                "event": {"type": "ops.incident_candidate.page", "payload": {"severity": 0.1}},
                "clause": "event_type_endswith:.alert",
            },
            {
                "name": "missing_type",
                "event": {"payload": {"severity": 0.1}},
                "clause": "event_type_contains:incident_candidate",
            },
            {
                "name": "empty_type",
                "event": {"type": "", "payload": {"severity": 0.1}},
                "clause": "event_type_endswith:.alert",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_event_type_negative_and_case_insensitive_string_predicates_match_namespaced_event_types(
        self,
    ) -> None:
        actions, trace = eval_policies(
            event={"type": "Ops.Incident_Candidate.Alert", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r1",
                    "when": [
                        "event_type_present",
                        "event_type_startswith_ci:ops.",
                        "event_type_contains_ci:incident_candidate",
                        "event_type_endswith_ci:.alert",
                        "event_type_not_startswith_ci:audit.",
                        "event_type_not_contains_ci:heartbeat",
                        "event_type_not_endswith_ci:.page",
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "ops"}}])
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r1",
                    "matched_clauses": [
                        "event_type_present",
                        "event_type_startswith_ci:ops.",
                        "event_type_contains_ci:incident_candidate",
                        "event_type_endswith_ci:.alert",
                        "event_type_not_startswith_ci:audit.",
                        "event_type_not_contains_ci:heartbeat",
                        "event_type_not_endswith_ci:.page",
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                }
            ],
        )

    def test_event_type_negative_and_case_insensitive_string_predicates_fail_cleanly_for_hits_misses_and_missing_types(
        self,
    ) -> None:
        cases = [
            {
                "name": "prefix_miss_ci",
                "event": {"type": "audit.incident_candidate.alert", "payload": {"severity": 0.1}},
                "clause": "event_type_startswith_ci:ops.",
            },
            {
                "name": "negative_contains_hit_ci",
                "event": {"type": "ops.heartbeat.alert", "payload": {"severity": 0.1}},
                "clause": "event_type_not_contains_ci:heartbeat",
            },
            {
                "name": "negative_suffix_hit_ci",
                "event": {"type": "Ops.Incident_Candidate.Alert", "payload": {"severity": 0.1}},
                "clause": "event_type_not_endswith_ci:.alert",
            },
            {
                "name": "missing_type",
                "event": {"payload": {"severity": 0.1}},
                "clause": "event_type_contains_ci:incident_candidate",
            },
            {
                "name": "empty_type",
                "event": {"type": "", "payload": {"severity": 0.1}},
                "clause": "event_type_not_startswith_ci:audit.",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_event_type_regex_predicates_match_and_negate_namespaced_event_types(self) -> None:
        actions, trace = eval_policies(
            event={"type": "Ops.Incident_Candidate.Alert", "payload": {"severity": 0.9}},
            rules=[
                {
                    "id": "r1",
                    "when": [
                        "event_type_present",
                        r"event_type_matches:^Ops\.[A-Za-z_]+\.(Alert|Page)$",
                        r"event_type_matches_ci:^ops\.[a-z_]+\.(alert|page)$",
                        r"event_type_not_matches:^ops\.heartbeat\..*$",
                        r"event_type_not_matches_ci:^OPS\.HEARTBEAT\..*$",
                        "payload_has:severity",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops_regex"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "ops_regex"}}])
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r1",
                    "matched_clauses": [
                        "event_type_present",
                        r"event_type_matches:^Ops\.[A-Za-z_]+\.(Alert|Page)$",
                        r"event_type_matches_ci:^ops\.[a-z_]+\.(alert|page)$",
                        r"event_type_not_matches:^ops\.heartbeat\..*$",
                        r"event_type_not_matches_ci:^OPS\.HEARTBEAT\..*$",
                        "payload_has:severity",
                    ],
                    "score": 1.0,
                }
            ],
        )

    def test_event_type_regex_predicates_fail_cleanly_for_hits_misses_and_missing_types(
        self,
    ) -> None:
        cases = [
            {
                "name": "regex_miss",
                "event": {"type": "ops.heartbeat.alert", "payload": {"severity": 0.1}},
                "clause": r"event_type_matches:^ops\.incident_candidate\..*$",
            },
            {
                "name": "regex_ci_miss",
                "event": {"type": "ticket.created", "payload": {"severity": 0.1}},
                "clause": r"event_type_matches_ci:^OPS\.INCIDENT_.*$",
            },
            {
                "name": "negative_regex_hit",
                "event": {"type": "ops.heartbeat.alert", "payload": {"severity": 0.1}},
                "clause": r"event_type_not_matches:^ops\.heartbeat\..*$",
            },
            {
                "name": "negative_regex_ci_hit",
                "event": {"type": "Ops.Heartbeat.Alert", "payload": {"severity": 0.1}},
                "clause": r"event_type_not_matches_ci:^ops\.heartbeat\..*$",
            },
            {
                "name": "missing_type",
                "event": {"payload": {"severity": 0.1}},
                "clause": r"event_type_matches_ci:^ops\.incident_.*$",
            },
            {
                "name": "empty_type",
                "event": {"type": "", "payload": {"severity": 0.1}},
                "clause": r"event_type_not_matches_ci:^ops\.heartbeat\..*$",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_event_type_payload_path_predicates_match_event_type_against_payload_contracts(
        self,
    ) -> None:
        clauses = [
            "event_type_present",
            "event_type_equals_path:policy.expected_type",
            "event_type_not_equals_path:blocked.exact_type",
            "event_type_equals_path_ci:policy.expected_type_ci",
            "event_type_not_equals_path_ci:blocked.exact_type_ci",
            "event_type_startswith_path:policy.prefix",
            "event_type_contains_path:policy.fragment",
            "event_type_endswith_path:policy.suffix",
            "event_type_not_startswith_path:blocked.prefix",
            "event_type_not_contains_path:blocked.fragment",
            "event_type_not_endswith_path:blocked.suffix",
            "event_type_startswith_path_ci:policy.prefix_ci",
            "event_type_contains_path_ci:policy.fragment_ci",
            "event_type_endswith_path_ci:policy.suffix_ci",
            "event_type_not_startswith_path_ci:blocked.prefix_ci",
            "event_type_not_contains_path_ci:blocked.fragment_ci",
            "event_type_not_endswith_path_ci:blocked.suffix_ci",
            r"event_type_matches_path:policy.regex",
            r"event_type_not_matches_path:blocked.regex",
            r"event_type_matches_path_ci:policy.regex_ci",
            r"event_type_not_matches_path_ci:blocked.regex_ci",
            "event_type_in_path:policy.allowed_types",
            "event_type_not_in_path:blocked.blocked_types",
            "event_type_in_path_ci:policy.allowed_types_ci",
            "event_type_not_in_path_ci:blocked.blocked_types_ci",
        ]
        actions, trace = eval_policies(
            event={
                "type": "Ops.Incident_Candidate.Alert",
                "payload": {
                    "policy": {
                        "expected_type": "Ops.Incident_Candidate.Alert",
                        "expected_type_ci": "ops.incident_candidate.alert",
                        "prefix": "Ops.",
                        "fragment": "Incident_Candidate",
                        "suffix": ".Alert",
                        "prefix_ci": "ops.",
                        "fragment_ci": "incident_candidate",
                        "suffix_ci": ".alert",
                        "regex": r"^Ops\.[A-Za-z_]+\.(Alert|Page)$",
                        "regex_ci": r"^ops\.[a-z_]+\.(alert|page)$",
                        "allowed_types": [
                            "Ops.Incident_Candidate.Alert",
                            "Ops.Incident_Candidate.Page",
                        ],
                        "allowed_types_ci": [
                            "ops.incident_candidate.alert",
                            "ops.incident_candidate.page",
                        ],
                    },
                    "blocked": {
                        "exact_type": "Ops.Heartbeat.Alert",
                        "exact_type_ci": "ops.heartbeat.alert",
                        "prefix": "Audit.",
                        "fragment": "Heartbeat",
                        "suffix": ".Page",
                        "prefix_ci": "audit.",
                        "fragment_ci": "heartbeat",
                        "suffix_ci": ".page",
                        "regex": r"^Ops\.Heartbeat\..*$",
                        "regex_ci": r"^ops\.heartbeat\..*$",
                        "blocked_types": ["Ops.Heartbeat.Alert", "Audit.Alert"],
                        "blocked_types_ci": ["ops.heartbeat.alert", "audit.alert"],
                    },
                },
            },
            rules=[
                {
                    "id": "r-event-type-path",
                    "when": clauses,
                    "then": [{"kind": "route", "params": {"target": "event_type_path_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "event_type_path_lane"}}])
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r-event-type-path",
                    "matched_clauses": clauses,
                    "score": 1.0,
                }
            ],
        )

    def test_event_type_payload_path_predicates_fail_cleanly_for_missing_types_shape_misses_and_blocked_membership(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_type",
                "event": {"payload": {"policy": {"expected_type": "alert"}}},
                "clause": "event_type_equals_path:policy.expected_type",
            },
            {
                "name": "empty_type",
                "event": {"type": "", "payload": {"policy": {"expected_type": "alert"}}},
                "clause": "event_type_equals_path:policy.expected_type",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"policy": {}}},
                "clause": "event_type_equals_path:policy.expected_type",
            },
            {
                "name": "negative_exact_hit",
                "event": {"type": "alert", "payload": {"blocked": {"exact_type": "alert"}}},
                "clause": "event_type_not_equals_path:blocked.exact_type",
            },
            {
                "name": "non_string_string_operand",
                "event": {"type": "alert", "payload": {"policy": {"prefix": 7}}},
                "clause": "event_type_startswith_path:policy.prefix",
            },
            {
                "name": "invalid_regex",
                "event": {"type": "alert", "payload": {"policy": {"regex": "("}}},
                "clause": r"event_type_matches_path:policy.regex",
            },
            {
                "name": "non_list_membership",
                "event": {"type": "alert", "payload": {"policy": {"allowed_types": "alert"}}},
                "clause": "event_type_in_path:policy.allowed_types",
            },
            {
                "name": "ci_non_string_member",
                "event": {
                    "type": "alert",
                    "payload": {"policy": {"allowed_types_ci": ["alert", 1]}},
                },
                "clause": "event_type_in_path_ci:policy.allowed_types_ci",
            },
            {
                "name": "blocked_membership_hit",
                "event": {
                    "type": "alert",
                    "payload": {"blocked": {"blocked_types": ["alert", "heartbeat"]}},
                },
                "clause": "event_type_not_in_path:blocked.blocked_types",
            },
            {
                "name": "blocked_membership_hit_ci",
                "event": {
                    "type": "Alert",
                    "payload": {"blocked": {"blocked_types_ci": ["heartbeat", "alert"]}},
                },
                "clause": "event_type_not_in_path_ci:blocked.blocked_types_ci",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_exists_and_equals_fire_on_nested_payload_data(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "alert": {
                        "bucket": {"confidence": "high", "severity": "critical"},
                        "id": "A-100",
                    }
                },
            },
            rules=[
                {
                    "id": "r-path",
                    "when": [
                        "event_type_present",
                        "payload_path_exists:alert.id",
                        "payload_path_equals:alert.bucket.severity=critical",
                        "payload_path_equals:alert.bucket.confidence=high",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "ops"}}])
        self.assertEqual(
            trace,
            [
                {
                    "rule_id": "r-path",
                    "matched_clauses": [
                        "event_type_present",
                        "payload_path_exists:alert.id",
                        "payload_path_equals:alert.bucket.severity=critical",
                        "payload_path_equals:alert.bucket.confidence=high",
                    ],
                    "score": 1.0,
                }
            ],
        )

    def test_payload_path_equals_supports_list_indexes_and_scalar_literals(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"kind": "service"}],
                    "flags": {"acked": False},
                    "meta": {"code": "01"},
                    "metrics": {"attempts": 2},
                    "nullable": None,
                },
            },
            rules=[
                {
                    "id": "r-scalars",
                    "when": [
                        "payload_path_equals:entities.0.kind=service",
                        "payload_path_equals:flags.acked=false",
                        "payload_path_equals:meta.code=01",
                        "payload_path_equals:metrics.attempts=2",
                        "payload_path_equals:nullable=null",
                    ],
                    "then": [{"kind": "act", "params": {"rule_id": "r-scalars"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "act", "params": {"rule_id": "r-scalars"}}])
        self.assertEqual(trace[0]["matched_clauses"], [
            "payload_path_equals:entities.0.kind=service",
            "payload_path_equals:flags.acked=false",
            "payload_path_equals:meta.code=01",
            "payload_path_equals:metrics.attempts=2",
            "payload_path_equals:nullable=null",
        ])

    def test_payload_path_case_insensitive_exact_string_predicates_match_nested_strings_and_list_indexes(
        self,
    ) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "entities": [{"value": "Straße A100"}],
                    "message": {"summary": "VERKEHRSUNFALL AUF DER STRASSE A100"},
                    "routing": {"service": "SVC-Berlin-Edge"},
                },
            },
            rules=[
                {
                    "id": "r-equals-ci",
                    "when": [
                        "payload_path_equals_ci:routing.service=svc-berlin-edge",
                        "payload_path_equals_ci:message.summary=verkehrsunfall auf der strasse a100",
                        "payload_path_equals_ci:entities.0.value=strasse a100",
                        "payload_path_not_equals_ci:message.summary=lagebild berlin",
                    ],
                    "then": [{"kind": "route", "params": {"target": "equals_ci_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "equals_ci_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_equals_ci:routing.service=svc-berlin-edge",
                "payload_path_equals_ci:message.summary=verkehrsunfall auf der strasse a100",
                "payload_path_equals_ci:entities.0.value=strasse a100",
                "payload_path_not_equals_ci:message.summary=lagebild berlin",
            ],
        )

    def test_payload_path_case_insensitive_exact_string_predicates_fail_cleanly_for_non_string_actuals_misses_and_missing_paths(
        self,
    ) -> None:
        cases = [
            {
                "name": "non_string_actual",
                "event": {"type": "normalize", "payload": {"routing": {"service": 17}}},
                "clause": "payload_path_equals_ci:routing.service=svc-berlin-edge",
            },
            {
                "name": "equals_miss",
                "event": {
                    "type": "normalize",
                    "payload": {"message": {"summary": "Lagebild Berlin"}},
                },
                "clause": "payload_path_equals_ci:message.summary=verkehrsunfall auf der strasse a100",
            },
            {
                "name": "negated_equals_hit",
                "event": {
                    "type": "normalize",
                    "payload": {"entities": [{"value": "Straße A100"}]},
                },
                "clause": "payload_path_not_equals_ci:entities.0.value=strasse a100",
            },
            {
                "name": "missing_path",
                "event": {"type": "normalize", "payload": {"message": {"summary": "hello"}}},
                "clause": "payload_path_not_equals_ci:routing.service=svc-berlin-edge",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_in_matches_csv_membership_deterministically(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"kind": "service"}],
                    "flags": {"acked": False},
                    "meta": {"code": "01"},
                    "routing": {"severity": "warning"},
                },
            },
            rules=[
                {
                    "id": "r-membership-csv",
                    "when": [
                        "payload_path_in:routing.severity=critical,warning",
                        "payload_path_in:entities.0.kind=service,worker",
                        "payload_path_in:flags.acked=false,true",
                        "payload_path_in:meta.code=01,02",
                    ],
                    "then": [{"kind": "route", "params": {"target": "triage"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "triage"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_in:routing.severity=critical,warning",
                "payload_path_in:entities.0.kind=service,worker",
                "payload_path_in:flags.acked=false,true",
                "payload_path_in:meta.code=01,02",
            ],
        )

    def test_payload_path_in_matches_json_list_membership_deterministically(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "metrics": {"attempts": 2},
                    "nullable": None,
                    "routing": {"severity": "warning"},
                },
            },
            rules=[
                {
                    "id": "r-membership-json",
                    "when": [
                        'payload_path_in:routing.severity=["critical", "warning"]',
                        "payload_path_in:metrics.attempts=[1, 2, 3]",
                        "payload_path_in:nullable=[null, \"missing\"]",
                    ],
                    "then": [{"kind": "route", "params": {"target": "enum"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "enum"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                'payload_path_in:routing.severity=["critical", "warning"]',
                "payload_path_in:metrics.attempts=[1, 2, 3]",
                "payload_path_in:nullable=[null, \"missing\"]",
            ],
        )

    def test_payload_path_not_equals_and_not_in_match_present_nested_scalars(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "flags": {"acked": False},
                    "meta": {"code": "01"},
                    "metrics": {"attempts": 2},
                    "routing": {"severity": "warning"},
                },
            },
            rules=[
                {
                    "id": "r-negated-scalars",
                    "when": [
                        "payload_path_not_equals:routing.severity=critical",
                        "payload_path_not_equals:flags.acked=true",
                        "payload_path_not_in:meta.code=02,03",
                        "payload_path_not_in:metrics.attempts=[3, 4]",
                    ],
                    "then": [{"kind": "route", "params": {"target": "negative_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "negative_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_not_equals:routing.severity=critical",
                "payload_path_not_equals:flags.acked=true",
                "payload_path_not_in:meta.code=02,03",
                "payload_path_not_in:metrics.attempts=[3, 4]",
            ],
        )

    def test_payload_path_negated_scalar_predicates_fail_cleanly_for_missing_paths_and_matches(self) -> None:
        cases = [
            {
                "name": "missing_path_not_equals",
                "event": {"type": "alert", "payload": {"routing": {"severity": "warning"}}},
                "clause": "payload_path_not_equals:routing.confidence=high",
            },
            {
                "name": "matching_value_not_equals",
                "event": {"type": "alert", "payload": {"routing": {"severity": "warning"}}},
                "clause": "payload_path_not_equals:routing.severity=warning",
            },
            {
                "name": "missing_path_not_in",
                "event": {"type": "alert", "payload": {"routing": {"severity": "warning"}}},
                "clause": "payload_path_not_in:routing.confidence=high,low",
            },
            {
                "name": "member_hit_not_in",
                "event": {"type": "alert", "payload": {"routing": {"severity": "warning"}}},
                "clause": "payload_path_not_in:routing.severity=critical,warning",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_casefold_membership_matches_string_scalars_and_lists_deterministically(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "flags": ["new", "Escalated"],
                    "message": {"level": "Info"},
                    "routing": {
                        "channels": ["push", "Sms"],
                        "service": "svc-berlin-edge",
                    },
                    "tags": ["Berlin", "Ops"],
                },
            },
            rules=[
                {
                    "id": "r-casefold-membership",
                    "when": [
                        "payload_path_in_ci:routing.service=svc-west,SVC-BERLIN-EDGE",
                        "payload_path_not_in_ci:message.level=warning,error",
                        "payload_path_any_in_ci:tags=ops,triage",
                        "payload_path_all_in_ci:routing.channels=PUSH,sms,email",
                        "payload_path_none_in_ci:flags=archived,ignored",
                    ],
                    "then": [
                        {"kind": "route", "params": {"target": "casefold_membership_lane"}}
                    ],
                }
            ],
        )

        self.assertEqual(
            actions,
            [{"kind": "route", "params": {"target": "casefold_membership_lane"}}],
        )
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_in_ci:routing.service=svc-west,SVC-BERLIN-EDGE",
                "payload_path_not_in_ci:message.level=warning,error",
                "payload_path_any_in_ci:tags=ops,triage",
                "payload_path_all_in_ci:routing.channels=PUSH,sms,email",
                "payload_path_none_in_ci:flags=archived,ignored",
            ],
        )

    def test_payload_path_casefold_membership_fails_cleanly_for_missing_paths_non_string_actuals_and_membership_hits(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_path_in_ci",
                "event": {"type": "alert", "payload": {"routing": {"service": "svc-berlin-edge"}}},
                "clause": "payload_path_in_ci:routing.channel=push,sms",
            },
            {
                "name": "non_string_actual_in_ci",
                "event": {"type": "alert", "payload": {"routing": {"attempts": 3}}},
                "clause": "payload_path_in_ci:routing.attempts=three,four",
            },
            {
                "name": "member_hit_not_in_ci",
                "event": {"type": "alert", "payload": {"message": {"level": "Warning"}}},
                "clause": "payload_path_not_in_ci:message.level=warning,error",
            },
            {
                "name": "non_list_actual_any_in_ci",
                "event": {"type": "alert", "payload": {"tags": "ops"}},
                "clause": "payload_path_any_in_ci:tags=ops,triage",
            },
            {
                "name": "non_string_member_any_in_ci",
                "event": {"type": "alert", "payload": {"tags": ["ops", 2]}},
                "clause": "payload_path_any_in_ci:tags=ops,triage",
            },
            {
                "name": "empty_list_all_in_ci",
                "event": {"type": "alert", "payload": {"routing": {"channels": []}}},
                "clause": "payload_path_all_in_ci:routing.channels=push,sms",
            },
            {
                "name": "member_miss_all_in_ci",
                "event": {"type": "alert", "payload": {"routing": {"channels": ["push", "pager"]}}},
                "clause": "payload_path_all_in_ci:routing.channels=push,sms",
            },
            {
                "name": "member_hit_none_in_ci",
                "event": {"type": "alert", "payload": {"flags": ["new", "Ignored"]}},
                "clause": "payload_path_none_in_ci:flags=archived,ignored",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_not_exists_matches_missing_nested_keys_and_indexes(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "entities": [{"kind": "district", "value": "Spandau"}],
                    "routing": {"service": "svc-west"},
                },
            },
            rules=[
                {
                    "id": "r-missing-paths",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_not_exists:routing.fallback_target",
                        "payload_path_not_exists:entities.1.value",
                        "payload_path_not_exists:meta.audit.last_seen",
                    ],
                    "then": [{"kind": "route", "params": {"target": "absence_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "absence_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_not_exists:routing.fallback_target",
                "payload_path_not_exists:entities.1.value",
                "payload_path_not_exists:meta.audit.last_seen",
            ],
        )

    def test_payload_path_not_exists_fails_cleanly_for_present_paths_even_when_values_are_falsey(self) -> None:
        cases = [
            {
                "name": "present_null",
                "event": {"type": "alert", "payload": {"routing": {"fallback_target": None}}},
                "clause": "payload_path_not_exists:routing.fallback_target",
            },
            {
                "name": "present_false",
                "event": {"type": "alert", "payload": {"flags": {"acked": False}}},
                "clause": "payload_path_not_exists:flags.acked",
            },
            {
                "name": "present_empty_list",
                "event": {"type": "alert", "payload": {"entities": []}},
                "clause": "payload_path_not_exists:entities",
            },
            {
                "name": "present_list_member",
                "event": {"type": "alert", "payload": {"entities": [{"value": "Spandau"}]}},
                "clause": "payload_path_not_exists:entities.0.value",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_type_predicates_match_exact_nested_runtime_types(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "entities": [{"kind": "district", "value": "Spandau"}],
                    "flags": {"acked": False},
                    "message": {"summary": "Typed payload ready"},
                    "meta": {"audit": {"last_seen": None}},
                    "priority": {"score": 0.97},
                    "routing": {"primary": "slack"},
                },
            },
            rules=[
                {
                    "id": "r-types",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_is_null:meta.audit.last_seen",
                        "payload_path_is_bool:flags.acked",
                        "payload_path_is_number:priority.score",
                        "payload_path_is_string:message.summary",
                        "payload_path_is_list:entities",
                        "payload_path_is_object:routing",
                    ],
                    "then": [{"kind": "route", "params": {"target": "type_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "type_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_is_null:meta.audit.last_seen",
                "payload_path_is_bool:flags.acked",
                "payload_path_is_number:priority.score",
                "payload_path_is_string:message.summary",
                "payload_path_is_list:entities",
                "payload_path_is_object:routing",
            ],
        )

    def test_payload_path_type_predicates_fail_cleanly_for_type_mismatches_and_missing_paths(self) -> None:
        cases = [
            {
                "name": "missing_path_null",
                "event": {"type": "alert", "payload": {"meta": {"audit": {}}}},
                "clause": "payload_path_is_null:meta.audit.last_seen",
            },
            {
                "name": "numeric_not_bool",
                "event": {"type": "alert", "payload": {"flags": {"acked": 0}}},
                "clause": "payload_path_is_bool:flags.acked",
            },
            {
                "name": "bool_not_number",
                "event": {"type": "alert", "payload": {"priority": {"score": False}}},
                "clause": "payload_path_is_number:priority.score",
            },
            {
                "name": "null_not_string",
                "event": {"type": "alert", "payload": {"message": {"summary": None}}},
                "clause": "payload_path_is_string:message.summary",
            },
            {
                "name": "object_not_list",
                "event": {"type": "alert", "payload": {"entities": {"first": "Spandau"}}},
                "clause": "payload_path_is_list:entities",
            },
            {
                "name": "string_not_object",
                "event": {"type": "alert", "payload": {"routing": {"primary": "slack"}}},
                "clause": "payload_path_is_object:routing.primary",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_object_key_predicates_match_literal_and_dynamic_keys(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "enrichment": {"labels": {"severity": "critical", "team": "ops"}},
                    "headers": {
                        "X-Env": "prod",
                        "X-Trace-Id": "abc123",
                        "x-alt-route": "blue",
                    },
                    "policy": {
                        "alt_header": "X-ALT-ROUTE",
                        "blocked_header": "X-Blocked",
                        "missing_header": "x-legacy",
                        "primary_header": "X-Env",
                    },
                },
            },
            rules=[
                {
                    "id": "r-object-keys",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_has_key:enrichment.labels=severity",
                        "payload_path_not_has_key:enrichment.labels=legacy",
                        "payload_path_has_key_path:headers=policy.primary_header",
                        "payload_path_not_has_key_path:headers=policy.blocked_header",
                        "payload_path_has_key_ci:headers=x-trace-id",
                        "payload_path_not_has_key_ci:headers=x-blocked",
                        "payload_path_has_key_path_ci:headers=policy.alt_header",
                        "payload_path_not_has_key_path_ci:headers=policy.missing_header",
                    ],
                    "then": [{"kind": "route", "params": {"target": "object_key_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "object_key_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_has_key:enrichment.labels=severity",
                "payload_path_not_has_key:enrichment.labels=legacy",
                "payload_path_has_key_path:headers=policy.primary_header",
                "payload_path_not_has_key_path:headers=policy.blocked_header",
                "payload_path_has_key_ci:headers=x-trace-id",
                "payload_path_not_has_key_ci:headers=x-blocked",
                "payload_path_has_key_path_ci:headers=policy.alt_header",
                "payload_path_not_has_key_path_ci:headers=policy.missing_header",
            ],
        )

    def test_payload_path_object_key_predicates_fail_cleanly_for_missing_paths_non_objects_non_string_dynamic_keys_and_key_hits(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_actual_path",
                "event": {"type": "alert", "payload": {"policy": {"primary_header": "X-Env"}}},
                "clause": "payload_path_has_key_path:headers=policy.primary_header",
            },
            {
                "name": "actual_path_not_object",
                "event": {"type": "alert", "payload": {"headers": ["X-Env"], "policy": {"primary_header": "X-Env"}}},
                "clause": "payload_path_has_key_path:headers=policy.primary_header",
            },
            {
                "name": "missing_dynamic_key_path",
                "event": {"type": "alert", "payload": {"headers": {"X-Env": "prod"}, "policy": {}}},
                "clause": "payload_path_has_key_path:headers=policy.primary_header",
            },
            {
                "name": "dynamic_key_not_string",
                "event": {"type": "alert", "payload": {"headers": {"X-Env": "prod"}, "policy": {"primary_header": 7}}},
                "clause": "payload_path_has_key_path:headers=policy.primary_header",
            },
            {
                "name": "literal_key_missing",
                "event": {"type": "alert", "payload": {"enrichment": {"labels": {"team": "ops"}}}},
                "clause": "payload_path_has_key:enrichment.labels=severity",
            },
            {
                "name": "not_has_key_hit",
                "event": {"type": "alert", "payload": {"enrichment": {"labels": {"legacy": True}}}},
                "clause": "payload_path_not_has_key:enrichment.labels=legacy",
            },
            {
                "name": "ci_not_has_key_hit_after_casefold",
                "event": {"type": "alert", "payload": {"headers": {"X-Blocked": "1"}}},
                "clause": "payload_path_not_has_key_ci:headers=x-blocked",
            },
            {
                "name": "ci_dynamic_not_has_key_hit_after_casefold",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": {"x-alt-route": "blue"},
                        "policy": {"alt_header": "X-ALT-ROUTE"},
                    },
                },
                "clause": "payload_path_not_has_key_path_ci:headers=policy.alt_header",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_object_key_set_predicates_match_required_and_forbidden_keys(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "enrichment": {"labels": {"severity": "critical", "team": "ops"}},
                    "headers": {
                        "X-Env": "prod",
                        "X-Trace-Id": "abc123",
                        "x-alt-route": "blue",
                    },
                },
            },
            rules=[
                {
                    "id": "r-object-key-sets",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_has_keys:enrichment.labels=severity,team",
                        "payload_path_missing_keys:enrichment.labels=legacy,deprecated",
                        "payload_path_has_keys_ci:headers=x-env,x-trace-id,x-alt-route",
                        "payload_path_missing_keys_ci:headers=x-blocked,x-legacy",
                    ],
                    "then": [{"kind": "route", "params": {"target": "object_key_set_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "object_key_set_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_has_keys:enrichment.labels=severity,team",
                "payload_path_missing_keys:enrichment.labels=legacy,deprecated",
                "payload_path_has_keys_ci:headers=x-env,x-trace-id,x-alt-route",
                "payload_path_missing_keys_ci:headers=x-blocked,x-legacy",
            ],
        )

    def test_payload_path_object_key_set_predicates_fail_cleanly_for_missing_paths_non_objects_and_key_set_mismatches(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_actual_path",
                "event": {"type": "alert", "payload": {}},
                "clause": "payload_path_has_keys:headers=X-Env,X-Trace-Id",
            },
            {
                "name": "actual_path_not_object",
                "event": {"type": "alert", "payload": {"headers": ["X-Env", "X-Trace-Id"]}},
                "clause": "payload_path_has_keys:headers=X-Env,X-Trace-Id",
            },
            {
                "name": "required_key_missing",
                "event": {"type": "alert", "payload": {"headers": {"X-Env": "prod"}}},
                "clause": "payload_path_has_keys:headers=X-Env,X-Trace-Id",
            },
            {
                "name": "forbidden_key_present",
                "event": {"type": "alert", "payload": {"headers": {"X-Legacy": "1"}}},
                "clause": "payload_path_missing_keys:headers=X-Legacy,X-Blocked",
            },
            {
                "name": "ci_required_key_missing_after_casefold",
                "event": {"type": "alert", "payload": {"headers": {"X-Env": "prod"}}},
                "clause": "payload_path_has_keys_ci:headers=x-env,x-trace-id",
            },
            {
                "name": "ci_forbidden_key_present_after_casefold",
                "event": {"type": "alert", "payload": {"headers": {"X-Blocked": "1"}}},
                "clause": "payload_path_missing_keys_ci:headers=x-blocked,x-legacy",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_object_key_set_path_predicates_match_dynamic_key_policies(
        self,
    ) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "enrichment": {"labels": {"severity": "critical", "team": "ops"}},
                    "headers": {
                        "X-Env": "prod",
                        "X-Trace-Id": "abc123",
                        "x-alt-route": "blue",
                    },
                    "policy": {
                        "required_labels": ["severity", "team"],
                        "forbidden_labels": ["legacy", "deprecated"],
                        "required_headers": ["x-env", "x-trace-id", "x-alt-route"],
                        "forbidden_headers": ["x-blocked", "x-legacy"],
                    },
                },
            },
            rules=[
                {
                    "id": "r-object-key-set-paths",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_has_keys_path:enrichment.labels=policy.required_labels",
                        "payload_path_missing_keys_path:enrichment.labels=policy.forbidden_labels",
                        "payload_path_has_keys_path_ci:headers=policy.required_headers",
                        "payload_path_missing_keys_path_ci:headers=policy.forbidden_headers",
                    ],
                    "then": [{"kind": "route", "params": {"target": "object_key_set_path_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "object_key_set_path_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_has_keys_path:enrichment.labels=policy.required_labels",
                "payload_path_missing_keys_path:enrichment.labels=policy.forbidden_labels",
                "payload_path_has_keys_path_ci:headers=policy.required_headers",
                "payload_path_missing_keys_path_ci:headers=policy.forbidden_headers",
            ],
        )

    def test_payload_path_object_key_set_path_predicates_fail_cleanly_for_missing_paths_non_objects_and_dynamic_key_set_mismatches(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_actual_path",
                "event": {"type": "alert", "payload": {"policy": {"required_headers": ["X-Env"]}}},
                "clause": "payload_path_has_keys_path:headers=policy.required_headers",
            },
            {
                "name": "missing_other_path",
                "event": {"type": "alert", "payload": {"headers": {"X-Env": "prod"}}},
                "clause": "payload_path_has_keys_path:headers=policy.required_headers",
            },
            {
                "name": "actual_path_not_object",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": ["X-Env", "X-Trace-Id"],
                        "policy": {"required_headers": ["X-Env", "X-Trace-Id"]},
                    },
                },
                "clause": "payload_path_has_keys_path:headers=policy.required_headers",
            },
            {
                "name": "other_path_not_list",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": {"X-Env": "prod"},
                        "policy": {"required_headers": "X-Env"},
                    },
                },
                "clause": "payload_path_has_keys_path:headers=policy.required_headers",
            },
            {
                "name": "other_path_empty_list",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": {"X-Env": "prod"},
                        "policy": {"required_headers": []},
                    },
                },
                "clause": "payload_path_has_keys_path:headers=policy.required_headers",
            },
            {
                "name": "other_path_non_string_members",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": {"X-Env": "prod"},
                        "policy": {"required_headers": ["X-Env", 2]},
                    },
                },
                "clause": "payload_path_has_keys_path:headers=policy.required_headers",
            },
            {
                "name": "required_key_missing",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": {"X-Env": "prod"},
                        "policy": {"required_headers": ["X-Env", "X-Trace-Id"]},
                    },
                },
                "clause": "payload_path_has_keys_path:headers=policy.required_headers",
            },
            {
                "name": "forbidden_key_present",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": {"X-Legacy": "1"},
                        "policy": {"forbidden_headers": ["X-Legacy", "X-Blocked"]},
                    },
                },
                "clause": "payload_path_missing_keys_path:headers=policy.forbidden_headers",
            },
            {
                "name": "ci_required_key_missing_after_casefold",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": {"X-Env": "prod"},
                        "policy": {"required_headers": ["x-env", "x-trace-id"]},
                    },
                },
                "clause": "payload_path_has_keys_path_ci:headers=policy.required_headers",
            },
            {
                "name": "ci_forbidden_key_present_after_casefold",
                "event": {
                    "type": "alert",
                    "payload": {
                        "headers": {"X-Blocked": "1"},
                        "policy": {"forbidden_headers": ["x-blocked", "x-legacy"]},
                    },
                },
                "clause": "payload_path_missing_keys_path_ci:headers=policy.forbidden_headers",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_empty_and_not_empty_predicates_match_sized_values_deterministically(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "entities": [],
                    "message": {"summary": ""},
                    "routing": {"channels": {}, "primary": "slack"},
                    "tags": ["ops"],
                },
            },
            rules=[
                {
                    "id": "r-emptiness",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_empty:entities",
                        "payload_path_empty:message.summary",
                        "payload_path_empty:routing.channels",
                        "payload_path_not_empty:routing.primary",
                        "payload_path_not_empty:tags",
                    ],
                    "then": [{"kind": "route", "params": {"target": "emptiness_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "emptiness_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_empty:entities",
                "payload_path_empty:message.summary",
                "payload_path_empty:routing.channels",
                "payload_path_not_empty:routing.primary",
                "payload_path_not_empty:tags",
            ],
        )

    def test_payload_path_empty_and_not_empty_predicates_fail_cleanly_for_non_sized_values_misses_and_missing_paths(
        self,
    ) -> None:
        cases = [
            {
                "name": "empty_numeric_actual",
                "event": {"type": "alert", "payload": {"metrics": {"attempts": 0}}},
                "clause": "payload_path_empty:metrics.attempts",
            },
            {
                "name": "empty_miss",
                "event": {"type": "alert", "payload": {"tags": ["ops"]}},
                "clause": "payload_path_empty:tags",
            },
            {
                "name": "not_empty_miss",
                "event": {"type": "alert", "payload": {"message": {"summary": ""}}},
                "clause": "payload_path_not_empty:message.summary",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"routing": {"service": "svc-1"}}},
                "clause": "payload_path_not_empty:routing.channels",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_clauses_fail_cleanly_for_missing_paths_and_mismatched_values(self) -> None:
        actions, trace = eval_policies(
            event={"type": "alert", "payload": {"routing": {"severity": "warning"}}},
            rules=[
                {
                    "id": "r1",
                    "when": [
                        "payload_path_exists:routing.confidence",
                        "payload_path_equals:routing.severity=critical",
                        "payload_path_in:routing.severity=critical,error",
                    ],
                    "then": [{"kind": "route", "params": {"target": "ops"}}],
                }
            ],
        )

        self.assertEqual(actions, [])
        self.assertEqual(trace, [])

    def test_payload_path_cross_field_predicates_match_exact_and_numeric_paths(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "metrics": {"retries": 2},
                    "priority": {"ceiling": 1.0, "floor": 0.9, "score": 0.97},
                    "routing": {"owner": "ops", "team": "ops", "backup_team": "security"},
                    "window": {"minutes_since_anchor": 6, "sla_minutes": 10},
                },
            },
            rules=[
                {
                    "id": "r-cross-field",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_equals_path:routing.team=routing.owner",
                        "payload_path_not_equals_path:routing.team=routing.backup_team",
                        "payload_path_gte_path:priority.score=priority.floor",
                        "payload_path_lte_path:priority.score=priority.ceiling",
                        "payload_path_lt_path:window.minutes_since_anchor=window.sla_minutes",
                        "payload_path_gt_path:window.sla_minutes=metrics.retries",
                    ],
                    "then": [{"kind": "route", "params": {"target": "cross_field_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "cross_field_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_equals_path:routing.team=routing.owner",
                "payload_path_not_equals_path:routing.team=routing.backup_team",
                "payload_path_gte_path:priority.score=priority.floor",
                "payload_path_lte_path:priority.score=priority.ceiling",
                "payload_path_lt_path:window.minutes_since_anchor=window.sla_minutes",
                "payload_path_gt_path:window.sla_minutes=metrics.retries",
            ],
        )

    def test_payload_path_cross_field_case_insensitive_predicates_match_string_paths(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "routing": {
                        "backup_team": "Security",
                        "owner": "ops",
                        "team": "Ops",
                    }
                },
            },
            rules=[
                {
                    "id": "r-cross-field-ci",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_equals_path_ci:routing.team=routing.owner",
                        "payload_path_not_equals_path_ci:routing.team=routing.backup_team",
                    ],
                    "then": [{"kind": "route", "params": {"target": "cross_field_casefold_lane"}}],
                }
            ],
        )

        self.assertEqual(
            actions,
            [{"kind": "route", "params": {"target": "cross_field_casefold_lane"}}],
        )
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_equals_path_ci:routing.team=routing.owner",
                "payload_path_not_equals_path_ci:routing.team=routing.backup_team",
            ],
        )

    def test_payload_path_cross_field_case_insensitive_predicates_fail_cleanly_for_missing_paths_non_string_values_and_membership_misses(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_other_path",
                "event": {"type": "alert", "payload": {"routing": {"team": "Ops"}}},
                "clause": "payload_path_equals_path_ci:routing.team=routing.owner",
            },
            {
                "name": "casefold_equality_miss",
                "event": {"type": "alert", "payload": {"routing": {"team": "Ops", "owner": "Security"}}},
                "clause": "payload_path_equals_path_ci:routing.team=routing.owner",
            },
            {
                "name": "non_string_other_path",
                "event": {"type": "alert", "payload": {"routing": {"team": "Ops", "owner": 7}}},
                "clause": "payload_path_equals_path_ci:routing.team=routing.owner",
            },
            {
                "name": "not_equals_ci_hit_after_casefold",
                "event": {"type": "alert", "payload": {"routing": {"team": "Ops", "backup_team": "OPS"}}},
                "clause": "payload_path_not_equals_path_ci:routing.team=routing.backup_team",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_cross_field_string_predicates_match_other_payload_strings(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "blocked": {
                        "fragment": "resolved",
                        "prefix": "Alarm",
                        "suffix": "tomorrow",
                    },
                    "message": {"subject": "Ticket 42 escalated"},
                    "policy": {
                        "fragment": "42",
                        "prefix": "Ticket",
                        "suffix": "escalated",
                    },
                },
            },
            rules=[
                {
                    "id": "r-cross-field-strings",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_startswith_path:message.subject=policy.prefix",
                        "payload_path_contains_path:message.subject=policy.fragment",
                        "payload_path_endswith_path:message.subject=policy.suffix",
                        "payload_path_not_startswith_path:message.subject=blocked.prefix",
                        "payload_path_not_contains_path:message.subject=blocked.fragment",
                        "payload_path_not_endswith_path:message.subject=blocked.suffix",
                    ],
                    "then": [
                        {"kind": "route", "params": {"target": "cross_field_string_lane"}}
                    ],
                }
            ],
        )

        self.assertEqual(
            actions,
            [{"kind": "route", "params": {"target": "cross_field_string_lane"}}],
        )
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_startswith_path:message.subject=policy.prefix",
                "payload_path_contains_path:message.subject=policy.fragment",
                "payload_path_endswith_path:message.subject=policy.suffix",
                "payload_path_not_startswith_path:message.subject=blocked.prefix",
                "payload_path_not_contains_path:message.subject=blocked.fragment",
                "payload_path_not_endswith_path:message.subject=blocked.suffix",
            ],
        )

    def test_payload_path_cross_field_case_insensitive_string_predicates_match_other_payload_strings(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "blocked": {
                        "fragment": "RESOLVED",
                        "prefix": "alarm",
                        "suffix": "TOMORROW",
                    },
                    "message": {"subject": "Ticket 42 ESCALATED"},
                    "policy": {
                        "fragment": "ticket 42",
                        "prefix": "ticket",
                        "suffix": "escalated",
                    },
                },
            },
            rules=[
                {
                    "id": "r-cross-field-strings-ci",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_startswith_path_ci:message.subject=policy.prefix",
                        "payload_path_contains_path_ci:message.subject=policy.fragment",
                        "payload_path_endswith_path_ci:message.subject=policy.suffix",
                        "payload_path_not_startswith_path_ci:message.subject=blocked.prefix",
                        "payload_path_not_contains_path_ci:message.subject=blocked.fragment",
                        "payload_path_not_endswith_path_ci:message.subject=blocked.suffix",
                    ],
                    "then": [
                        {
                            "kind": "route",
                            "params": {"target": "cross_field_string_casefold_lane"},
                        }
                    ],
                }
            ],
        )

        self.assertEqual(
            actions,
            [
                {
                    "kind": "route",
                    "params": {"target": "cross_field_string_casefold_lane"},
                }
            ],
        )
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_startswith_path_ci:message.subject=policy.prefix",
                "payload_path_contains_path_ci:message.subject=policy.fragment",
                "payload_path_endswith_path_ci:message.subject=policy.suffix",
                "payload_path_not_startswith_path_ci:message.subject=blocked.prefix",
                "payload_path_not_contains_path_ci:message.subject=blocked.fragment",
                "payload_path_not_endswith_path_ci:message.subject=blocked.suffix",
            ],
        )

    def test_payload_path_cross_field_string_predicates_fail_cleanly_for_missing_paths_non_string_values_and_string_hits(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_other_path",
                "event": {"type": "alert", "payload": {"message": {"subject": "Ticket 42 escalated"}}},
                "clause": "payload_path_contains_path:message.subject=policy.fragment",
            },
            {
                "name": "non_string_actual",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"subject": 42}, "policy": {"fragment": "42"}},
                },
                "clause": "payload_path_contains_path:message.subject=policy.fragment",
            },
            {
                "name": "non_string_other",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"subject": "Ticket 42 escalated"}, "policy": {"fragment": 42}},
                },
                "clause": "payload_path_contains_path:message.subject=policy.fragment",
            },
            {
                "name": "prefix_miss",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"subject": "Ticket 42 escalated"}, "policy": {"prefix": "Alarm"}},
                },
                "clause": "payload_path_startswith_path:message.subject=policy.prefix",
            },
            {
                "name": "not_contains_hit_after_casefold",
                "event": {
                    "type": "alert",
                    "payload": {
                        "blocked": {"fragment": "ticket 42"},
                        "message": {"subject": "Ticket 42 escalated"},
                    },
                },
                "clause": "payload_path_not_contains_path_ci:message.subject=blocked.fragment",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_cross_field_regex_predicates_match_other_payload_patterns(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "blocked": {
                        "subject_regex": "resolved|suppressed",
                        "subject_regex_ci": "SUPPRESSED|RESOLVED",
                    },
                    "message": {"subject": "Ticket 42 ESCALATED"},
                    "policy": {
                        "subject_regex": r"^Ticket\s+\d+\s+ESCALATED$",
                        "subject_regex_ci": r"^ticket\s+42\s+escalated$",
                    },
                },
            },
            rules=[
                {
                    "id": "r-cross-field-regex",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_matches_path:message.subject=policy.subject_regex",
                        "payload_path_not_matches_path:message.subject=blocked.subject_regex",
                        "payload_path_matches_path_ci:message.subject=policy.subject_regex_ci",
                        "payload_path_not_matches_path_ci:message.subject=blocked.subject_regex_ci",
                    ],
                    "then": [
                        {"kind": "route", "params": {"target": "cross_field_regex_lane"}}
                    ],
                }
            ],
        )

        self.assertEqual(
            actions,
            [{"kind": "route", "params": {"target": "cross_field_regex_lane"}}],
        )
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_matches_path:message.subject=policy.subject_regex",
                "payload_path_not_matches_path:message.subject=blocked.subject_regex",
                "payload_path_matches_path_ci:message.subject=policy.subject_regex_ci",
                "payload_path_not_matches_path_ci:message.subject=blocked.subject_regex_ci",
            ],
        )

    def test_payload_path_cross_field_regex_predicates_fail_cleanly_for_missing_paths_non_string_values_invalid_patterns_and_regex_hits(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_other_path",
                "event": {"type": "alert", "payload": {"message": {"subject": "Ticket 42 escalated"}}},
                "clause": "payload_path_matches_path:message.subject=policy.subject_regex",
            },
            {
                "name": "non_string_actual",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"subject": 42}, "policy": {"subject_regex": r"^42$"}},
                },
                "clause": "payload_path_matches_path:message.subject=policy.subject_regex",
            },
            {
                "name": "non_string_other",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"subject": "Ticket 42 escalated"}, "policy": {"subject_regex": 42}},
                },
                "clause": "payload_path_matches_path:message.subject=policy.subject_regex",
            },
            {
                "name": "invalid_other_regex",
                "event": {
                    "type": "alert",
                    "payload": {
                        "message": {"subject": "Ticket 42 escalated"},
                        "policy": {"subject_regex": "("},
                    },
                },
                "clause": "payload_path_matches_path:message.subject=policy.subject_regex",
            },
            {
                "name": "not_matches_ci_hit_after_casefold",
                "event": {
                    "type": "alert",
                    "payload": {
                        "blocked": {"subject_regex_ci": r"ticket\s+42"},
                        "message": {"subject": "Ticket 42 escalated"},
                    },
                },
                "clause": "payload_path_not_matches_path_ci:message.subject=blocked.subject_regex_ci",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_dynamic_membership_predicates_match_other_payload_lists(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "flags": {"acked": False},
                    "policy": {
                        "allowed_ack_states": [True],
                        "allowed_priority_tiers": [1, 2, 3],
                    },
                    "priority": {"tier": 2},
                    "routing": {
                        "allowed_teams": ["ops", "security"],
                        "blocked_teams": ["legacy", "audit"],
                        "team": "ops",
                    },
                },
            },
            rules=[
                {
                    "id": "r-dynamic-membership",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_in_path:routing.team=routing.allowed_teams",
                        "payload_path_not_in_path:routing.team=routing.blocked_teams",
                        "payload_path_in_path:priority.tier=policy.allowed_priority_tiers",
                        "payload_path_not_in_path:flags.acked=policy.allowed_ack_states",
                    ],
                    "then": [{"kind": "route", "params": {"target": "dynamic_membership_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "dynamic_membership_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_in_path:routing.team=routing.allowed_teams",
                "payload_path_not_in_path:routing.team=routing.blocked_teams",
                "payload_path_in_path:priority.tier=policy.allowed_priority_tiers",
                "payload_path_not_in_path:flags.acked=policy.allowed_ack_states",
            ],
        )

    def test_payload_path_dynamic_membership_case_insensitive_predicates_match_string_lists(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "routing": {
                        "blocked_teams": ["legacy", "audit"],
                        "mirrors": ["Tier-1", "ops"],
                        "team": "Ops",
                    }
                },
            },
            rules=[
                {
                    "id": "r-dynamic-membership-ci",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_in_path_ci:routing.team=routing.mirrors",
                        "payload_path_not_in_path_ci:routing.team=routing.blocked_teams",
                    ],
                    "then": [{"kind": "route", "params": {"target": "dynamic_membership_casefold_lane"}}],
                }
            ],
        )

        self.assertEqual(
            actions,
            [{"kind": "route", "params": {"target": "dynamic_membership_casefold_lane"}}],
        )
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_in_path_ci:routing.team=routing.mirrors",
                "payload_path_not_in_path_ci:routing.team=routing.blocked_teams",
            ],
        )

    def test_payload_path_dynamic_membership_predicates_fail_cleanly_for_missing_paths_non_lists_empty_lists_and_membership_hits(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_other_path",
                "event": {"type": "alert", "payload": {"routing": {"team": "ops"}}},
                "clause": "payload_path_in_path:routing.team=routing.allowed_teams",
            },
            {
                "name": "other_path_not_list",
                "event": {"type": "alert", "payload": {"routing": {"allowed_teams": "ops", "team": "ops"}}},
                "clause": "payload_path_in_path:routing.team=routing.allowed_teams",
            },
            {
                "name": "empty_other_list",
                "event": {"type": "alert", "payload": {"routing": {"allowed_teams": [], "team": "ops"}}},
                "clause": "payload_path_not_in_path:routing.team=routing.allowed_teams",
            },
            {
                "name": "membership_miss",
                "event": {"type": "alert", "payload": {"routing": {"allowed_teams": ["security"], "team": "ops"}}},
                "clause": "payload_path_in_path:routing.team=routing.allowed_teams",
            },
            {
                "name": "not_in_hit",
                "event": {"type": "alert", "payload": {"routing": {"blocked_teams": ["ops", "legacy"], "team": "ops"}}},
                "clause": "payload_path_not_in_path:routing.team=routing.blocked_teams",
            },
            {
                "name": "ci_non_string_actual",
                "event": {"type": "alert", "payload": {"routing": {"mirrors": ["7", "8"], "team": 7}}},
                "clause": "payload_path_in_path_ci:routing.team=routing.mirrors",
            },
            {
                "name": "ci_non_string_member",
                "event": {"type": "alert", "payload": {"routing": {"mirrors": ["ops", 7], "team": "Ops"}}},
                "clause": "payload_path_in_path_ci:routing.team=routing.mirrors",
            },
            {
                "name": "ci_not_in_hit_after_casefold",
                "event": {"type": "alert", "payload": {"routing": {"blocked_teams": ["OPS"], "team": "ops"}}},
                "clause": "payload_path_not_in_path_ci:routing.team=routing.blocked_teams",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_cross_field_list_membership_predicates_match_other_payload_lists(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "audit": {
                        "labels": ["Ops", "night-shift"],
                        "mirrors": ["ops", "weekend"],
                        "teams": ["Core", "Escalations"],
                    },
                    "flags": ["new", "triaged"],
                    "policy": {
                        "allowed_labels": ["core", "escalations", "ops"],
                        "allowed_tags": ["customer", "sev1", "sev2"],
                        "allowed_targets": ["email", "sms", "push"],
                        "blocked_flags": ["archived", "ignored"],
                        "blocked_labels": ["legacy", "ignored"],
                    },
                    "routing": {
                        "requested_targets": ["pager", "sms"],
                        "tags": ["customer", "sev1"],
                    },
                },
            },
            rules=[
                {
                    "id": "r-cross-field-list-membership",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_any_in_path:routing.requested_targets=policy.allowed_targets",
                        "payload_path_all_in_path:routing.tags=policy.allowed_tags",
                        "payload_path_none_in_path:flags=policy.blocked_flags",
                        "payload_path_any_in_path_ci:audit.labels=audit.mirrors",
                        "payload_path_all_in_path_ci:audit.teams=policy.allowed_labels",
                        "payload_path_none_in_path_ci:audit.labels=policy.blocked_labels",
                    ],
                    "then": [
                        {
                            "kind": "route",
                            "params": {"target": "cross_field_list_membership_lane"},
                        }
                    ],
                }
            ],
        )

        self.assertEqual(
            actions,
            [{"kind": "route", "params": {"target": "cross_field_list_membership_lane"}}],
        )
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_any_in_path:routing.requested_targets=policy.allowed_targets",
                "payload_path_all_in_path:routing.tags=policy.allowed_tags",
                "payload_path_none_in_path:flags=policy.blocked_flags",
                "payload_path_any_in_path_ci:audit.labels=audit.mirrors",
                "payload_path_all_in_path_ci:audit.teams=policy.allowed_labels",
                "payload_path_none_in_path_ci:audit.labels=policy.blocked_labels",
            ],
        )

    def test_payload_path_cross_field_list_membership_predicates_fail_cleanly_for_missing_paths_non_lists_empty_lists_and_membership_hits(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_actual_path",
                "event": {"type": "alert", "payload": {"policy": {"allowed_targets": ["sms"]}}},
                "clause": "payload_path_any_in_path:routing.requested_targets=policy.allowed_targets",
            },
            {
                "name": "actual_path_not_list",
                "event": {
                    "type": "alert",
                    "payload": {
                        "policy": {"allowed_targets": ["sms"]},
                        "routing": {"requested_targets": "sms"},
                    },
                },
                "clause": "payload_path_any_in_path:routing.requested_targets=policy.allowed_targets",
            },
            {
                "name": "empty_actual_list",
                "event": {
                    "type": "alert",
                    "payload": {
                        "policy": {"allowed_tags": ["sev1"]},
                        "routing": {"tags": []},
                    },
                },
                "clause": "payload_path_all_in_path:routing.tags=policy.allowed_tags",
            },
            {
                "name": "empty_other_list",
                "event": {
                    "type": "alert",
                    "payload": {
                        "flags": ["new"],
                        "policy": {"blocked_flags": []},
                    },
                },
                "clause": "payload_path_none_in_path:flags=policy.blocked_flags",
            },
            {
                "name": "all_in_path_membership_miss",
                "event": {
                    "type": "alert",
                    "payload": {
                        "policy": {"allowed_tags": ["sev1"]},
                        "routing": {"tags": ["sev1", "customer"]},
                    },
                },
                "clause": "payload_path_all_in_path:routing.tags=policy.allowed_tags",
            },
            {
                "name": "none_in_path_hit",
                "event": {
                    "type": "alert",
                    "payload": {
                        "flags": ["ignored"],
                        "policy": {"blocked_flags": ["archived", "ignored"]},
                    },
                },
                "clause": "payload_path_none_in_path:flags=policy.blocked_flags",
            },
            {
                "name": "ci_non_string_actual_member",
                "event": {
                    "type": "alert",
                    "payload": {
                        "audit": {"labels": ["ops", 7], "mirrors": ["ops", "weekend"]},
                    },
                },
                "clause": "payload_path_any_in_path_ci:audit.labels=audit.mirrors",
            },
            {
                "name": "ci_non_string_other_member",
                "event": {
                    "type": "alert",
                    "payload": {
                        "audit": {"teams": ["Core"]},
                        "policy": {"allowed_labels": ["core", 9]},
                    },
                },
                "clause": "payload_path_all_in_path_ci:audit.teams=policy.allowed_labels",
            },
            {
                "name": "ci_none_in_path_hit_after_casefold",
                "event": {
                    "type": "alert",
                    "payload": {
                        "audit": {"labels": ["Legacy"]},
                        "policy": {"blocked_labels": ["legacy", "ignored"]},
                    },
                },
                "clause": "payload_path_none_in_path_ci:audit.labels=policy.blocked_labels",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_dynamic_length_predicates_match_other_payload_lengths(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "audit": {"labels": ["ops", "night"]},
                    "entities": [{"id": "a"}, {"id": "b"}],
                    "flags": ["triaged"],
                    "message": {"subject": "Ticket 42 escalated"},
                    "meta": {"annotations": {"owner": "ops", "tier": "gold"}},
                    "policy": {
                        "allowed_targets": ["email", "sms", "push"],
                        "annotation_cap": ["a", "b", "c"],
                        "blocked_targets": ["pager"],
                        "expected_channels": ["sms", "push"],
                        "prefix": "Ticket",
                    },
                    "routing": {"channels": ["sms", "push"]},
                },
            },
            rules=[
                {
                    "id": "r-dynamic-lengths",
                    "when": [
                        "event_type_present",
                        "event_type_equals:normalize",
                        "payload_path_len_eq_path:routing.channels=policy.expected_channels",
                        "payload_path_len_not_eq_path:routing.channels=policy.blocked_targets",
                        "payload_path_len_gt_path:message.subject=policy.prefix",
                        "payload_path_len_gte_path:entities=audit.labels",
                        "payload_path_len_lt_path:flags=policy.allowed_targets",
                        "payload_path_len_lte_path:meta.annotations=policy.annotation_cap",
                    ],
                    "then": [{"kind": "route", "params": {"target": "dynamic_length_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "dynamic_length_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:normalize",
                "payload_path_len_eq_path:routing.channels=policy.expected_channels",
                "payload_path_len_not_eq_path:routing.channels=policy.blocked_targets",
                "payload_path_len_gt_path:message.subject=policy.prefix",
                "payload_path_len_gte_path:entities=audit.labels",
                "payload_path_len_lt_path:flags=policy.allowed_targets",
                "payload_path_len_lte_path:meta.annotations=policy.annotation_cap",
            ],
        )

    def test_payload_path_dynamic_length_predicates_fail_cleanly_for_missing_paths_unsized_values_and_length_misses(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_other_path",
                "event": {"type": "alert", "payload": {"routing": {"channels": ["sms", "push"]}}},
                "clause": "payload_path_len_eq_path:routing.channels=policy.expected_channels",
            },
            {
                "name": "unsized_actual",
                "event": {"type": "alert", "payload": {"metrics": {"count": 2}, "policy": {"expected_channels": ["sms", "push"]}}},
                "clause": "payload_path_len_eq_path:metrics.count=policy.expected_channels",
            },
            {
                "name": "unsized_other",
                "event": {"type": "alert", "payload": {"routing": {"channels": ["sms", "push"]}, "policy": {"expected_count": 2}}},
                "clause": "payload_path_len_eq_path:routing.channels=policy.expected_count",
            },
            {
                "name": "length_miss",
                "event": {"type": "alert", "payload": {"routing": {"channels": ["sms", "push"]}, "policy": {"expected_channels": ["push"]}}},
                "clause": "payload_path_len_eq_path:routing.channels=policy.expected_channels",
            },
            {
                "name": "not_eq_hit",
                "event": {"type": "alert", "payload": {"routing": {"channels": ["sms", "push"]}, "policy": {"mirrors": ["email", "pager"]}}},
                "clause": "payload_path_len_not_eq_path:routing.channels=policy.mirrors",
            },
            {
                "name": "gt_threshold_miss",
                "event": {"type": "alert", "payload": {"message": {"subject": "Ticket"}, "policy": {"prefix": "Escalated"}}},
                "clause": "payload_path_len_gt_path:message.subject=policy.prefix",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_cross_field_predicates_fail_cleanly_for_missing_paths_type_mismatches_and_threshold_misses(
        self,
    ) -> None:
        cases = [
            {
                "name": "missing_other_path",
                "event": {"type": "alert", "payload": {"routing": {"team": "ops"}}},
                "clause": "payload_path_equals_path:routing.team=routing.owner",
            },
            {
                "name": "equality_miss",
                "event": {"type": "alert", "payload": {"routing": {"team": "ops", "owner": "security"}}},
                "clause": "payload_path_equals_path:routing.team=routing.owner",
            },
            {
                "name": "non_numeric_other_path",
                "event": {"type": "alert", "payload": {"priority": {"score": 0.97, "floor": "0.9"}}},
                "clause": "payload_path_gte_path:priority.score=priority.floor",
            },
            {
                "name": "threshold_miss",
                "event": {"type": "alert", "payload": {"window": {"minutes_since_anchor": 12, "sla_minutes": 10}}},
                "clause": "payload_path_lt_path:window.minutes_since_anchor=window.sla_minutes",
            },
            {
                "name": "bool_actual_is_not_numeric",
                "event": {"type": "alert", "payload": {"metrics": {"retries": False, "limit": 1}}},
                "clause": "payload_path_gt_path:metrics.limit=metrics.retries",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_any_in_matches_list_membership_deterministically(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "flags": [False, True],
                    "routing": {"channels": ["push", "sms"]},
                    "tags": ["ops", "berlin"],
                    "thresholds": [0.5, 0.9],
                    "nullable_values": [None, "fallback"],
                },
            },
            rules=[
                {
                    "id": "r-any-membership",
                    "when": [
                        "payload_path_any_in:routing.channels=email,push",
                        "payload_path_any_in:tags=munich,berlin",
                        "payload_path_any_in:thresholds=[0.8, 0.9]",
                        "payload_path_any_in:flags=[true]",
                        'payload_path_any_in:nullable_values=[null, "missing"]',
                    ],
                    "then": [{"kind": "route", "params": {"target": "list_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "list_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_any_in:routing.channels=email,push",
                "payload_path_any_in:tags=munich,berlin",
                "payload_path_any_in:thresholds=[0.8, 0.9]",
                "payload_path_any_in:flags=[true]",
                'payload_path_any_in:nullable_values=[null, "missing"]',
            ],
        )

    def test_payload_path_any_in_fails_cleanly_for_non_list_actuals_empty_lists_and_misses(self) -> None:
        cases = [
            {
                "name": "non_list_actual",
                "event": {"type": "alert", "payload": {"routing": {"channels": "push"}}},
                "clause": "payload_path_any_in:routing.channels=email,push",
            },
            {
                "name": "empty_list",
                "event": {"type": "alert", "payload": {"tags": []}},
                "clause": "payload_path_any_in:tags=ops,berlin",
            },
            {
                "name": "membership_miss",
                "event": {"type": "alert", "payload": {"tags": ["munich", "west"]}},
                "clause": "payload_path_any_in:tags=ops,berlin",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"routing": {"service": "svc-1"}}},
                "clause": "payload_path_any_in:routing.channels=email,push",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_all_in_matches_list_subset_guards_deterministically(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "flags": [False, False],
                    "routing": {"channels": ["push", "sms"]},
                    "tags": ["ops", "berlin"],
                    "thresholds": [0.5, 0.9],
                    "nullable_values": [None, "fallback"],
                },
            },
            rules=[
                {
                    "id": "r-all-membership",
                    "when": [
                        'payload_path_all_in:routing.channels=["push", "sms", "email"]',
                        "payload_path_all_in:tags=ops,berlin,triage",
                        "payload_path_all_in:thresholds=[0.5, 0.9, 1.0]",
                        "payload_path_all_in:flags=[false]",
                        'payload_path_all_in:nullable_values=[null, "fallback", "missing"]',
                    ],
                    "then": [{"kind": "route", "params": {"target": "all_in_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "all_in_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                'payload_path_all_in:routing.channels=["push", "sms", "email"]',
                "payload_path_all_in:tags=ops,berlin,triage",
                "payload_path_all_in:thresholds=[0.5, 0.9, 1.0]",
                "payload_path_all_in:flags=[false]",
                'payload_path_all_in:nullable_values=[null, "fallback", "missing"]',
            ],
        )

    def test_payload_path_all_in_fails_cleanly_for_non_list_actuals_empty_lists_partial_misses_and_missing_paths(self) -> None:
        cases = [
            {
                "name": "non_list_actual",
                "event": {"type": "alert", "payload": {"routing": {"channels": "push"}}},
                "clause": "payload_path_all_in:routing.channels=push,sms",
            },
            {
                "name": "empty_list",
                "event": {"type": "alert", "payload": {"tags": []}},
                "clause": "payload_path_all_in:tags=ops,berlin",
            },
            {
                "name": "partial_membership_miss",
                "event": {"type": "alert", "payload": {"tags": ["ops", "munich"]}},
                "clause": "payload_path_all_in:tags=ops,berlin",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"routing": {"service": "svc-1"}}},
                "clause": "payload_path_all_in:routing.channels=push,sms",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_none_in_matches_disjoint_non_empty_lists_deterministically(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "flags": [False, False],
                    "routing": {"channels": ["push", "sms"]},
                    "tags": ["ops", "berlin"],
                    "thresholds": [0.5, 0.9],
                    "nullable_values": [None, "fallback"],
                },
            },
            rules=[
                {
                    "id": "r-none-membership",
                    "when": [
                        "payload_path_none_in:routing.channels=email,slack",
                        "payload_path_none_in:tags=munich,triage",
                        "payload_path_none_in:thresholds=[0.1, 1.0]",
                        "payload_path_none_in:flags=[true]",
                        'payload_path_none_in:nullable_values=["missing", "other"]',
                    ],
                    "then": [{"kind": "route", "params": {"target": "none_in_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "none_in_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_none_in:routing.channels=email,slack",
                "payload_path_none_in:tags=munich,triage",
                "payload_path_none_in:thresholds=[0.1, 1.0]",
                "payload_path_none_in:flags=[true]",
                'payload_path_none_in:nullable_values=["missing", "other"]',
            ],
        )

    def test_payload_path_none_in_fails_cleanly_for_non_list_actuals_empty_lists_member_hits_and_missing_paths(
        self,
    ) -> None:
        cases = [
            {
                "name": "non_list_actual",
                "event": {"type": "alert", "payload": {"routing": {"channels": "push"}}},
                "clause": "payload_path_none_in:routing.channels=email,push",
            },
            {
                "name": "empty_list",
                "event": {"type": "alert", "payload": {"tags": []}},
                "clause": "payload_path_none_in:tags=ops,berlin",
            },
            {
                "name": "member_hit",
                "event": {"type": "alert", "payload": {"tags": ["ops", "munich"]}},
                "clause": "payload_path_none_in:tags=berlin,munich",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"routing": {"service": "svc-1"}}},
                "clause": "payload_path_none_in:routing.channels=email,push",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_string_predicates_match_nested_strings_and_list_indexes(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"value": "A100 Ausfahrt Spandau"}],
                    "message": {"summary": "false alarm at A100 Ausfahrt Spandau avoided"},
                    "routing": {"service": "svc-berlin-edge"},
                },
            },
            rules=[
                {
                    "id": "r-strings",
                    "when": [
                        "payload_path_startswith:routing.service=svc-",
                        "payload_path_contains:message.summary=false alarm",
                        "payload_path_contains:entities.0.value=Spandau",
                        "payload_path_endswith:routing.service=edge",
                        "payload_path_endswith:message.summary=avoided",
                    ],
                    "then": [{"kind": "route", "params": {"target": "string_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "string_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_startswith:routing.service=svc-",
                "payload_path_contains:message.summary=false alarm",
                "payload_path_contains:entities.0.value=Spandau",
                "payload_path_endswith:routing.service=edge",
                "payload_path_endswith:message.summary=avoided",
            ],
        )

    def test_payload_path_string_predicates_fail_cleanly_for_non_string_actuals_and_misses(self) -> None:
        cases = [
            {
                "name": "non_string_actual",
                "event": {"type": "alert", "payload": {"routing": {"service": 17}}},
                "clause": "payload_path_startswith:routing.service=svc-",
            },
            {
                "name": "prefix_miss",
                "event": {
                    "type": "alert",
                    "payload": {"routing": {"service": "queue-berlin-edge"}},
                },
                "clause": "payload_path_startswith:routing.service=svc-",
            },
            {
                "name": "contains_miss",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"summary": "Minor incident in Charlottenburg"}},
                },
                "clause": "payload_path_contains:message.summary=Spandau",
            },
            {
                "name": "suffix_miss",
                "event": {
                    "type": "alert",
                    "payload": {"routing": {"service": "svc-berlin-core"}},
                },
                "clause": "payload_path_endswith:routing.service=edge",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"message": {"summary": "hello"}}},
                "clause": "payload_path_contains:routing.service=svc-",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_negative_string_predicates_match_nested_strings_and_list_indexes(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"value": "A100 Ausfahrt Spandau"}],
                    "message": {"summary": "minor delay at A100 Ausfahrt Spandau pending review"},
                    "routing": {"service": "queue-berlin-core"},
                },
            },
            rules=[
                {
                    "id": "r-negative-strings",
                    "when": [
                        "payload_path_not_startswith:routing.service=svc-",
                        "payload_path_not_contains:message.summary=false alarm",
                        "payload_path_not_contains:entities.0.value=Charlottenburg",
                        "payload_path_not_endswith:routing.service=edge",
                        "payload_path_not_endswith:message.summary=avoided",
                    ],
                    "then": [{"kind": "route", "params": {"target": "negative_string_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "negative_string_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_not_startswith:routing.service=svc-",
                "payload_path_not_contains:message.summary=false alarm",
                "payload_path_not_contains:entities.0.value=Charlottenburg",
                "payload_path_not_endswith:routing.service=edge",
                "payload_path_not_endswith:message.summary=avoided",
            ],
        )

    def test_payload_path_negative_string_predicates_fail_cleanly_for_non_string_actuals_misses_and_missing_paths(self) -> None:
        cases = [
            {
                "name": "non_string_actual",
                "event": {"type": "alert", "payload": {"routing": {"service": 17}}},
                "clause": "payload_path_not_startswith:routing.service=svc-",
            },
            {
                "name": "negated_prefix_match",
                "event": {
                    "type": "alert",
                    "payload": {"routing": {"service": "svc-berlin-edge"}},
                },
                "clause": "payload_path_not_startswith:routing.service=svc-",
            },
            {
                "name": "negated_contains_match",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"summary": "false alarm in Spandau"}},
                },
                "clause": "payload_path_not_contains:message.summary=false alarm",
            },
            {
                "name": "negated_suffix_match",
                "event": {
                    "type": "alert",
                    "payload": {"routing": {"service": "queue-berlin-edge"}},
                },
                "clause": "payload_path_not_endswith:routing.service=edge",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"message": {"summary": "hello"}}},
                "clause": "payload_path_not_contains:routing.service=svc-",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_case_insensitive_string_predicates_match_nested_strings_and_list_indexes(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "entities": [{"value": "Straße A100, Berlin"}],
                    "message": {"summary": "VERKEHRSUNFALL auf der STRASSE A100"},
                    "routing": {"service": "SVC-Berlin-Edge"},
                },
            },
            rules=[
                {
                    "id": "r-strings-ci",
                    "when": [
                        "payload_path_startswith_ci:routing.service=svc-",
                        "payload_path_contains_ci:message.summary=verkehrsunfall",
                        "payload_path_contains_ci:entities.0.value=strasse",
                        "payload_path_endswith_ci:routing.service=edge",
                        "payload_path_endswith_ci:message.summary=a100",
                    ],
                    "then": [{"kind": "route", "params": {"target": "string_ci_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "string_ci_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_startswith_ci:routing.service=svc-",
                "payload_path_contains_ci:message.summary=verkehrsunfall",
                "payload_path_contains_ci:entities.0.value=strasse",
                "payload_path_endswith_ci:routing.service=edge",
                "payload_path_endswith_ci:message.summary=a100",
            ],
        )

    def test_payload_path_case_insensitive_string_predicates_fail_cleanly_for_non_string_actuals_and_misses(
        self,
    ) -> None:
        cases = [
            {
                "name": "non_string_actual",
                "event": {"type": "normalize", "payload": {"routing": {"service": 17}}},
                "clause": "payload_path_startswith_ci:routing.service=svc-",
            },
            {
                "name": "prefix_miss",
                "event": {
                    "type": "normalize",
                    "payload": {"routing": {"service": "queue-berlin-edge"}},
                },
                "clause": "payload_path_startswith_ci:routing.service=svc-",
            },
            {
                "name": "contains_miss",
                "event": {
                    "type": "normalize",
                    "payload": {"message": {"summary": "Lage in Charlottenburg"}},
                },
                "clause": "payload_path_contains_ci:message.summary=verkehrsunfall",
            },
            {
                "name": "suffix_miss",
                "event": {
                    "type": "normalize",
                    "payload": {"routing": {"service": "svc-berlin-core"}},
                },
                "clause": "payload_path_endswith_ci:routing.service=edge",
            },
            {
                "name": "missing_path",
                "event": {"type": "normalize", "payload": {"message": {"summary": "hello"}}},
                "clause": "payload_path_contains_ci:routing.service=svc-",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_negative_case_insensitive_string_predicates_match_nested_strings_and_list_indexes(
        self,
    ) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"value": "Straße A100, Berlin"}],
                    "message": {"summary": "VERKEHRSLAGE auf der STRASSE A100"},
                    "routing": {"service": "Queue-Berlin-Core"},
                },
            },
            rules=[
                {
                    "id": "r-negative-strings-ci",
                    "when": [
                        "payload_path_not_startswith_ci:routing.service=svc-",
                        "payload_path_not_contains_ci:message.summary=false alarm",
                        "payload_path_not_contains_ci:entities.0.value=charlottenburg",
                        "payload_path_not_endswith_ci:routing.service=edge",
                        "payload_path_not_endswith_ci:message.summary=resolved",
                    ],
                    "then": [{"kind": "route", "params": {"target": "negative_string_ci_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "negative_string_ci_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_not_startswith_ci:routing.service=svc-",
                "payload_path_not_contains_ci:message.summary=false alarm",
                "payload_path_not_contains_ci:entities.0.value=charlottenburg",
                "payload_path_not_endswith_ci:routing.service=edge",
                "payload_path_not_endswith_ci:message.summary=resolved",
            ],
        )

    def test_payload_path_negative_case_insensitive_string_predicates_fail_cleanly_for_non_string_actuals_misses_and_missing_paths(
        self,
    ) -> None:
        cases = [
            {
                "name": "non_string_actual",
                "event": {"type": "alert", "payload": {"routing": {"service": 17}}},
                "clause": "payload_path_not_startswith_ci:routing.service=svc-",
            },
            {
                "name": "negated_prefix_match",
                "event": {
                    "type": "alert",
                    "payload": {"routing": {"service": "SVC-Berlin-Edge"}},
                },
                "clause": "payload_path_not_startswith_ci:routing.service=svc-",
            },
            {
                "name": "negated_contains_match",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"summary": "FALSE ALARM in Spandau"}},
                },
                "clause": "payload_path_not_contains_ci:message.summary=false alarm",
            },
            {
                "name": "negated_suffix_match",
                "event": {
                    "type": "alert",
                    "payload": {"routing": {"service": "queue-berlin-edge"}},
                },
                "clause": "payload_path_not_endswith_ci:routing.service=edge",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"message": {"summary": "hello"}}},
                "clause": "payload_path_not_contains_ci:routing.service=svc-",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_case_insensitive_regex_predicates_match_nested_strings_and_list_indexes(
        self,
    ) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"value": "SVC-EDGE-01"}],
                    "message": {"summary": "URGENT Alert 42 escalated to Berlin"},
                    "routing": {"service": "Queue-Berlin-Edge"},
                },
            },
            rules=[
                {
                    "id": "r-regex-ci",
                    "when": [
                        r"payload_path_matches_ci:routing.service=queue-(berlin|munich)-(edge|core)",
                        r"payload_path_matches_ci:message.summary=\balert\s+42\b",
                        r"payload_path_matches_ci:entities.0.value=svc-edge-\d{2}",
                    ],
                    "then": [{"kind": "route", "params": {"target": "regex_ci_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "regex_ci_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                r"payload_path_matches_ci:routing.service=queue-(berlin|munich)-(edge|core)",
                r"payload_path_matches_ci:message.summary=\balert\s+42\b",
                r"payload_path_matches_ci:entities.0.value=svc-edge-\d{2}",
            ],
        )

    def test_payload_path_negative_case_insensitive_regex_predicates_match_when_patterns_do_not_match(
        self,
    ) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"value": "svc-core-01"}],
                    "message": {"summary": "Minor incident pending review"},
                    "routing": {"service": "Queue-Hamburg-Core"},
                },
            },
            rules=[
                {
                    "id": "r-negative-regex-ci",
                    "when": [
                        r"payload_path_not_matches_ci:routing.service=queue-(berlin|munich)-(edge|core)",
                        r"payload_path_not_matches_ci:message.summary=\balert\s+42\b",
                        r"payload_path_not_matches_ci:entities.0.value=svc-edge-\d{2}",
                    ],
                    "then": [{"kind": "route", "params": {"target": "negative_regex_ci_lane"}}],
                }
            ],
        )

        self.assertEqual(
            actions,
            [{"kind": "route", "params": {"target": "negative_regex_ci_lane"}}],
        )
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                r"payload_path_not_matches_ci:routing.service=queue-(berlin|munich)-(edge|core)",
                r"payload_path_not_matches_ci:message.summary=\balert\s+42\b",
                r"payload_path_not_matches_ci:entities.0.value=svc-edge-\d{2}",
            ],
        )

    def test_payload_path_case_insensitive_regex_predicates_fail_cleanly_for_non_string_actuals_hits_and_missing_paths(
        self,
    ) -> None:
        cases = [
            {
                "name": "non_string_actual",
                "event": {"type": "alert", "payload": {"routing": {"service": 17}}},
                "clause": r"payload_path_matches_ci:routing.service=queue-(berlin|munich)-(edge|core)",
            },
            {
                "name": "regex_miss",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"summary": "alert 7 escalated"}},
                },
                "clause": r"payload_path_matches_ci:message.summary=\balert\s+42\b",
            },
            {
                "name": "negated_regex_hit",
                "event": {
                    "type": "alert",
                    "payload": {"entities": [{"value": "SVC-EDGE-01"}]},
                },
                "clause": r"payload_path_not_matches_ci:entities.0.value=svc-edge-\d{2}",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"message": {"summary": "hello"}}},
                "clause": r"payload_path_not_matches_ci:routing.service=queue-(berlin|munich)-(edge|core)",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_regex_predicates_match_nested_strings_and_list_indexes(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"value": "svc-edge-01"}],
                    "message": {"summary": "urgent alert 42 escalated to berlin"},
                    "routing": {"service": "queue-berlin-edge"},
                },
            },
            rules=[
                {
                    "id": "r-regex",
                    "when": [
                        r"payload_path_matches:routing.service=queue-(berlin|munich)-(edge|core)",
                        r"payload_path_matches:message.summary=\balert\s+42\b",
                        r"payload_path_matches:entities.0.value=svc-edge-\d{2}",
                    ],
                    "then": [{"kind": "route", "params": {"target": "regex_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "regex_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                r"payload_path_matches:routing.service=queue-(berlin|munich)-(edge|core)",
                r"payload_path_matches:message.summary=\balert\s+42\b",
                r"payload_path_matches:entities.0.value=svc-edge-\d{2}",
            ],
        )

    def test_payload_path_negative_regex_predicates_match_when_patterns_do_not_match(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "alert",
                "payload": {
                    "entities": [{"value": "svc-core-01"}],
                    "message": {"summary": "minor incident pending review"},
                    "routing": {"service": "queue-hamburg-core"},
                },
            },
            rules=[
                {
                    "id": "r-negative-regex",
                    "when": [
                        r"payload_path_not_matches:routing.service=queue-(berlin|munich)-(edge|core)",
                        r"payload_path_not_matches:message.summary=\balert\s+42\b",
                        r"payload_path_not_matches:entities.0.value=svc-edge-\d{2}",
                    ],
                    "then": [{"kind": "route", "params": {"target": "negative_regex_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "negative_regex_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                r"payload_path_not_matches:routing.service=queue-(berlin|munich)-(edge|core)",
                r"payload_path_not_matches:message.summary=\balert\s+42\b",
                r"payload_path_not_matches:entities.0.value=svc-edge-\d{2}",
            ],
        )

    def test_payload_path_regex_predicates_fail_cleanly_for_non_string_actuals_hits_and_missing_paths(self) -> None:
        cases = [
            {
                "name": "non_string_actual",
                "event": {"type": "alert", "payload": {"routing": {"service": 17}}},
                "clause": r"payload_path_matches:routing.service=queue-(berlin|munich)-(edge|core)",
            },
            {
                "name": "regex_miss",
                "event": {
                    "type": "alert",
                    "payload": {"message": {"summary": "alert 7 escalated"}},
                },
                "clause": r"payload_path_matches:message.summary=\balert\s+42\b",
            },
            {
                "name": "negated_regex_hit",
                "event": {
                    "type": "alert",
                    "payload": {"entities": [{"value": "svc-edge-01"}]},
                },
                "clause": r"payload_path_not_matches:entities.0.value=svc-edge-\d{2}",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"message": {"summary": "hello"}}},
                "clause": r"payload_path_not_matches:routing.service=queue-(berlin|munich)-(edge|core)",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_length_predicates_match_strings_lists_and_objects(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "entities": [{"kind": "location"}, {"kind": "vehicle_count"}],
                    "message": {"summary": "Spandau West"},
                    "routing": {"channels": {"ops": "slack", "backup": "sms"}},
                },
            },
            rules=[
                {
                    "id": "r-lengths",
                    "when": [
                        "payload_path_len_gte:entities=1",
                        "payload_path_len_gt:message.summary=5",
                        "payload_path_len_lte:routing.channels=2",
                        "payload_path_len_lt:entities=3",
                    ],
                    "then": [{"kind": "route", "params": {"target": "length_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "length_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_len_gte:entities=1",
                "payload_path_len_gt:message.summary=5",
                "payload_path_len_lte:routing.channels=2",
                "payload_path_len_lt:entities=3",
            ],
        )

    def test_payload_path_length_predicates_match_zero_lengths_deterministically(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "entities": [],
                    "message": {"summary": ""},
                    "routing": {"channels": {}},
                },
            },
            rules=[
                {
                    "id": "r-zero-lengths",
                    "when": [
                        "payload_path_len_gte:entities=0",
                        "payload_path_len_lte:entities=0",
                        "payload_path_len_lte:message.summary=0",
                        "payload_path_len_lte:routing.channels=0",
                    ],
                    "then": [{"kind": "route", "params": {"target": "zero_length_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "zero_length_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_len_gte:entities=0",
                "payload_path_len_lte:entities=0",
                "payload_path_len_lte:message.summary=0",
                "payload_path_len_lte:routing.channels=0",
            ],
        )

    def test_payload_path_exact_length_predicates_match_strings_lists_and_objects(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "normalize",
                "payload": {
                    "entities": [{"kind": "location"}, {"kind": "vehicle_count"}],
                    "message": {"summary": "Ops ready"},
                    "routing": {"channels": {"ops": "slack", "backup": "sms"}},
                },
            },
            rules=[
                {
                    "id": "r-exact-lengths",
                    "when": [
                        "payload_path_len_eq:entities=2",
                        "payload_path_len_eq:message.summary=9",
                        "payload_path_len_not_eq:routing.channels=3",
                    ],
                    "then": [{"kind": "route", "params": {"target": "exact_length_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "exact_length_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "payload_path_len_eq:entities=2",
                "payload_path_len_eq:message.summary=9",
                "payload_path_len_not_eq:routing.channels=3",
            ],
        )

    def test_payload_path_length_predicates_fail_cleanly_for_non_sized_actuals_and_misses(self) -> None:
        cases = [
            {
                "name": "numeric_actual",
                "event": {"type": "alert", "payload": {"metrics": {"attempts": 3}}},
                "clause": "payload_path_len_gte:metrics.attempts=1",
            },
            {
                "name": "exact_length_miss",
                "event": {"type": "alert", "payload": {"entities": [{"kind": "service"}]}},
                "clause": "payload_path_len_eq:entities=2",
            },
            {
                "name": "exact_negative_length_hit",
                "event": {"type": "alert", "payload": {"routing": {"channels": {"ops": "slack", "backup": "sms", "pager": "pagerduty"}}}},
                "clause": "payload_path_len_not_eq:routing.channels=3",
            },
            {
                "name": "threshold_miss",
                "event": {"type": "alert", "payload": {"entities": []}},
                "clause": "payload_path_len_gt:entities=0",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"entities": [{"kind": "service"}]}},
                "clause": "payload_path_len_lte:routing.channels=2",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_payload_path_numeric_comparators_match_finite_nested_numbers(self) -> None:
        actions, trace = eval_policies(
            event={
                "type": "incident_candidate",
                "payload": {
                    "dedupe": {"key": "site-17:power"},
                    "geo": {"distance_meters": 320},
                    "metrics": {"retries": 3},
                    "priority": {"score": 0.97},
                    "window": {"minutes_since_anchor": 6},
                },
            },
            rules=[
                {
                    "id": "r-thresholds",
                    "when": [
                        "event_type_present",
                        "event_type_equals:incident_candidate",
                        "payload_path_exists:dedupe.key",
                        "payload_path_gte:priority.score=0.9",
                        "payload_path_gt:metrics.retries=2",
                        "payload_path_lte:window.minutes_since_anchor=10",
                        "payload_path_lt:geo.distance_meters=500",
                    ],
                    "then": [{"kind": "route", "params": {"target": "hot_lane"}}],
                }
            ],
        )

        self.assertEqual(actions, [{"kind": "route", "params": {"target": "hot_lane"}}])
        self.assertEqual(
            trace[0]["matched_clauses"],
            [
                "event_type_present",
                "event_type_equals:incident_candidate",
                "payload_path_exists:dedupe.key",
                "payload_path_gte:priority.score=0.9",
                "payload_path_gt:metrics.retries=2",
                "payload_path_lte:window.minutes_since_anchor=10",
                "payload_path_lt:geo.distance_meters=500",
            ],
        )

    def test_payload_path_numeric_comparators_fail_cleanly_for_non_numeric_actuals_and_threshold_misses(self) -> None:
        cases = [
            {
                "name": "string_actual",
                "event": {"type": "alert", "payload": {"priority": {"score": "0.97"}}},
                "clause": "payload_path_gte:priority.score=0.9",
            },
            {
                "name": "bool_actual",
                "event": {"type": "alert", "payload": {"flags": {"acked": False}}},
                "clause": "payload_path_gt:flags.acked=0",
            },
            {
                "name": "threshold_miss",
                "event": {"type": "alert", "payload": {"window": {"minutes_since_anchor": 12}}},
                "clause": "payload_path_lte:window.minutes_since_anchor=10",
            },
            {
                "name": "missing_path",
                "event": {"type": "alert", "payload": {"window": {"minutes_since_anchor": 6}}},
                "clause": "payload_path_lt:geo.distance_meters=500",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                actions, trace = eval_policies(
                    event=case["event"],
                    rules=[
                        {
                            "id": "r1",
                            "when": [case["clause"]],
                            "then": [{"kind": "route", "params": {"target": "ops"}}],
                        }
                    ],
                )

                self.assertEqual(actions, [])
                self.assertEqual(trace, [])

    def test_event_type_set_clauses_require_non_empty_string_members(self) -> None:
        invalid_clauses = [
            ("event_type_in:", "at least one member"),
            ("event_type_in:alert,,heartbeat", "non-empty members"),
            ("event_type_in:[]", "at least one member"),
            ("event_type_in:{}", "JSON form must decode to an array"),
            ("event_type_in:[true]", "non-empty strings"),
            ('event_type_in:[""]', "non-empty strings"),
            ("event_type_equals_ci:", "non-empty value"),
            ("event_type_startswith:", "non-empty value"),
            ("event_type_contains:", "non-empty value"),
            ("event_type_endswith:", "non-empty value"),
            ("event_type_not_startswith:", "non-empty value"),
            ("event_type_not_contains:", "non-empty value"),
            ("event_type_not_endswith:", "non-empty value"),
            ("event_type_startswith_ci:", "non-empty value"),
            ("event_type_contains_ci:", "non-empty value"),
            ("event_type_endswith_ci:", "non-empty value"),
            ("event_type_not_startswith_ci:", "non-empty value"),
            ("event_type_not_contains_ci:", "non-empty value"),
            ("event_type_not_endswith_ci:", "non-empty value"),
            ("event_type_matches:", "non-empty regex"),
            ("event_type_matches:(ops", "valid '<regex>' value"),
            ("event_type_not_matches:", "non-empty regex"),
            ("event_type_not_matches:(ops", "valid '<regex>' value"),
            ("event_type_matches_ci:", "non-empty regex"),
            ("event_type_matches_ci:(ops", "valid '<regex>' value"),
            ("event_type_not_matches_ci:", "non-empty regex"),
            ("event_type_not_matches_ci:(ops", "valid '<regex>' value"),
            ("event_type_equals_path:", "non-empty payload path"),
            ("event_type_not_equals_path:policy..expected_type", "without empty segments"),
            ("event_type_equals_path_ci:", "non-empty payload path"),
            ("event_type_not_equals_path_ci:policy..expected_type", "without empty segments"),
            ("event_type_startswith_path:", "non-empty payload path"),
            ("event_type_not_contains_path:policy..fragment", "without empty segments"),
            ("event_type_startswith_path_ci:", "non-empty payload path"),
            ("event_type_not_contains_path_ci:policy..fragment", "without empty segments"),
            ("event_type_matches_path:", "non-empty payload path"),
            ("event_type_not_matches_path:policy..regex", "without empty segments"),
            ("event_type_matches_path_ci:", "non-empty payload path"),
            ("event_type_not_matches_path_ci:policy..regex", "without empty segments"),
            ("event_type_in_path:", "non-empty payload path"),
            ("event_type_not_in_path:policy..allowed_types", "without empty segments"),
            ("event_type_in_path_ci:", "non-empty payload path"),
            ("event_type_not_in_path_ci:policy..allowed_types", "without empty segments"),
            ("event_type_not_in:", "at least one member"),
            ("event_type_not_in:alert,,heartbeat", "non-empty members"),
            ("event_type_not_in:[]", "at least one member"),
            ("event_type_not_in:{}", "JSON form must decode to an array"),
            ("event_type_not_in:[null]", "non-empty strings"),
            ("event_type_in_ci:", "at least one member"),
            ("event_type_in_ci:alert,,heartbeat", "non-empty members"),
            ("event_type_in_ci:[]", "at least one member"),
            ("event_type_in_ci:{}", "JSON form must decode to an array"),
            ("event_type_in_ci:[true]", "non-empty strings"),
            ('event_type_in_ci:[""]', "non-empty strings"),
            ("event_type_not_in_ci:", "at least one member"),
            ("event_type_not_in_ci:alert,,heartbeat", "non-empty members"),
            ("event_type_not_in_ci:[]", "at least one member"),
            ("event_type_not_in_ci:{}", "JSON form must decode to an array"),
            ("event_type_not_in_ci:[null]", "non-empty strings"),
        ]

        for clause, expected_message in invalid_clauses:
            with self.subTest(clause=clause):
                with self.assertRaisesRegex(TypeError, expected_message):
                    eval_policies(
                        event={"type": "alert", "payload": {"severity": "critical"}},
                        rules=[
                            {
                                "id": "r1",
                                "when": [clause],
                                "then": [{"kind": "route", "params": {"target": "ops"}}],
                            }
                        ],
                    )

    def test_payload_path_clause_syntax_errors_are_rejected(self) -> None:
        invalid_clauses = [
            ("payload_path_empty:", "non-empty payload path"),
            ("payload_path_empty:routing..severity", "without empty segments"),
            ("payload_path_not_empty:", "non-empty payload path"),
            ("payload_path_not_empty:routing..severity", "without empty segments"),
            ("payload_path_exists:", "non-empty payload path"),
            ("payload_path_exists:routing..severity", "without empty segments"),
            ("payload_path_not_exists:", "non-empty payload path"),
            ("payload_path_not_exists:routing..severity", "without empty segments"),
            ("payload_path_is_null:", "non-empty payload path"),
            ("payload_path_is_null:routing..severity", "without empty segments"),
            ("payload_path_is_bool:", "non-empty payload path"),
            ("payload_path_is_bool:routing..severity", "without empty segments"),
            ("payload_path_is_number:", "non-empty payload path"),
            ("payload_path_is_number:routing..severity", "without empty segments"),
            ("payload_path_is_string:", "non-empty payload path"),
            ("payload_path_is_string:routing..severity", "without empty segments"),
            ("payload_path_is_list:", "non-empty payload path"),
            ("payload_path_is_list:routing..severity", "without empty segments"),
            ("payload_path_is_object:", "non-empty payload path"),
            ("payload_path_is_object:routing..severity", "without empty segments"),
            ("payload_path_has_key:routing.labels", "<path>=<string>"),
            ("payload_path_has_key:=severity", "non-empty payload path"),
            ("payload_path_has_key:routing..labels=severity", "without empty segments"),
            ("payload_path_has_key:routing.labels=   ", "<path>=<string>"),
            ("payload_path_not_has_key:routing.labels", "<path>=<string>"),
            ("payload_path_not_has_key:=legacy", "non-empty payload path"),
            ("payload_path_has_key_ci:routing.headers", "<path>=<string>"),
            ("payload_path_has_key_ci:=x-trace-id", "non-empty payload path"),
            ("payload_path_not_has_key_ci:routing.headers=   ", "<path>=<string>"),
            ("payload_path_has_keys:routing.labels", "<path>=<csv-or-json-list>"),
            ("payload_path_has_keys:=severity,team", "non-empty payload path"),
            ("payload_path_has_keys:routing..labels=severity,team", "without empty segments"),
            ("payload_path_has_keys:routing.labels=severity,", "non-empty members"),
            ("payload_path_missing_keys:routing.labels", "<path>=<csv-or-json-list>"),
            ("payload_path_missing_keys:=legacy,deprecated", "non-empty payload path"),
            ("payload_path_has_keys_ci:routing.headers", "<path>=<csv-or-json-list>"),
            ("payload_path_has_keys_ci:=x-trace-id,x-env", "non-empty payload path"),
            ("payload_path_missing_keys_ci:routing.headers=x-blocked,", "non-empty members"),
            ("payload_path_has_keys_path:routing.headers", "<path>=<other.path>"),
            ("payload_path_has_keys_path:=policy.required_headers", "non-empty payload path"),
            ("payload_path_missing_keys_path:routing..headers=policy.forbidden_headers", "without empty segments"),
            ("payload_path_has_keys_path_ci:routing.headers", "<path>=<other.path>"),
            ("payload_path_has_keys_path_ci:=policy.required_headers", "non-empty payload path"),
            ("payload_path_missing_keys_path_ci:routing.headers=policy..forbidden_headers", "without empty segments"),
            ("payload_path_missing_keys_path_ci:routing.headers=", "<path>=<other.path>"),
            ("payload_path_has_key_path:routing.headers", "<path>=<other.path>"),
            ("payload_path_has_key_path:=policy.primary_header", "non-empty payload path"),
            ("payload_path_not_has_key_path:routing..headers=policy.primary_header", "without empty segments"),
            ("payload_path_not_has_key_path:routing.headers=", "<path>=<other.path>"),
            ("payload_path_has_key_path_ci:routing.headers", "<path>=<other.path>"),
            ("payload_path_has_key_path_ci:=policy.primary_header", "non-empty payload path"),
            ("payload_path_not_has_key_path_ci:routing.headers=policy..primary_header", "without empty segments"),
            ("payload_path_not_has_key_path_ci:routing.headers=", "<path>=<other.path>"),
            ("payload_path_equals:routing.severity", "<path>=<value>"),
            ("payload_path_equals:=critical", "non-empty payload path"),
            ("payload_path_not_equals:routing.severity", "<path>=<value>"),
            ("payload_path_not_equals:=critical", "non-empty payload path"),
            ("payload_path_equals_path:routing.team", "<path>=<other.path>"),
            ("payload_path_equals_path:=routing.owner", "non-empty payload path"),
            ("payload_path_equals_path:routing..team=routing.owner", "without empty segments"),
            ("payload_path_not_equals_path:routing.team=", "<path>=<other.path>"),
            ("payload_path_equals_path_ci:routing.team", "<path>=<other.path>"),
            ("payload_path_equals_path_ci:=routing.owner", "non-empty payload path"),
            ("payload_path_not_equals_path_ci:routing.team=routing..backup_team", "without empty segments"),
            ("payload_path_not_equals_path_ci:routing.team=", "<path>=<other.path>"),
            ("payload_path_startswith_path:message.subject", "<path>=<other.path>"),
            ("payload_path_contains_path:=policy.fragment", "non-empty payload path"),
            ("payload_path_endswith_path:message..subject=policy.suffix", "without empty segments"),
            ("payload_path_not_contains_path:message.subject=", "<path>=<other.path>"),
            ("payload_path_startswith_path_ci:message.subject", "<path>=<other.path>"),
            ("payload_path_contains_path_ci:=policy.fragment", "non-empty payload path"),
            ("payload_path_endswith_path_ci:message.subject=policy..suffix", "without empty segments"),
            ("payload_path_not_contains_path_ci:message.subject=", "<path>=<other.path>"),
            ("payload_path_matches_path:message.subject", "<path>=<other.path>"),
            ("payload_path_matches_path:=policy.subject_regex", "non-empty payload path"),
            ("payload_path_matches_path_ci:message..subject=policy.subject_regex", "without empty segments"),
            ("payload_path_not_matches_path_ci:message.subject=", "<path>=<other.path>"),
            ("payload_path_in_path:routing.team", "<path>=<other.path>"),
            ("payload_path_in_path:=routing.allowed_teams", "non-empty payload path"),
            ("payload_path_in_path:routing..team=routing.allowed_teams", "without empty segments"),
            ("payload_path_not_in_path:routing.team=", "<path>=<other.path>"),
            ("payload_path_in_path_ci:routing.team", "<path>=<other.path>"),
            ("payload_path_in_path_ci:=routing.allowed_teams", "non-empty payload path"),
            ("payload_path_not_in_path_ci:routing.team=routing..blocked_teams", "without empty segments"),
            ("payload_path_not_in_path_ci:routing.team=", "<path>=<other.path>"),
            ("payload_path_any_in_path:routing.tags", "<path>=<other.path>"),
            ("payload_path_any_in_path:=policy.allowed_tags", "non-empty payload path"),
            ("payload_path_all_in_path:routing..tags=policy.allowed_tags", "without empty segments"),
            ("payload_path_none_in_path:routing.tags=", "<path>=<other.path>"),
            ("payload_path_any_in_path_ci:audit.labels", "<path>=<other.path>"),
            ("payload_path_any_in_path_ci:=audit.mirrors", "non-empty payload path"),
            ("payload_path_all_in_path_ci:audit..teams=policy.allowed_labels", "without empty segments"),
            ("payload_path_none_in_path_ci:audit.labels=", "<path>=<other.path>"),
            ("payload_path_gt_path:priority.score", "<path>=<other.path>"),
            ("payload_path_gte_path:=priority.floor", "non-empty payload path"),
            ("payload_path_lt_path:priority.score=priority..floor", "without empty segments"),
            ("payload_path_lte_path:priority.score=", "<path>=<other.path>"),
            ("payload_path_in:routing.severity", "<path>=<csv-or-json-list>"),
            ("payload_path_in:=critical,warning", "non-empty payload path"),
            ("payload_path_in:routing.severity=critical,,warning", "non-empty members"),
            ("payload_path_in:routing.severity=[]", "at least one member"),
            ("payload_path_in:routing.severity={}", "JSON form must decode to an array"),
            ("payload_path_in:routing.severity=[{}]", "JSON scalars"),
            ("payload_path_not_in:routing.severity", "<path>=<csv-or-json-list>"),
            ("payload_path_not_in:=critical,warning", "non-empty payload path"),
            ("payload_path_not_in:routing.severity=critical,,warning", "non-empty members"),
            ("payload_path_not_in:routing.severity=[]", "at least one member"),
            ("payload_path_not_in:routing.severity={}", "JSON form must decode to an array"),
            ("payload_path_not_in:routing.severity=[{}]", "JSON scalars"),
            ("payload_path_in_ci:routing.service", "<path>=<csv-or-json-list>"),
            ("payload_path_in_ci:=svc-berlin-edge,svc-west", "non-empty payload path"),
            ("payload_path_in_ci:routing.service=svc-berlin-edge,,svc-west", "non-empty members"),
            ("payload_path_in_ci:routing.service=[]", "at least one member"),
            ("payload_path_in_ci:routing.service={}", "JSON form must decode to an array"),
            ("payload_path_in_ci:routing.service=[1]", "members must be strings"),
            ("payload_path_not_in_ci:message.level", "<path>=<csv-or-json-list>"),
            ("payload_path_not_in_ci:=warning,error", "non-empty payload path"),
            ("payload_path_not_in_ci:message.level=warning,,error", "non-empty members"),
            ("payload_path_not_in_ci:message.level=[]", "at least one member"),
            ("payload_path_not_in_ci:message.level={}", "JSON form must decode to an array"),
            ("payload_path_not_in_ci:message.level=[false]", "members must be strings"),
            ("payload_path_equals_ci:routing.service", "<path>=<string>"),
            ("payload_path_equals_ci:=svc-berlin-edge", "non-empty payload path"),
            ("payload_path_not_equals_ci:message.summary", "<path>=<string>"),
            ("payload_path_not_equals_ci:=lagebild berlin", "non-empty payload path"),
            ("payload_path_any_in:routing.channels", "<path>=<csv-or-json-list>"),
            ("payload_path_any_in:=push,sms", "non-empty payload path"),
            ("payload_path_any_in:routing.channels=push,,sms", "non-empty members"),
            ("payload_path_any_in:routing.channels=[]", "at least one member"),
            ("payload_path_any_in:routing.channels={}", "JSON form must decode to an array"),
            ("payload_path_any_in:routing.channels=[{}]", "JSON scalars"),
            ("payload_path_any_in_ci:routing.channels", "<path>=<csv-or-json-list>"),
            ("payload_path_any_in_ci:=push,sms", "non-empty payload path"),
            ("payload_path_any_in_ci:routing.channels=push,,sms", "non-empty members"),
            ("payload_path_any_in_ci:routing.channels=[]", "at least one member"),
            ("payload_path_any_in_ci:routing.channels={}", "JSON form must decode to an array"),
            ("payload_path_any_in_ci:routing.channels=[1]", "members must be strings"),
            ("payload_path_all_in_ci:routing.channels", "<path>=<csv-or-json-list>"),
            ("payload_path_all_in_ci:=push,sms", "non-empty payload path"),
            ("payload_path_all_in_ci:routing.channels=push,,sms", "non-empty members"),
            ("payload_path_all_in_ci:routing.channels=[]", "at least one member"),
            ("payload_path_all_in_ci:routing.channels={}", "JSON form must decode to an array"),
            ("payload_path_all_in_ci:routing.channels=[false]", "members must be strings"),
            ("payload_path_none_in:routing.channels", "<path>=<csv-or-json-list>"),
            ("payload_path_none_in:=push,sms", "non-empty payload path"),
            ("payload_path_none_in:routing.channels=push,,sms", "non-empty members"),
            ("payload_path_none_in:routing.channels=[]", "at least one member"),
            ("payload_path_none_in:routing.channels={}", "JSON form must decode to an array"),
            ("payload_path_none_in:routing.channels=[{}]", "JSON scalars"),
            ("payload_path_none_in_ci:routing.channels", "<path>=<csv-or-json-list>"),
            ("payload_path_none_in_ci:=push,sms", "non-empty payload path"),
            ("payload_path_none_in_ci:routing.channels=push,,sms", "non-empty members"),
            ("payload_path_none_in_ci:routing.channels=[]", "at least one member"),
            ("payload_path_none_in_ci:routing.channels={}", "JSON form must decode to an array"),
            ("payload_path_none_in_ci:routing.channels=[null]", "members must be strings"),
            ("payload_path_startswith:routing.service", "<path>=<string>"),
            ("payload_path_startswith:=svc-", "non-empty payload path"),
            ("payload_path_contains:message.summary=", "<path>=<string>"),
            ("payload_path_contains:=Spandau", "non-empty payload path"),
            ("payload_path_endswith:message.summary", "<path>=<string>"),
            ("payload_path_endswith:=edge", "non-empty payload path"),
            ("payload_path_not_startswith:routing.service", "<path>=<string>"),
            ("payload_path_not_startswith:=svc-", "non-empty payload path"),
            ("payload_path_not_contains:message.summary=", "<path>=<string>"),
            ("payload_path_not_contains:=Spandau", "non-empty payload path"),
            ("payload_path_not_endswith:message.summary", "<path>=<string>"),
            ("payload_path_not_endswith:=edge", "non-empty payload path"),
            ("payload_path_startswith_ci:routing.service", "<path>=<string>"),
            ("payload_path_startswith_ci:=svc-", "non-empty payload path"),
            ("payload_path_contains_ci:message.summary=", "<path>=<string>"),
            ("payload_path_contains_ci:=Spandau", "non-empty payload path"),
            ("payload_path_endswith_ci:message.summary", "<path>=<string>"),
            ("payload_path_endswith_ci:=edge", "non-empty payload path"),
            ("payload_path_not_startswith_ci:routing.service", "<path>=<string>"),
            ("payload_path_not_startswith_ci:=svc-", "non-empty payload path"),
            ("payload_path_not_contains_ci:message.summary=", "<path>=<string>"),
            ("payload_path_not_contains_ci:=Spandau", "non-empty payload path"),
            ("payload_path_not_endswith_ci:message.summary", "<path>=<string>"),
            ("payload_path_not_endswith_ci:=edge", "non-empty payload path"),
            ("payload_path_matches:routing.service", "<path>=<regex>"),
            ("payload_path_matches:=queue-(berlin|munich)", "non-empty payload path"),
            ("payload_path_matches:routing.service=(queue-(berlin|munich)", "valid '<path>=<regex>' pair"),
            ("payload_path_not_matches:message.summary", "<path>=<regex>"),
            ("payload_path_not_matches:=\\balert\\s+42\\b", "non-empty payload path"),
            ("payload_path_not_matches:message.summary=(alert", "valid '<path>=<regex>' pair"),
            ("payload_path_matches_ci:routing.service", "<path>=<regex>"),
            ("payload_path_matches_ci:=queue-(berlin|munich)", "non-empty payload path"),
            ("payload_path_matches_ci:routing.service=(queue-(berlin|munich)", "valid '<path>=<regex>' pair"),
            ("payload_path_not_matches_ci:message.summary", "<path>=<regex>"),
            ("payload_path_not_matches_ci:=\\balert\\s+42\\b", "non-empty payload path"),
            ("payload_path_not_matches_ci:message.summary=(alert", "valid '<path>=<regex>' pair"),
            ("payload_path_len_eq:entities", "<path>=<integer>"),
            ("payload_path_len_not_eq:=2", "non-empty payload path"),
            ("payload_path_len_gt:entities", "<path>=<integer>"),
            ("payload_path_len_gte:=1", "non-empty payload path"),
            ("payload_path_len_lt:entities=1.5", "non-negative integer"),
            ("payload_path_len_lte:entities=-1", "non-negative integer"),
            ("payload_path_len_eq_path:entities", "<path>=<other.path>"),
            ("payload_path_len_not_eq_path:=policy.expected_channels", "non-empty payload path"),
            ("payload_path_len_gt_path:entities=policy..expected_channels", "without empty segments"),
            ("payload_path_len_gte_path:entities=", "<path>=<other.path>"),
            ("payload_path_len_lt_path:entities", "<path>=<other.path>"),
            ("payload_path_len_lte_path:=policy.annotation_cap", "non-empty payload path"),
            ("payload_path_gt:priority.score", "<path>=<number>"),
            ("payload_path_gte:=0.9", "non-empty payload path"),
            ("payload_path_lt:priority.score=true", "finite numeric"),
            ("payload_path_lte:priority.score=critical", "finite numeric"),
        ]

        for clause, expected_message in invalid_clauses:
            with self.subTest(clause=clause):
                with self.assertRaisesRegex(TypeError, expected_message):
                    eval_policies(
                        event={"type": "alert", "payload": {"routing": {"severity": "critical"}}},
                        rules=[
                            {
                                "id": "r1",
                                "when": [clause],
                                "then": [{"kind": "route", "params": {"target": "ops"}}],
                            }
                        ],
                    )

    def test_score_semantics_are_structural_not_severity_or_confidence_based(self) -> None:
        rules = [
            {
                "id": "r-route",
                "when": ["event_type_present", "payload_has:severity", "payload_has:confidence"],
                "then": [{"kind": "route", "params": {"target": "ops"}}],
            }
        ]

        low_values_event = {"type": "alert", "payload": {"severity": 0.1, "confidence": 0.1}}
        high_values_event = {"type": "alert", "payload": {"severity": 0.9, "confidence": 0.95}}

        _, low_trace = eval_policies(low_values_event, rules)
        _, high_trace = eval_policies(high_values_event, rules)

        self.assertEqual(low_trace[0]["matched_clauses"], high_trace[0]["matched_clauses"])
        self.assertEqual(low_trace[0]["score"], 1.0)
        self.assertEqual(high_trace[0]["score"], 1.0)

    def test_threshold_like_clauses_are_not_implicitly_interpreted(self) -> None:
        try:
            actions, trace = eval_policies(
                event={"type": "alert", "payload": {"severity": 0.95, "confidence": 0.98}},
                rules=[
                    {
                        "id": "r-threshold",
                        "when": ["event_type_present", "payload_min_severity:0.70"],
                        "then": [{"kind": "route", "params": {"target": "ops"}}],
                    }
                ],
            )
        except TypeError as exc:
            self.assertIn("unsupported clause", str(exc))
        else:
            self.assertEqual(actions, [])
            self.assertEqual(trace, [])

    def test_expression_language_clause_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "expression syntax"):
            eval_policies(
                event={"type": "alert", "payload": {"severity": 0.9}},
                rules=[
                    {
                        "id": "r1",
                        "when": ["event_type_present && payload_has:severity"],
                        "then": [{"kind": "route", "params": {"target": "ops"}}],
                    }
                ],
            )

    def test_actions_must_be_declarative_outputs(self) -> None:
        class NonDeclarative:
            pass

        with self.assertRaisesRegex(TypeError, "declarative JSON-like data"):
            eval_policies(
                event={"type": "ingest", "payload": {}},
                rules=[
                    {
                        "id": "r1",
                        "when": ["event_type_present"],
                        "then": [{"kind": "act", "params": {"callback": NonDeclarative()}}],
                    }
                ],
            )

    def test_runtime_refs_require_binding_map_when_ref_fields_exist(self) -> None:
        with self.assertRaisesRegex(TypeError, "no refs mapping was provided"):
            eval_policies(
                event={"type": "ingest", "payload": {"text_ref": "@txt_001"}},
                rules=[
                    {
                        "id": "r1",
                        "when": ["event_type_present"],
                        "then": [{"kind": "act", "params": {"template_ref": "@tpl_ops"}}],
                    }
                ],
            )

    def test_runtime_refs_reject_missing_bindings(self) -> None:
        with self.assertRaisesRegex(TypeError, "missing ref id"):
            eval_policies(
                event={"type": "ingest", "payload": {"text_ref": "@txt_001"}},
                rules=[
                    {
                        "id": "r1",
                        "when": ["event_type_present"],
                        "then": [{"kind": "act", "params": {"template_ref": "@tpl_ops"}}],
                    }
                ],
                refs={"txt_001": "text"},
            )

    def test_runtime_refs_reject_invalid_ref_literals(self) -> None:
        with self.assertRaisesRegex(TypeError, "invalid ref id"):
            eval_policies(
                event={"type": "ingest", "payload": {"text_ref": "@txt?001"}},
                rules=[
                    {
                        "id": "r1",
                        "when": ["event_type_present"],
                        "then": [{"kind": "act", "params": {"template_ref": "@tpl_ops"}}],
                    }
                ],
                refs={"txt_001": "text", "tpl_ops": "template"},
            )

    def test_runtime_refs_reject_colliding_bindings(self) -> None:
        with self.assertRaisesRegex(TypeError, "colliding ref ids"):
            eval_policies(
                event={"type": "ingest", "payload": {"text_ref": "@txt_001"}},
                rules=[
                    {
                        "id": "r1",
                        "when": ["event_type_present"],
                        "then": [{"kind": "act", "params": {"template_ref": "@tpl_ops"}}],
                    }
                ],
                refs={"txt_001": "text", "@txt_001": "duplicate", "tpl_ops": "template"},
            )

    def test_runtime_refs_validate_successfully_when_all_bindings_exist(self) -> None:
        actions, trace = eval_policies(
            event={"type": "ingest", "payload": {"text_ref": "@txt_001"}},
            rules=[
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"template_ref": "@tpl_ops"}}],
                }
            ],
            refs={"txt_001": "text", "tpl_ops": "template"},
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(len(trace), 1)

    def test_eval_envelope_can_materialize_action_plan_with_resolved_refs(self) -> None:
        envelope = eval_policies_envelope(
            event={"type": "ingest", "payload": {"severity": "high"}},
            rules=[
                {
                    "id": "route_ops",
                    "when": ["event_type_present", "payload_has:severity"],
                    "then": [
                        {
                            "kind": "notify",
                            "params": {
                                "channel": "ops",
                                "severity_ref": "@sev_label",
                                "payload": {
                                    "template_ref": "@tpl_ops",
                                    "targets": ["primary", {"ticket_ref": "@ticket_42"}],
                                },
                            },
                        }
                    ],
                }
            ],
            refs={"sev_label": "critical", "tpl_ops": "tpl://ops", "ticket_42": "INC-42"},
            include_action_plan=True,
        )

        self.assertEqual(
            envelope,
            {
                "actions": [
                    {
                        "kind": "notify",
                        "params": {
                            "channel": "ops",
                            "payload": {
                                "targets": ["primary", {"ticket_ref": "@ticket_42"}],
                                "template_ref": "@tpl_ops",
                            },
                            "severity_ref": "@sev_label",
                        },
                    }
                ],
                "trace": [
                    {
                        "rule_id": "route_ops",
                        "matched_clauses": ["event_type_present", "payload_has:severity"],
                        "score": 1.0,
                    }
                ],
                "action_plan": [
                    {
                        "step": 1,
                        "kind": "notify",
                        "params": {
                            "channel": "ops",
                            "payload": {
                                "targets": ["primary", {"ticket": "INC-42"}],
                                "template": "tpl://ops",
                            },
                            "severity": "critical",
                        },
                    }
                ],
                "resolved_refs": {
                    "sev_label": "critical",
                    "ticket_42": "INC-42",
                    "tpl_ops": "tpl://ops",
                },
            },
        )

    def test_eval_envelope_action_plan_reports_materialization_collisions_as_runtime_error(self) -> None:
        envelope = eval_policies_envelope(
            event={"type": "ingest", "payload": {}},
            rules=[
                {
                    "id": "route_ops",
                    "when": ["event_type_present"],
                    "then": [
                        {
                            "kind": "notify",
                            "params": {"channel": "ops", "channel_ref": "@chan_ops"},
                        }
                    ],
                }
            ],
            refs={"chan_ops": "ops-resolved"},
            include_action_plan=True,
        )

        self.assertEqual(
            envelope["actions"],
            [{"kind": "notify", "params": {"channel": "ops", "channel_ref": "@chan_ops"}}],
        )
        self.assertEqual(
            envelope["trace"],
            [{"rule_id": "route_ops", "matched_clauses": ["event_type_present"], "score": 1.0}],
        )
        self.assertEqual(envelope["action_plan"], [])
        self.assertEqual(envelope["resolved_refs"], {})
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")
        self.assertEqual(
            envelope["error"]["message"],
            "action_plan[1].params.channel_ref materializes duplicate action-plan key 'channel'",
        )

    def test_output_ordering_is_stable_for_duplicate_rule_ids(self) -> None:
        actions, trace = eval_policies(
            event={"type": "ingest", "payload": {}},
            rules=[
                {
                    "id": "same",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"step": 1}}],
                },
                {
                    "id": "same",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"step": 2}}],
                },
            ],
        )

        self.assertEqual(actions, [
            {"kind": "act", "params": {"step": 1}},
            {"kind": "act", "params": {"step": 2}},
        ])
        self.assertEqual([item["rule_id"] for item in trace], ["same", "same"])

    def test_input_objects_are_not_mutated(self) -> None:
        event = Event(type="ingest", payload={"z": 2, "a": 1})
        rules = [
            {
                "id": "r1",
                "when": ["event_type_present"],
                "then": [{"kind": "act", "params": {"z": 2, "a": 1}}],
            }
        ]
        before_event_payload = deepcopy(event.payload)
        before_rules = deepcopy(rules)

        actions, trace = eval_policies(event, rules)

        self.assertEqual(event.payload, before_event_payload)
        self.assertEqual(rules, before_rules)
        self.assertIsNot(actions[0]["params"], rules[0]["then"][0]["params"])
        self.assertEqual(trace[0]["matched_clauses"], ["event_type_present"])

    def test_ir_rule_without_when_then_uses_safe_defaults(self) -> None:
        actions, trace = eval_policies(
            Event(type="ingest", payload={}),
            [Rule(id="rule-default")],
        )

        self.assertEqual(actions, [{"kind": "act", "params": {"rule_id": "rule-default"}}])
        self.assertEqual(
            trace,
            [{"rule_id": "rule-default", "matched_clauses": ["event_type_present"], "score": 1.0}],
        )


if __name__ == "__main__":
    unittest.main()
