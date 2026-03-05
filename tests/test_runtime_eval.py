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

        # Runtime sorts by rule_id for deterministic ordering independent of input list order.
        self.assertEqual([step["rule_id"] for step in first_trace], ["r1", "r2"])

        self.assertEqual(first_actions[0]["params"], {"a": {"a": 1, "b": 2}, "z": 9})
        self.assertEqual(first_actions[1]["params"], {"a": 1, "z": 2})

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
