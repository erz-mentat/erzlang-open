from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from runtime.errors import ERROR_ENVELOPE_FIELD_ORDER


ROOT = Path(__file__).resolve().parents[1]
ERROR_FIXTURES = ROOT / "tests" / "fixtures" / "errors"
EVAL_FIXTURES = ROOT / "examples" / "eval"
COMPARE_PRESET_FIXTURES = EVAL_FIXTURES / "compare-presets"
PATH_PREDICATE_OK_ENVELOPE_FIXTURE = EVAL_FIXTURES / "event-path-ok.expected.envelope.json"
PATH_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE = (
    EVAL_FIXTURES / "event-path-no-action.expected.envelope.json"
)
PATH_PREDICATE_NO_ACTION_SUMMARY_FIXTURE = (
    EVAL_FIXTURES / "event-path-no-action.expected.summary.txt"
)
STRING_PREDICATE_OK_ENVELOPE_FIXTURE = EVAL_FIXTURES / "event-string-ok.expected.envelope.json"
STRING_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE = (
    EVAL_FIXTURES / "event-string-no-action.expected.envelope.json"
)
STRING_PREDICATE_NO_ACTION_SUMMARY_FIXTURE = (
    EVAL_FIXTURES / "event-string-no-action.expected.summary.txt"
)
LENGTH_PREDICATE_OK_ENVELOPE_FIXTURE = EVAL_FIXTURES / "event-length-ok.expected.envelope.json"
LENGTH_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE = (
    EVAL_FIXTURES / "event-length-no-action.expected.envelope.json"
)
LENGTH_PREDICATE_NO_ACTION_SUMMARY_FIXTURE = (
    EVAL_FIXTURES / "event-length-no-action.expected.summary.txt"
)
ANY_IN_PREDICATE_OK_ENVELOPE_FIXTURE = EVAL_FIXTURES / "event-any-in-ok.expected.envelope.json"
ANY_IN_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE = (
    EVAL_FIXTURES / "event-any-in-no-action.expected.envelope.json"
)
ANY_IN_PREDICATE_NO_ACTION_SUMMARY_FIXTURE = (
    EVAL_FIXTURES / "event-any-in-no-action.expected.summary.txt"
)
ALL_IN_PREDICATE_OK_ENVELOPE_FIXTURE = EVAL_FIXTURES / "event-all-in-ok.expected.envelope.json"
ALL_IN_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE = (
    EVAL_FIXTURES / "event-all-in-no-action.expected.envelope.json"
)
ALL_IN_PREDICATE_NO_ACTION_SUMMARY_FIXTURE = (
    EVAL_FIXTURES / "event-all-in-no-action.expected.summary.txt"
)
NONE_IN_PREDICATE_OK_ENVELOPE_FIXTURE = EVAL_FIXTURES / "event-none-in-ok.expected.envelope.json"
NONE_IN_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE = (
    EVAL_FIXTURES / "event-none-in-no-action.expected.envelope.json"
)
NONE_IN_PREDICATE_NO_ACTION_SUMMARY_FIXTURE = (
    EVAL_FIXTURES / "event-none-in-no-action.expected.summary.txt"
)
THRESHOLD_PREDICATE_OK_ENVELOPE_FIXTURE = EVAL_FIXTURES / "event-threshold-ok.expected.envelope.json"
THRESHOLD_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE = (
    EVAL_FIXTURES / "event-threshold-no-action.expected.envelope.json"
)
THRESHOLD_PREDICATE_NO_ACTION_SUMMARY_FIXTURE = (
    EVAL_FIXTURES / "event-threshold-no-action.expected.summary.txt"
)
ACTION_PLAN_SINGLE_ENVELOPE_FIXTURE = EVAL_FIXTURES / "event-ok.action-plan.expected.envelope.json"
ACTION_PLAN_SINGLE_SUMMARY_FIXTURE = EVAL_FIXTURES / "event-ok.action-plan.expected.summary.txt"
ACTION_PLAN_SIDECAR_ENVELOPE_FIXTURE = (
    EVAL_FIXTURES / "event-sidecar.action-plan.expected.envelope.json"
)
ACTION_PLAN_SIDECAR_SUMMARY_FIXTURE = (
    EVAL_FIXTURES / "event-sidecar.action-plan.expected.summary.txt"
)
ACTION_PLAN_BATCH_ENVELOPE_FIXTURE = EVAL_FIXTURES / "batch.action-plan.expected.envelope.json"
ACTION_PLAN_BATCH_SUMMARY_FIXTURE = EVAL_FIXTURES / "batch.action-plan.expected.summary.txt"
THRESHOLD_HANDOFF_FIXTURES = EVAL_FIXTURES / "threshold-handoff"
THRESHOLD_HANDOFF_BASELINE_VERIFY_SUMMARY_FIXTURE = (
    THRESHOLD_HANDOFF_FIXTURES / "baseline.verify.expected.summary.txt"
)
THRESHOLD_HANDOFF_TRIAGE_VERIFY_SUMMARY_FIXTURE = (
    THRESHOLD_HANDOFF_FIXTURES / "triage.verify.expected.summary.txt"
)
THRESHOLD_HANDOFF_COMPARE_SUMMARY_FIXTURE = (
    THRESHOLD_HANDOFF_FIXTURES / "triage-vs-baseline.compare.expected.summary.txt"
)
PROGRAM_PACK_FIXTURES = ROOT / "examples" / "program-packs"
PROGRAM_PACK_INDEX = PROGRAM_PACK_FIXTURES / "program-pack-index.json"
DEDUP_CLUSTER_PACK = PROGRAM_PACK_FIXTURES / "dedup-cluster"
ALERT_ROUTING_PACK = PROGRAM_PACK_FIXTURES / "alert-routing"
INGEST_NORMALIZE_PACK = PROGRAM_PACK_FIXTURES / "ingest-normalize"
REFS_HANDOFF_PACK = PROGRAM_PACK_FIXTURES / "refs-handoff"


class CliErrorModeTests(unittest.TestCase):
    def _run_cli(self, *args: str, stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "cli.main", *args],
            cwd=ROOT,
            text=True,
            input=stdin_text,
            capture_output=True,
            check=False,
        )

    def _read_error_snapshot(self, name: str) -> str:
        return (ERROR_FIXTURES / name).read_text(encoding="utf-8")

    def _assert_json_error_snapshot(
        self,
        *,
        completed: subprocess.CompletedProcess[str],
        snapshot_name: str,
        expect_span_position: int | None,
    ) -> dict[str, object]:
        self.assertEqual(completed.stderr, self._read_error_snapshot(snapshot_name))

        envelope = json.loads(completed.stderr)
        self.assertEqual(list(envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
        self.assertEqual(list(envelope["details"].keys()), ["error_type", "command"])

        if expect_span_position is None:
            self.assertIsNone(envelope["span"])
        else:
            self.assertIsInstance(envelope["span"], dict)
            self.assertEqual(list(envelope["span"].keys()), ["position"])
            self.assertEqual(envelope["span"]["position"], expect_span_position)

        return envelope

    def test_json_error_mode_snapshot_parity_matrix(self) -> None:
        cases = [
            {
                "name": "parse_syntax",
                "args": ("parse", "-", "--json-errors"),
                "stdin_text": 'ev{type:"x"',
                "snapshot": "parse_syntax.stderr",
                "code": "ERZ_PARSE_SYNTAX",
                "stage": "parse",
                "command": "parse",
                "error_type": "CompactParseError",
                "expect_span_position": 11,
            },
            {
                "name": "validate_schema",
                "args": ("validate", "-", "--json-errors"),
                "stdin_text": "ev{payload:{}}",
                "snapshot": "validate_schema.stderr",
                "code": "ERZ_VALIDATE_SCHEMA",
                "stage": "validate",
                "command": "validate",
                "error_type": "CompactValidationError",
                "expect_span_position": None,
            },
            {
                "name": "pack_missing_event",
                "args": ("pack", "-", "--json-errors"),
                "stdin_text": "{}",
                "snapshot": "transform_pack_missing_event.stderr",
                "code": "ERZ_TRANSFORM_ERROR",
                "stage": "transform",
                "command": "pack",
                "error_type": "TransformError",
                "expect_span_position": None,
            },
            {
                "name": "unpack_missing_header",
                "args": ("unpack", "-", "--json-errors"),
                "stdin_text": 'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}\n',
                "snapshot": "transform_unpack_missing_header.stderr",
                "code": "ERZ_TRANSFORM_ERROR",
                "stage": "transform",
                "command": "unpack",
                "error_type": "TransformError",
                "expect_span_position": None,
            },
            {
                "name": "unpack_unexpected_character",
                "args": ("unpack", "-", "--json-errors"),
                "stdin_text": (
                    'erz{v:0.1}\n'
                    'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}\n'
                    '#\n'
                ),
                "snapshot": "transform_unpack_unexpected_char.stderr",
                "code": "ERZ_TRANSFORM_ERROR",
                "stage": "transform",
                "command": "unpack",
                "error_type": "TransformError",
                "expect_span_position": 114,
            },
            {
                "name": "unpack_unexpected_character_secondary_span",
                "args": ("unpack", "-", "--json-errors"),
                "stdin_text": (
                    'erz{v:0.1}\n'
                    'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}\n'
                    'rf{id:txt_001,v:"hello"}\n'
                    '!\n'
                ),
                "snapshot": "transform_unpack_unexpected_char_secondary.stderr",
                "code": "ERZ_TRANSFORM_ERROR",
                "stage": "transform",
                "command": "unpack",
                "error_type": "TransformError",
                "expect_span_position": 139,
            },
            {
                "name": "parse_io",
                "args": ("parse", "missing-file.erz", "--json-errors"),
                "stdin_text": None,
                "snapshot": "io_missing_file.stderr",
                "code": "ERZ_IO_ERROR",
                "stage": "cli",
                "command": "parse",
                "error_type": "FileNotFoundError",
                "expect_span_position": None,
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                completed = self._run_cli(*case["args"], stdin_text=case["stdin_text"])
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(completed.stdout, "")

                envelope = self._assert_json_error_snapshot(
                    completed=completed,
                    snapshot_name=case["snapshot"],
                    expect_span_position=case["expect_span_position"],
                )
                self.assertEqual(envelope["code"], case["code"])
                self.assertEqual(envelope["stage"], case["stage"])
                self.assertEqual(envelope["details"]["command"], case["command"])
                self.assertEqual(envelope["details"]["error_type"], case["error_type"])

        parse_envelope = json.loads(self._read_error_snapshot("parse_syntax.stderr"))
        validate_envelope = json.loads(self._read_error_snapshot("validate_schema.stderr"))
        transform_pack_envelope = json.loads(
            self._read_error_snapshot("transform_pack_missing_event.stderr")
        )
        transform_unpack_envelope = json.loads(
            self._read_error_snapshot("transform_unpack_missing_header.stderr")
        )
        transform_unpack_position_envelope = json.loads(
            self._read_error_snapshot("transform_unpack_unexpected_char.stderr")
        )
        transform_unpack_secondary_position_envelope = json.loads(
            self._read_error_snapshot("transform_unpack_unexpected_char_secondary.stderr")
        )
        io_envelope = json.loads(self._read_error_snapshot("io_missing_file.stderr"))

        self.assertEqual(list(parse_envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
        self.assertEqual(list(validate_envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
        self.assertEqual(list(transform_pack_envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
        self.assertEqual(list(transform_unpack_envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
        self.assertEqual(
            list(transform_unpack_position_envelope.keys()),
            list(ERROR_ENVELOPE_FIELD_ORDER),
        )
        self.assertEqual(
            list(transform_unpack_secondary_position_envelope.keys()),
            list(ERROR_ENVELOPE_FIELD_ORDER),
        )
        self.assertEqual(list(io_envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))

    def test_json_error_mode_details_key_order_strictness_canary(self) -> None:
        cases = [
            {
                "name": "parse_syntax",
                "args": ("parse", "-", "--json-errors"),
                "stdin_text": 'ev{type:"x"',
                "snapshot": "parse_syntax.stderr",
                "expect_command": "parse",
                "expect_error_type": "CompactParseError",
            },
            {
                "name": "validate_schema",
                "args": ("validate", "-", "--json-errors"),
                "stdin_text": "ev{payload:{}}",
                "snapshot": "validate_schema.stderr",
                "expect_command": "validate",
                "expect_error_type": "CompactValidationError",
            },
            {
                "name": "pack_missing_event",
                "args": ("pack", "-", "--json-errors"),
                "stdin_text": "{}",
                "snapshot": "transform_pack_missing_event.stderr",
                "expect_command": "pack",
                "expect_error_type": "TransformError",
            },
            {
                "name": "unpack_missing_header",
                "args": ("unpack", "-", "--json-errors"),
                "stdin_text": 'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}\n',
                "snapshot": "transform_unpack_missing_header.stderr",
                "expect_command": "unpack",
                "expect_error_type": "TransformError",
            },
            {
                "name": "parse_io",
                "args": ("parse", "missing-file.erz", "--json-errors"),
                "stdin_text": None,
                "snapshot": "io_missing_file.stderr",
                "expect_command": "parse",
                "expect_error_type": "FileNotFoundError",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                completed = self._run_cli(*case["args"], stdin_text=case["stdin_text"])
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(completed.stdout, "")
                self.assertEqual(completed.stderr, self._read_error_snapshot(case["snapshot"]))

                envelope = json.loads(completed.stderr)
                self.assertEqual(list(envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
                self.assertEqual(list(envelope["details"].keys()), ["error_type", "command"])
                self.assertEqual(
                    list(envelope["details"].items()),
                    [
                        ("error_type", case["expect_error_type"]),
                        ("command", case["expect_command"]),
                    ],
                )

    def test_parse_default_error_mode_stays_human_readable(self) -> None:
        completed = self._run_cli("parse", "-", stdin_text='ev{type:"x"')

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertTrue(completed.stderr.startswith("error: "))

        with self.assertRaises(json.JSONDecodeError):
            json.loads(completed.stderr)


class CliEvalCommandTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "cli.main", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_eval_command_example_fixture_success_shape(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace"])
        self.assertEqual(
            envelope["actions"],
            [{"kind": "notify", "params": {"channel": "ops", "severity_ref": "@sev_label"}}],
        )
        self.assertEqual(
            envelope["trace"],
            [
                {
                    "rule_id": "route_ops",
                    "matched_clauses": ["event_type_present", "payload_has:severity"],
                    "score": 1.0,
                }
            ],
        )

    def test_eval_command_example_fixture_determinism(self) -> None:
        args = (
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
        )
        first = self._run_cli(*args)
        second = self._run_cli(*args)

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(first.stdout, second.stdout)

    def test_eval_command_example_fixture_runtime_error_shape(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "error"])
        self.assertEqual(envelope["actions"], [])
        self.assertEqual(envelope["trace"], [])
        self.assertEqual(envelope["error"]["stage"], "runtime")
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")
        self.assertEqual(envelope["error"]["details"]["command"], "eval")

    def test_eval_command_summary_mode_success_shape(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, "status=ok actions=1 trace=1\n")

    def test_eval_command_summary_mode_runtime_error_shape(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=error code=ERZ_RUNTIME_CONTRACT stage=runtime actions=0 trace=0\n",
        )

    def test_eval_command_strict_mode_returns_non_zero_on_runtime_error(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
            "--strict",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "error"])
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")
        self.assertEqual(envelope["error"]["stage"], "runtime")

    def test_eval_command_strict_mode_keeps_zero_exit_on_success(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--strict",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace"])

    def test_eval_command_exit_policy_strict_runtime_error_returns_non_zero(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
            "--exit-policy",
            "strict",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "error"])
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")

    def test_eval_command_exit_policy_strict_no_actions_no_match_returns_non_zero(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-no-action.json"),
            "--exit-policy",
            "strict-no-actions",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace"])
        self.assertEqual(envelope["actions"], [])
        self.assertEqual(envelope["trace"], [])

    def test_eval_command_exit_policy_default_no_match_keeps_zero_exit(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-no-action.json"),
            "--exit-policy",
            "default",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace"])
        self.assertEqual(envelope["actions"], [])
        self.assertEqual(envelope["trace"], [])

    def test_eval_command_exit_policy_conflict_with_legacy_strict_flag_fails(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--strict",
            "--exit-policy",
            "strict-no-actions",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --strict cannot be combined with --exit-policy strict-no-actions\n",
        )

    def test_eval_command_output_file_stdout_parity_for_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "eval-output.json"
            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(output_path.read_text(encoding="utf-8"), result.stdout)

    def test_eval_command_output_file_summary_and_strict_runtime_error_parity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "eval-output.txt"
            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-invalid.json"),
                "--summary",
                "--strict",
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")
            self.assertEqual(
                result.stdout,
                "status=error code=ERZ_RUNTIME_CONTRACT stage=runtime actions=0 trace=0\n",
            )
            self.assertEqual(output_path.read_text(encoding="utf-8"), result.stdout)

    def test_eval_command_refs_sidecar_supports_external_runtime_ref_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            program_path = Path(tmp_dir) / "program-no-rf.erz"
            refs_path = Path(tmp_dir) / "refs.json"

            program_path.write_text(
                "\n".join(
                    [
                        "erz{v:1}",
                        'rule{id:"route_ops",when:["event_type_present","payload_has:severity"],then:[{kind:"notify",params:{channel:"ops",severity_ref:"@sev_label"}}]}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            refs_path.write_text('{"sev_label":"high"}\n', encoding="utf-8")

            result = self._run_cli(
                "eval",
                str(program_path),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--refs",
                str(refs_path),
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")

            envelope = json.loads(result.stdout)
            self.assertEqual(list(envelope.keys()), ["actions", "trace"])
            self.assertEqual(
                envelope["actions"],
                [{"kind": "notify", "params": {"channel": "ops", "severity_ref": "@sev_label"}}],
            )
            self.assertEqual(
                envelope["trace"],
                [
                    {
                        "rule_id": "route_ops",
                        "matched_clauses": ["event_type_present", "payload_has:severity"],
                        "score": 1.0,
                    }
                ],
            )

    def test_eval_command_refs_sidecar_collision_with_program_refs_fails_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            refs_path = Path(tmp_dir) / "refs-collision.json"
            refs_path.write_text('{"@sev_label":"critical"}\n', encoding="utf-8")

            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--refs",
                str(refs_path),
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "error: --refs collision with program refs for id(s): @sev_label\n",
            )

    def test_eval_command_action_plan_matches_checked_in_single_event_fixture(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--action-plan",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            ACTION_PLAN_SINGLE_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

        json_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--action-plan",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(
            json_result.stdout,
            ACTION_PLAN_SINGLE_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_action_plan_matches_checked_in_sidecar_fixture(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-sidecar.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--refs",
            str(EVAL_FIXTURES / "refs-sidecar.json"),
            "--action-plan",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            ACTION_PLAN_SIDECAR_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

        json_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-sidecar.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--refs",
            str(EVAL_FIXTURES / "refs-sidecar.json"),
            "--action-plan",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(
            json_result.stdout,
            ACTION_PLAN_SIDECAR_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_action_plan_matches_checked_in_batch_fixture(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--action-plan",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            ACTION_PLAN_BATCH_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

        json_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--action-plan",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(
            json_result.stdout,
            ACTION_PLAN_BATCH_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_single_event_handoff_bundle_wraps_summary_exit_and_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle_file = Path(tmp_dir) / "event.handoff-bundle.json"
            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--action-plan",
                "--handoff-bundle-file",
                str(bundle_file),
            )
            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        expected_eval = json.loads(ACTION_PLAN_SINGLE_ENVELOPE_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(bundle_payload["kind"], "erz.eval.handoff_bundle.v1")
        self.assertEqual(bundle_payload["surface"], "eval")
        self.assertEqual(
            bundle_payload["source"],
            {"program": "program.erz", "input": "event-ok.json"},
        )
        self.assertEqual(
            bundle_payload["primary"],
            {"key": "eval", "details": expected_eval},
        )
        self.assertEqual(
            bundle_payload["summary_line"],
            ACTION_PLAN_SINGLE_SUMMARY_FIXTURE.read_text(encoding="utf-8").strip(),
        )
        self.assertEqual(bundle_payload["exit"], {"policy": "default", "code": 0})
        self.assertEqual(bundle_payload["eval"], expected_eval)

    def test_eval_command_batch_handoff_bundle_wraps_summary_exit_and_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle_file = Path(tmp_dir) / "batch.handoff-bundle.json"
            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--action-plan",
                "--handoff-bundle-file",
                str(bundle_file),
            )
            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        expected_eval = json.loads(ACTION_PLAN_BATCH_ENVELOPE_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(bundle_payload["kind"], "erz.eval.handoff_bundle.v1")
        self.assertEqual(bundle_payload["surface"], "eval")
        self.assertEqual(
            bundle_payload["source"],
            {"program": "program.erz", "batch": "batch"},
        )
        self.assertEqual(
            bundle_payload["primary"],
            {"key": "eval", "details": expected_eval},
        )
        self.assertEqual(
            bundle_payload["summary_line"],
            ACTION_PLAN_BATCH_SUMMARY_FIXTURE.read_text(encoding="utf-8").strip(),
        )
        self.assertEqual(bundle_payload["exit"], {"policy": "default", "code": 0})
        self.assertEqual(bundle_payload["eval"], expected_eval)

    def test_eval_command_batch_output_verify_handoff_bundle_wraps_summary_exit_and_details(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            bundle_file = Path(tmp_dir) / "verify.handoff-bundle.json"

            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
            )
            json_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )
            bundle_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--handoff-bundle-file",
                str(bundle_file),
            )
            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(bundle_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(bundle_result.stderr, "")
        self.assertEqual(bundle_result.stdout, json_result.stdout)
        self.assertEqual(
            bundle_payload,
            {
                "kind": "erz.eval.batch_output_verify_handoff_bundle.v1",
                "surface": "batch_output_verify",
                "primary": {
                    "key": "verify",
                    "details": json.loads(json_result.stdout),
                },
                "summary_line": summary_result.stdout.rstrip("\n"),
                "exit": {"code": 0},
                "batch_output_root": "batch-output",
                "verify": json.loads(json_result.stdout),
            },
        )

    def test_eval_command_batch_output_compare_handoff_bundle_wraps_summary_exit_and_details(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            bundle_file = Path(tmp_dir) / "compare.handoff-bundle.json"

            baseline_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            candidate_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )
            json_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            bundle_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--handoff-bundle-file",
                str(bundle_file),
            )
            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))

        self.assertEqual(baseline_result.returncode, 0)
        self.assertEqual(candidate_result.returncode, 0)
        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(bundle_result.returncode, 0)
        self.assertEqual(baseline_result.stderr, "")
        self.assertEqual(candidate_result.stderr, "")
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(bundle_result.stderr, "")
        self.assertEqual(bundle_result.stdout, json_result.stdout)
        self.assertEqual(
            bundle_payload,
            {
                "kind": "erz.eval.batch_output_compare_handoff_bundle.v1",
                "surface": "batch_output_compare",
                "primary": {
                    "key": "compare",
                    "details": json.loads(json_result.stdout),
                },
                "summary_line": summary_result.stdout.rstrip("\n"),
                "exit": {"code": 0},
                "candidate_root": "candidate",
                "baseline_root": "baseline",
                "compare": json.loads(json_result.stdout),
            },
        )

    def test_eval_command_batch_output_verify_handoff_bundle_is_written_before_nonzero_exit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            bundle_file = Path(tmp_dir) / "verify.failure.handoff-bundle.json"

            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            tampered_artifact = output_dir / summary_payload["event_artifacts"][0]
            tampered_artifact.write_text('{"tampered":true}\n', encoding="utf-8")

            summary_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
            )
            json_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )
            bundle_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--handoff-bundle-file",
                str(bundle_file),
            )
            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(bundle_result.returncode, 1)
        self.assertEqual(emit_result.stderr, "")
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(bundle_result.stderr, "")
        self.assertEqual(bundle_result.stdout, json_result.stdout)
        self.assertEqual(bundle_payload["kind"], "erz.eval.batch_output_verify_handoff_bundle.v1")
        self.assertEqual(bundle_payload["surface"], "batch_output_verify")
        self.assertEqual(bundle_payload["summary_line"], summary_result.stdout.rstrip("\n"))
        self.assertEqual(bundle_payload["exit"], {"code": 1})
        self.assertEqual(bundle_payload["batch_output_root"], "batch-output")
        self.assertEqual(bundle_payload["verify"], json.loads(json_result.stdout))
        self.assertEqual(
            bundle_payload["primary"],
            {"key": "verify", "details": bundle_payload["verify"]},
        )
        self.assertEqual(bundle_payload["verify"]["status"], "error")
        self.assertEqual(len(bundle_payload["verify"]["mismatched_artifacts"]), 1)

    def test_eval_command_batch_output_compare_handoff_bundle_is_written_before_nonzero_exit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            bundle_file = Path(tmp_dir) / "compare.failure.handoff-bundle.json"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "baseline-001",
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "candidate-002",
            )
            candidate_summary = json.loads(
                (candidate_dir / "summary.json").read_text(encoding="utf-8")
            )
            tampered_artifact = candidate_dir / candidate_summary["event_artifacts"][0]
            tampered_artifact.write_text('{"tampered":true}\n', encoding="utf-8")

            summary_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )
            json_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            bundle_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--handoff-bundle-file",
                str(bundle_file),
            )
            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_candidate.returncode, 0)
        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(bundle_result.returncode, 1)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_candidate.stderr, "")
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(bundle_result.stderr, "")
        self.assertEqual(bundle_result.stdout, json_result.stdout)
        self.assertEqual(bundle_payload["kind"], "erz.eval.batch_output_compare_handoff_bundle.v1")
        self.assertEqual(bundle_payload["surface"], "batch_output_compare")
        self.assertEqual(bundle_payload["summary_line"], summary_result.stdout.rstrip("\n"))
        self.assertEqual(bundle_payload["exit"], {"code": 1})
        self.assertEqual(bundle_payload["candidate_root"], "candidate")
        self.assertEqual(bundle_payload["baseline_root"], "baseline")
        self.assertEqual(bundle_payload["compare"], json.loads(json_result.stdout))
        self.assertEqual(
            bundle_payload["primary"],
            {"key": "compare", "details": bundle_payload["compare"]},
        )
        self.assertEqual(bundle_payload["compare"]["status"], "error")
        self.assertEqual(bundle_payload["compare"]["baseline_run_id"], "baseline-001")
        self.assertEqual(bundle_payload["compare"]["candidate_run_id"], "candidate-002")
        self.assertEqual(len(bundle_payload["compare"]["changed_artifacts"]), 1)

    def test_eval_command_action_plan_error_keeps_raw_actions_and_trace_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            program_path = Path(tmp_dir) / "program-action-plan-collision.erz"
            event_path = Path(tmp_dir) / "event.json"
            program_path.write_text(
                "\n".join(
                    [
                        "erz{v:1}",
                        'rule{id:"route_ops",when:["event_type_present"],then:[{kind:"notify",params:{channel:"ops",channel_ref:"@chan_ops"}}]}',
                        'rf{id:"chan_ops",v:"ops-resolved"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            event_path.write_text('{"type":"ingest","payload":{}}\n', encoding="utf-8")

            summary_result = self._run_cli(
                "eval",
                str(program_path),
                "--input",
                str(event_path),
                "--action-plan",
                "--summary",
            )
            json_result = self._run_cli(
                "eval",
                str(program_path),
                "--input",
                str(event_path),
                "--action-plan",
            )

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=error code=ERZ_RUNTIME_CONTRACT stage=runtime actions=1 trace=1 plan=0 resolved_refs=0\n",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")

        envelope = json.loads(json_result.stdout)
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

    def test_eval_command_action_plan_is_not_supported_with_verify_or_compare_lanes(self) -> None:
        verify_result = self._run_cli(
            "eval",
            "--batch-output-verify",
            str(EVAL_FIXTURES / "batch"),
            "--action-plan",
        )
        self.assertEqual(verify_result.returncode, 1)
        self.assertEqual(verify_result.stdout, "")
        self.assertEqual(
            verify_result.stderr,
            "error: --action-plan is not supported with --batch-output-verify\n",
        )

        compare_result = self._run_cli(
            "eval",
            "--batch-output-compare",
            str(EVAL_FIXTURES / "compare-presets" / "baseline"),
            "--batch-output-compare-against",
            str(EVAL_FIXTURES / "compare-presets" / "baseline"),
            "--action-plan",
        )
        self.assertEqual(compare_result.returncode, 1)
        self.assertEqual(compare_result.stdout, "")
        self.assertEqual(
            compare_result.stderr,
            "error: --action-plan is not supported with --batch-output-compare\n",
        )

    def test_eval_command_meta_mode_adds_deterministic_hash_fields(self) -> None:
        program_payload = (EVAL_FIXTURES / "program.erz").read_text(encoding="utf-8")
        event_payload = (EVAL_FIXTURES / "event-ok.json").read_text(encoding="utf-8")

        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--meta",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "meta"])
        self.assertEqual(
            list(envelope["meta"].keys()),
            ["program_sha256", "event_sha256"],
        )
        self.assertEqual(
            envelope["meta"]["program_sha256"],
            hashlib.sha256(program_payload.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            envelope["meta"]["event_sha256"],
            hashlib.sha256(event_payload.encode("utf-8")).hexdigest(),
        )

    def test_eval_command_meta_mode_generated_at_is_opt_in_and_ordered(self) -> None:
        generated_at = "2026-03-06T18:30:00Z"

        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--meta",
            "--generated-at",
            generated_at,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(
            list(envelope["meta"].keys()),
            ["program_sha256", "event_sha256", "generated_at"],
        )
        self.assertEqual(envelope["meta"]["generated_at"], generated_at)

    def test_eval_command_generated_at_requires_meta_mode(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--generated-at",
            "2026-03-06T18:30:00Z",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: --generated-at requires --meta\n")

    def test_eval_command_meta_mode_runtime_error_shape_remains_stable(self) -> None:
        args = (
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
            "--meta",
        )

        first = self._run_cli(*args)
        second = self._run_cli(*args)

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(first.stdout, second.stdout)

        envelope = json.loads(first.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "error", "meta"])
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")
        self.assertEqual(envelope["error"]["stage"], "runtime")

    def test_eval_command_summary_policy_suffix_for_single_eval(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--summary",
            "--summary-policy",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, "status=ok actions=1 trace=1 policy=default exit=0\n")

    def test_eval_command_summary_policy_requires_summary(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--summary-policy",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: --summary-policy requires --summary\n")

    def test_eval_command_batch_mode_aggregate_envelope_shape(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["events", "summary"])
        self.assertEqual(
            [entry["event"] for entry in envelope["events"]],
            ["01-ok.json", "02-no-action.json", "03-invalid.json"],
        )

        self.assertEqual(list(envelope["events"][0].keys()), ["event", "actions", "trace"])
        self.assertEqual(len(envelope["events"][0]["actions"]), 1)
        self.assertEqual(len(envelope["events"][0]["trace"]), 1)

        self.assertEqual(list(envelope["events"][1].keys()), ["event", "actions", "trace"])
        self.assertEqual(envelope["events"][1]["actions"], [])
        self.assertEqual(envelope["events"][1]["trace"], [])

        self.assertEqual(list(envelope["events"][2].keys()), ["event", "actions", "trace", "error"])
        self.assertEqual(envelope["events"][2]["actions"], [])
        self.assertEqual(envelope["events"][2]["trace"], [])
        self.assertEqual(envelope["events"][2]["error"]["code"], "ERZ_RUNTIME_CONTRACT")

        self.assertEqual(
            envelope["summary"],
            {
                "event_count": 3,
                "total_event_count": 3,
                "error_count": 1,
                "no_action_count": 1,
                "action_count": 1,
                "trace_count": 1,
            },
        )

    def test_eval_command_batch_index_preserves_declared_event_order(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(
            [entry["event"] for entry in envelope["events"]],
            ["02-no-action.json", "01-ok.json", "03-invalid.json"],
        )
        self.assertEqual(
            envelope["summary"],
            {
                "event_count": 3,
                "total_event_count": 3,
                "error_count": 1,
                "no_action_count": 1,
                "action_count": 1,
                "trace_count": 1,
            },
        )

    def test_eval_command_batch_index_filters_apply_after_declared_order(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(
            [entry["event"] for entry in envelope["events"]],
            ["02-no-action.json", "01-ok.json"],
        )
        self.assertEqual(
            envelope["summary"],
            {
                "event_count": 2,
                "total_event_count": 3,
                "error_count": 0,
                "no_action_count": 1,
                "action_count": 1,
                "trace_count": 1,
            },
        )

    def test_eval_command_batch_strict_requires_selector(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--batch-strict",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --batch-strict requires at least one --batch-expected-* selector\n",
        )

    def test_eval_command_batch_expected_event_count_requires_batch_strict(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--batch-expected-event-count",
            "2",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --batch-expected-event-count requires --batch-strict\n",
        )

    def test_eval_command_batch_expected_total_event_count_requires_batch_strict(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--batch-expected-total-event-count",
            "3",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --batch-expected-total-event-count requires --batch-strict\n",
        )

    def test_eval_command_batch_expected_total_event_requires_batch_strict(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--batch-expected-total-event",
            "01-ok.json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --batch-expected-total-event requires --batch-strict\n",
        )

    def test_eval_command_batch_strict_rejects_duplicate_expected_total_event_selector(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--batch-strict",
            "--batch-expected-total-event",
            "01-ok.json",
            "--batch-expected-total-event",
            "01-ok.json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: duplicate --batch-expected-total-event selector: 01-ok.json\n",
        )

    def test_eval_command_batch_strict_rejects_duplicate_expected_selected_event_selector(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--batch-strict",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "02-no-action.json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: duplicate --batch-expected-selected-event selector: 02-no-action.json\n",
        )

    def test_eval_command_batch_expected_action_plan_count_requires_batch_strict(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--action-plan",
            "--batch-expected-action-plan-count",
            "1",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --batch-expected-action-plan-count requires --batch-strict\n",
        )

    def test_eval_command_batch_expected_action_plan_count_requires_action_plan(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--batch-strict",
            "--batch-expected-action-plan-count",
            "1",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --batch-expected-action-plan-count requires --action-plan\n",
        )

    def test_eval_command_batch_expected_resolved_refs_count_requires_action_plan(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--batch-strict",
            "--batch-expected-resolved-refs-count",
            "1",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --batch-expected-resolved-refs-count requires --action-plan\n",
        )

    def test_eval_command_batch_strict_can_gate_action_plan_and_resolved_ref_counts(self) -> None:
        summary_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--action-plan",
            "--summary",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-action-plan-count",
            "1",
            "--batch-expected-resolved-refs-count",
            "1",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )
        json_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--action-plan",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-action-plan-count",
            "1",
            "--batch-expected-resolved-refs-count",
            "1",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=ok replay_status=ok events=2 errors=0 no_actions=1 actions=1 trace=1 plan=1 resolved_refs=1 total_events=3 strict_mismatches=0\n",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["summary"]["action_plan_count"], 1)
        self.assertEqual(envelope["summary"]["resolved_ref_count"], 1)
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_event_count": 2,
                "expected_selected_event_names": ["02-no-action.json", "01-ok.json"],
                "expected_action_plan_count": 1,
                "expected_resolved_refs_count": 1,
            },
        )
        self.assertEqual(envelope["strict_profile_mismatches"], [])

    def test_eval_command_batch_strict_reports_action_plan_and_resolved_ref_count_mismatch(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--action-plan",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-action-plan-count",
            "2",
            "--batch-expected-resolved-refs-count",
            "0",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["summary"]["action_plan_count"], 1)
        self.assertEqual(envelope["summary"]["resolved_ref_count"], 1)
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "action_plan_count",
                    "expected": 2,
                    "actual": 1,
                },
                {
                    "field": "resolved_ref_count",
                    "expected": 0,
                    "actual": 1,
                },
            ],
        )

    def test_eval_command_batch_strict_can_gate_clean_batch_index_subset_exactly(self) -> None:
        summary_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--summary",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )
        json_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=ok replay_status=ok events=2 errors=0 no_actions=1 actions=1 trace=1 total_events=3 strict_mismatches=0\n",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["summary"]["total_event_count"], 3)
        self.assertEqual(envelope["selected_event_names"], ["02-no-action.json", "01-ok.json"])
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_event_count": 2,
                "expected_selected_event_names": ["02-no-action.json", "01-ok.json"],
            },
        )
        self.assertEqual(envelope["strict_profile_mismatches"], [])

    def test_eval_command_batch_strict_reports_selector_mismatches_without_hiding_raw_green_replay(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-selected-event",
            "01-ok.json",
            "--batch-expected-selected-event",
            "02-no-action.json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["selected_event_names"], ["02-no-action.json", "01-ok.json"])
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "selected_event_names",
                    "expected": ["01-ok.json", "02-no-action.json"],
                    "actual": ["02-no-action.json", "01-ok.json"],
                }
            ],
        )

    def test_eval_command_batch_strict_can_gate_prefilter_total_event_count(self) -> None:
        summary_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--summary",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-total-event-count",
            "3",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )
        json_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-total-event-count",
            "3",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=ok replay_status=ok events=2 errors=0 no_actions=1 actions=1 trace=1 total_events=3 strict_mismatches=0\n",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["summary"]["total_event_count"], 3)
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_event_count": 2,
                "expected_total_event_count": 3,
                "expected_selected_event_names": ["02-no-action.json", "01-ok.json"],
            },
        )
        self.assertEqual(envelope["strict_profile_mismatches"], [])

    def test_eval_command_batch_strict_reports_prefilter_total_event_count_mismatch(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-total-event-count",
            "2",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["summary"]["total_event_count"], 3)
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "total_event_count",
                    "expected": 2,
                    "actual": 3,
                }
            ],
        )

    def test_eval_command_batch_strict_can_gate_prefilter_total_event_identity(self) -> None:
        summary_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--summary",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-total-event-count",
            "3",
            "--batch-expected-total-event",
            "02-no-action.json",
            "--batch-expected-total-event",
            "01-ok.json",
            "--batch-expected-total-event",
            "03-invalid.json",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )
        json_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-total-event-count",
            "3",
            "--batch-expected-total-event",
            "02-no-action.json",
            "--batch-expected-total-event",
            "01-ok.json",
            "--batch-expected-total-event",
            "03-invalid.json",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=ok replay_status=ok events=2 errors=0 no_actions=1 actions=1 trace=1 total_events=3 strict_mismatches=0\n",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(
            envelope["total_event_names"],
            ["02-no-action.json", "01-ok.json", "03-invalid.json"],
        )
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_event_count": 2,
                "expected_total_event_count": 3,
                "expected_total_event_names": [
                    "02-no-action.json",
                    "01-ok.json",
                    "03-invalid.json",
                ],
                "expected_selected_event_names": ["02-no-action.json", "01-ok.json"],
            },
        )
        self.assertEqual(envelope["strict_profile_mismatches"], [])

    def test_eval_command_batch_strict_reports_prefilter_total_event_identity_mismatch(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch-index.json"),
            "--exclude",
            "*invalid*.json",
            "--batch-strict",
            "--batch-expected-event-count",
            "2",
            "--batch-expected-total-event-count",
            "3",
            "--batch-expected-total-event",
            "01-ok.json",
            "--batch-expected-total-event",
            "02-no-action.json",
            "--batch-expected-total-event",
            "03-invalid.json",
            "--batch-expected-selected-event",
            "02-no-action.json",
            "--batch-expected-selected-event",
            "01-ok.json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(
            envelope["total_event_names"],
            ["02-no-action.json", "01-ok.json", "03-invalid.json"],
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "total_event_names",
                    "expected": [
                        "01-ok.json",
                        "02-no-action.json",
                        "03-invalid.json",
                    ],
                    "actual": [
                        "02-no-action.json",
                        "01-ok.json",
                        "03-invalid.json",
                    ],
                }
            ],
        )

    def test_eval_command_batch_summary_rule_counts_report_deterministic_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            batch_dir = Path(tmpdir)
            shutil.copyfile(EVAL_FIXTURES / "batch" / "01-ok.json", batch_dir / "01-ok.json")
            shutil.copyfile(EVAL_FIXTURES / "batch" / "01-ok.json", batch_dir / "02-ok.json")
            shutil.copyfile(
                EVAL_FIXTURES / "batch" / "02-no-action.json",
                batch_dir / "03-no-action.json",
            )

            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-summary-rule-counts",
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(
            envelope["summary"],
            {
                "event_count": 3,
                "total_event_count": 3,
                "error_count": 0,
                "no_action_count": 1,
                "action_count": 2,
                "trace_count": 2,
                "rule_counts": {
                    "route_ops": 2,
                },
            },
        )

    def test_eval_command_batch_summary_action_kind_counts_report_deterministic_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            batch_dir = Path(tmpdir)
            shutil.copyfile(EVAL_FIXTURES / "batch" / "01-ok.json", batch_dir / "01-ok.json")
            shutil.copyfile(EVAL_FIXTURES / "batch" / "01-ok.json", batch_dir / "02-ok.json")
            shutil.copyfile(
                EVAL_FIXTURES / "batch" / "02-no-action.json",
                batch_dir / "03-no-action.json",
            )

            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-summary-rule-counts",
                "--batch-summary-action-kind-counts",
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(
            envelope["summary"],
            {
                "event_count": 3,
                "total_event_count": 3,
                "error_count": 0,
                "no_action_count": 1,
                "action_count": 2,
                "trace_count": 2,
                "rule_counts": {
                    "route_ops": 2,
                },
                "action_kind_counts": {
                    "notify": 2,
                },
            },
        )

    def test_eval_command_batch_include_exclude_filters_are_deterministic(self) -> None:
        include_only = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--include",
            "*ok*.json",
        )
        exclude_invalid = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--exclude",
            "*invalid*.json",
        )

        self.assertEqual(include_only.returncode, 0)
        self.assertEqual(include_only.stderr, "")
        include_envelope = json.loads(include_only.stdout)
        self.assertEqual([entry["event"] for entry in include_envelope["events"]], ["01-ok.json"])
        self.assertEqual(
            include_envelope["summary"],
            {
                "event_count": 1,
                "total_event_count": 3,
                "error_count": 0,
                "no_action_count": 0,
                "action_count": 1,
                "trace_count": 1,
            },
        )

        self.assertEqual(exclude_invalid.returncode, 0)
        self.assertEqual(exclude_invalid.stderr, "")
        exclude_envelope = json.loads(exclude_invalid.stdout)
        self.assertEqual(
            [entry["event"] for entry in exclude_envelope["events"]],
            ["01-ok.json", "02-no-action.json"],
        )
        self.assertEqual(
            exclude_envelope["summary"],
            {
                "event_count": 2,
                "total_event_count": 3,
                "error_count": 0,
                "no_action_count": 1,
                "action_count": 1,
                "trace_count": 1,
            },
        )

    def test_eval_command_batch_include_exclude_empty_selection_diagnostic(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--include",
            "*.json",
            "--exclude",
            "*.json",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --batch filters matched no .json files (include='*.json', exclude='*.json')\n",
        )

    def test_eval_command_include_exclude_require_batch(self) -> None:
        include_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--include",
            "*.json",
        )
        exclude_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--exclude",
            "*.json",
        )

        self.assertEqual(include_result.returncode, 1)
        self.assertEqual(include_result.stdout, "")
        self.assertEqual(include_result.stderr, "error: --include requires --batch\n")

        self.assertEqual(exclude_result.returncode, 1)
        self.assertEqual(exclude_result.stdout, "")
        self.assertEqual(exclude_result.stderr, "error: --exclude requires --batch\n")

    def test_eval_command_batch_summary_rule_counts_guardrails(self) -> None:
        require_batch = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--batch-summary-rule-counts",
        )
        reject_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--batch-summary-rule-counts",
            "--summary",
        )

        self.assertEqual(require_batch.returncode, 1)
        self.assertEqual(require_batch.stdout, "")
        self.assertEqual(require_batch.stderr, "error: --batch-summary-rule-counts requires --batch\n")

        self.assertEqual(reject_summary.returncode, 1)
        self.assertEqual(reject_summary.stdout, "")
        self.assertEqual(
            reject_summary.stderr,
            "error: --batch-summary-rule-counts is not supported with --summary\n",
        )

    def test_eval_command_batch_summary_action_kind_counts_guardrails(self) -> None:
        require_batch = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--batch-summary-action-kind-counts",
        )
        reject_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--batch-summary-action-kind-counts",
            "--summary",
        )

        self.assertEqual(require_batch.returncode, 1)
        self.assertEqual(require_batch.stdout, "")
        self.assertEqual(
            require_batch.stderr,
            "error: --batch-summary-action-kind-counts requires --batch\n",
        )

        self.assertEqual(reject_summary.returncode, 1)
        self.assertEqual(reject_summary.stdout, "")
        self.assertEqual(
            reject_summary.stderr,
            "error: --batch-summary-action-kind-counts is not supported with --summary\n",
        )

    def test_eval_command_batch_mode_strict_exit_policy_aggregation(self) -> None:
        base_args = (
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
        )

        default_run = self._run_cli(*base_args, "--exit-policy", "default")
        strict_run = self._run_cli(*base_args, "--exit-policy", "strict")
        strict_no_actions_run = self._run_cli(*base_args, "--exit-policy", "strict-no-actions")

        self.assertEqual(default_run.returncode, 0)
        self.assertEqual(strict_run.returncode, 1)
        self.assertEqual(strict_no_actions_run.returncode, 1)

        self.assertEqual(default_run.stderr, "")
        self.assertEqual(strict_run.stderr, "")
        self.assertEqual(strict_no_actions_run.stderr, "")

        self.assertEqual(default_run.stdout, strict_run.stdout)
        self.assertEqual(default_run.stdout, strict_no_actions_run.stdout)

    def test_eval_command_batch_summary_policy_suffix_reports_aggregated_exit(self) -> None:
        result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--summary",
            "--summary-policy",
            "--exit-policy",
            "strict-no-actions",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=error events=3 errors=1 no_actions=1 actions=1 trace=1 policy=strict-no-actions exit=1\n",
        )

    def test_eval_command_batch_output_writes_deterministic_event_and_summary_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            args = (
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
            )

            first = self._run_cli(*args)
            first_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }
            second = self._run_cli(*args)
            second_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }

            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(first.stderr, "")
            self.assertEqual(second.stderr, "")
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(first_artifacts, second_artifacts)

            envelope = json.loads(first.stdout)
            self.assertEqual(
                sorted(second_artifacts.keys()),
                [
                    "01-ok.envelope.json",
                    "02-no-action.envelope.json",
                    "03-invalid.envelope.json",
                    "summary.json",
                ],
            )

            for event_entry in envelope["events"]:
                event_name = event_entry["event"]
                artifact_name = event_name[:-5] + ".envelope.json"
                self.assertIn(artifact_name, second_artifacts)
                self.assertEqual(json.loads(second_artifacts[artifact_name]), event_entry)

            summary_artifact = json.loads(second_artifacts["summary.json"])
            self.assertEqual(list(summary_artifact.keys()), ["mode", "event_artifacts", "summary"])
            self.assertEqual(summary_artifact["mode"], "all")
            self.assertEqual(
                summary_artifact["event_artifacts"],
                [
                    "01-ok.envelope.json",
                    "02-no-action.envelope.json",
                    "03-invalid.envelope.json",
                ],
            )
            self.assertEqual(summary_artifact["summary"], envelope["summary"])

    def test_eval_command_batch_output_errors_only_writes_failure_and_no_action_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-errors-only",
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")

            envelope = json.loads(result.stdout)
            self.assertEqual(
                [entry["event"] for entry in envelope["events"]],
                ["01-ok.json", "02-no-action.json", "03-invalid.json"],
            )

            artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }
            self.assertEqual(
                sorted(artifacts.keys()),
                [
                    "02-no-action.envelope.json",
                    "03-invalid.envelope.json",
                    "summary.json",
                ],
            )

            summary_artifact = json.loads(artifacts["summary.json"])
            self.assertEqual(summary_artifact["mode"], "errors-only")
            self.assertEqual(
                summary_artifact["event_artifacts"],
                ["02-no-action.envelope.json", "03-invalid.envelope.json"],
            )
            self.assertEqual(summary_artifact["summary"], envelope["summary"])

    def test_eval_command_batch_output_manifest_adds_deterministic_sha256_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            args = (
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            first = self._run_cli(*args)
            first_artifacts = {
                str(path.relative_to(output_dir)): path.read_text(encoding="utf-8")
                for path in sorted(output_dir.rglob("*.json"))
            }
            second = self._run_cli(*args)
            second_artifacts = {
                str(path.relative_to(output_dir)): path.read_text(encoding="utf-8")
                for path in sorted(output_dir.rglob("*.json"))
            }

            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(first.stderr, "")
            self.assertEqual(second.stderr, "")
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(first_artifacts, second_artifacts)

            summary_artifact = json.loads(second_artifacts["summary.json"])
            self.assertEqual(
                list(summary_artifact.keys()),
                ["mode", "event_artifacts", "artifact_sha256", "summary"],
            )
            self.assertEqual(summary_artifact["mode"], "all")

            artifact_hashes = summary_artifact["artifact_sha256"]
            self.assertEqual(
                list(artifact_hashes.keys()),
                summary_artifact["event_artifacts"],
            )

            for artifact_name in summary_artifact["event_artifacts"]:
                self.assertIn(artifact_name, second_artifacts)
                self.assertEqual(
                    artifact_hashes[artifact_name],
                    hashlib.sha256(second_artifacts[artifact_name].encode("utf-8")).hexdigest(),
                )

    def test_eval_command_batch_output_layout_by_status_groups_event_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-layout",
                "by-status",
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")

            artifacts = {
                str(path.relative_to(output_dir)): path.read_text(encoding="utf-8")
                for path in sorted(output_dir.rglob("*.json"))
            }
            self.assertEqual(
                sorted(artifacts.keys()),
                [
                    "error/03-invalid.envelope.json",
                    "no-action/02-no-action.envelope.json",
                    "ok/01-ok.envelope.json",
                    "summary.json",
                ],
            )

            summary_artifact = json.loads(artifacts["summary.json"])
            self.assertEqual(
                list(summary_artifact.keys()),
                ["mode", "layout", "event_artifacts", "summary"],
            )
            self.assertEqual(summary_artifact["mode"], "all")
            self.assertEqual(summary_artifact["layout"], "by-status")
            self.assertEqual(
                summary_artifact["event_artifacts"],
                [
                    "ok/01-ok.envelope.json",
                    "no-action/02-no-action.envelope.json",
                    "error/03-invalid.envelope.json",
                ],
            )

    def test_eval_command_batch_output_run_id_stamps_summary_metadata_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            baseline_args = (
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
            )
            run_id_args = (
                *baseline_args,
                "--batch-output",
                str(output_dir),
                "--batch-output-run-id",
                "ci-run-2026-03-06T20-30-00Z",
            )

            baseline = self._run_cli(*baseline_args)
            first = self._run_cli(*run_id_args)
            first_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }
            second = self._run_cli(*run_id_args)
            second_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(first.stderr, "")
            self.assertEqual(second.stderr, "")
            self.assertEqual(first.stdout, baseline.stdout)
            self.assertEqual(second.stdout, baseline.stdout)
            self.assertEqual(first_artifacts, second_artifacts)

            summary_artifact = json.loads(second_artifacts["summary.json"])
            self.assertEqual(
                list(summary_artifact.keys()),
                ["mode", "run", "event_artifacts", "summary"],
            )
            self.assertEqual(summary_artifact["mode"], "all")
            self.assertEqual(summary_artifact["run"], {"id": "ci-run-2026-03-06T20-30-00Z"})

    def test_eval_command_batch_output_self_verify_writes_manifest_and_preserves_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            verify_summary_file = Path(tmp_dir) / "self-verify.json"
            verify_json_file = Path(tmp_dir) / "self-verify-sidecar.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
            )
            self_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-summary-file",
                str(verify_summary_file),
                "--batch-output-self-verify-json-file",
                str(verify_json_file),
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(self_verify.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(self_verify.stderr, "")
            self.assertEqual(self_verify.stdout, baseline.stdout)

            summary_artifact = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                list(summary_artifact.keys()),
                ["mode", "event_artifacts", "artifact_sha256", "summary"],
            )
            self.assertEqual(summary_artifact["mode"], "all")
            self.assertEqual(len(summary_artifact["event_artifacts"]), 3)
            self.assertEqual(len(summary_artifact["artifact_sha256"]), 3)

            verify_payload = json.loads(verify_summary_file.read_text(encoding="utf-8"))
            self.assertEqual(
                verify_payload,
                json.loads(verify_json_file.read_text(encoding="utf-8")),
            )
            self.assertEqual(verify_payload["status"], "ok")
            self.assertEqual(verify_payload["checked"], 3)
            self.assertEqual(verify_payload["verified"], 3)
            self.assertEqual(verify_payload["selected_artifacts_count"], 3)
            self.assertEqual(verify_payload["selected_manifest_entries_count"], 3)

            verify_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )
            self.assertEqual(verify_result.returncode, 0)
            self.assertEqual(verify_result.stderr, "")
            self.assertEqual(
                verify_summary_file.read_text(encoding="utf-8"),
                verify_result.stdout,
            )
            self.assertEqual(
                verify_json_file.read_text(encoding="utf-8"),
                verify_result.stdout,
            )

    def test_eval_command_batch_output_self_verify_strict_profile_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            verify_summary_file = Path(tmp_dir) / "self-verify.summary.txt"
            verify_json_file = Path(tmp_dir) / "self-verify.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--summary",
            )
            self_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--summary",
                "--batch-output",
                str(output_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "ci-run-2026-03-07T11-15-00Z",
                "--batch-output-self-verify",
                "--batch-output-self-verify-strict",
                "--batch-output-self-verify-summary-file",
                str(verify_summary_file),
                "--batch-output-self-verify-json-file",
                str(verify_json_file),
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$",
                "--batch-output-verify-expected-event-count",
                "3",
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(self_verify.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(self_verify.stderr, "")
            self.assertEqual(self_verify.stdout, baseline.stdout)

            summary_artifact = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                list(summary_artifact.keys()),
                ["mode", "layout", "run", "event_artifacts", "artifact_sha256", "summary"],
            )
            self.assertEqual(summary_artifact["mode"], "errors-only")
            self.assertEqual(summary_artifact["layout"], "by-status")
            self.assertEqual(summary_artifact["run"], {"id": "ci-run-2026-03-07T11-15-00Z"})
            self.assertEqual(len(summary_artifact["event_artifacts"]), 2)
            self.assertEqual(len(summary_artifact["artifact_sha256"]), 2)

            standalone_verify_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$",
                "--batch-output-verify-expected-event-count",
                "3",
            )
            standalone_verify_json = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$",
                "--batch-output-verify-expected-event-count",
                "3",
            )
            self.assertEqual(standalone_verify_summary.returncode, 0)
            self.assertEqual(standalone_verify_summary.stderr, "")
            self.assertEqual(standalone_verify_json.returncode, 0)
            self.assertEqual(standalone_verify_json.stderr, "")
            self.assertEqual(
                verify_summary_file.read_text(encoding="utf-8"),
                standalone_verify_summary.stdout,
            )
            self.assertEqual(
                verify_json_file.read_text(encoding="utf-8"),
                standalone_verify_json.stdout,
            )
            verify_payload = json.loads(verify_json_file.read_text(encoding="utf-8"))
            self.assertEqual(verify_payload["status"], "ok")
            self.assertEqual(verify_payload["strict_profile_mismatches"], [])
            self.assertEqual(verify_payload["strict_profile"]["expected_mode"], "errors-only")
            self.assertEqual(verify_payload["strict_profile"]["expected_layout"], "by-status")

    def test_eval_command_batch_output_self_verify_can_gate_action_plan_and_resolved_ref_counts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            verify_summary_file = Path(tmp_dir) / "self-verify.summary.txt"
            verify_json_file = Path(tmp_dir) / "self-verify.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--action-plan",
                "--summary",
            )
            self_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--action-plan",
                "--summary",
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-strict",
                "--batch-output-self-verify-summary-file",
                str(verify_summary_file),
                "--batch-output-self-verify-json-file",
                str(verify_json_file),
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )
            standalone_verify_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )
            standalone_verify_json = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(self_verify.returncode, 0)
            self.assertEqual(self_verify.stderr, "")
            self.assertEqual(self_verify.stdout, baseline.stdout)
            self.assertEqual(standalone_verify_summary.returncode, 0)
            self.assertEqual(standalone_verify_summary.stderr, "")
            self.assertEqual(standalone_verify_json.returncode, 0)
            self.assertEqual(standalone_verify_json.stderr, "")
            self.assertEqual(
                verify_summary_file.read_text(encoding="utf-8"),
                standalone_verify_summary.stdout,
            )
            self.assertEqual(
                verify_json_file.read_text(encoding="utf-8"),
                standalone_verify_json.stdout,
            )

            verify_payload = json.loads(verify_json_file.read_text(encoding="utf-8"))
            self.assertEqual(verify_payload["status"], "ok")
            self.assertEqual(verify_payload["action_plan_count"], 1)
            self.assertEqual(verify_payload["resolved_ref_count"], 1)
            self.assertEqual(
                verify_summary_file.read_text(encoding="utf-8"),
                "status=ok checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 plan=1 resolved_refs=1 strict_mismatches=0\n",
            )
            self.assertEqual(
                verify_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_event_count": 3,
                    "expected_action_plan_count": 1,
                    "expected_resolved_refs_count": 1,
                },
            )
            self.assertEqual(verify_payload["strict_profile_mismatches"], [])

    def test_eval_command_batch_output_self_verify_strict_profile_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            verify_summary_file = Path(tmp_dir) / "self-verify.summary.txt"
            verify_json_file = Path(tmp_dir) / "self-verify.json"

            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-errors-only",
                "--batch-output-self-verify",
                "--batch-output-self-verify-strict",
                "--batch-output-self-verify-summary-file",
                str(verify_summary_file),
                "--batch-output-self-verify-json-file",
                str(verify_json_file),
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "error: --batch-output-self-verify-strict failed: status=error checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=1\n",
            )
            standalone_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
            )
            self.assertEqual(standalone_verify.returncode, 1)
            self.assertEqual(standalone_verify.stderr, "")
            self.assertEqual(
                verify_summary_file.read_text(encoding="utf-8"),
                standalone_verify.stdout,
            )
            self.assertEqual(
                verify_json_file.read_text(encoding="utf-8"),
                standalone_verify.stdout,
            )
            verify_payload = json.loads(verify_json_file.read_text(encoding="utf-8"))
            self.assertEqual(verify_payload["status"], "error")
            self.assertEqual(
                verify_payload["strict_profile_mismatches"],
                [{"field": "mode", "expected": "all", "actual": "errors-only"}],
            )

    def test_eval_command_batch_output_self_compare_preserves_stdout_and_exports_compare_summary(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            compare_summary_file = Path(tmp_dir) / "self-compare.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "baseline-001",
            )
            self_compare = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-run-id",
                "candidate-002",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(compare_summary_file),
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(self_compare.returncode, 0)
            self.assertEqual(self_compare.stderr, "")
            self.assertEqual(self_compare.stdout, baseline.stdout)

            compare_payload = json.loads(compare_summary_file.read_text(encoding="utf-8"))
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(compare_payload["candidate_run_id"], "candidate-002")
            self.assertEqual(compare_payload["compared"], 3)
            self.assertEqual(compare_payload["matched"], 3)
            self.assertEqual(compare_payload["baseline_only_artifacts"], [])
            self.assertEqual(compare_payload["candidate_only_artifacts"], [])
            self.assertEqual(compare_payload["missing_baseline_artifacts"], [])
            self.assertEqual(compare_payload["missing_candidate_artifacts"], [])
            self.assertEqual(compare_payload["changed_artifacts"], [])
            self.assertEqual(compare_payload["metadata_mismatches"], [])
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 3)

    def test_eval_command_batch_output_self_compare_auto_writes_manifest_when_baseline_has_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            compare_summary_file = Path(tmp_dir) / "self-compare.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-manifest",
            )
            self_compare = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(compare_summary_file),
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(self_compare.returncode, 0)
            self.assertEqual(self_compare.stderr, "")
            self.assertEqual(self_compare.stdout, baseline.stdout)

            compare_payload = json.loads(compare_summary_file.read_text(encoding="utf-8"))
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["metadata_mismatches"], [])

            candidate_summary = json.loads((candidate_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                list(candidate_summary.keys()),
                ["mode", "event_artifacts", "artifact_sha256", "summary"],
            )
            self.assertEqual(len(candidate_summary["artifact_sha256"]), 3)

    def test_eval_command_batch_output_self_compare_strict_allows_expected_asymmetric_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            compare_summary_file = Path(tmp_dir) / "self-compare-strict.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "baseline-001",
            )
            self_compare = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-run-id",
                "candidate-002",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-self-compare-strict",
                "--batch-output-compare-profile",
                "expected-asymmetric-drift",
                "--batch-output-compare-expected-compared-count",
                "2",
                "--batch-output-compare-expected-matched-count",
                "2",
                "--batch-output-compare-expected-baseline-only-count",
                "1",
                "--batch-output-compare-expected-candidate-only-count",
                "0",
                "--batch-output-compare-expected-missing-baseline-count",
                "0",
                "--batch-output-compare-expected-missing-candidate-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "2",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-summary-file",
                str(compare_summary_file),
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(self_compare.returncode, 0)
            self.assertEqual(self_compare.stderr, "")
            self.assertEqual(self_compare.stdout, baseline.stdout)

            compare_payload = json.loads(compare_summary_file.read_text(encoding="utf-8"))
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(compare_payload["candidate_run_id"], "candidate-002")
            self.assertEqual(compare_payload["compare_status"], "error")
            self.assertEqual(compare_payload["compared"], 2)
            self.assertEqual(compare_payload["matched"], 2)
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 2)
            self.assertEqual(compare_payload["strict_profile_mismatches"], [])
            self.assertEqual(compare_payload["strict_profile"]["expected_status"], "error")

    def test_eval_command_batch_output_self_compare_reports_drift_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            compare_summary_file = Path(tmp_dir) / "self-compare-fail.json"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "baseline-001",
            )
            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-run-id",
                "candidate-002",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(compare_summary_file),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "error: --batch-output-self-compare-against failed: status=error compared=2 matched=2 changed=0 baseline_only=1 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=2 selected_baseline=3 selected_candidate=2\n",
            )

            compare_payload = json.loads(compare_summary_file.read_text(encoding="utf-8"))
            self.assertEqual(compare_payload["status"], "error")
            self.assertEqual(compare_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(compare_payload["candidate_run_id"], "candidate-002")
            self.assertEqual(compare_payload["compared"], 2)
            self.assertEqual(compare_payload["matched"], 2)
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 2)
            self.assertEqual(len(compare_payload["baseline_only_artifacts"]), 1)
            self.assertEqual(compare_payload["candidate_only_artifacts"], [])
            self.assertEqual(len(compare_payload["metadata_mismatches"]), 2)

    def test_eval_command_batch_output_self_compare_manifest_baseline_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_auto_dir = Path(tmp_dir) / "candidate-auto"
            candidate_explicit_dir = Path(tmp_dir) / "candidate-explicit"
            auto_compare_file = Path(tmp_dir) / "self-compare-auto.json"
            explicit_compare_file = Path(tmp_dir) / "self-compare-explicit.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "baseline-001",
            )
            auto_manifest = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_auto_dir),
                "--batch-output-run-id",
                "candidate-auto-002",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(auto_compare_file),
            )
            explicit_manifest = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_explicit_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "candidate-explicit-003",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(explicit_compare_file),
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(auto_manifest.returncode, 0)
            self.assertEqual(auto_manifest.stderr, "")
            self.assertEqual(explicit_manifest.returncode, 0)
            self.assertEqual(explicit_manifest.stderr, "")
            self.assertEqual(auto_manifest.stdout, baseline.stdout)
            self.assertEqual(explicit_manifest.stdout, baseline.stdout)

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            auto_summary = json.loads((candidate_auto_dir / "summary.json").read_text(encoding="utf-8"))
            explicit_summary = json.loads(
                (candidate_explicit_dir / "summary.json").read_text(encoding="utf-8")
            )
            auto_compare_payload = json.loads(auto_compare_file.read_text(encoding="utf-8"))
            explicit_compare_payload = json.loads(explicit_compare_file.read_text(encoding="utf-8"))

            self.assertEqual(auto_summary["artifact_sha256"], baseline_summary["artifact_sha256"])
            self.assertEqual(explicit_summary["artifact_sha256"], baseline_summary["artifact_sha256"])
            self.assertEqual(auto_compare_payload["status"], "ok")
            self.assertEqual(explicit_compare_payload["status"], "ok")
            self.assertEqual(auto_compare_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(explicit_compare_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(auto_compare_payload["candidate_run_id"], "candidate-auto-002")
            self.assertEqual(explicit_compare_payload["candidate_run_id"], "candidate-explicit-003")
            self.assertEqual(auto_compare_payload["metadata_mismatches"], [])
            self.assertEqual(explicit_compare_payload["metadata_mismatches"], [])
            auto_compare_without_run = dict(auto_compare_payload)
            explicit_compare_without_run = dict(explicit_compare_payload)
            auto_compare_without_run.pop("candidate_run_id")
            explicit_compare_without_run.pop("candidate_run_id")
            self.assertEqual(auto_compare_without_run, explicit_compare_without_run)
            self.assertEqual(auto_summary["run"]["id"], "candidate-auto-002")
            self.assertEqual(explicit_summary["run"]["id"], "candidate-explicit-003")

    def test_eval_command_batch_output_summary_file_stdout_parity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            summary_file = Path(tmp_dir) / "batch-aggregate.json"

            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-summary-file",
                str(summary_file),
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(summary_file.read_text(encoding="utf-8"), result.stdout)

            payload = json.loads(result.stdout)
            self.assertEqual(list(payload.keys()), ["events", "summary"])
            self.assertEqual(payload["summary"]["event_count"], 3)

    def test_eval_command_batch_output_handoff_bundle_embeds_summary_and_generation_time_verdicts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            bundle_file = Path(tmp_dir) / "handoff-bundle.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "baseline-001",
            )
            baseline_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--summary",
            )
            candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--summary",
                "--batch-output",
                str(candidate_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "candidate-002",
                "--batch-output-self-verify",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
            )
            standalone_verify_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(candidate_dir),
                "--summary",
            )
            standalone_verify_json = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(candidate_dir),
            )
            standalone_compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )
            standalone_compare_json = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(baseline_summary.returncode, 0)
            self.assertEqual(candidate.returncode, 0)
            self.assertEqual(standalone_verify_summary.returncode, 0)
            self.assertEqual(standalone_verify_json.returncode, 0)
            self.assertEqual(standalone_compare_summary.returncode, 0)
            self.assertEqual(standalone_compare_json.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(baseline_summary.stderr, "")
            self.assertEqual(candidate.stderr, "")
            self.assertEqual(standalone_verify_summary.stderr, "")
            self.assertEqual(standalone_verify_json.stderr, "")
            self.assertEqual(standalone_compare_summary.stderr, "")
            self.assertEqual(standalone_compare_json.stderr, "")
            self.assertEqual(candidate.stdout, baseline_summary.stdout)

            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))
            expected_batch_output_summary = json.loads(
                (candidate_dir / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(bundle_payload["kind"], "erz.eval.batch_output_handoff_bundle.v1")
            self.assertEqual(bundle_payload["surface"], "batch_output")
            self.assertEqual(
                bundle_payload["primary"],
                {"key": "batch_output_summary", "details": expected_batch_output_summary},
            )
            self.assertEqual(
                bundle_payload["summary_line"],
                baseline_summary.stdout.rstrip("\n"),
            )
            self.assertEqual(bundle_payload["exit"], {"policy": "default", "code": 0})
            self.assertEqual(bundle_payload["batch_output_root"], "candidate")
            self.assertEqual(bundle_payload["self_compare_against_root"], "baseline")
            self.assertEqual(bundle_payload["batch_output_summary"], expected_batch_output_summary)
            self.assertEqual(
                bundle_payload["self_verify"]["summary_line"],
                standalone_verify_summary.stdout.rstrip("\n"),
            )
            self.assertEqual(
                bundle_payload["self_verify"]["details"],
                json.loads(standalone_verify_json.stdout),
            )
            self.assertEqual(
                bundle_payload["self_compare"]["summary_line"],
                standalone_compare_summary.stdout.rstrip("\n"),
            )
            self.assertEqual(
                bundle_payload["self_compare"]["details"],
                json.loads(standalone_compare_json.stdout),
            )

    def test_eval_command_batch_output_handoff_bundle_uses_stable_cross_root_labels(
        self,
    ) -> None:
        threshold_handoff = EVAL_FIXTURES / "threshold-handoff"

        with tempfile.TemporaryDirectory() as tmp_dir:
            candidate_dir = Path(tmp_dir) / "candidate-triage"
            bundle_file = Path(tmp_dir) / "handoff-bundle.json"

            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program-thresholds.erz"),
                "--batch",
                str(threshold_handoff / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-manifest",
                "--batch-output-run-id",
                "threshold-ci-triage-001",
                "--batch-output-self-compare-against",
                str(threshold_handoff / "baseline"),
                "--batch-output-self-compare-strict",
                "--batch-output-compare-profile",
                "expected-asymmetric-drift",
                "--batch-output-compare-expected-baseline-only-count",
                "3",
                "--batch-output-compare-expected-candidate-only-count",
                "2",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "4",
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")

            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))
            self.assertEqual(bundle_payload["batch_output_root"], "triage-by-status")
            self.assertEqual(bundle_payload["self_compare_against_root"], "baseline")
            self.assertEqual(bundle_payload["self_compare"]["details"]["status"], "ok")

    def test_eval_command_batch_output_handoff_bundle_is_written_before_self_verify_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            candidate_dir = Path(tmp_dir) / "candidate"
            bundle_file = Path(tmp_dir) / "handoff-bundle.json"

            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-self-verify",
                "--batch-output-self-verify-strict",
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "error: --batch-output-self-verify-strict failed: status=error checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=1\n",
            )

            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))
            expected_batch_output_summary = json.loads(
                (candidate_dir / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(bundle_payload["kind"], "erz.eval.batch_output_handoff_bundle.v1")
            self.assertEqual(bundle_payload["surface"], "batch_output")
            self.assertEqual(
                bundle_payload["primary"],
                {"key": "batch_output_summary", "details": expected_batch_output_summary},
            )
            self.assertEqual(
                bundle_payload["summary_line"],
                "status=error events=3 errors=1 no_actions=1 actions=1 trace=1",
            )
            self.assertEqual(bundle_payload["exit"], {"policy": "default", "code": 1})
            self.assertEqual(bundle_payload["batch_output_root"], "candidate")
            self.assertEqual(bundle_payload["self_verify"]["details"]["status"], "error")
            self.assertEqual(
                bundle_payload["self_verify"]["details"]["strict_profile_mismatches"],
                [{"field": "mode", "expected": "all", "actual": "errors-only"}],
            )
            self.assertEqual(
                bundle_payload["self_verify"]["summary_line"],
                result.stderr.removeprefix("error: --batch-output-self-verify-strict failed: ").rstrip("\n"),
            )
            self.assertIsNone(bundle_payload["self_compare"])
            self.assertEqual(bundle_payload["batch_output_summary"], expected_batch_output_summary)

    def test_eval_command_batch_output_handoff_bundle_is_written_before_self_compare_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            bundle_file = Path(tmp_dir) / "handoff-bundle.json"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "baseline-001",
            )
            result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-run-id",
                "candidate-002",
                "--batch-output-self-verify",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "error: --batch-output-self-compare-against failed: status=error compared=2 matched=2 changed=0 baseline_only=1 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=3 selected_baseline=3 selected_candidate=2\n",
            )

            bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))
            expected_batch_output_summary = json.loads(
                (candidate_dir / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(bundle_payload["kind"], "erz.eval.batch_output_handoff_bundle.v1")
            self.assertEqual(bundle_payload["surface"], "batch_output")
            self.assertEqual(
                bundle_payload["primary"],
                {"key": "batch_output_summary", "details": expected_batch_output_summary},
            )
            self.assertEqual(
                bundle_payload["summary_line"],
                "status=error events=3 errors=1 no_actions=1 actions=1 trace=1",
            )
            self.assertEqual(bundle_payload["exit"], {"policy": "default", "code": 1})
            self.assertEqual(bundle_payload["batch_output_root"], "candidate")
            self.assertEqual(bundle_payload["self_compare_against_root"], "baseline")
            self.assertEqual(bundle_payload["self_verify"]["details"]["status"], "ok")
            self.assertEqual(bundle_payload["self_compare"]["details"]["status"], "error")
            self.assertEqual(bundle_payload["self_compare"]["summary_line"], result.stderr.removeprefix("error: --batch-output-self-compare-against failed: ").rstrip("\n"))
            self.assertEqual(bundle_payload["batch_output_summary"], expected_batch_output_summary)

    def test_eval_command_batch_output_verify_reports_deterministic_pass_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            first_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )
            second_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )
            summary_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(first_verify.returncode, 0)
            self.assertEqual(second_verify.returncode, 0)
            self.assertEqual(summary_verify.returncode, 0)

            self.assertEqual(emit_result.stderr, "")
            self.assertEqual(first_verify.stderr, "")
            self.assertEqual(second_verify.stderr, "")
            self.assertEqual(summary_verify.stderr, "")

            self.assertEqual(first_verify.stdout, second_verify.stdout)
            self.assertEqual(
                summary_verify.stdout,
                "status=ok checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3\n",
            )

            verify_payload = json.loads(first_verify.stdout)
            self.assertEqual(
                list(verify_payload.keys()),
                [
                    "status",
                    "checked",
                    "verified",
                    "missing_artifacts",
                    "missing_manifest_entries",
                    "invalid_manifest_hashes",
                    "mismatched_artifacts",
                    "unexpected_manifest_entries",
                    "selected_artifacts_count",
                    "selected_manifest_entries_count",
                ],
            )
            self.assertEqual(verify_payload["status"], "ok")
            self.assertEqual(verify_payload["checked"], 3)
            self.assertEqual(verify_payload["verified"], 3)
            self.assertEqual(verify_payload["missing_artifacts"], [])
            self.assertEqual(verify_payload["missing_manifest_entries"], [])
            self.assertEqual(verify_payload["invalid_manifest_hashes"], [])
            self.assertEqual(verify_payload["mismatched_artifacts"], [])
            self.assertEqual(verify_payload["unexpected_manifest_entries"], [])
            self.assertEqual(verify_payload["selected_artifacts_count"], 3)
            self.assertEqual(verify_payload["selected_manifest_entries_count"], 3)

    def test_eval_command_batch_output_verify_fails_on_tampered_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            tampered_artifact = output_dir / "01-ok.envelope.json"
            tampered_artifact.write_text('{"tampered":true}\n', encoding="utf-8")

            verify_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )

            self.assertEqual(verify_result.returncode, 1)
            self.assertEqual(verify_result.stderr, "")

            verify_payload = json.loads(verify_result.stdout)
            self.assertEqual(verify_payload["status"], "error")
            self.assertEqual(verify_payload["checked"], 3)
            self.assertEqual(verify_payload["verified"], 2)
            self.assertEqual(verify_payload["missing_artifacts"], [])
            self.assertEqual(verify_payload["missing_manifest_entries"], [])
            self.assertEqual(verify_payload["invalid_manifest_hashes"], [])
            self.assertEqual(verify_payload["unexpected_manifest_entries"], [])
            self.assertEqual(len(verify_payload["mismatched_artifacts"]), 1)

            mismatch = verify_payload["mismatched_artifacts"][0]
            self.assertEqual(
                mismatch,
                {
                    "artifact": "01-ok.envelope.json",
                    "expected": mismatch["expected"],
                    "actual": hashlib.sha256('{"tampered":true}\n'.encode("utf-8")).hexdigest(),
                },
            )
            self.assertNotEqual(mismatch["expected"], mismatch["actual"])

    def test_eval_command_batch_output_verify_strict_profile_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "ci-run-2026-03-07T09-30-00Z",
            )
            verify_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-layout",
                "by-status",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$",
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-layout",
                "by-status",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")
            self.assertEqual(verify_result.returncode, 0)
            self.assertEqual(verify_result.stderr, "")
            self.assertEqual(summary_result.returncode, 0)
            self.assertEqual(summary_result.stderr, "")
            self.assertEqual(
                summary_result.stdout,
                "status=ok checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=0\n",
            )

            verify_payload = json.loads(verify_result.stdout)
            self.assertEqual(verify_payload["status"], "ok")
            self.assertEqual(
                verify_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_layout": "by-status",
                    "expected_run_id_pattern": "^ci-run-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$",
                },
            )
            self.assertEqual(verify_payload["strict_profile_mismatches"], [])

    def test_eval_command_batch_output_verify_strict_profile_detects_metadata_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "nightly-2026-03-07",
            )
            verify_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mode",
                "all",
                "--batch-output-verify-expected-layout",
                "flat",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-.*$",
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mode",
                "all",
                "--batch-output-verify-expected-layout",
                "flat",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-.*$",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")
            self.assertEqual(verify_result.returncode, 1)
            self.assertEqual(verify_result.stderr, "")
            self.assertEqual(summary_result.returncode, 1)
            self.assertEqual(summary_result.stderr, "")
            self.assertEqual(
                summary_result.stdout,
                "status=error checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=3\n",
            )

            verify_payload = json.loads(verify_result.stdout)
            self.assertEqual(verify_payload["status"], "error")
            self.assertEqual(
                verify_payload["strict_profile_mismatches"],
                [
                    {"field": "mode", "expected": "all", "actual": "errors-only"},
                    {"field": "layout", "expected": "flat", "actual": "by-status"},
                    {"field": "run.id", "expected": "^ci-run-.*$", "actual": "nightly-2026-03-07"},
                ],
            )

    def test_eval_command_batch_output_verify_can_gate_action_plan_and_resolved_ref_counts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--action-plan",
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            verify_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")
            self.assertEqual(verify_result.returncode, 0)
            self.assertEqual(verify_result.stderr, "")
            self.assertEqual(summary_result.returncode, 0)
            self.assertEqual(summary_result.stderr, "")
            self.assertEqual(
                summary_result.stdout,
                "status=ok checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 plan=1 resolved_refs=1 strict_mismatches=0\n",
            )

            verify_payload = json.loads(verify_result.stdout)
            self.assertEqual(verify_payload["status"], "ok")
            self.assertEqual(verify_payload["action_plan_count"], 1)
            self.assertEqual(verify_payload["resolved_ref_count"], 1)
            self.assertEqual(
                verify_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_event_count": 3,
                    "expected_action_plan_count": 1,
                    "expected_resolved_refs_count": 1,
                },
            )
            self.assertEqual(verify_payload["strict_profile_mismatches"], [])

    def test_eval_command_batch_output_verify_action_plan_counts_follow_summary_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--action-plan",
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            verify_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-include",
                "*no-action*",
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-selected-artifact-count",
                "1",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-include",
                "*no-action*",
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-selected-artifact-count",
                "1",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")
            self.assertEqual(verify_result.returncode, 0)
            self.assertEqual(verify_result.stderr, "")
            self.assertEqual(summary_result.returncode, 0)
            self.assertEqual(summary_result.stderr, "")
            self.assertEqual(
                summary_result.stdout,
                "status=ok checked=1 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=1 selected_manifest=1 plan=1 resolved_refs=1 strict_mismatches=0\n",
            )

            verify_payload = json.loads(verify_result.stdout)
            self.assertEqual(verify_payload["status"], "ok")
            self.assertEqual(verify_payload["action_plan_count"], 1)
            self.assertEqual(verify_payload["resolved_ref_count"], 1)
            self.assertEqual(
                verify_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_action_plan_count": 1,
                    "expected_resolved_refs_count": 1,
                    "expected_selected_artifact_count": 1,
                },
            )
            self.assertEqual(verify_payload["strict_profile_mismatches"], [])

    def test_eval_command_batch_output_verify_reports_missing_action_plan_contract_surface(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            verify_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")
            self.assertEqual(verify_result.returncode, 1)
            self.assertEqual(verify_result.stderr, "")
            self.assertEqual(summary_result.returncode, 1)
            self.assertEqual(summary_result.stderr, "")
            self.assertEqual(
                summary_result.stdout,
                "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=2\n",
            )

            verify_payload = json.loads(verify_result.stdout)
            self.assertEqual(verify_payload["status"], "error")
            self.assertEqual(
                verify_payload["strict_profile_mismatches"],
                [
                    {
                        "field": "summary.action_plan_count",
                        "expected": 1,
                        "actual": "<missing>",
                    },
                    {
                        "field": "summary.resolved_ref_count",
                        "expected": 1,
                        "actual": "<missing>",
                    },
                ],
            )
            self.assertNotIn("action_plan_count", verify_payload)
            self.assertNotIn("resolved_ref_count", verify_payload)

    def test_eval_command_batch_output_verify_profile_presets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
            )
            triage_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-profile",
                "triage-by-status",
            )
            triage_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-profile",
                "triage-by-status",
                "--summary",
            )
            default_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-profile",
                "default",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(triage_verify.returncode, 0)
            self.assertEqual(triage_verify.stderr, "")
            self.assertEqual(triage_summary.returncode, 0)
            self.assertEqual(triage_summary.stderr, "")
            self.assertEqual(
                triage_summary.stdout,
                "status=ok checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=0\n",
            )

            triage_payload = json.loads(triage_verify.stdout)
            self.assertEqual(triage_payload["status"], "ok")
            self.assertEqual(
                triage_payload["strict_profile"],
                {
                    "expected_mode": "errors-only",
                    "expected_layout": "by-status",
                },
            )
            self.assertEqual(triage_payload["strict_profile_mismatches"], [])

            self.assertEqual(default_verify.returncode, 1)
            self.assertEqual(default_verify.stderr, "")
            default_payload = json.loads(default_verify.stdout)
            self.assertEqual(default_payload["status"], "error")
            self.assertEqual(
                default_payload["strict_profile_mismatches"],
                [
                    {"field": "mode", "expected": "all", "actual": "errors-only"},
                    {"field": "layout", "expected": "flat", "actual": "by-status"},
                ],
            )

    def test_eval_command_batch_output_verify_require_run_id_toggle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            strict_verify_without_toggle = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
            )
            strict_verify_with_toggle = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-require-run-id",
            )
            strict_verify_with_toggle_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-require-run-id",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_verify_without_toggle.returncode, 0)
            self.assertEqual(strict_verify_without_toggle.stderr, "")

            self.assertEqual(strict_verify_with_toggle.returncode, 1)
            self.assertEqual(strict_verify_with_toggle.stderr, "")
            self.assertEqual(strict_verify_with_toggle_summary.returncode, 1)
            self.assertEqual(strict_verify_with_toggle_summary.stderr, "")
            self.assertEqual(
                strict_verify_with_toggle_summary.stdout,
                "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            baseline_payload = json.loads(strict_verify_without_toggle.stdout)
            self.assertEqual(baseline_payload["status"], "ok")
            self.assertEqual(baseline_payload["strict_profile_mismatches"], [])

            strict_payload = json.loads(strict_verify_with_toggle.stdout)
            self.assertEqual(strict_payload["status"], "error")
            self.assertEqual(
                strict_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "require_run_id": True,
                },
            )
            self.assertEqual(
                strict_payload["strict_profile_mismatches"],
                [{"field": "run.id", "expected": "present", "actual": "<missing>"}],
            )

    def test_eval_command_batch_output_verify_expected_event_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            strict_pass = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "3",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "2",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "2",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_pass.returncode, 0)
            self.assertEqual(strict_pass.stderr, "")
            pass_payload = json.loads(strict_pass.stdout)
            self.assertEqual(pass_payload["status"], "ok")
            self.assertEqual(
                pass_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_event_count": 3,
                },
            )
            self.assertEqual(pass_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "summary.event_count", "expected": 2, "actual": 3}],
            )

    def test_eval_command_batch_output_verify_expected_verified_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            invalid_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "invalid" in artifact
            )
            (output_dir / invalid_artifact).write_text('{"tampered":true}\n', encoding="utf-8")

            strict_pass = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "*ok*",
                "--batch-output-verify-expected-verified-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-verified-count",
                "3",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-verified-count",
                "3",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_pass.returncode, 0)
            self.assertEqual(strict_pass.stderr, "")
            pass_payload = json.loads(strict_pass.stdout)
            self.assertEqual(pass_payload["status"], "ok")
            self.assertEqual(
                pass_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_verified_count": 1,
                },
            )
            self.assertEqual(pass_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "verified", "expected": 3, "actual": 2}],
            )

    def test_eval_command_batch_output_verify_expected_checked_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            invalid_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "invalid" in artifact
            )
            (output_dir / invalid_artifact).write_text('{"tampered":true}\n', encoding="utf-8")

            strict_pass = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "*ok*",
                "--batch-output-verify-expected-checked-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "*ok*",
                "--batch-output-verify-expected-checked-count",
                "2",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "*ok*",
                "--batch-output-verify-expected-checked-count",
                "2",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_pass.returncode, 0)
            self.assertEqual(strict_pass.stderr, "")
            pass_payload = json.loads(strict_pass.stdout)
            self.assertEqual(pass_payload["status"], "ok")
            self.assertEqual(
                pass_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_checked_count": 1,
                },
            )
            self.assertEqual(pass_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=1 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=1 selected_manifest=1 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "checked", "expected": 2, "actual": 1}],
            )

    def test_eval_command_batch_output_verify_expected_missing_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            missing_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "invalid" in artifact
            )
            (output_dir / missing_artifact).unlink()

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-missing-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-missing-count",
                "0",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-missing-count",
                "0",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 1)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "error")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_missing_count": 1,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=2 missing=1 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "missing_artifacts.count", "expected": 0, "actual": 1}],
            )

    def test_eval_command_batch_output_verify_expected_mismatched_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            mismatched_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "ok" in artifact
            )
            artifact_path = output_dir / mismatched_artifact
            artifact_path.write_text(
                artifact_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mismatched-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mismatched-count",
                "0",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mismatched-count",
                "0",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 1)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "error")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_mismatched_count": 1,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "mismatched_artifacts.count", "expected": 0, "actual": 1}],
            )

    def test_eval_command_batch_output_verify_expected_manifest_missing_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_path = output_dir / "summary.json"
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            manifest_payload = summary_payload["artifact_sha256"]
            missing_manifest_artifact = summary_payload["event_artifacts"][0]
            del manifest_payload[missing_manifest_artifact]
            summary_path.write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-missing-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-missing-count",
                "0",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-missing-count",
                "0",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 1)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "error")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_manifest_missing_count": 1,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=2 missing=0 manifest_missing=1 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=2 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "missing_manifest_entries.count", "expected": 0, "actual": 1}],
            )

    def test_eval_command_batch_output_verify_expected_invalid_hashes_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_path = output_dir / "summary.json"
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            invalid_hash_artifact = summary_payload["event_artifacts"][0]
            summary_payload["artifact_sha256"][invalid_hash_artifact] = "not-a-sha256"
            summary_path.write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-invalid-hashes-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-invalid-hashes-count",
                "0",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-invalid-hashes-count",
                "0",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 1)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "error")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_invalid_hashes_count": 1,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=1 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "invalid_manifest_hashes.count", "expected": 0, "actual": 1}],
            )

    def test_eval_command_batch_output_verify_expected_unexpected_manifest_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_path = output_dir / "summary.json"
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            summary_payload["artifact_sha256"]["unexpected/ghost.envelope.json"] = (
                "0" * 64
            )
            summary_path.write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-unexpected-manifest-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-unexpected-manifest-count",
                "0",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-unexpected-manifest-count",
                "0",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 1)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "error")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_unexpected_manifest_count": 1,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=1 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "unexpected_manifest_entries.count", "expected": 0, "actual": 1}],
            )

    def test_eval_command_batch_output_verify_expected_status_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-status",
                "ok",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-status",
                "error",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-status",
                "error",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 0)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "ok")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_status": "ok",
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "status", "expected": "error", "actual": "ok"}],
            )

    def test_eval_command_batch_output_verify_expected_strict_mismatches_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            tampered_artifact_relpath = summary_payload["event_artifacts"][0]
            (output_dir / tampered_artifact_relpath).write_text('{"tampered":true}\n', encoding="utf-8")

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mismatched-count",
                "0",
                "--batch-output-verify-expected-strict-mismatches-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mismatched-count",
                "0",
                "--batch-output-verify-expected-strict-mismatches-count",
                "0",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mismatched-count",
                "0",
                "--batch-output-verify-expected-strict-mismatches-count",
                "0",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 1)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "error")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_mismatched_count": 0,
                    "expected_strict_mismatches_count": 1,
                },
            )
            self.assertEqual(
                match_payload["strict_profile_mismatches"],
                [{"field": "mismatched_artifacts.count", "expected": 0, "actual": 1}],
            )

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=2\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [
                    {"field": "mismatched_artifacts.count", "expected": 0, "actual": 1},
                    {
                        "field": "strict_profile_mismatches.count",
                        "expected": 0,
                        "actual": 1,
                    },
                ],
            )

    def test_eval_command_batch_output_verify_expected_event_artifact_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-artifact-count",
                "3",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-artifact-count",
                "2",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-artifact-count",
                "2",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 0)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "ok")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_event_artifact_count": 3,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "event_artifacts.count", "expected": 2, "actual": 3}],
            )

    def test_eval_command_batch_output_verify_expected_manifest_entry_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-entry-count",
                "3",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-entry-count",
                "2",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-entry-count",
                "2",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 0)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "ok")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_manifest_entry_count": 3,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "artifact_sha256.count", "expected": 2, "actual": 3}],
            )

    def test_eval_command_batch_output_verify_expected_selected_artifact_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "01-*",
                "--batch-output-verify-expected-selected-artifact-count",
                "1",
            )
            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "01-*",
                "--batch-output-verify-expected-selected-artifact-count",
                "2",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "01-*",
                "--batch-output-verify-expected-selected-artifact-count",
                "2",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 0)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "ok")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_selected_artifact_count": 1,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=1 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=1 selected_manifest=1 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "selected_artifacts.count", "expected": 2, "actual": 1}],
            )

    def test_eval_command_batch_output_verify_expected_selected_artifact_requires_strict_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-selected-artifact",
                "01-ok.envelope.json",
            )
            without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-selected-artifact",
                "01-ok.envelope.json",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(without_verify.returncode, 1)
            self.assertEqual(without_verify.stdout, "")
            self.assertEqual(
                without_verify.stderr,
                "error: --batch-output-verify-expected-selected-artifact requires strict verify\n",
            )

            self.assertEqual(without_strict.returncode, 1)
            self.assertEqual(without_strict.stdout, "")
            self.assertEqual(
                without_strict.stderr,
                "error: --batch-output-verify-expected-selected-artifact requires strict verify\n",
            )

    def test_eval_command_batch_output_verify_rejects_duplicate_expected_selected_artifact_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-selected-artifact",
                "01-ok.envelope.json",
                "--batch-output-verify-expected-selected-artifact",
                "01-ok.envelope.json",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "error: duplicate --batch-output-verify-expected-selected-artifact selector: 01-ok.envelope.json\n",
            )

    def test_eval_command_batch_output_verify_strict_can_gate_exact_selected_artifact_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "*no-action*",
                "--batch-output-verify-expected-selected-artifact",
                "02-no-action.envelope.json",
            )
            strict_match_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "*no-action*",
                "--batch-output-verify-expected-selected-artifact",
                "02-no-action.envelope.json",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 0)
            self.assertEqual(strict_match.stderr, "")
            self.assertEqual(strict_match_summary.returncode, 0)
            self.assertEqual(strict_match_summary.stderr, "")
            self.assertEqual(
                strict_match_summary.stdout,
                "status=ok checked=1 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=1 selected_manifest=1 strict_mismatches=0\n",
            )
            self.assertEqual(
                json.loads(strict_match.stdout),
                {
                    "status": "ok",
                    "checked": 1,
                    "verified": 1,
                    "missing_artifacts": [],
                    "missing_manifest_entries": [],
                    "invalid_manifest_hashes": [],
                    "mismatched_artifacts": [],
                    "unexpected_manifest_entries": [],
                    "selected_artifacts_count": 1,
                    "selected_manifest_entries_count": 1,
                    "selected_artifacts": ["02-no-action.envelope.json"],
                    "strict_profile": {
                        "expected_mode": "all",
                        "expected_selected_artifacts": [
                            "02-no-action.envelope.json"
                        ],
                    },
                    "strict_profile_mismatches": [],
                },
            )

    def test_eval_command_batch_output_verify_strict_reports_selected_artifact_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            summary_path = output_dir / "summary.json"
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            summary_payload["event_artifacts"] = list(reversed(summary_payload["event_artifacts"]))
            summary_path.write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            result = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-selected-artifact",
                "01-ok.envelope.json",
                "--batch-output-verify-expected-selected-artifact",
                "02-no-action.envelope.json",
                "--batch-output-verify-expected-selected-artifact",
                "03-invalid.envelope.json",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "status": "error",
                    "checked": 3,
                    "verified": 3,
                    "missing_artifacts": [],
                    "missing_manifest_entries": [],
                    "invalid_manifest_hashes": [],
                    "mismatched_artifacts": [],
                    "unexpected_manifest_entries": [],
                    "selected_artifacts_count": 3,
                    "selected_manifest_entries_count": 3,
                    "selected_artifacts": [
                        "03-invalid.envelope.json",
                        "02-no-action.envelope.json",
                        "01-ok.envelope.json",
                    ],
                    "strict_profile": {
                        "expected_mode": "all",
                        "expected_selected_artifacts": [
                            "01-ok.envelope.json",
                            "02-no-action.envelope.json",
                            "03-invalid.envelope.json",
                        ],
                    },
                    "strict_profile_mismatches": [
                        {
                            "field": "selected_artifacts",
                            "expected": [
                                "01-ok.envelope.json",
                                "02-no-action.envelope.json",
                                "03-invalid.envelope.json",
                            ],
                            "actual": [
                                "03-invalid.envelope.json",
                                "02-no-action.envelope.json",
                                "01-ok.envelope.json",
                            ],
                        }
                    ],
                },
            )

    def test_eval_command_batch_output_verify_expected_manifest_selected_entry_count_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )

            strict_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "0*-*.envelope.json",
                "--batch-output-verify-expected-manifest-selected-entry-count",
                "3",
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            manifest_payload = summary_payload["artifact_sha256"]
            manifest_payload.pop("02-no-action.envelope.json")
            (output_dir / "summary.json").write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            strict_fail = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "0*-*.envelope.json",
                "--batch-output-verify-expected-manifest-selected-entry-count",
                "3",
            )
            strict_fail_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-include",
                "0*-*.envelope.json",
                "--batch-output-verify-expected-manifest-selected-entry-count",
                "3",
                "--summary",
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(strict_match.returncode, 0)
            self.assertEqual(strict_match.stderr, "")
            match_payload = json.loads(strict_match.stdout)
            self.assertEqual(match_payload["status"], "ok")
            self.assertEqual(
                match_payload["strict_profile"],
                {
                    "expected_mode": "all",
                    "expected_manifest_selected_entry_count": 3,
                },
            )
            self.assertEqual(match_payload["strict_profile_mismatches"], [])

            self.assertEqual(strict_fail.returncode, 1)
            self.assertEqual(strict_fail.stderr, "")
            self.assertEqual(strict_fail_summary.returncode, 1)
            self.assertEqual(strict_fail_summary.stderr, "")
            self.assertEqual(
                strict_fail_summary.stdout,
                "status=error checked=3 verified=2 missing=0 manifest_missing=1 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=2 strict_mismatches=1\n",
            )

            fail_payload = json.loads(strict_fail.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(
                fail_payload["strict_profile_mismatches"],
                [{"field": "selected_manifest_entries.count", "expected": 3, "actual": 2}],
            )

    def test_eval_command_batch_output_verify_summary_file_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            verify_json_file = Path(tmp_dir) / "verify-pass.json"
            verify_summary_file = Path(tmp_dir) / "verify-pass-summary.txt"
            verify_json_sidecar_file = Path(tmp_dir) / "verify-sidecar.json"
            verify_fail_file = Path(tmp_dir) / "verify-fail.json"
            verify_fail_json_sidecar_file = Path(tmp_dir) / "verify-fail-sidecar.json"

            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            verify_baseline = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )
            verify_with_json_file = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-summary-file",
                str(verify_json_file),
            )
            verify_with_summary_file = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
                "--batch-output-verify-summary-file",
                str(verify_summary_file),
            )
            verify_with_summary_and_json_sidecar = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
                "--batch-output-verify-json-file",
                str(verify_json_sidecar_file),
            )

            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            self.assertEqual(verify_baseline.returncode, 0)
            self.assertEqual(verify_baseline.stderr, "")

            self.assertEqual(verify_with_json_file.returncode, 0)
            self.assertEqual(verify_with_json_file.stderr, "")
            self.assertEqual(verify_with_json_file.stdout, verify_baseline.stdout)
            self.assertEqual(verify_json_file.read_text(encoding="utf-8"), verify_with_json_file.stdout)

            self.assertEqual(verify_with_summary_file.returncode, 0)
            self.assertEqual(verify_with_summary_file.stderr, "")
            self.assertEqual(
                verify_with_summary_file.stdout,
                "status=ok checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3\n",
            )
            self.assertEqual(
                verify_summary_file.read_text(encoding="utf-8"),
                verify_with_summary_file.stdout,
            )

            self.assertEqual(verify_with_summary_and_json_sidecar.returncode, 0)
            self.assertEqual(verify_with_summary_and_json_sidecar.stderr, "")
            self.assertEqual(
                verify_with_summary_and_json_sidecar.stdout,
                verify_with_summary_file.stdout,
            )
            self.assertEqual(
                verify_json_sidecar_file.read_text(encoding="utf-8"),
                verify_baseline.stdout,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            artifact_relpath = summary_payload["event_artifacts"][0]
            tampered_artifact = output_dir / artifact_relpath
            tampered_artifact.write_text('{"tampered":true}\\n', encoding="utf-8")

            verify_fail_with_json_file = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-summary-file",
                str(verify_fail_file),
            )
            verify_fail_with_summary_and_json_sidecar = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
                "--batch-output-verify-json-file",
                str(verify_fail_json_sidecar_file),
            )

            self.assertEqual(verify_fail_with_json_file.returncode, 1)
            self.assertEqual(verify_fail_with_json_file.stderr, "")
            fail_payload = json.loads(verify_fail_with_json_file.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertGreaterEqual(len(fail_payload["mismatched_artifacts"]), 1)
            self.assertEqual(
                verify_fail_file.read_text(encoding="utf-8"),
                verify_fail_with_json_file.stdout,
            )

            self.assertEqual(verify_fail_with_summary_and_json_sidecar.returncode, 1)
            self.assertEqual(verify_fail_with_summary_and_json_sidecar.stderr, "")
            self.assertTrue(verify_fail_with_summary_and_json_sidecar.stdout.startswith("status=error "))
            fail_sidecar_payload = json.loads(
                verify_fail_json_sidecar_file.read_text(encoding="utf-8")
            )
            self.assertEqual(fail_sidecar_payload["status"], "error")
            self.assertGreaterEqual(len(fail_sidecar_payload["mismatched_artifacts"]), 1)

    def test_eval_command_batch_output_verify_subset_selectors_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"

            emit_result = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            )
            self.assertEqual(emit_result.returncode, 0)
            self.assertEqual(emit_result.stderr, "")

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            invalid_artifact = next(
                artifact
                for artifact in summary_payload["event_artifacts"]
                if "invalid" in artifact
            )
            (output_dir / invalid_artifact).write_text('{"tampered":true}\n', encoding="utf-8")

            subset_ok = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
                "--batch-output-verify-include",
                "*ok*",
            )
            subset_excluding_invalid = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
                "--batch-output-verify-include",
                "*.envelope.json",
                "--batch-output-verify-exclude",
                "*invalid*",
            )
            full_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
            )
            subset_no_match = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-include",
                "*does-not-exist*",
            )

            self.assertEqual(subset_ok.returncode, 0)
            self.assertEqual(subset_ok.stderr, "")
            self.assertEqual(
                subset_ok.stdout,
                "status=ok checked=1 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=1 selected_manifest=1\n",
            )

            self.assertEqual(subset_excluding_invalid.returncode, 0)
            self.assertEqual(subset_excluding_invalid.stderr, "")
            self.assertEqual(
                subset_excluding_invalid.stdout,
                "status=ok checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2\n",
            )

            self.assertEqual(full_verify.returncode, 1)
            self.assertEqual(full_verify.stderr, "")
            self.assertEqual(
                full_verify.stdout,
                "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=3 selected_manifest=3\n",
            )

            self.assertEqual(subset_no_match.returncode, 1)
            self.assertEqual(subset_no_match.stdout, "")
            self.assertEqual(
                subset_no_match.stderr,
                "error: --batch-output-verify selectors matched no artifacts (include='*does-not-exist*', exclude='<none>')\n",
            )

    def test_eval_command_batch_output_compare_reports_deterministic_regression_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "baseline-001",
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-run-id",
                "candidate-002",
            )
            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            candidate_summary = json.loads((candidate_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(baseline_summary["run"]["id"], "baseline-001")
            self.assertEqual(candidate_summary["run"]["id"], "candidate-002")
            self.assertNotIn("artifact_sha256", baseline_summary)
            self.assertNotIn("artifact_sha256", candidate_summary)

            self.assertEqual(compare_result.returncode, 0)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(summary_result.returncode, 0)
            self.assertEqual(summary_result.stderr, "")
            self.assertEqual(
                summary_result.stdout,
                "status=ok compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=3 selected_candidate=3\n",
            )

            compare_payload = json.loads(compare_result.stdout)
            self.assertEqual(
                list(compare_payload.keys()),
                [
                    "status",
                    "baseline_run_id",
                    "candidate_run_id",
                    "compared",
                    "matched",
                    "baseline_only_artifacts",
                    "candidate_only_artifacts",
                    "missing_baseline_artifacts",
                    "missing_candidate_artifacts",
                    "changed_artifacts",
                    "metadata_mismatches",
                    "selected_baseline_artifacts_count",
                    "selected_candidate_artifacts_count",
                ],
            )
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(compare_payload["candidate_run_id"], "candidate-002")
            self.assertEqual(compare_payload["compared"], 3)
            self.assertEqual(compare_payload["matched"], 3)
            self.assertEqual(compare_payload["baseline_only_artifacts"], [])
            self.assertEqual(compare_payload["candidate_only_artifacts"], [])
            self.assertEqual(compare_payload["missing_baseline_artifacts"], [])
            self.assertEqual(compare_payload["missing_candidate_artifacts"], [])
            self.assertEqual(compare_payload["changed_artifacts"], [])
            self.assertEqual(compare_payload["metadata_mismatches"], [])
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 3)

    def test_eval_command_batch_output_compare_summary_file_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            compare_json_file = Path(tmp_dir) / "compare-pass.json"
            compare_summary_file = Path(tmp_dir) / "compare-pass-summary.txt"
            compare_json_sidecar_file = Path(tmp_dir) / "compare-sidecar.json"
            compare_fail_json_file = Path(tmp_dir) / "compare-fail.json"
            compare_fail_json_sidecar_file = Path(tmp_dir) / "compare-fail-sidecar.json"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "baseline-001",
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-run-id",
                "candidate-002",
            )
            compare_baseline = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            compare_with_json_file = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(compare_json_file),
            )
            compare_with_summary_file = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
                "--batch-output-compare-summary-file",
                str(compare_summary_file),
            )
            compare_with_summary_and_json_sidecar = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
                "--batch-output-compare-json-file",
                str(compare_json_sidecar_file),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            self.assertEqual(compare_baseline.returncode, 0)
            self.assertEqual(compare_baseline.stderr, "")

            self.assertEqual(compare_with_json_file.returncode, 0)
            self.assertEqual(compare_with_json_file.stderr, "")
            self.assertEqual(compare_with_json_file.stdout, compare_baseline.stdout)
            self.assertEqual(compare_json_file.read_text(encoding="utf-8"), compare_with_json_file.stdout)

            compare_baseline_payload = json.loads(compare_baseline.stdout)
            self.assertEqual(compare_baseline_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(compare_baseline_payload["candidate_run_id"], "candidate-002")

            self.assertEqual(compare_with_summary_file.returncode, 0)
            self.assertEqual(compare_with_summary_file.stderr, "")
            self.assertEqual(
                compare_with_summary_file.stdout,
                "status=ok compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=3 selected_candidate=3\n",
            )
            self.assertEqual(
                compare_summary_file.read_text(encoding="utf-8"),
                compare_with_summary_file.stdout,
            )

            self.assertEqual(compare_with_summary_and_json_sidecar.returncode, 0)
            self.assertEqual(compare_with_summary_and_json_sidecar.stderr, "")
            self.assertEqual(
                compare_with_summary_and_json_sidecar.stdout,
                compare_with_summary_file.stdout,
            )
            self.assertEqual(
                compare_json_sidecar_file.read_text(encoding="utf-8"),
                compare_baseline.stdout,
            )

            candidate_summary = json.loads((candidate_dir / "summary.json").read_text(encoding="utf-8"))
            tampered_artifact = candidate_dir / candidate_summary["event_artifacts"][0]
            tampered_artifact.write_text('{"tampered":true}\\n', encoding="utf-8")

            compare_fail_with_json_file = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(compare_fail_json_file),
            )
            compare_fail_with_summary_and_json_sidecar = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
                "--batch-output-compare-json-file",
                str(compare_fail_json_sidecar_file),
            )

            self.assertEqual(compare_fail_with_json_file.returncode, 1)
            self.assertEqual(compare_fail_with_json_file.stderr, "")
            self.assertEqual(
                compare_fail_json_file.read_text(encoding="utf-8"),
                compare_fail_with_json_file.stdout,
            )

            fail_payload = json.loads(compare_fail_with_json_file.stdout)
            self.assertEqual(fail_payload["status"], "error")
            self.assertEqual(fail_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(fail_payload["candidate_run_id"], "candidate-002")
            self.assertEqual(len(fail_payload["changed_artifacts"]), 1)

            self.assertEqual(compare_fail_with_summary_and_json_sidecar.returncode, 1)
            self.assertEqual(compare_fail_with_summary_and_json_sidecar.stderr, "")
            self.assertTrue(compare_fail_with_summary_and_json_sidecar.stdout.startswith("status=error "))
            fail_sidecar_payload = json.loads(
                compare_fail_json_sidecar_file.read_text(encoding="utf-8")
            )
            self.assertEqual(fail_sidecar_payload["status"], "error")
            self.assertEqual(len(fail_sidecar_payload["changed_artifacts"]), 1)

    def test_eval_command_batch_output_compare_detects_artifact_and_metadata_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "baseline-001",
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-run-id",
                "candidate-002",
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))

            tampered_artifact = candidate_dir / candidate_summary["event_artifacts"][0]
            tampered_artifact.write_text(
                '{"event":"01-ok.json","actions":[{"kind":"notify","params":{"channel":"drift"}}],"trace":[]}\n',
                encoding="utf-8",
            )

            baseline_action_count = baseline_summary["summary"]["action_count"]
            candidate_summary["summary"]["action_count"] = baseline_action_count + 7
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 1)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(summary_result.returncode, 1)
            self.assertEqual(summary_result.stderr, "")
            self.assertEqual(
                summary_result.stdout,
                "status=error compared=3 matched=2 changed=1 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=3 selected_candidate=3\n",
            )

            compare_payload = json.loads(compare_result.stdout)
            self.assertEqual(compare_payload["status"], "error")
            self.assertEqual(compare_payload["compared"], 3)
            self.assertEqual(compare_payload["matched"], 2)
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 3)
            self.assertEqual(compare_payload["baseline_only_artifacts"], [])
            self.assertEqual(compare_payload["candidate_only_artifacts"], [])
            self.assertEqual(compare_payload["missing_baseline_artifacts"], [])
            self.assertEqual(compare_payload["missing_candidate_artifacts"], [])
            self.assertEqual(
                compare_payload["changed_artifacts"],
                [
                    {
                        "artifact": tampered_artifact.name,
                        "baseline": hashlib.sha256(
                            (baseline_dir / tampered_artifact.name).read_bytes()
                        ).hexdigest(),
                        "candidate": hashlib.sha256(tampered_artifact.read_bytes()).hexdigest(),
                    }
                ],
            )
            self.assertEqual(
                compare_payload["metadata_mismatches"],
                [
                    {
                        "field": "summary.action_count",
                        "baseline": baseline_action_count,
                        "candidate": baseline_action_count + 7,
                    }
                ],
            )

    def test_eval_command_batch_output_compare_detects_manifest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "baseline-001",
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "candidate-002",
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            manifest_artifact = sorted(candidate_summary["artifact_sha256"])[0]
            candidate_summary["artifact_sha256"][manifest_artifact] = "0" * 64
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            summary_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 1)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(summary_result.returncode, 1)
            self.assertEqual(summary_result.stderr, "")
            self.assertEqual(
                summary_result.stdout,
                "status=error compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=3 selected_candidate=3\n",
            )

            compare_payload = json.loads(compare_result.stdout)
            self.assertEqual(compare_payload["status"], "error")
            self.assertEqual(compare_payload["compared"], 3)
            self.assertEqual(compare_payload["matched"], 3)
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 3)
            self.assertEqual(compare_payload["changed_artifacts"], [])
            self.assertEqual(
                compare_payload["metadata_mismatches"],
                [
                    {
                        "field": "artifact_sha256",
                        "baseline": baseline_summary["artifact_sha256"],
                        "candidate": {
                            artifact: candidate_summary["artifact_sha256"][artifact]
                            for artifact in sorted(candidate_summary["artifact_sha256"])
                        },
                    }
                ],
            )

    def test_eval_command_batch_output_compare_empty_artifact_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_dir = Path(tmp_dir) / "batch"
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            batch_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(EVAL_FIXTURES / "event-ok.json", batch_dir / "01-ok.json")

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-errors-only",
                "--batch-output-manifest",
                "--batch-output-run-id",
                "baseline-empty-001",
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-manifest",
                "--batch-output-run-id",
                "candidate-empty-002",
            )
            compare_pass = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            compare_pass_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            self.assertEqual(baseline_summary["event_artifacts"], [])
            self.assertEqual(candidate_summary["event_artifacts"], [])
            self.assertEqual(baseline_summary["artifact_sha256"], {})
            self.assertEqual(candidate_summary["artifact_sha256"], {})

            self.assertEqual(compare_pass.returncode, 0)
            self.assertEqual(compare_pass.stderr, "")
            self.assertEqual(compare_pass_summary.returncode, 0)
            self.assertEqual(compare_pass_summary.stderr, "")
            self.assertEqual(
                compare_pass_summary.stdout,
                "status=ok compared=0 matched=0 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=0 selected_candidate=0\n",
            )
            self.assertEqual(
                json.loads(compare_pass.stdout),
                {
                    "status": "ok",
                    "baseline_run_id": "baseline-empty-001",
                    "candidate_run_id": "candidate-empty-002",
                    "compared": 0,
                    "matched": 0,
                    "baseline_only_artifacts": [],
                    "candidate_only_artifacts": [],
                    "missing_baseline_artifacts": [],
                    "missing_candidate_artifacts": [],
                    "changed_artifacts": [],
                    "metadata_mismatches": [],
                    "selected_baseline_artifacts_count": 0,
                    "selected_candidate_artifacts_count": 0,
                },
            )

            candidate_summary["summary"]["action_count"] = baseline_summary["summary"]["action_count"] + 1
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_fail = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            compare_fail_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )

            self.assertEqual(compare_fail.returncode, 1)
            self.assertEqual(compare_fail.stderr, "")
            self.assertEqual(compare_fail_summary.returncode, 1)
            self.assertEqual(compare_fail_summary.stderr, "")
            self.assertEqual(
                compare_fail_summary.stdout,
                "status=error compared=0 matched=0 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=0 selected_candidate=0\n",
            )
            self.assertEqual(
                json.loads(compare_fail.stdout)["metadata_mismatches"],
                [
                    {
                        "field": "summary.action_count",
                        "baseline": baseline_summary["summary"]["action_count"],
                        "candidate": baseline_summary["summary"]["action_count"] + 1,
                    }
                ],
            )

    def test_eval_command_batch_output_compare_scoped_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "baseline-001",
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "candidate-002",
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            tampered_artifact = candidate_dir / "02-no-action.envelope.json"
            tampered_artifact.write_text(
                '{"event":"02-no-action.json","actions":[{"kind":"notify","params":{"channel":"drift"}}],"trace":[]}\n',
                encoding="utf-8",
            )
            candidate_summary["artifact_sha256"]["02-no-action.envelope.json"] = "0" * 64
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            full_compare = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
            )
            scoped_pass = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "01-ok.envelope.json",
            )
            scoped_pass_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "01-ok.envelope.json",
                "--summary",
            )
            scoped_fail = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "02-no-action.envelope.json",
            )
            scoped_no_match = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "*does-not-exist*",
            )

            self.assertEqual(full_compare.returncode, 1)
            self.assertEqual(full_compare.stderr, "")
            self.assertEqual(
                full_compare.stdout,
                "status=error compared=3 matched=2 changed=1 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=3 selected_candidate=3\n",
            )

            self.assertEqual(scoped_pass.returncode, 0)
            self.assertEqual(scoped_pass.stderr, "")
            self.assertEqual(scoped_pass_summary.returncode, 0)
            self.assertEqual(scoped_pass_summary.stderr, "")
            self.assertEqual(
                scoped_pass_summary.stdout,
                "status=ok compared=1 matched=1 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=1 selected_candidate=1\n",
            )
            self.assertEqual(
                json.loads(scoped_pass.stdout),
                {
                    "status": "ok",
                    "baseline_run_id": "baseline-001",
                    "candidate_run_id": "candidate-002",
                    "compared": 1,
                    "matched": 1,
                    "baseline_only_artifacts": [],
                    "candidate_only_artifacts": [],
                    "missing_baseline_artifacts": [],
                    "missing_candidate_artifacts": [],
                    "changed_artifacts": [],
                    "metadata_mismatches": [],
                    "selected_baseline_artifacts_count": 1,
                    "selected_candidate_artifacts_count": 1,
                },
            )

            self.assertEqual(scoped_fail.returncode, 1)
            self.assertEqual(scoped_fail.stderr, "")
            self.assertEqual(
                json.loads(scoped_fail.stdout),
                {
                    "status": "error",
                    "baseline_run_id": "baseline-001",
                    "candidate_run_id": "candidate-002",
                    "compared": 1,
                    "matched": 0,
                    "baseline_only_artifacts": [],
                    "candidate_only_artifacts": [],
                    "missing_baseline_artifacts": [],
                    "missing_candidate_artifacts": [],
                    "selected_baseline_artifacts_count": 1,
                    "selected_candidate_artifacts_count": 1,
                    "changed_artifacts": [
                        {
                            "artifact": "02-no-action.envelope.json",
                            "baseline": hashlib.sha256(
                                (baseline_dir / "02-no-action.envelope.json").read_bytes()
                            ).hexdigest(),
                            "candidate": hashlib.sha256(tampered_artifact.read_bytes()).hexdigest(),
                        }
                    ],
                    "metadata_mismatches": [
                        {
                            "field": "artifact_sha256",
                            "baseline": {
                                "02-no-action.envelope.json": json.loads(
                                    (baseline_dir / "summary.json").read_text(encoding="utf-8")
                                )["artifact_sha256"]["02-no-action.envelope.json"]
                            },
                            "candidate": {"02-no-action.envelope.json": "0" * 64},
                        }
                    ],
                },
            )

            self.assertEqual(scoped_no_match.returncode, 1)
            self.assertEqual(scoped_no_match.stdout, "")
            self.assertEqual(
                scoped_no_match.stderr,
                "error: --batch-output-compare selectors matched no artifacts (include='*does-not-exist*', exclude='<none>')\n",
            )

    def test_eval_command_batch_output_compare_strict_expected_drift_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "baseline-001",
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
                "--batch-output-manifest",
                "--batch-output-run-id",
                "candidate-002",
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            tampered_artifact = candidate_dir / "02-no-action.envelope.json"
            tampered_artifact.write_text(
                '{"event":"02-no-action.json","actions":[{"kind":"notify","params":{"channel":"drift"}}],"trace":[]}\n',
                encoding="utf-8",
            )

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "error",
                "--batch-output-compare-expected-compared-count",
                "3",
                "--batch-output-compare-expected-matched-count",
                "2",
                "--batch-output-compare-expected-changed-count",
                "1",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "3",
            )
            compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "error",
                "--batch-output-compare-expected-compared-count",
                "3",
                "--batch-output-compare-expected-matched-count",
                "2",
                "--batch-output-compare-expected-changed-count",
                "1",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "3",
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 0)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(compare_summary.returncode, 0)
            self.assertEqual(compare_summary.stderr, "")
            self.assertEqual(
                compare_summary.stdout,
                "status=ok compare_status=error compared=3 matched=2 changed=1 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=3 selected_candidate=3 strict_mismatches=0\n",
            )

            compare_payload = json.loads(compare_result.stdout)
            self.assertEqual(
                list(compare_payload.keys()),
                [
                    "status",
                    "compare_status",
                    "baseline_run_id",
                    "candidate_run_id",
                    "compared",
                    "matched",
                    "baseline_only_artifacts",
                    "candidate_only_artifacts",
                    "missing_baseline_artifacts",
                    "missing_candidate_artifacts",
                    "changed_artifacts",
                    "metadata_mismatches",
                    "selected_baseline_artifacts_count",
                    "selected_candidate_artifacts_count",
                    "strict_profile",
                    "strict_profile_mismatches",
                ],
            )
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["compare_status"], "error")
            self.assertEqual(compare_payload["baseline_run_id"], "baseline-001")
            self.assertEqual(compare_payload["candidate_run_id"], "candidate-002")
            self.assertEqual(compare_payload["compared"], 3)
            self.assertEqual(compare_payload["matched"], 2)
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 3)
            self.assertEqual(compare_payload["baseline_only_artifacts"], [])
            self.assertEqual(compare_payload["candidate_only_artifacts"], [])
            self.assertEqual(compare_payload["missing_baseline_artifacts"], [])
            self.assertEqual(compare_payload["missing_candidate_artifacts"], [])
            self.assertEqual(compare_payload["metadata_mismatches"], [])
            self.assertEqual(compare_payload["strict_profile_mismatches"], [])
            self.assertEqual(
                compare_payload["strict_profile"],
                {
                    "expected_status": "error",
                    "expected_compared_count": 3,
                    "expected_matched_count": 2,
                    "expected_changed_count": 1,
                    "expected_selected_baseline_count": 3,
                    "expected_selected_candidate_count": 3,
                },
            )
            self.assertEqual(
                compare_payload["changed_artifacts"],
                [
                    {
                        "artifact": "02-no-action.envelope.json",
                        "baseline": hashlib.sha256(
                            (baseline_dir / "02-no-action.envelope.json").read_bytes()
                        ).hexdigest(),
                        "candidate": hashlib.sha256(tampered_artifact.read_bytes()).hexdigest(),
                    }
                ],
            )

    def test_eval_command_batch_output_compare_strict_extended_drift_selectors_pass_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            baseline_summary_path = baseline_dir / "summary.json"
            baseline_summary = json.loads(baseline_summary_path.read_text(encoding="utf-8"))
            baseline_summary["event_artifacts"].append("ghost-baseline.envelope.json")
            baseline_summary_path.write_text(
                f"{json.dumps(baseline_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            candidate_summary["event_artifacts"].append("ghost-candidate.envelope.json")
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "error",
                "--batch-output-compare-expected-compared-count",
                "3",
                "--batch-output-compare-expected-matched-count",
                "3",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-baseline-only-count",
                "1",
                "--batch-output-compare-expected-candidate-only-count",
                "1",
                "--batch-output-compare-expected-missing-baseline-count",
                "1",
                "--batch-output-compare-expected-missing-candidate-count",
                "1",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "1",
                "--batch-output-compare-expected-selected-baseline-count",
                "4",
                "--batch-output-compare-expected-selected-candidate-count",
                "4",
            )
            compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "error",
                "--batch-output-compare-expected-compared-count",
                "3",
                "--batch-output-compare-expected-matched-count",
                "3",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-baseline-only-count",
                "1",
                "--batch-output-compare-expected-candidate-only-count",
                "1",
                "--batch-output-compare-expected-missing-baseline-count",
                "1",
                "--batch-output-compare-expected-missing-candidate-count",
                "1",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "1",
                "--batch-output-compare-expected-selected-baseline-count",
                "4",
                "--batch-output-compare-expected-selected-candidate-count",
                "4",
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 0)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(compare_summary.returncode, 0)
            self.assertEqual(compare_summary.stderr, "")
            self.assertEqual(
                compare_summary.stdout,
                "status=ok compare_status=error compared=3 matched=3 changed=0 baseline_only=1 candidate_only=1 missing_baseline=1 missing_candidate=1 metadata_mismatches=1 selected_baseline=4 selected_candidate=4 strict_mismatches=0\n",
            )

            compare_payload = json.loads(compare_result.stdout)
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["compare_status"], "error")
            self.assertEqual(compare_payload["compared"], 3)
            self.assertEqual(compare_payload["matched"], 3)
            self.assertEqual(compare_payload["baseline_only_artifacts"], ["ghost-baseline.envelope.json"])
            self.assertEqual(compare_payload["candidate_only_artifacts"], ["ghost-candidate.envelope.json"])
            self.assertEqual(compare_payload["missing_baseline_artifacts"], ["ghost-baseline.envelope.json"])
            self.assertEqual(compare_payload["missing_candidate_artifacts"], ["ghost-candidate.envelope.json"])
            self.assertEqual(compare_payload["changed_artifacts"], [])
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 4)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 4)
            self.assertEqual(
                compare_payload["metadata_mismatches"],
                [
                    {
                        "field": "event_artifacts",
                        "baseline": baseline_summary["event_artifacts"],
                        "candidate": candidate_summary["event_artifacts"],
                    }
                ],
            )
            self.assertEqual(compare_payload["strict_profile_mismatches"], [])
            self.assertEqual(
                compare_payload["strict_profile"],
                {
                    "expected_status": "error",
                    "expected_compared_count": 3,
                    "expected_matched_count": 3,
                    "expected_changed_count": 0,
                    "expected_baseline_only_count": 1,
                    "expected_candidate_only_count": 1,
                    "expected_missing_baseline_count": 1,
                    "expected_missing_candidate_count": 1,
                    "expected_metadata_mismatches_count": 1,
                    "expected_selected_baseline_count": 4,
                    "expected_selected_candidate_count": 4,
                },
            )

    def test_eval_command_batch_output_compare_can_surface_and_gate_action_plan_and_resolved_ref_counts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--exclude",
                "*invalid*.json",
                "--action-plan",
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--exclude",
                "*invalid*.json",
                "--action-plan",
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-compared-count",
                "2",
                "--batch-output-compare-expected-matched-count",
                "2",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "0",
                "--batch-output-compare-expected-selected-baseline-count",
                "2",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
            )
            compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-compared-count",
                "2",
                "--batch-output-compare-expected-matched-count",
                "2",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "0",
                "--batch-output-compare-expected-selected-baseline-count",
                "2",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 0)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(compare_summary.returncode, 0)
            self.assertEqual(compare_summary.stderr, "")
            self.assertEqual(
                compare_summary.stdout,
                "status=ok compare_status=ok compared=2 matched=2 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=2 selected_candidate=2 baseline_plan=1 candidate_plan=1 baseline_resolved_refs=1 candidate_resolved_refs=1 strict_mismatches=0\n",
            )

            compare_payload = json.loads(compare_result.stdout)
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["compare_status"], "ok")
            self.assertEqual(compare_payload["compared"], 2)
            self.assertEqual(compare_payload["matched"], 2)
            self.assertEqual(compare_payload["metadata_mismatches"], [])
            self.assertEqual(compare_payload["baseline_action_plan_count"], 1)
            self.assertEqual(compare_payload["candidate_action_plan_count"], 1)
            self.assertEqual(compare_payload["baseline_resolved_ref_count"], 1)
            self.assertEqual(compare_payload["candidate_resolved_ref_count"], 1)
            self.assertEqual(compare_payload["strict_profile_mismatches"], [])
            self.assertEqual(
                compare_payload["strict_profile"],
                {
                    "expected_status": "ok",
                    "expected_compared_count": 2,
                    "expected_matched_count": 2,
                    "expected_changed_count": 0,
                    "expected_metadata_mismatches_count": 0,
                    "expected_baseline_action_plan_count": 1,
                    "expected_candidate_action_plan_count": 1,
                    "expected_baseline_resolved_refs_count": 1,
                    "expected_candidate_resolved_refs_count": 1,
                    "expected_selected_baseline_count": 2,
                    "expected_selected_candidate_count": 2,
                },
            )

    def test_eval_command_batch_output_compare_action_plan_counts_follow_summary_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--exclude",
                "*invalid*.json",
                "--action-plan",
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--exclude",
                "*invalid*.json",
                "--action-plan",
                "--batch-output",
                str(candidate_dir),
            )

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "*no-action*",
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-compared-count",
                "1",
                "--batch-output-compare-expected-matched-count",
                "1",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "0",
                "--batch-output-compare-expected-selected-baseline-count",
                "1",
                "--batch-output-compare-expected-selected-candidate-count",
                "1",
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
            )
            compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "*no-action*",
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-compared-count",
                "1",
                "--batch-output-compare-expected-matched-count",
                "1",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "0",
                "--batch-output-compare-expected-selected-baseline-count",
                "1",
                "--batch-output-compare-expected-selected-candidate-count",
                "1",
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
                "--summary",
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")
            self.assertEqual(compare_result.returncode, 0)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(compare_summary.returncode, 0)
            self.assertEqual(compare_summary.stderr, "")
            self.assertEqual(
                compare_summary.stdout,
                "status=ok compare_status=ok compared=1 matched=1 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=1 selected_candidate=1 baseline_plan=1 candidate_plan=1 baseline_resolved_refs=1 candidate_resolved_refs=1 strict_mismatches=0\n",
            )

            compare_payload = json.loads(compare_result.stdout)
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["compare_status"], "ok")
            self.assertEqual(compare_payload["baseline_action_plan_count"], 1)
            self.assertEqual(compare_payload["candidate_action_plan_count"], 1)
            self.assertEqual(compare_payload["baseline_resolved_ref_count"], 1)
            self.assertEqual(compare_payload["candidate_resolved_ref_count"], 1)
            self.assertEqual(compare_payload["strict_profile_mismatches"], [])
            self.assertEqual(
                compare_payload["strict_profile"],
                {
                    "expected_status": "ok",
                    "expected_compared_count": 1,
                    "expected_matched_count": 1,
                    "expected_changed_count": 0,
                    "expected_metadata_mismatches_count": 0,
                    "expected_baseline_action_plan_count": 1,
                    "expected_candidate_action_plan_count": 1,
                    "expected_baseline_resolved_refs_count": 1,
                    "expected_candidate_resolved_refs_count": 1,
                    "expected_selected_baseline_count": 1,
                    "expected_selected_candidate_count": 1,
                },
            )

    def test_eval_command_batch_output_compare_strict_reports_missing_action_plan_and_resolved_ref_counts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--exclude",
                "*invalid*.json",
                "--action-plan",
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--exclude",
                "*invalid*.json",
                "--action-plan",
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            candidate_summary["summary"].pop("action_plan_count")
            candidate_summary["summary"].pop("resolved_ref_count")
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "error",
                "--batch-output-compare-expected-compared-count",
                "2",
                "--batch-output-compare-expected-matched-count",
                "2",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "2",
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")

            compare_payload = json.loads(result.stdout)
            self.assertEqual(compare_payload["status"], "error")
            self.assertEqual(compare_payload["compare_status"], "error")
            self.assertEqual(compare_payload["baseline_action_plan_count"], 1)
            self.assertNotIn("candidate_action_plan_count", compare_payload)
            self.assertEqual(compare_payload["baseline_resolved_ref_count"], 1)
            self.assertNotIn("candidate_resolved_ref_count", compare_payload)
            self.assertEqual(
                compare_payload["metadata_mismatches"],
                [
                    {
                        "field": "summary.action_plan_count",
                        "baseline": 1,
                        "candidate": "<missing>",
                    },
                    {
                        "field": "summary.resolved_ref_count",
                        "baseline": 1,
                        "candidate": "<missing>",
                    },
                ],
            )
            self.assertEqual(
                compare_payload["strict_profile_mismatches"],
                [
                    {
                        "field": "candidate.summary.action_plan_count",
                        "expected": 1,
                        "actual": "<missing>",
                    },
                    {
                        "field": "candidate.summary.resolved_ref_count",
                        "expected": 1,
                        "actual": "<missing>",
                    },
                ],
            )

    def test_eval_command_batch_output_self_compare_strict_can_gate_action_plan_and_resolved_ref_counts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            compare_json_file = Path(tmp_dir) / "self-compare.json"

            baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--exclude",
                "*invalid*.json",
                "--action-plan",
                "--batch-output",
                str(baseline_dir),
            )
            candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch-index.json"),
                "--exclude",
                "*invalid*.json",
                "--action-plan",
                "--batch-output",
                str(candidate_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-self-compare-strict",
                "--batch-output-compare-json-file",
                str(compare_json_file),
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-compared-count",
                "2",
                "--batch-output-compare-expected-matched-count",
                "2",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "0",
                "--batch-output-compare-expected-selected-baseline-count",
                "2",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
            )

            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(baseline.stderr, "")
            self.assertEqual(candidate.returncode, 0)
            self.assertEqual(candidate.stderr, "")
            self.assertEqual(candidate.stdout, baseline.stdout)

            compare_payload = json.loads(compare_json_file.read_text(encoding="utf-8"))
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["compare_status"], "ok")
            self.assertEqual(compare_payload["baseline_action_plan_count"], 1)
            self.assertEqual(compare_payload["candidate_action_plan_count"], 1)
            self.assertEqual(compare_payload["baseline_resolved_ref_count"], 1)
            self.assertEqual(compare_payload["candidate_resolved_ref_count"], 1)
            self.assertEqual(compare_payload["strict_profile_mismatches"], [])
            self.assertEqual(
                compare_payload["strict_profile"],
                {
                    "expected_status": "ok",
                    "expected_compared_count": 2,
                    "expected_matched_count": 2,
                    "expected_changed_count": 0,
                    "expected_metadata_mismatches_count": 0,
                    "expected_baseline_action_plan_count": 1,
                    "expected_candidate_action_plan_count": 1,
                    "expected_baseline_resolved_refs_count": 1,
                    "expected_candidate_resolved_refs_count": 1,
                    "expected_selected_baseline_count": 2,
                    "expected_selected_candidate_count": 2,
                },
            )

    def test_eval_command_batch_output_compare_expected_selected_artifact_requires_strict_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-expected-selected-baseline-artifact",
                "01-ok.envelope.json",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "error: --batch-output-compare-expected-selected-baseline-artifact requires strict compare\n",
            )

    def test_eval_command_batch_output_compare_rejects_duplicate_expected_selected_artifact_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-selected-baseline-artifact",
                "01-ok.envelope.json",
                "--batch-output-compare-expected-selected-baseline-artifact",
                "01-ok.envelope.json",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "error: duplicate --batch-output-compare-expected-selected-baseline-artifact selector: 01-ok.envelope.json\n",
            )

    def test_eval_command_batch_output_compare_strict_can_gate_exact_selected_artifact_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "*no-action*",
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-selected-baseline-count",
                "1",
                "--batch-output-compare-expected-selected-candidate-count",
                "1",
                "--batch-output-compare-expected-selected-baseline-artifact",
                "02-no-action.envelope.json",
                "--batch-output-compare-expected-selected-candidate-artifact",
                "02-no-action.envelope.json",
            )
            compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "*no-action*",
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-selected-baseline-count",
                "1",
                "--batch-output-compare-expected-selected-candidate-count",
                "1",
                "--batch-output-compare-expected-selected-baseline-artifact",
                "02-no-action.envelope.json",
                "--batch-output-compare-expected-selected-candidate-artifact",
                "02-no-action.envelope.json",
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 0)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(compare_summary.returncode, 0)
            self.assertEqual(compare_summary.stderr, "")
            self.assertEqual(
                compare_summary.stdout,
                "status=ok compare_status=ok compared=1 matched=1 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=1 selected_candidate=1 strict_mismatches=0\n",
            )
            self.assertEqual(
                json.loads(compare_result.stdout),
                {
                    "status": "ok",
                    "compare_status": "ok",
                    "compared": 1,
                    "matched": 1,
                    "baseline_only_artifacts": [],
                    "candidate_only_artifacts": [],
                    "missing_baseline_artifacts": [],
                    "missing_candidate_artifacts": [],
                    "changed_artifacts": [],
                    "metadata_mismatches": [],
                    "selected_baseline_artifacts_count": 1,
                    "selected_candidate_artifacts_count": 1,
                    "selected_baseline_artifacts": ["02-no-action.envelope.json"],
                    "selected_candidate_artifacts": ["02-no-action.envelope.json"],
                    "strict_profile": {
                        "expected_status": "ok",
                        "expected_selected_baseline_count": 1,
                        "expected_selected_candidate_count": 1,
                        "expected_selected_baseline_artifacts": [
                            "02-no-action.envelope.json"
                        ],
                        "expected_selected_candidate_artifacts": [
                            "02-no-action.envelope.json"
                        ],
                    },
                    "strict_profile_mismatches": [],
                },
            )

    def test_eval_command_batch_output_compare_strict_reports_selected_candidate_artifact_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            candidate_summary["event_artifacts"] = list(reversed(candidate_summary["event_artifacts"]))
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "error",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "1",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "3",
                "--batch-output-compare-expected-selected-baseline-artifact",
                "01-ok.envelope.json",
                "--batch-output-compare-expected-selected-baseline-artifact",
                "02-no-action.envelope.json",
                "--batch-output-compare-expected-selected-baseline-artifact",
                "03-invalid.envelope.json",
                "--batch-output-compare-expected-selected-candidate-artifact",
                "01-ok.envelope.json",
                "--batch-output-compare-expected-selected-candidate-artifact",
                "02-no-action.envelope.json",
                "--batch-output-compare-expected-selected-candidate-artifact",
                "03-invalid.envelope.json",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "status": "error",
                    "compare_status": "error",
                    "compared": 3,
                    "matched": 3,
                    "baseline_only_artifacts": [],
                    "candidate_only_artifacts": [],
                    "missing_baseline_artifacts": [],
                    "missing_candidate_artifacts": [],
                    "changed_artifacts": [],
                    "metadata_mismatches": [
                        {
                            "field": "event_artifacts",
                            "baseline": [
                                "01-ok.envelope.json",
                                "02-no-action.envelope.json",
                                "03-invalid.envelope.json",
                            ],
                            "candidate": [
                                "03-invalid.envelope.json",
                                "02-no-action.envelope.json",
                                "01-ok.envelope.json",
                            ],
                        }
                    ],
                    "selected_baseline_artifacts_count": 3,
                    "selected_candidate_artifacts_count": 3,
                    "selected_baseline_artifacts": [
                        "01-ok.envelope.json",
                        "02-no-action.envelope.json",
                        "03-invalid.envelope.json",
                    ],
                    "selected_candidate_artifacts": [
                        "03-invalid.envelope.json",
                        "02-no-action.envelope.json",
                        "01-ok.envelope.json",
                    ],
                    "strict_profile": {
                        "expected_status": "error",
                        "expected_metadata_mismatches_count": 1,
                        "expected_selected_baseline_count": 3,
                        "expected_selected_candidate_count": 3,
                        "expected_selected_baseline_artifacts": [
                            "01-ok.envelope.json",
                            "02-no-action.envelope.json",
                            "03-invalid.envelope.json",
                        ],
                        "expected_selected_candidate_artifacts": [
                            "01-ok.envelope.json",
                            "02-no-action.envelope.json",
                            "03-invalid.envelope.json",
                        ],
                    },
                    "strict_profile_mismatches": [
                        {
                            "field": "selected_candidate_artifacts",
                            "expected": [
                                "01-ok.envelope.json",
                                "02-no-action.envelope.json",
                                "03-invalid.envelope.json",
                            ],
                            "actual": [
                                "03-invalid.envelope.json",
                                "02-no-action.envelope.json",
                                "01-ok.envelope.json",
                            ],
                        }
                    ],
                },
            )

    def test_eval_command_batch_output_compare_profile_clean_auto_enables_strict_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-profile",
                "clean",
            )
            compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-profile",
                "clean",
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 0)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(compare_summary.returncode, 0)
            self.assertEqual(compare_summary.stderr, "")
            self.assertEqual(
                compare_summary.stdout,
                "status=ok compare_status=ok compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=3 selected_candidate=3 strict_mismatches=0\n",
            )
            self.assertEqual(
                json.loads(compare_result.stdout),
                {
                    "status": "ok",
                    "compare_status": "ok",
                    "compared": 3,
                    "matched": 3,
                    "baseline_only_artifacts": [],
                    "candidate_only_artifacts": [],
                    "missing_baseline_artifacts": [],
                    "missing_candidate_artifacts": [],
                    "changed_artifacts": [],
                    "metadata_mismatches": [],
                    "selected_baseline_artifacts_count": 3,
                    "selected_candidate_artifacts_count": 3,
                    "strict_profile": {
                        "expected_status": "ok",
                        "expected_changed_count": 0,
                        "expected_baseline_only_count": 0,
                        "expected_candidate_only_count": 0,
                        "expected_missing_baseline_count": 0,
                        "expected_missing_candidate_count": 0,
                        "expected_metadata_mismatches_count": 0,
                    },
                    "strict_profile_mismatches": [],
                },
            )

    def test_eval_command_batch_output_compare_strict_profile_metadata_only_allows_selector_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            candidate_summary["event_artifacts"] = list(reversed(candidate_summary["event_artifacts"]))
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-profile",
                "metadata-only",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "1",
            )
            compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-profile",
                "metadata-only",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "1",
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 0)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(compare_summary.returncode, 0)
            self.assertEqual(compare_summary.stderr, "")
            self.assertEqual(
                compare_summary.stdout,
                "status=ok compare_status=error compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=3 selected_candidate=3 strict_mismatches=0\n",
            )

            compare_payload = json.loads(compare_result.stdout)
            self.assertEqual(compare_payload["status"], "ok")
            self.assertEqual(compare_payload["compare_status"], "error")
            self.assertEqual(compare_payload["compared"], 3)
            self.assertEqual(compare_payload["matched"], 3)
            self.assertEqual(compare_payload["baseline_only_artifacts"], [])
            self.assertEqual(compare_payload["candidate_only_artifacts"], [])
            self.assertEqual(compare_payload["missing_baseline_artifacts"], [])
            self.assertEqual(compare_payload["missing_candidate_artifacts"], [])
            self.assertEqual(compare_payload["changed_artifacts"], [])
            self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
            self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 3)
            self.assertEqual(compare_payload["strict_profile_mismatches"], [])
            self.assertEqual(
                compare_payload["metadata_mismatches"],
                [
                    {
                        "field": "event_artifacts",
                        "baseline": [
                            "01-ok.envelope.json",
                            "02-no-action.envelope.json",
                            "03-invalid.envelope.json",
                        ],
                        "candidate": [
                            "03-invalid.envelope.json",
                            "02-no-action.envelope.json",
                            "01-ok.envelope.json",
                        ],
                    }
                ],
            )
            self.assertEqual(
                compare_payload["strict_profile"],
                {
                    "expected_status": "error",
                    "expected_changed_count": 0,
                    "expected_baseline_only_count": 0,
                    "expected_candidate_only_count": 0,
                    "expected_missing_baseline_count": 0,
                    "expected_missing_candidate_count": 0,
                    "expected_metadata_mismatches_count": 1,
                },
            )

    def test_eval_command_compare_checked_in_preset_fixtures_cover_clean_metadata_and_asymmetric_profiles(self) -> None:
        clean_result = self._run_cli(
            "eval",
            "--batch-output-compare",
            str(COMPARE_PRESET_FIXTURES / "candidate-clean"),
            "--batch-output-compare-against",
            str(COMPARE_PRESET_FIXTURES / "baseline"),
            "--batch-output-compare-profile",
            "clean",
            "--summary",
        )
        metadata_result = self._run_cli(
            "eval",
            "--batch-output-compare",
            str(COMPARE_PRESET_FIXTURES / "candidate-metadata-only"),
            "--batch-output-compare-against",
            str(COMPARE_PRESET_FIXTURES / "baseline"),
            "--batch-output-compare-profile",
            "metadata-only",
            "--batch-output-compare-expected-metadata-mismatches-count",
            "1",
            "--summary",
        )
        asymmetric_result = self._run_cli(
            "eval",
            "--batch-output-compare",
            str(COMPARE_PRESET_FIXTURES / "candidate-asymmetric"),
            "--batch-output-compare-against",
            str(COMPARE_PRESET_FIXTURES / "baseline"),
            "--batch-output-compare-profile",
            "expected-asymmetric-drift",
            "--batch-output-compare-expected-baseline-only-count",
            "3",
            "--batch-output-compare-expected-candidate-only-count",
            "2",
            "--batch-output-compare-expected-selected-baseline-count",
            "3",
            "--batch-output-compare-expected-selected-candidate-count",
            "2",
            "--batch-output-compare-expected-metadata-mismatches-count",
            "4",
            "--summary",
        )

        self.assertEqual(clean_result.returncode, 0)
        self.assertEqual(clean_result.stderr, "")
        self.assertEqual(
            clean_result.stdout,
            "status=ok compare_status=ok compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=3 selected_candidate=3 strict_mismatches=0\n",
        )

        self.assertEqual(metadata_result.returncode, 0)
        self.assertEqual(metadata_result.stderr, "")
        self.assertEqual(
            metadata_result.stdout,
            "status=ok compare_status=error compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=3 selected_candidate=3 strict_mismatches=0\n",
        )

        self.assertEqual(asymmetric_result.returncode, 0)
        self.assertEqual(asymmetric_result.stderr, "")
        self.assertEqual(
            asymmetric_result.stdout,
            "status=ok compare_status=error compared=0 matched=0 changed=0 baseline_only=3 candidate_only=2 missing_baseline=0 missing_candidate=0 metadata_mismatches=4 selected_baseline=3 selected_candidate=2 strict_mismatches=0\n",
        )

    def test_eval_command_path_predicate_example_fixture_is_copy_pasteable(self) -> None:
        ok_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-paths.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-path-ok.json"),
        )
        no_action_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-paths.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-path-no-action.json"),
        )
        no_action_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-paths.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-path-no-action.json"),
            "--summary",
        )

        self.assertEqual(ok_result.returncode, 0)
        self.assertEqual(ok_result.stderr, "")
        self.assertEqual(
            ok_result.stdout,
            PATH_PREDICATE_OK_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_result.returncode, 0)
        self.assertEqual(no_action_result.stderr, "")
        self.assertEqual(
            no_action_result.stdout,
            PATH_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_summary.returncode, 0)
        self.assertEqual(no_action_summary.stderr, "")
        self.assertEqual(
            no_action_summary.stdout,
            PATH_PREDICATE_NO_ACTION_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_string_predicate_example_fixture_is_copy_pasteable(self) -> None:
        ok_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-strings.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-string-ok.json"),
        )
        no_action_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-strings.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-string-no-action.json"),
        )
        no_action_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-strings.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-string-no-action.json"),
            "--summary",
        )

        self.assertEqual(ok_result.returncode, 0)
        self.assertEqual(ok_result.stderr, "")
        self.assertEqual(
            ok_result.stdout,
            STRING_PREDICATE_OK_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_result.returncode, 0)
        self.assertEqual(no_action_result.stderr, "")
        self.assertEqual(
            no_action_result.stdout,
            STRING_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_summary.returncode, 0)
        self.assertEqual(no_action_summary.stderr, "")
        self.assertEqual(
            no_action_summary.stdout,
            STRING_PREDICATE_NO_ACTION_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_length_predicate_example_fixture_is_copy_pasteable(self) -> None:
        ok_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-lengths.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-length-ok.json"),
        )
        no_action_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-lengths.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-length-no-action.json"),
        )
        no_action_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-lengths.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-length-no-action.json"),
            "--summary",
        )

        self.assertEqual(ok_result.returncode, 0)
        self.assertEqual(ok_result.stderr, "")
        self.assertEqual(
            ok_result.stdout,
            LENGTH_PREDICATE_OK_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_result.returncode, 0)
        self.assertEqual(no_action_result.stderr, "")
        self.assertEqual(
            no_action_result.stdout,
            LENGTH_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_summary.returncode, 0)
        self.assertEqual(no_action_summary.stderr, "")
        self.assertEqual(
            no_action_summary.stdout,
            LENGTH_PREDICATE_NO_ACTION_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_any_in_predicate_example_fixture_is_copy_pasteable(self) -> None:
        ok_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-any-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-any-in-ok.json"),
        )
        no_action_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-any-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-any-in-no-action.json"),
        )
        no_action_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-any-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-any-in-no-action.json"),
            "--summary",
        )

        self.assertEqual(ok_result.returncode, 0)
        self.assertEqual(ok_result.stderr, "")
        self.assertEqual(
            ok_result.stdout,
            ANY_IN_PREDICATE_OK_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_result.returncode, 0)
        self.assertEqual(no_action_result.stderr, "")
        self.assertEqual(
            no_action_result.stdout,
            ANY_IN_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_summary.returncode, 0)
        self.assertEqual(no_action_summary.stderr, "")
        self.assertEqual(
            no_action_summary.stdout,
            ANY_IN_PREDICATE_NO_ACTION_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_all_in_predicate_example_fixture_is_copy_pasteable(self) -> None:
        ok_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-all-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-all-in-ok.json"),
        )
        no_action_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-all-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-all-in-no-action.json"),
        )
        no_action_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-all-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-all-in-no-action.json"),
            "--summary",
        )

        self.assertEqual(ok_result.returncode, 0)
        self.assertEqual(ok_result.stderr, "")
        self.assertEqual(
            ok_result.stdout,
            ALL_IN_PREDICATE_OK_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_result.returncode, 0)
        self.assertEqual(no_action_result.stderr, "")
        self.assertEqual(
            no_action_result.stdout,
            ALL_IN_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_summary.returncode, 0)
        self.assertEqual(no_action_summary.stderr, "")
        self.assertEqual(
            no_action_summary.stdout,
            ALL_IN_PREDICATE_NO_ACTION_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_none_in_predicate_example_fixture_is_copy_pasteable(self) -> None:
        ok_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-none-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-none-in-ok.json"),
        )
        no_action_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-none-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-none-in-no-action.json"),
        )
        no_action_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-none-in.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-none-in-no-action.json"),
            "--summary",
        )

        self.assertEqual(ok_result.returncode, 0)
        self.assertEqual(ok_result.stderr, "")
        self.assertEqual(
            ok_result.stdout,
            NONE_IN_PREDICATE_OK_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_result.returncode, 0)
        self.assertEqual(no_action_result.stderr, "")
        self.assertEqual(
            no_action_result.stdout,
            NONE_IN_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_summary.returncode, 0)
        self.assertEqual(no_action_summary.stderr, "")
        self.assertEqual(
            no_action_summary.stdout,
            NONE_IN_PREDICATE_NO_ACTION_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_threshold_predicate_example_fixture_is_copy_pasteable(self) -> None:
        ok_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-thresholds.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-threshold-ok.json"),
        )
        no_action_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-thresholds.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-threshold-no-action.json"),
        )
        no_action_summary = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program-thresholds.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-threshold-no-action.json"),
            "--summary",
        )

        self.assertEqual(ok_result.returncode, 0)
        self.assertEqual(ok_result.stderr, "")
        self.assertEqual(
            ok_result.stdout,
            THRESHOLD_PREDICATE_OK_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_result.returncode, 0)
        self.assertEqual(no_action_result.stderr, "")
        self.assertEqual(
            no_action_result.stdout,
            THRESHOLD_PREDICATE_NO_ACTION_ENVELOPE_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(no_action_summary.returncode, 0)
        self.assertEqual(no_action_summary.stderr, "")
        self.assertEqual(
            no_action_summary.stdout,
            THRESHOLD_PREDICATE_NO_ACTION_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_threshold_handoff_verify_fixtures_are_copy_pasteable(self) -> None:
        baseline_result = self._run_cli(
            "eval",
            "--batch-output-verify",
            str(THRESHOLD_HANDOFF_FIXTURES / "baseline"),
            "--summary",
            "--batch-output-verify-profile",
            "default",
            "--batch-output-verify-require-run-id",
            "--batch-output-verify-expected-run-id-pattern",
            "^threshold-ci-.*$",
            "--batch-output-verify-expected-event-count",
            "3",
        )
        triage_result = self._run_cli(
            "eval",
            "--batch-output-verify",
            str(THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"),
            "--summary",
            "--batch-output-verify-profile",
            "triage-by-status",
            "--batch-output-verify-require-run-id",
            "--batch-output-verify-expected-run-id-pattern",
            "^threshold-ci-.*$",
            "--batch-output-verify-expected-event-count",
            "3",
        )

        self.assertEqual(baseline_result.returncode, 0)
        self.assertEqual(baseline_result.stderr, "")
        self.assertEqual(
            baseline_result.stdout,
            THRESHOLD_HANDOFF_BASELINE_VERIFY_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

        self.assertEqual(triage_result.returncode, 0)
        self.assertEqual(triage_result.stderr, "")
        self.assertEqual(
            triage_result.stdout,
            THRESHOLD_HANDOFF_TRIAGE_VERIFY_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_threshold_handoff_compare_fixture_is_copy_pasteable(self) -> None:
        compare_result = self._run_cli(
            "eval",
            "--batch-output-compare",
            str(THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"),
            "--batch-output-compare-against",
            str(THRESHOLD_HANDOFF_FIXTURES / "baseline"),
            "--summary",
            "--batch-output-compare-profile",
            "expected-asymmetric-drift",
            "--batch-output-compare-expected-baseline-only-count",
            "3",
            "--batch-output-compare-expected-candidate-only-count",
            "2",
            "--batch-output-compare-expected-selected-baseline-count",
            "3",
            "--batch-output-compare-expected-selected-candidate-count",
            "2",
            "--batch-output-compare-expected-metadata-mismatches-count",
            "4",
        )

        self.assertEqual(compare_result.returncode, 0)
        self.assertEqual(compare_result.stderr, "")
        self.assertEqual(
            compare_result.stdout,
            THRESHOLD_HANDOFF_COMPARE_SUMMARY_FIXTURE.read_text(encoding="utf-8"),
        )

    def test_eval_command_batch_output_compare_strict_selector_mismatch_fails_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            emit_candidate = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(candidate_dir),
            )

            self.assertEqual(emit_baseline.returncode, 0)
            self.assertEqual(emit_baseline.stderr, "")
            self.assertEqual(emit_candidate.returncode, 0)
            self.assertEqual(emit_candidate.stderr, "")

            tampered_artifact = candidate_dir / "01-ok.envelope.json"
            tampered_artifact.write_text(
                '{"event":"01-ok.json","actions":[{"kind":"notify","params":{"channel":"drift"}}],"trace":[]}\n',
                encoding="utf-8",
            )

            compare_result = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "error",
                "--batch-output-compare-expected-changed-count",
                "0",
            )
            compare_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "error",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--summary",
            )

            self.assertEqual(compare_result.returncode, 1)
            self.assertEqual(compare_result.stderr, "")
            self.assertEqual(compare_summary.returncode, 1)
            self.assertEqual(compare_summary.stderr, "")
            self.assertEqual(
                compare_summary.stdout,
                "status=error compare_status=error compared=3 matched=2 changed=1 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=3 selected_candidate=3 strict_mismatches=1\n",
            )
            self.assertEqual(
                json.loads(compare_result.stdout)["strict_profile_mismatches"],
                [
                    {
                        "field": "changed_artifacts.count",
                        "expected": 0,
                        "actual": 1,
                    }
                ],
            )

    def test_eval_command_batch_output_compare_strict_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            candidate_dir = Path(tmp_dir) / "candidate"
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            baseline_dir.mkdir(parents=True, exist_ok=True)

            strict_without_compare = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-compare-strict",
            )
            expected_without_strict = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-expected-compared-count",
                "1",
            )
            extended_expected_without_strict = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-expected-metadata-mismatches-count",
                "1",
            )
            action_plan_expected_without_strict = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
            )
            strict_without_selector = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
            )
            negative_selector = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-changed-count",
                "-1",
            )

            self.assertEqual(strict_without_compare.returncode, 1)
            self.assertEqual(strict_without_compare.stdout, "")
            self.assertEqual(
                strict_without_compare.stderr,
                "error: --batch-output-compare-strict requires --batch-output-compare\n",
            )

            self.assertEqual(expected_without_strict.returncode, 1)
            self.assertEqual(expected_without_strict.stdout, "")
            self.assertEqual(
                expected_without_strict.stderr,
                "error: --batch-output-compare-expected-compared-count requires strict compare\n",
            )

            self.assertEqual(extended_expected_without_strict.returncode, 1)
            self.assertEqual(extended_expected_without_strict.stdout, "")
            self.assertEqual(
                extended_expected_without_strict.stderr,
                "error: --batch-output-compare-expected-metadata-mismatches-count requires strict compare\n",
            )

            self.assertEqual(action_plan_expected_without_strict.returncode, 1)
            self.assertEqual(action_plan_expected_without_strict.stdout, "")
            self.assertEqual(
                action_plan_expected_without_strict.stderr,
                "error: --batch-output-compare-expected-baseline-action-plan-count requires strict compare\n",
            )

            self.assertEqual(strict_without_selector.returncode, 1)
            self.assertEqual(strict_without_selector.stdout, "")
            self.assertEqual(
                strict_without_selector.stderr,
                "error: --batch-output-compare-strict requires at least one --batch-output-compare-expected-* selector or --batch-output-compare-profile\n",
            )

            self.assertEqual(negative_selector.returncode, 1)
            self.assertEqual(negative_selector.stdout, "")
            self.assertEqual(
                negative_selector.stderr,
                "error: --batch-output-compare-expected-changed-count must be >= 0\n",
            )

    def test_eval_command_batch_output_self_compare_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "candidate"
            baseline_dir = Path(tmp_dir) / "baseline"

            strict_without_against = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-compare-strict",
            )
            self_compare_without_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-self-compare-against",
                str(baseline_dir),
            )
            self_compare_empty = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-compare-against",
                "",
            )
            profile_without_self_compare_strict = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-profile",
                "clean",
            )
            expected_without_self_compare_strict = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-expected-changed-count",
                "0",
            )
            self_compare_with_compare = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(output_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
            )
            self_compare_strict_with_compare = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(output_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-self-compare-strict",
            )
            self_compare_missing_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
            )
            baseline_generation = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            self_compare_summary_file_same_as_output = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(Path(tmp_dir) / "compare-output-collision.txt"),
                "--output",
                str(Path(tmp_dir) / "compare-output-collision.txt"),
            )
            self_compare_json_file_same_as_output = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-json-file",
                str(Path(tmp_dir) / "compare-output-collision.json"),
                "--output",
                str(Path(tmp_dir) / "compare-output-collision.json"),
            )
            self_compare_summary_file_same_as_batch_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-summary-file",
                str(Path(tmp_dir) / "batch-compare-collision.json"),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(Path(tmp_dir) / "batch-compare-collision.json"),
            )
            self_compare_json_file_same_as_batch_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-summary-file",
                str(Path(tmp_dir) / "batch-compare-json-collision.json"),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-json-file",
                str(Path(tmp_dir) / "batch-compare-json-collision.json"),
            )
            compare_summary_file_same_as_self_verify_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-summary-file",
                str(Path(tmp_dir) / "self-verify-compare-summary-collision.json"),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(Path(tmp_dir) / "self-verify-compare-summary-collision.json"),
            )
            compare_json_file_same_as_self_verify_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-summary-file",
                str(Path(tmp_dir) / "self-verify-compare-cross-collision.json"),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-json-file",
                str(Path(tmp_dir) / "self-verify-compare-cross-collision.json"),
            )
            compare_summary_file_same_as_self_verify_json = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-json-file",
                str(Path(tmp_dir) / "self-verify-compare-summary-json-collision.json"),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(Path(tmp_dir) / "self-verify-compare-summary-json-collision.json"),
            )
            compare_json_file_same_as_self_verify_json = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-json-file",
                str(Path(tmp_dir) / "self-verify-compare-json-collision.json"),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-json-file",
                str(Path(tmp_dir) / "self-verify-compare-json-collision.json"),
            )
            selector_miss_output_dir = Path(tmp_dir) / "candidate-selector-miss"
            self_compare_selector_miss = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(selector_miss_output_dir),
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-include",
                "*.does-not-match",
            )

            self.assertEqual(strict_without_against.returncode, 1)
            self.assertEqual(strict_without_against.stdout, "")
            self.assertEqual(
                strict_without_against.stderr,
                "error: --batch-output-self-compare-strict requires --batch-output-self-compare-against\n",
            )

            self.assertEqual(self_compare_without_output_dir.returncode, 1)
            self.assertEqual(self_compare_without_output_dir.stdout, "")
            self.assertEqual(
                self_compare_without_output_dir.stderr,
                "error: --batch-output-self-compare-against requires --batch-output\n",
            )

            self.assertEqual(self_compare_empty.returncode, 1)
            self.assertEqual(self_compare_empty.stdout, "")
            self.assertEqual(
                self_compare_empty.stderr,
                "error: --batch-output-self-compare-against must be non-empty when provided\n",
            )

            self.assertEqual(profile_without_self_compare_strict.returncode, 1)
            self.assertEqual(profile_without_self_compare_strict.stdout, "")
            self.assertEqual(
                profile_without_self_compare_strict.stderr,
                "error: --batch-output-compare-profile requires --batch-output-self-compare-strict\n",
            )

            self.assertEqual(expected_without_self_compare_strict.returncode, 1)
            self.assertEqual(expected_without_self_compare_strict.stdout, "")
            self.assertEqual(
                expected_without_self_compare_strict.stderr,
                "error: --batch-output-compare-expected-changed-count requires --batch-output-self-compare-strict\n",
            )

            self.assertEqual(self_compare_with_compare.returncode, 1)
            self.assertEqual(self_compare_with_compare.stdout, "")
            self.assertEqual(
                self_compare_with_compare.stderr,
                "error: --batch-output-self-compare-against is not supported with --batch-output-compare\n",
            )

            self.assertEqual(self_compare_strict_with_compare.returncode, 1)
            self.assertEqual(self_compare_strict_with_compare.stdout, "")
            self.assertEqual(
                self_compare_strict_with_compare.stderr,
                "error: --batch-output-self-compare-strict is not supported with --batch-output-compare\n",
            )

            self.assertEqual(self_compare_missing_baseline.returncode, 1)
            self.assertEqual(self_compare_missing_baseline.stdout, "")
            self.assertEqual(
                self_compare_missing_baseline.stderr,
                "error: --batch-output-self-compare-against must point to an existing directory\n",
            )

            self.assertEqual(baseline_generation.returncode, 0)
            self.assertEqual(baseline_generation.stderr, "")

            self.assertEqual(self_compare_summary_file_same_as_output.returncode, 1)
            self.assertEqual(self_compare_summary_file_same_as_output.stdout, "")
            self.assertEqual(
                self_compare_summary_file_same_as_output.stderr,
                "error: --output must differ from --batch-output-compare-summary-file so eval output cannot overwrite the compare sidecar\n",
            )

            self.assertEqual(self_compare_json_file_same_as_output.returncode, 1)
            self.assertEqual(self_compare_json_file_same_as_output.stdout, "")
            self.assertEqual(
                self_compare_json_file_same_as_output.stderr,
                "error: --output must differ from --batch-output-compare-json-file so eval output cannot overwrite the compare sidecar\n",
            )

            self.assertEqual(self_compare_summary_file_same_as_batch_summary.returncode, 1)
            self.assertEqual(self_compare_summary_file_same_as_batch_summary.stdout, "")
            self.assertEqual(
                self_compare_summary_file_same_as_batch_summary.stderr,
                "error: --batch-output-summary-file must differ from --batch-output-compare-summary-file so the batch aggregate sidecar cannot be overwritten\n",
            )

            self.assertEqual(self_compare_json_file_same_as_batch_summary.returncode, 1)
            self.assertEqual(self_compare_json_file_same_as_batch_summary.stdout, "")
            self.assertEqual(
                self_compare_json_file_same_as_batch_summary.stderr,
                "error: --batch-output-summary-file must differ from --batch-output-compare-json-file so the batch aggregate sidecar cannot be overwritten\n",
            )

            self.assertEqual(compare_summary_file_same_as_self_verify_summary.returncode, 1)
            self.assertEqual(compare_summary_file_same_as_self_verify_summary.stdout, "")
            self.assertEqual(
                compare_summary_file_same_as_self_verify_summary.stderr,
                "error: --batch-output-compare-summary-file must differ from --batch-output-self-verify-summary-file so compare output cannot overwrite the self-verify sidecar\n",
            )

            self.assertEqual(compare_json_file_same_as_self_verify_summary.returncode, 1)
            self.assertEqual(compare_json_file_same_as_self_verify_summary.stdout, "")
            self.assertEqual(
                compare_json_file_same_as_self_verify_summary.stderr,
                "error: --batch-output-compare-json-file must differ from --batch-output-self-verify-summary-file so compare output cannot overwrite the self-verify sidecar\n",
            )

            self.assertEqual(compare_summary_file_same_as_self_verify_json.returncode, 1)
            self.assertEqual(compare_summary_file_same_as_self_verify_json.stdout, "")
            self.assertEqual(
                compare_summary_file_same_as_self_verify_json.stderr,
                "error: --batch-output-compare-summary-file must differ from --batch-output-self-verify-json-file so compare output cannot overwrite the self-verify sidecar\n",
            )

            self.assertEqual(compare_json_file_same_as_self_verify_json.returncode, 1)
            self.assertEqual(compare_json_file_same_as_self_verify_json.stdout, "")
            self.assertEqual(
                compare_json_file_same_as_self_verify_json.stderr,
                "error: --batch-output-compare-json-file must differ from --batch-output-self-verify-json-file so compare output cannot overwrite the self-verify sidecar\n",
            )

            self.assertEqual(self_compare_selector_miss.returncode, 1)
            self.assertEqual(self_compare_selector_miss.stdout, "")
            self.assertEqual(
                self_compare_selector_miss.stderr,
                "error: --batch-output-self-compare selectors matched no artifacts (include='*.does-not-match', exclude='<none>')\n",
            )

    def test_eval_command_batch_output_compare_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            candidate_dir = Path(tmp_dir) / "candidate"
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            baseline_dir.mkdir(parents=True, exist_ok=True)

            compare_without_against = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
            )
            against_without_compare = self._run_cli(
                "eval",
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            compare_missing_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            compare_with_batch = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
            )
            compare_with_verify = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-verify",
                str(candidate_dir),
            )
            compare_summary_file_without_compare = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-compare-summary-file",
                str(candidate_dir / "compare.json"),
            )
            compare_json_file_without_compare = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-compare-json-file",
                str(candidate_dir / "compare-sidecar.json"),
            )
            compare_summary_file_empty = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                "",
            )
            compare_json_file_empty = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-json-file",
                "",
            )
            compare_summary_file_same_as_output = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(Path(tmp_dir) / "compare-output-collision.txt"),
                "--output",
                str(Path(tmp_dir) / "compare-output-collision.txt"),
            )
            compare_json_file_same_as_output = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-json-file",
                str(Path(tmp_dir) / "compare-output-collision.json"),
                "--output",
                str(Path(tmp_dir) / "compare-output-collision.json"),
            )
            compare_summary_and_json_same_path_with_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
                "--batch-output-compare-summary-file",
                str(Path(tmp_dir) / "compare-sidecar-same-path.txt"),
                "--batch-output-compare-json-file",
                str(Path(tmp_dir) / "compare-sidecar-same-path.txt"),
            )
            compare_with_verify_json_file = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-verify-json-file",
                str(candidate_dir / "verify-sidecar.json"),
            )
            compare_with_self_verify_summary_file = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-self-verify-summary-file",
                str(candidate_dir / "self-verify.summary.txt"),
            )
            compare_with_self_verify_json_file = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-self-verify-json-file",
                str(candidate_dir / "self-verify.json"),
            )

            self.assertEqual(compare_without_against.returncode, 1)
            self.assertEqual(compare_without_against.stdout, "")
            self.assertEqual(
                compare_without_against.stderr,
                "error: --batch-output-compare requires --batch-output-compare-against\n",
            )

            self.assertEqual(against_without_compare.returncode, 1)
            self.assertEqual(against_without_compare.stdout, "")
            self.assertEqual(
                against_without_compare.stderr,
                "error: --batch-output-compare-against requires --batch-output-compare\n",
            )

            self.assertEqual(compare_missing_summary.returncode, 1)
            self.assertEqual(compare_missing_summary.stdout, "")
            self.assertEqual(
                compare_missing_summary.stderr,
                "error: --batch-output-compare directory must contain summary.json\n",
            )

            self.assertEqual(compare_with_batch.returncode, 1)
            self.assertEqual(compare_with_batch.stdout, "")
            self.assertEqual(
                compare_with_batch.stderr,
                "error: --batch-output-compare cannot be combined with --input or --batch\n",
            )

            self.assertEqual(compare_with_verify.returncode, 1)
            self.assertEqual(compare_with_verify.stdout, "")
            self.assertEqual(
                compare_with_verify.stderr,
                "error: --batch-output-verify is not supported with --batch-output-compare\n",
            )

            self.assertEqual(compare_summary_file_without_compare.returncode, 1)
            self.assertEqual(compare_summary_file_without_compare.stdout, "")
            self.assertEqual(
                compare_summary_file_without_compare.stderr,
                "error: --batch-output-compare-summary-file requires --batch-output-compare or --batch-output-self-compare-against\n",
            )

            self.assertEqual(compare_json_file_without_compare.returncode, 1)
            self.assertEqual(compare_json_file_without_compare.stdout, "")
            self.assertEqual(
                compare_json_file_without_compare.stderr,
                "error: --batch-output-compare-json-file requires --batch-output-compare or --batch-output-self-compare-against\n",
            )

            self.assertEqual(compare_summary_file_empty.returncode, 1)
            self.assertEqual(compare_summary_file_empty.stdout, "")
            self.assertEqual(
                compare_summary_file_empty.stderr,
                "error: --batch-output-compare-summary-file must be non-empty when provided\n",
            )

            self.assertEqual(compare_json_file_empty.returncode, 1)
            self.assertEqual(compare_json_file_empty.stdout, "")
            self.assertEqual(
                compare_json_file_empty.stderr,
                "error: --batch-output-compare-json-file must be non-empty when provided\n",
            )

            self.assertEqual(compare_summary_file_same_as_output.returncode, 1)
            self.assertEqual(compare_summary_file_same_as_output.stdout, "")
            self.assertEqual(
                compare_summary_file_same_as_output.stderr,
                "error: --output must differ from --batch-output-compare-summary-file so eval output cannot overwrite the compare sidecar\n",
            )

            self.assertEqual(compare_json_file_same_as_output.returncode, 1)
            self.assertEqual(compare_json_file_same_as_output.stdout, "")
            self.assertEqual(
                compare_json_file_same_as_output.stderr,
                "error: --output must differ from --batch-output-compare-json-file so eval output cannot overwrite the compare sidecar\n",
            )

            self.assertEqual(compare_summary_and_json_same_path_with_summary.returncode, 1)
            self.assertEqual(compare_summary_and_json_same_path_with_summary.stdout, "")
            self.assertEqual(
                compare_summary_and_json_same_path_with_summary.stderr,
                "error: --batch-output-compare-summary-file and --batch-output-compare-json-file must differ when --summary is set\n",
            )

            self.assertEqual(compare_with_verify_json_file.returncode, 1)
            self.assertEqual(compare_with_verify_json_file.stdout, "")
            self.assertEqual(
                compare_with_verify_json_file.stderr,
                "error: --batch-output-verify-json-file is not supported with --batch-output-compare\n",
            )

            self.assertEqual(compare_with_self_verify_summary_file.returncode, 1)
            self.assertEqual(compare_with_self_verify_summary_file.stdout, "")
            self.assertEqual(
                compare_with_self_verify_summary_file.stderr,
                "error: --batch-output-self-verify-summary-file is not supported with --batch-output-compare\n",
            )

            self.assertEqual(compare_with_self_verify_json_file.returncode, 1)
            self.assertEqual(compare_with_self_verify_json_file.stdout, "")
            self.assertEqual(
                compare_with_self_verify_json_file.stderr,
                "error: --batch-output-self-verify-json-file is not supported with --batch-output-compare\n",
            )

    def test_eval_command_batch_output_verify_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            output_dir.mkdir(parents=True, exist_ok=True)

            verify_with_batch = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-verify",
                str(output_dir),
            )
            verify_without_summary_artifact = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )

            (output_dir / "summary.json").write_text(
                '{"mode":"all","event_artifacts":["01-ok.envelope.json"]}\n',
                encoding="utf-8",
            )
            verify_without_manifest = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
            )
            missing_inputs = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
            )
            strict_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-strict",
            )
            profile_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-profile",
                "default",
            )
            verify_summary_file_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-summary-file",
                str(output_dir / "verify-summary.txt"),
            )
            verify_json_file_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-json-file",
                str(output_dir / "verify-sidecar.json"),
            )
            verify_include_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-include",
                "*ok*",
            )
            verify_exclude_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-exclude",
                "*invalid*",
            )
            verify_summary_file_empty = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-summary-file",
                "",
            )
            verify_json_file_empty = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-json-file",
                "",
            )
            verify_include_empty = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-include",
                "",
            )
            verify_exclude_empty = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-exclude",
                "",
            )
            expected_mode_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-mode",
                "all",
            )
            expected_event_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-event-count",
                "3",
            )
            expected_event_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-event-count",
                "3",
            )
            expected_event_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "-1",
            )
            expected_verified_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-verified-count",
                "3",
            )
            expected_verified_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-verified-count",
                "3",
            )
            expected_verified_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-verified-count",
                "-1",
            )
            expected_checked_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-checked-count",
                "3",
            )
            expected_checked_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-checked-count",
                "3",
            )
            expected_checked_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-checked-count",
                "-1",
            )
            expected_missing_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-missing-count",
                "1",
            )
            expected_missing_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-missing-count",
                "1",
            )
            expected_missing_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-missing-count",
                "-1",
            )
            expected_mismatched_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-mismatched-count",
                "1",
            )
            expected_mismatched_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-mismatched-count",
                "1",
            )
            expected_mismatched_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-mismatched-count",
                "-1",
            )
            expected_manifest_missing_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-manifest-missing-count",
                "1",
            )
            expected_manifest_missing_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-manifest-missing-count",
                "1",
            )
            expected_manifest_missing_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-missing-count",
                "-1",
            )
            expected_invalid_hashes_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-invalid-hashes-count",
                "1",
            )
            expected_invalid_hashes_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-invalid-hashes-count",
                "1",
            )
            expected_invalid_hashes_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-invalid-hashes-count",
                "-1",
            )
            expected_unexpected_manifest_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-unexpected-manifest-count",
                "1",
            )
            expected_unexpected_manifest_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-unexpected-manifest-count",
                "1",
            )
            expected_unexpected_manifest_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-unexpected-manifest-count",
                "-1",
            )
            expected_status_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-status",
                "ok",
            )
            expected_status_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-status",
                "ok",
            )
            expected_strict_mismatches_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-strict-mismatches-count",
                "0",
            )
            expected_strict_mismatches_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-strict-mismatches-count",
                "0",
            )
            expected_strict_mismatches_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-strict-mismatches-count",
                "-1",
            )
            expected_event_artifact_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-event-artifact-count",
                "3",
            )
            expected_event_artifact_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-event-artifact-count",
                "3",
            )
            expected_event_artifact_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-artifact-count",
                "-1",
            )
            expected_manifest_entry_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-manifest-entry-count",
                "3",
            )
            expected_manifest_entry_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-manifest-entry-count",
                "3",
            )
            expected_manifest_entry_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-entry-count",
                "-1",
            )
            expected_selected_artifact_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-selected-artifact-count",
                "1",
            )
            expected_selected_artifact_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-selected-artifact-count",
                "1",
            )
            expected_selected_artifact_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-selected-artifact-count",
                "-1",
            )
            expected_manifest_selected_entry_count_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-expected-manifest-selected-entry-count",
                "1",
            )
            expected_manifest_selected_entry_count_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-expected-manifest-selected-entry-count",
                "1",
            )
            expected_manifest_selected_entry_count_negative = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-manifest-selected-entry-count",
                "-1",
            )
            invalid_run_id_pattern = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-run-id-pattern",
                "[",
            )
            require_run_id_without_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-verify-require-run-id",
            )
            require_run_id_without_strict = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-require-run-id",
            )
            self_verify_with_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-self-verify",
            )
            self_verify_summary_file_with_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-self-verify-summary-file",
                str(output_dir / "self-verify.summary.txt"),
            )
            self_verify_json_file_with_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-self-verify-json-file",
                str(output_dir / "self-verify.json"),
            )
            summary_file_with_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-summary-file",
                str(output_dir / "aggregate.json"),
            )
            self_verify_strict_with_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-self-verify-strict",
            )
            self_verify_strict_without_self_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify-strict",
            )

            self.assertEqual(verify_with_batch.returncode, 1)
            self.assertEqual(verify_with_batch.stdout, "")
            self.assertEqual(
                verify_with_batch.stderr,
                "error: --batch-output-verify cannot be combined with --input or --batch\n",
            )

            self.assertEqual(verify_without_summary_artifact.returncode, 1)
            self.assertEqual(verify_without_summary_artifact.stdout, "")
            self.assertEqual(
                verify_without_summary_artifact.stderr,
                "error: --batch-output-verify directory must contain summary.json\n",
            )

            self.assertEqual(verify_without_manifest.returncode, 1)
            self.assertEqual(verify_without_manifest.stdout, "")
            self.assertEqual(
                verify_without_manifest.stderr,
                "error: --batch-output-verify summary.json must contain artifact_sha256 object (run eval with --batch-output-manifest)\n",
            )

            self.assertEqual(missing_inputs.returncode, 1)
            self.assertEqual(missing_inputs.stdout, "")
            self.assertEqual(missing_inputs.stderr, "error: one of --input or --batch is required\n")

            self.assertEqual(strict_without_verify.returncode, 1)
            self.assertEqual(strict_without_verify.stdout, "")
            self.assertEqual(
                strict_without_verify.stderr,
                "error: --batch-output-verify-strict requires --batch-output-verify\n",
            )

            self.assertEqual(profile_without_verify.returncode, 1)
            self.assertEqual(profile_without_verify.stdout, "")
            self.assertEqual(
                profile_without_verify.stderr,
                "error: --batch-output-verify-profile requires --batch-output-verify\n",
            )

            self.assertEqual(verify_summary_file_without_verify.returncode, 1)
            self.assertEqual(verify_summary_file_without_verify.stdout, "")
            self.assertEqual(
                verify_summary_file_without_verify.stderr,
                "error: --batch-output-verify-summary-file requires --batch-output-verify\n",
            )

            self.assertEqual(verify_json_file_without_verify.returncode, 1)
            self.assertEqual(verify_json_file_without_verify.stdout, "")
            self.assertEqual(
                verify_json_file_without_verify.stderr,
                "error: --batch-output-verify-json-file requires --batch-output-verify\n",
            )

            self.assertEqual(verify_include_without_verify.returncode, 1)
            self.assertEqual(verify_include_without_verify.stdout, "")
            self.assertEqual(
                verify_include_without_verify.stderr,
                "error: --batch-output-verify-include requires --batch-output-verify\n",
            )

            self.assertEqual(verify_exclude_without_verify.returncode, 1)
            self.assertEqual(verify_exclude_without_verify.stdout, "")
            self.assertEqual(
                verify_exclude_without_verify.stderr,
                "error: --batch-output-verify-exclude requires --batch-output-verify\n",
            )

            self.assertEqual(verify_summary_file_empty.returncode, 1)
            self.assertEqual(verify_summary_file_empty.stdout, "")
            self.assertEqual(
                verify_summary_file_empty.stderr,
                "error: --batch-output-verify-summary-file must be non-empty when provided\n",
            )

            self.assertEqual(verify_json_file_empty.returncode, 1)
            self.assertEqual(verify_json_file_empty.stdout, "")
            self.assertEqual(
                verify_json_file_empty.stderr,
                "error: --batch-output-verify-json-file must be non-empty when provided\n",
            )

            self.assertEqual(verify_include_empty.returncode, 1)
            self.assertEqual(verify_include_empty.stdout, "")
            self.assertEqual(
                verify_include_empty.stderr,
                "error: --batch-output-verify-include must be non-empty when provided\n",
            )

            self.assertEqual(verify_exclude_empty.returncode, 1)
            self.assertEqual(verify_exclude_empty.stdout, "")
            self.assertEqual(
                verify_exclude_empty.stderr,
                "error: --batch-output-verify-exclude must be non-empty when provided\n",
            )

            self.assertEqual(expected_mode_without_strict.returncode, 1)
            self.assertEqual(expected_mode_without_strict.stdout, "")
            self.assertEqual(
                expected_mode_without_strict.stderr,
                "error: --batch-output-verify-expected-mode requires strict verify\n",
            )

            self.assertEqual(expected_event_count_without_verify.returncode, 1)
            self.assertEqual(expected_event_count_without_verify.stdout, "")
            self.assertEqual(
                expected_event_count_without_verify.stderr,
                "error: --batch-output-verify-expected-event-count requires strict verify\n",
            )

            self.assertEqual(expected_event_count_without_strict.returncode, 1)
            self.assertEqual(expected_event_count_without_strict.stdout, "")
            self.assertEqual(
                expected_event_count_without_strict.stderr,
                "error: --batch-output-verify-expected-event-count requires strict verify\n",
            )

            self.assertEqual(expected_event_count_negative.returncode, 1)
            self.assertEqual(expected_event_count_negative.stdout, "")
            self.assertEqual(
                expected_event_count_negative.stderr,
                "error: --batch-output-verify-expected-event-count must be >= 0\n",
            )

            self.assertEqual(expected_verified_count_without_verify.returncode, 1)
            self.assertEqual(expected_verified_count_without_verify.stdout, "")
            self.assertEqual(
                expected_verified_count_without_verify.stderr,
                "error: --batch-output-verify-expected-verified-count requires strict verify\n",
            )

            self.assertEqual(expected_verified_count_without_strict.returncode, 1)
            self.assertEqual(expected_verified_count_without_strict.stdout, "")
            self.assertEqual(
                expected_verified_count_without_strict.stderr,
                "error: --batch-output-verify-expected-verified-count requires strict verify\n",
            )

            self.assertEqual(expected_verified_count_negative.returncode, 1)
            self.assertEqual(expected_verified_count_negative.stdout, "")
            self.assertEqual(
                expected_verified_count_negative.stderr,
                "error: --batch-output-verify-expected-verified-count must be >= 0\n",
            )

            self.assertEqual(expected_checked_count_without_verify.returncode, 1)
            self.assertEqual(expected_checked_count_without_verify.stdout, "")
            self.assertEqual(
                expected_checked_count_without_verify.stderr,
                "error: --batch-output-verify-expected-checked-count requires strict verify\n",
            )

            self.assertEqual(expected_checked_count_without_strict.returncode, 1)
            self.assertEqual(expected_checked_count_without_strict.stdout, "")
            self.assertEqual(
                expected_checked_count_without_strict.stderr,
                "error: --batch-output-verify-expected-checked-count requires strict verify\n",
            )

            self.assertEqual(expected_checked_count_negative.returncode, 1)
            self.assertEqual(expected_checked_count_negative.stdout, "")
            self.assertEqual(
                expected_checked_count_negative.stderr,
                "error: --batch-output-verify-expected-checked-count must be >= 0\n",
            )

            self.assertEqual(expected_missing_count_without_verify.returncode, 1)
            self.assertEqual(expected_missing_count_without_verify.stdout, "")
            self.assertEqual(
                expected_missing_count_without_verify.stderr,
                "error: --batch-output-verify-expected-missing-count requires strict verify\n",
            )

            self.assertEqual(expected_missing_count_without_strict.returncode, 1)
            self.assertEqual(expected_missing_count_without_strict.stdout, "")
            self.assertEqual(
                expected_missing_count_without_strict.stderr,
                "error: --batch-output-verify-expected-missing-count requires strict verify\n",
            )

            self.assertEqual(expected_missing_count_negative.returncode, 1)
            self.assertEqual(expected_missing_count_negative.stdout, "")
            self.assertEqual(
                expected_missing_count_negative.stderr,
                "error: --batch-output-verify-expected-missing-count must be >= 0\n",
            )

            self.assertEqual(expected_mismatched_count_without_verify.returncode, 1)
            self.assertEqual(expected_mismatched_count_without_verify.stdout, "")
            self.assertEqual(
                expected_mismatched_count_without_verify.stderr,
                "error: --batch-output-verify-expected-mismatched-count requires strict verify\n",
            )

            self.assertEqual(expected_mismatched_count_without_strict.returncode, 1)
            self.assertEqual(expected_mismatched_count_without_strict.stdout, "")
            self.assertEqual(
                expected_mismatched_count_without_strict.stderr,
                "error: --batch-output-verify-expected-mismatched-count requires strict verify\n",
            )

            self.assertEqual(expected_mismatched_count_negative.returncode, 1)
            self.assertEqual(expected_mismatched_count_negative.stdout, "")
            self.assertEqual(
                expected_mismatched_count_negative.stderr,
                "error: --batch-output-verify-expected-mismatched-count must be >= 0\n",
            )

            self.assertEqual(expected_manifest_missing_count_without_verify.returncode, 1)
            self.assertEqual(expected_manifest_missing_count_without_verify.stdout, "")
            self.assertEqual(
                expected_manifest_missing_count_without_verify.stderr,
                "error: --batch-output-verify-expected-manifest-missing-count requires strict verify\n",
            )

            self.assertEqual(expected_manifest_missing_count_without_strict.returncode, 1)
            self.assertEqual(expected_manifest_missing_count_without_strict.stdout, "")
            self.assertEqual(
                expected_manifest_missing_count_without_strict.stderr,
                "error: --batch-output-verify-expected-manifest-missing-count requires strict verify\n",
            )

            self.assertEqual(expected_manifest_missing_count_negative.returncode, 1)
            self.assertEqual(expected_manifest_missing_count_negative.stdout, "")
            self.assertEqual(
                expected_manifest_missing_count_negative.stderr,
                "error: --batch-output-verify-expected-manifest-missing-count must be >= 0\n",
            )

            self.assertEqual(expected_invalid_hashes_count_without_verify.returncode, 1)
            self.assertEqual(expected_invalid_hashes_count_without_verify.stdout, "")
            self.assertEqual(
                expected_invalid_hashes_count_without_verify.stderr,
                "error: --batch-output-verify-expected-invalid-hashes-count requires strict verify\n",
            )

            self.assertEqual(expected_invalid_hashes_count_without_strict.returncode, 1)
            self.assertEqual(expected_invalid_hashes_count_without_strict.stdout, "")
            self.assertEqual(
                expected_invalid_hashes_count_without_strict.stderr,
                "error: --batch-output-verify-expected-invalid-hashes-count requires strict verify\n",
            )

            self.assertEqual(expected_invalid_hashes_count_negative.returncode, 1)
            self.assertEqual(expected_invalid_hashes_count_negative.stdout, "")
            self.assertEqual(
                expected_invalid_hashes_count_negative.stderr,
                "error: --batch-output-verify-expected-invalid-hashes-count must be >= 0\n",
            )

            self.assertEqual(expected_unexpected_manifest_count_without_verify.returncode, 1)
            self.assertEqual(expected_unexpected_manifest_count_without_verify.stdout, "")
            self.assertEqual(
                expected_unexpected_manifest_count_without_verify.stderr,
                "error: --batch-output-verify-expected-unexpected-manifest-count requires strict verify\n",
            )

            self.assertEqual(expected_unexpected_manifest_count_without_strict.returncode, 1)
            self.assertEqual(expected_unexpected_manifest_count_without_strict.stdout, "")
            self.assertEqual(
                expected_unexpected_manifest_count_without_strict.stderr,
                "error: --batch-output-verify-expected-unexpected-manifest-count requires strict verify\n",
            )

            self.assertEqual(expected_unexpected_manifest_count_negative.returncode, 1)
            self.assertEqual(expected_unexpected_manifest_count_negative.stdout, "")
            self.assertEqual(
                expected_unexpected_manifest_count_negative.stderr,
                "error: --batch-output-verify-expected-unexpected-manifest-count must be >= 0\n",
            )

            self.assertEqual(expected_status_without_verify.returncode, 1)
            self.assertEqual(expected_status_without_verify.stdout, "")
            self.assertEqual(
                expected_status_without_verify.stderr,
                "error: --batch-output-verify-expected-status requires strict verify\n",
            )

            self.assertEqual(expected_status_without_strict.returncode, 1)
            self.assertEqual(expected_status_without_strict.stdout, "")
            self.assertEqual(
                expected_status_without_strict.stderr,
                "error: --batch-output-verify-expected-status requires strict verify\n",
            )

            self.assertEqual(expected_strict_mismatches_count_without_verify.returncode, 1)
            self.assertEqual(expected_strict_mismatches_count_without_verify.stdout, "")
            self.assertEqual(
                expected_strict_mismatches_count_without_verify.stderr,
                "error: --batch-output-verify-expected-strict-mismatches-count requires strict verify\n",
            )

            self.assertEqual(expected_strict_mismatches_count_without_strict.returncode, 1)
            self.assertEqual(expected_strict_mismatches_count_without_strict.stdout, "")
            self.assertEqual(
                expected_strict_mismatches_count_without_strict.stderr,
                "error: --batch-output-verify-expected-strict-mismatches-count requires strict verify\n",
            )

            self.assertEqual(expected_strict_mismatches_count_negative.returncode, 1)
            self.assertEqual(expected_strict_mismatches_count_negative.stdout, "")
            self.assertEqual(
                expected_strict_mismatches_count_negative.stderr,
                "error: --batch-output-verify-expected-strict-mismatches-count must be >= 0\n",
            )

            self.assertEqual(expected_event_artifact_count_without_verify.returncode, 1)
            self.assertEqual(expected_event_artifact_count_without_verify.stdout, "")
            self.assertEqual(
                expected_event_artifact_count_without_verify.stderr,
                "error: --batch-output-verify-expected-event-artifact-count requires strict verify\n",
            )

            self.assertEqual(expected_event_artifact_count_without_strict.returncode, 1)
            self.assertEqual(expected_event_artifact_count_without_strict.stdout, "")
            self.assertEqual(
                expected_event_artifact_count_without_strict.stderr,
                "error: --batch-output-verify-expected-event-artifact-count requires strict verify\n",
            )

            self.assertEqual(expected_event_artifact_count_negative.returncode, 1)
            self.assertEqual(expected_event_artifact_count_negative.stdout, "")
            self.assertEqual(
                expected_event_artifact_count_negative.stderr,
                "error: --batch-output-verify-expected-event-artifact-count must be >= 0\n",
            )

            self.assertEqual(expected_manifest_entry_count_without_verify.returncode, 1)
            self.assertEqual(expected_manifest_entry_count_without_verify.stdout, "")
            self.assertEqual(
                expected_manifest_entry_count_without_verify.stderr,
                "error: --batch-output-verify-expected-manifest-entry-count requires strict verify\n",
            )

            self.assertEqual(expected_manifest_entry_count_without_strict.returncode, 1)
            self.assertEqual(expected_manifest_entry_count_without_strict.stdout, "")
            self.assertEqual(
                expected_manifest_entry_count_without_strict.stderr,
                "error: --batch-output-verify-expected-manifest-entry-count requires strict verify\n",
            )

            self.assertEqual(expected_manifest_entry_count_negative.returncode, 1)
            self.assertEqual(expected_manifest_entry_count_negative.stdout, "")
            self.assertEqual(
                expected_manifest_entry_count_negative.stderr,
                "error: --batch-output-verify-expected-manifest-entry-count must be >= 0\n",
            )

            self.assertEqual(expected_selected_artifact_count_without_verify.returncode, 1)
            self.assertEqual(expected_selected_artifact_count_without_verify.stdout, "")
            self.assertEqual(
                expected_selected_artifact_count_without_verify.stderr,
                "error: --batch-output-verify-expected-selected-artifact-count requires strict verify\n",
            )

            self.assertEqual(expected_selected_artifact_count_without_strict.returncode, 1)
            self.assertEqual(expected_selected_artifact_count_without_strict.stdout, "")
            self.assertEqual(
                expected_selected_artifact_count_without_strict.stderr,
                "error: --batch-output-verify-expected-selected-artifact-count requires strict verify\n",
            )

            self.assertEqual(expected_selected_artifact_count_negative.returncode, 1)
            self.assertEqual(expected_selected_artifact_count_negative.stdout, "")
            self.assertEqual(
                expected_selected_artifact_count_negative.stderr,
                "error: --batch-output-verify-expected-selected-artifact-count must be >= 0\n",
            )

            self.assertEqual(expected_manifest_selected_entry_count_without_verify.returncode, 1)
            self.assertEqual(expected_manifest_selected_entry_count_without_verify.stdout, "")
            self.assertEqual(
                expected_manifest_selected_entry_count_without_verify.stderr,
                "error: --batch-output-verify-expected-manifest-selected-entry-count requires strict verify\n",
            )

            self.assertEqual(expected_manifest_selected_entry_count_without_strict.returncode, 1)
            self.assertEqual(expected_manifest_selected_entry_count_without_strict.stdout, "")
            self.assertEqual(
                expected_manifest_selected_entry_count_without_strict.stderr,
                "error: --batch-output-verify-expected-manifest-selected-entry-count requires strict verify\n",
            )

            self.assertEqual(expected_manifest_selected_entry_count_negative.returncode, 1)
            self.assertEqual(expected_manifest_selected_entry_count_negative.stdout, "")
            self.assertEqual(
                expected_manifest_selected_entry_count_negative.stderr,
                "error: --batch-output-verify-expected-manifest-selected-entry-count must be >= 0\n",
            )

            self.assertEqual(invalid_run_id_pattern.returncode, 1)
            self.assertEqual(invalid_run_id_pattern.stdout, "")
            self.assertIn(
                "error: --batch-output-verify-expected-run-id-pattern must be a valid regex:",
                invalid_run_id_pattern.stderr,
            )

            self.assertEqual(require_run_id_without_verify.returncode, 1)
            self.assertEqual(require_run_id_without_verify.stdout, "")
            self.assertEqual(
                require_run_id_without_verify.stderr,
                "error: --batch-output-verify-require-run-id requires --batch-output-verify\n",
            )

            self.assertEqual(require_run_id_without_strict.returncode, 1)
            self.assertEqual(require_run_id_without_strict.stdout, "")
            self.assertEqual(
                require_run_id_without_strict.stderr,
                "error: --batch-output-verify-require-run-id requires strict verify\n",
            )

            self.assertEqual(self_verify_with_verify.returncode, 1)
            self.assertEqual(self_verify_with_verify.stdout, "")
            self.assertEqual(
                self_verify_with_verify.stderr,
                "error: --batch-output-self-verify is not supported with --batch-output-verify\n",
            )

            self.assertEqual(self_verify_summary_file_with_verify.returncode, 1)
            self.assertEqual(self_verify_summary_file_with_verify.stdout, "")
            self.assertEqual(
                self_verify_summary_file_with_verify.stderr,
                "error: --batch-output-self-verify-summary-file is not supported with --batch-output-verify\n",
            )

            self.assertEqual(self_verify_json_file_with_verify.returncode, 1)
            self.assertEqual(self_verify_json_file_with_verify.stdout, "")
            self.assertEqual(
                self_verify_json_file_with_verify.stderr,
                "error: --batch-output-self-verify-json-file is not supported with --batch-output-verify\n",
            )

            self.assertEqual(summary_file_with_verify.returncode, 1)
            self.assertEqual(summary_file_with_verify.stdout, "")
            self.assertEqual(
                summary_file_with_verify.stderr,
                "error: --batch-output-summary-file is not supported with --batch-output-verify\n",
            )

            self.assertEqual(self_verify_strict_with_verify.returncode, 1)
            self.assertEqual(self_verify_strict_with_verify.stdout, "")
            self.assertEqual(
                self_verify_strict_with_verify.stderr,
                "error: --batch-output-self-verify-strict is not supported with --batch-output-verify\n",
            )

            self.assertEqual(self_verify_strict_without_self_verify.returncode, 1)
            self.assertEqual(self_verify_strict_without_self_verify.stdout, "")
            self.assertEqual(
                self_verify_strict_without_self_verify.stderr,
                "error: --batch-output-self-verify-strict requires --batch-output-self-verify\n",
            )

    def test_eval_command_batch_output_flags_require_batch_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"

            batch_output_without_batch = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output",
                str(output_dir),
            )
            errors_only_without_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-errors-only",
            )
            manifest_without_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-manifest",
            )
            layout_without_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-layout",
                "by-status",
            )
            run_id_without_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-run-id",
                "ci-run-2026-03-06T20-30-00Z",
            )
            summary_file_without_batch = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--batch-output-summary-file",
                str(output_dir / "aggregate.json"),
            )
            summary_file_with_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--summary",
                "--batch-output-summary-file",
                str(output_dir / "aggregate.json"),
            )
            self_verify_without_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-self-verify",
            )
            self_verify_summary_file_without_self_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify-summary-file",
                str(output_dir / "self-verify.summary.txt"),
            )
            self_verify_json_file_without_self_verify = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify-json-file",
                str(output_dir / "self-verify.json"),
            )
            empty_run_id = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-run-id",
                "",
            )
            empty_summary_file = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-summary-file",
                "",
            )
            empty_self_verify_summary_file = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-summary-file",
                "",
            )
            empty_self_verify_json_file = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-json-file",
                "",
            )
            self_verify_summary_file_inside_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-summary-file",
                str(output_dir / "summary.json"),
            )
            self_verify_json_file_inside_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-json-file",
                str(output_dir / "self-verify.json"),
            )
            self_verify_summary_file_same_as_output = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-summary-file",
                str(Path(tmp_dir) / "collision.txt"),
                "--output",
                str(Path(tmp_dir) / "collision.txt"),
            )
            self_verify_json_file_same_as_output = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
                "--batch-output-self-verify-json-file",
                str(Path(tmp_dir) / "collision.json"),
                "--output",
                str(Path(tmp_dir) / "collision.json"),
            )
            self_verify_summary_and_json_same_path_with_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--summary",
                "--batch-output-self-verify",
                "--batch-output-self-verify-summary-file",
                str(Path(tmp_dir) / "same-sidecar-path.txt"),
                "--batch-output-self-verify-json-file",
                str(Path(tmp_dir) / "same-sidecar-path.txt"),
            )
            batch_output_summary_file_same_as_self_verify_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-summary-file",
                str(Path(tmp_dir) / "batch-sidecar-collision.json"),
                "--batch-output-self-verify",
                "--batch-output-self-verify-summary-file",
                str(Path(tmp_dir) / "batch-sidecar-collision.json"),
            )
            batch_output_summary_file_same_as_self_verify_json = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-summary-file",
                str(Path(tmp_dir) / "batch-json-collision.json"),
                "--batch-output-self-verify",
                "--batch-output-self-verify-json-file",
                str(Path(tmp_dir) / "batch-json-collision.json"),
            )

            self.assertEqual(batch_output_without_batch.returncode, 1)
            self.assertEqual(batch_output_without_batch.stdout, "")
            self.assertEqual(
                batch_output_without_batch.stderr,
                "error: --batch-output requires --batch\n",
            )

            self.assertEqual(errors_only_without_output_dir.returncode, 1)
            self.assertEqual(errors_only_without_output_dir.stdout, "")
            self.assertEqual(
                errors_only_without_output_dir.stderr,
                "error: --batch-output-errors-only requires --batch-output\n",
            )

            self.assertEqual(manifest_without_output_dir.returncode, 1)
            self.assertEqual(manifest_without_output_dir.stdout, "")
            self.assertEqual(
                manifest_without_output_dir.stderr,
                "error: --batch-output-manifest requires --batch-output\n",
            )

            self.assertEqual(layout_without_output_dir.returncode, 1)
            self.assertEqual(layout_without_output_dir.stdout, "")
            self.assertEqual(
                layout_without_output_dir.stderr,
                "error: --batch-output-layout requires --batch-output\n",
            )

            self.assertEqual(run_id_without_output_dir.returncode, 1)
            self.assertEqual(run_id_without_output_dir.stdout, "")
            self.assertEqual(
                run_id_without_output_dir.stderr,
                "error: --batch-output-run-id requires --batch-output\n",
            )

            self.assertEqual(summary_file_without_batch.returncode, 1)
            self.assertEqual(summary_file_without_batch.stdout, "")
            self.assertEqual(
                summary_file_without_batch.stderr,
                "error: --batch-output-summary-file requires --batch\n",
            )

            self.assertEqual(summary_file_with_summary.returncode, 1)
            self.assertEqual(summary_file_with_summary.stdout, "")
            self.assertEqual(
                summary_file_with_summary.stderr,
                "error: --batch-output-summary-file is not supported with --summary\n",
            )

            self.assertEqual(self_verify_without_output_dir.returncode, 1)
            self.assertEqual(self_verify_without_output_dir.stdout, "")
            self.assertEqual(
                self_verify_without_output_dir.stderr,
                "error: --batch-output-self-verify requires --batch-output\n",
            )

            self.assertEqual(self_verify_summary_file_without_self_verify.returncode, 1)
            self.assertEqual(self_verify_summary_file_without_self_verify.stdout, "")
            self.assertEqual(
                self_verify_summary_file_without_self_verify.stderr,
                "error: --batch-output-self-verify-summary-file requires --batch-output-self-verify\n",
            )

            self.assertEqual(self_verify_json_file_without_self_verify.returncode, 1)
            self.assertEqual(self_verify_json_file_without_self_verify.stdout, "")
            self.assertEqual(
                self_verify_json_file_without_self_verify.stderr,
                "error: --batch-output-self-verify-json-file requires --batch-output-self-verify\n",
            )

            self.assertEqual(empty_run_id.returncode, 1)
            self.assertEqual(empty_run_id.stdout, "")
            self.assertEqual(
                empty_run_id.stderr,
                "error: --batch-output-run-id must be non-empty when provided\n",
            )

            self.assertEqual(empty_summary_file.returncode, 1)
            self.assertEqual(empty_summary_file.stdout, "")
            self.assertEqual(
                empty_summary_file.stderr,
                "error: --batch-output-summary-file must be non-empty when provided\n",
            )

            self.assertEqual(empty_self_verify_summary_file.returncode, 1)
            self.assertEqual(empty_self_verify_summary_file.stdout, "")
            self.assertEqual(
                empty_self_verify_summary_file.stderr,
                "error: --batch-output-self-verify-summary-file must be non-empty when provided\n",
            )

            self.assertEqual(empty_self_verify_json_file.returncode, 1)
            self.assertEqual(empty_self_verify_json_file.stdout, "")
            self.assertEqual(
                empty_self_verify_json_file.stderr,
                "error: --batch-output-self-verify-json-file must be non-empty when provided\n",
            )

            self.assertEqual(self_verify_summary_file_inside_output_dir.returncode, 1)
            self.assertEqual(self_verify_summary_file_inside_output_dir.stdout, "")
            self.assertEqual(
                self_verify_summary_file_inside_output_dir.stderr,
                "error: --batch-output-self-verify-summary-file must be outside --batch-output to avoid overwriting verified artifacts\n",
            )

            self.assertEqual(self_verify_json_file_inside_output_dir.returncode, 1)
            self.assertEqual(self_verify_json_file_inside_output_dir.stdout, "")
            self.assertEqual(
                self_verify_json_file_inside_output_dir.stderr,
                "error: --batch-output-self-verify-json-file must be outside --batch-output to avoid overwriting verified artifacts\n",
            )

            self.assertEqual(self_verify_summary_file_same_as_output.returncode, 1)
            self.assertEqual(self_verify_summary_file_same_as_output.stdout, "")
            self.assertEqual(
                self_verify_summary_file_same_as_output.stderr,
                "error: --output must differ from --batch-output-self-verify-summary-file so eval output cannot overwrite the self-verify sidecar\n",
            )

            self.assertEqual(self_verify_json_file_same_as_output.returncode, 1)
            self.assertEqual(self_verify_json_file_same_as_output.stdout, "")
            self.assertEqual(
                self_verify_json_file_same_as_output.stderr,
                "error: --output must differ from --batch-output-self-verify-json-file so eval output cannot overwrite the self-verify sidecar\n",
            )

            self.assertEqual(self_verify_summary_and_json_same_path_with_summary.returncode, 1)
            self.assertEqual(self_verify_summary_and_json_same_path_with_summary.stdout, "")
            self.assertEqual(
                self_verify_summary_and_json_same_path_with_summary.stderr,
                "error: --batch-output-self-verify-summary-file and --batch-output-self-verify-json-file must differ when --summary is set\n",
            )

            self.assertEqual(
                batch_output_summary_file_same_as_self_verify_summary.returncode,
                1,
            )
            self.assertEqual(
                batch_output_summary_file_same_as_self_verify_summary.stdout,
                "",
            )
            self.assertEqual(
                batch_output_summary_file_same_as_self_verify_summary.stderr,
                "error: --batch-output-summary-file must differ from --batch-output-self-verify-summary-file so the batch aggregate sidecar cannot be overwritten\n",
            )

            self.assertEqual(
                batch_output_summary_file_same_as_self_verify_json.returncode,
                1,
            )
            self.assertEqual(
                batch_output_summary_file_same_as_self_verify_json.stdout,
                "",
            )
            self.assertEqual(
                batch_output_summary_file_same_as_self_verify_json.stderr,
                "error: --batch-output-summary-file must differ from --batch-output-self-verify-json-file so the batch aggregate sidecar cannot be overwritten\n",
            )

    def test_eval_command_batch_output_handoff_bundle_validates_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            bundle_file = Path(tmp_dir) / "handoff-bundle.json"

            bundle_without_output = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
            )
            empty_bundle_file = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-handoff-bundle-file",
                "",
            )
            bundle_inside_output_dir = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-handoff-bundle-file",
                str(output_dir / "handoff-bundle.json"),
            )
            bundle_same_as_output = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(output_dir),
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
                "--output",
                str(bundle_file),
            )
            bundle_with_standalone_verify = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
            )
            bundle_with_standalone_compare = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(output_dir),
                "--batch-output-compare-against",
                str(output_dir),
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
            )

            self.assertEqual(bundle_without_output.returncode, 1)
            self.assertEqual(bundle_without_output.stdout, "")
            self.assertEqual(
                bundle_without_output.stderr,
                "error: --batch-output-handoff-bundle-file requires --batch-output\n",
            )

            self.assertEqual(empty_bundle_file.returncode, 1)
            self.assertEqual(empty_bundle_file.stdout, "")
            self.assertEqual(
                empty_bundle_file.stderr,
                "error: --batch-output-handoff-bundle-file must be non-empty when provided\n",
            )

            self.assertEqual(bundle_inside_output_dir.returncode, 1)
            self.assertEqual(bundle_inside_output_dir.stdout, "")
            self.assertEqual(
                bundle_inside_output_dir.stderr,
                "error: --batch-output-handoff-bundle-file must be outside --batch-output to avoid mutating handed-off artifacts\n",
            )

            self.assertEqual(bundle_same_as_output.returncode, 1)
            self.assertEqual(bundle_same_as_output.stdout, "")
            self.assertEqual(
                bundle_same_as_output.stderr,
                "error: --output must differ from --batch-output-handoff-bundle-file so eval output cannot overwrite the handoff bundle\n",
            )

            self.assertEqual(bundle_with_standalone_verify.returncode, 1)
            self.assertEqual(bundle_with_standalone_verify.stdout, "")
            self.assertEqual(
                bundle_with_standalone_verify.stderr,
                "error: --batch-output-handoff-bundle-file is not supported with --batch-output-verify\n",
            )

            self.assertEqual(bundle_with_standalone_compare.returncode, 1)
            self.assertEqual(bundle_with_standalone_compare.stdout, "")
            self.assertEqual(
                bundle_with_standalone_compare.stderr,
                "error: --batch-output-handoff-bundle-file is not supported with --batch-output-compare\n",
            )

    def test_eval_command_handoff_bundle_validates_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle_file = Path(tmp_dir) / "handoff-bundle.json"
            output_file = Path(tmp_dir) / "eval-output.json"
            summary_file = Path(tmp_dir) / "summary.txt"
            json_file = Path(tmp_dir) / "envelope.json"
            batch_output_dir = Path(tmp_dir) / "batch-output"

            empty_bundle_file = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--handoff-bundle-file",
                "",
            )
            bundle_same_as_output = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--handoff-bundle-file",
                str(bundle_file),
                "--output",
                str(bundle_file),
            )
            bundle_same_as_summary = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--summary-file",
                str(summary_file),
                "--handoff-bundle-file",
                str(summary_file),
            )
            bundle_same_as_json = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--json-file",
                str(json_file),
                "--handoff-bundle-file",
                str(json_file),
            )
            bundle_with_batch_output = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(batch_output_dir),
                "--handoff-bundle-file",
                str(output_file),
            )

            self.assertEqual(empty_bundle_file.returncode, 1)
            self.assertEqual(empty_bundle_file.stdout, "")
            self.assertEqual(
                empty_bundle_file.stderr,
                "error: --handoff-bundle-file must be non-empty when provided\n",
            )

            self.assertEqual(bundle_same_as_output.returncode, 1)
            self.assertEqual(bundle_same_as_output.stdout, "")
            self.assertEqual(
                bundle_same_as_output.stderr,
                "error: --handoff-bundle-file must differ from --output so eval output cannot overwrite the handoff bundle\n",
            )

            self.assertEqual(bundle_same_as_summary.returncode, 1)
            self.assertEqual(bundle_same_as_summary.stdout, "")
            self.assertEqual(
                bundle_same_as_summary.stderr,
                "error: --handoff-bundle-file must differ from --summary-file because they export different output shapes\n",
            )

            self.assertEqual(bundle_same_as_json.returncode, 1)
            self.assertEqual(bundle_same_as_json.stdout, "")
            self.assertEqual(
                bundle_same_as_json.stderr,
                "error: --handoff-bundle-file must differ from --json-file because they export different output shapes\n",
            )

            self.assertEqual(bundle_with_batch_output.returncode, 1)
            self.assertEqual(bundle_with_batch_output.stdout, "")
            self.assertEqual(
                bundle_with_batch_output.stderr,
                "error: --handoff-bundle-file is not supported with --batch-output\n",
            )

    def test_eval_command_standalone_verify_and_compare_handoff_bundle_validate_contracts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_output_dir = Path(tmp_dir) / "batch-output"
            baseline_dir = Path(tmp_dir) / "baseline"
            verify_summary_file = Path(tmp_dir) / "verify.summary.txt"
            verify_json_file = Path(tmp_dir) / "verify.json"
            compare_summary_file = Path(tmp_dir) / "compare.summary.txt"
            compare_json_file = Path(tmp_dir) / "compare.json"
            shared_output_file = Path(tmp_dir) / "shared-output.txt"

            emit_verify_target = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(batch_output_dir),
            )
            emit_compare_baseline = self._run_cli(
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(EVAL_FIXTURES / "batch"),
                "--batch-output",
                str(baseline_dir),
            )
            empty_verify_bundle_file = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(batch_output_dir),
                "--handoff-bundle-file",
                "",
            )
            verify_bundle_same_as_output = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(batch_output_dir),
                "--handoff-bundle-file",
                str(shared_output_file),
                "--output",
                str(shared_output_file),
            )
            verify_bundle_same_as_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(batch_output_dir),
                "--batch-output-verify-summary-file",
                str(verify_summary_file),
                "--handoff-bundle-file",
                str(verify_summary_file),
            )
            verify_bundle_same_as_json = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(batch_output_dir),
                "--batch-output-verify-json-file",
                str(verify_json_file),
                "--handoff-bundle-file",
                str(verify_json_file),
            )
            empty_compare_bundle_file = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(batch_output_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--handoff-bundle-file",
                "",
            )
            compare_bundle_same_as_output = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(batch_output_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--handoff-bundle-file",
                str(shared_output_file),
                "--output",
                str(shared_output_file),
            )
            compare_bundle_same_as_summary = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(batch_output_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(compare_summary_file),
                "--handoff-bundle-file",
                str(compare_summary_file),
            )
            compare_bundle_same_as_json = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(batch_output_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--batch-output-compare-json-file",
                str(compare_json_file),
                "--handoff-bundle-file",
                str(compare_json_file),
            )

            self.assertEqual(emit_verify_target.returncode, 0)
            self.assertEqual(emit_compare_baseline.returncode, 0)
            self.assertEqual(emit_verify_target.stderr, "")
            self.assertEqual(emit_compare_baseline.stderr, "")

            self.assertEqual(empty_verify_bundle_file.returncode, 1)
            self.assertEqual(empty_verify_bundle_file.stdout, "")
            self.assertEqual(
                empty_verify_bundle_file.stderr,
                "error: --handoff-bundle-file must be non-empty when provided\n",
            )

            self.assertEqual(verify_bundle_same_as_output.returncode, 1)
            self.assertEqual(verify_bundle_same_as_output.stdout, "")
            self.assertEqual(
                verify_bundle_same_as_output.stderr,
                "error: --handoff-bundle-file must differ from --output so eval output cannot overwrite the handoff bundle\n",
            )

            self.assertEqual(verify_bundle_same_as_summary.returncode, 1)
            self.assertEqual(verify_bundle_same_as_summary.stdout, "")
            self.assertEqual(
                verify_bundle_same_as_summary.stderr,
                "error: --handoff-bundle-file must differ from --batch-output-verify-summary-file because they export different output shapes\n",
            )

            self.assertEqual(verify_bundle_same_as_json.returncode, 1)
            self.assertEqual(verify_bundle_same_as_json.stdout, "")
            self.assertEqual(
                verify_bundle_same_as_json.stderr,
                "error: --handoff-bundle-file must differ from --batch-output-verify-json-file because they export different output shapes\n",
            )

            self.assertEqual(empty_compare_bundle_file.returncode, 1)
            self.assertEqual(empty_compare_bundle_file.stdout, "")
            self.assertEqual(
                empty_compare_bundle_file.stderr,
                "error: --handoff-bundle-file must be non-empty when provided\n",
            )

            self.assertEqual(compare_bundle_same_as_output.returncode, 1)
            self.assertEqual(compare_bundle_same_as_output.stdout, "")
            self.assertEqual(
                compare_bundle_same_as_output.stderr,
                "error: --handoff-bundle-file must differ from --output so eval output cannot overwrite the handoff bundle\n",
            )

            self.assertEqual(compare_bundle_same_as_summary.returncode, 1)
            self.assertEqual(compare_bundle_same_as_summary.stdout, "")
            self.assertEqual(
                compare_bundle_same_as_summary.stderr,
                "error: --handoff-bundle-file must differ from --batch-output-compare-summary-file because they export different output shapes\n",
            )

            self.assertEqual(compare_bundle_same_as_json.returncode, 1)
            self.assertEqual(compare_bundle_same_as_json.stdout, "")
            self.assertEqual(
                compare_bundle_same_as_json.stderr,
                "error: --handoff-bundle-file must differ from --batch-output-compare-json-file because they export different output shapes\n",
            )

    def test_eval_command_batch_mode_rejects_meta_options(self) -> None:
        meta_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--meta",
        )
        generated_at_result = self._run_cli(
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(EVAL_FIXTURES / "batch"),
            "--generated-at",
            "2026-03-06T19:00:00Z",
        )

        self.assertEqual(meta_result.returncode, 1)
        self.assertEqual(meta_result.stdout, "")
        self.assertEqual(meta_result.stderr, "error: --meta is not supported with --batch\n")

        self.assertEqual(generated_at_result.returncode, 1)
        self.assertEqual(generated_at_result.stdout, "")
        self.assertEqual(
            generated_at_result.stderr,
            "error: --generated-at is not supported with --batch\n",
        )


class CliProgramPackReplayTests(unittest.TestCase):
    def _run_cli(self, *args: str, stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "cli.main", *args],
            cwd=ROOT,
            text=True,
            input=stdin_text,
            capture_output=True,
            check=False,
        )

    def test_pack_replay_summary_reports_dedup_cluster_fixture_match(self) -> None:
        result = self._run_cli("pack-replay", str(DEDUP_CLUSTER_PACK), "--summary")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0\n",
        )

    def test_pack_replay_reports_checked_in_action_plan_for_fixture_matrix_pack(self) -> None:
        result = self._run_cli("pack-replay", str(DEDUP_CLUSTER_PACK))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(
            envelope["fixtures"][0]["action_plan"],
            [
                {
                    "step": 1,
                    "kind": "cluster_attach",
                    "params": {
                        "cluster_bucket": "ops",
                        "mode": "dedup",
                        "reason": "time_geo_category_match",
                    },
                }
            ],
        )
        self.assertEqual(
            envelope["fixtures"][2]["action_plan"],
            [
                {
                    "step": 1,
                    "kind": "cluster_new",
                    "params": {
                        "cluster_bucket": "ops",
                        "mode": "new",
                        "reason": "time_window_miss",
                    },
                }
            ],
        )
        self.assertNotIn("action_plan", envelope["fixtures"][3])

    def test_pack_replay_reports_materialized_action_plan_for_inline_baseline_refs(self) -> None:
        result = self._run_cli("pack-replay", str(INGEST_NORMALIZE_PACK))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["fixtures"][0]["action_plan"], [
            {"step": 1, "kind": "queue_normalize", "params": {"pipeline": "nlp-v1"}}
        ])
        self.assertEqual(
            envelope["fixtures"][1]["action_plan"],
            [
                {
                    "step": 1,
                    "kind": "notify",
                    "params": {
                        "channel": "ops_dispatch",
                        "template": "Normalisierung abgeschlossen: Einsatzlage aktualisieren.",
                    },
                }
            ],
        )
        self.assertEqual(
            envelope["fixtures"][1]["resolved_refs"],
            {"tpl_norm_ready": "Normalisierung abgeschlossen: Einsatzlage aktualisieren."},
        )

    def test_pack_replay_reports_materialized_action_plan_and_resolved_refs_for_checked_in_fixture_matrix_refs_pack(self) -> None:
        result = self._run_cli("pack-replay", str(REFS_HANDOFF_PACK))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["pack_id"], "sprint-7-program-pack-4-refs-handoff")
        self.assertEqual(
            [fixture["id"] for fixture in envelope["fixtures"]],
            ["ops_primary_page", "security_triage", "ops_digest", "no_match_finance"],
        )
        self.assertEqual(
            envelope["fixtures"][0]["action_plan"],
            [
                {
                    "step": 1,
                    "kind": "notify",
                    "params": {
                        "channel": "ops_pager",
                        "labels": [{"value": "critical"}, {"value": "ops"}],
                        "payload": {
                            "owner": {"team": "ops"},
                            "priority": "p1",
                            "runbook": "rb://ops/primary-page",
                        },
                        "template": "Page primary on-call immediately",
                    },
                }
            ],
        )
        self.assertEqual(
            envelope["fixtures"][0]["resolved_refs"],
            {
                "ch_ops_pager": "ops_pager",
                "label_critical": "critical",
                "label_ops": "ops",
                "prio_p1": "p1",
                "runbook_ops": "rb://ops/primary-page",
                "team_ops": "ops",
                "tpl_ops_page": "Page primary on-call immediately",
            },
        )
        self.assertEqual(
            envelope["fixtures"][1]["resolved_refs"],
            {
                "ch_sec_triage": "security_triage",
                "label_critical": "critical",
                "label_security": "security",
                "label_triage": "triage",
                "prio_p1": "p1",
                "runbook_sec": "rb://security/triage",
                "team_sec": "security",
                "tpl_sec_triage": "Escalate to security triage",
            },
        )
        self.assertEqual(
            envelope["fixtures"][2]["resolved_refs"],
            {
                "ch_ops_digest": "ops_digest",
                "label_ops": "ops",
                "label_warning": "warning",
                "prio_p2": "p2",
                "team_ops": "ops",
                "tpl_ops_digest": "Queue for ops digest review",
            },
        )
        self.assertNotIn("action_plan", envelope["fixtures"][3])
        self.assertNotIn("resolved_refs", envelope["fixtures"][3])

    def test_pack_replay_can_compare_expected_action_plan_and_resolved_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "action-plan-pack"
            pack_dir.mkdir()
            (pack_dir / "program.erz").write_text(
                "\n".join(
                    [
                        "erz{v:1}",
                        'rule{id:"route_ops",when:["event_type_present","payload_has:severity"],then:[{kind:"notify",params:{channel:"ops",severity_ref:"@sev_label"}}]}',
                        'rf{id:"sev_label",v:"high"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            baseline_payload = {
                "rules": [
                    {
                        "id": "route_ops",
                        "when": ["event_type_present", "payload_has:severity"],
                        "then": [
                            {
                                "kind": "notify",
                                "params": {"channel": "ops", "severity_ref": "@sev_label"},
                            }
                        ],
                    }
                ],
                "fixtures": [
                    {
                        "id": "fixture-01",
                        "event": {"type": "ingest", "payload": {"severity": "high"}},
                        "expected_actions": [
                            {
                                "kind": "notify",
                                "params": {"channel": "ops", "severity_ref": "@sev_label"},
                            }
                        ],
                        "expected_trace": [
                            {
                                "rule_id": "route_ops",
                                "matched_clauses": ["event_type_present", "payload_has:severity"],
                                "score": 1.0,
                            }
                        ],
                        "expected_action_plan": [
                            {
                                "step": 1,
                                "kind": "notify",
                                "params": {"channel": "ops", "severity": "high"},
                            }
                        ],
                        "expected_resolved_refs": {"sev_label": "high"},
                    }
                ],
            }
            (pack_dir / "baseline.json").write_text(
                json.dumps(baseline_payload, indent=2),
                encoding="utf-8",
            )

            ok_result = self._run_cli("pack-replay", str(pack_dir))
            self.assertEqual(ok_result.returncode, 0)
            self.assertEqual(ok_result.stderr, "")
            ok_envelope = json.loads(ok_result.stdout)
            self.assertEqual(ok_envelope["fixtures"][0]["status"], "ok")
            self.assertEqual(
                ok_envelope["fixtures"][0]["action_plan"],
                [{"step": 1, "kind": "notify", "params": {"channel": "ops", "severity": "high"}}],
            )
            self.assertEqual(ok_envelope["fixtures"][0]["resolved_refs"], {"sev_label": "high"})

            baseline_payload["fixtures"][0]["expected_action_plan"][0]["params"]["severity"] = "critical"
            (pack_dir / "baseline.json").write_text(
                json.dumps(baseline_payload, indent=2),
                encoding="utf-8",
            )

            mismatch_result = self._run_cli("pack-replay", str(pack_dir))
            self.assertEqual(mismatch_result.returncode, 1)
            self.assertEqual(mismatch_result.stderr, "")
            mismatch_envelope = json.loads(mismatch_result.stdout)
            self.assertEqual(mismatch_envelope["fixtures"][0]["fixture_class"], "expectation_mismatch")
            self.assertEqual(mismatch_envelope["fixtures"][0]["mismatch_fields"], ["action_plan"])
            self.assertEqual(
                mismatch_envelope["fixtures"][0]["expected_action_plan"],
                [{"step": 1, "kind": "notify", "params": {"channel": "ops", "severity": "critical"}}],
            )
            self.assertEqual(
                mismatch_envelope["fixtures"][0]["expected_resolved_refs"],
                {"sev_label": "high"},
            )
            self.assertEqual(
                mismatch_envelope["summary"]["mismatch_field_counts"],
                {"actions": 0, "trace": 0, "action_plan": 1, "resolved_refs": 0},
            )
            self.assertEqual(
                mismatch_envelope["summary"]["mismatch_field_ids"],
                {
                    "actions": [],
                    "trace": [],
                    "action_plan": ["fixture-01"],
                    "resolved_refs": [],
                },
            )

            mismatch_summary_result = self._run_cli("pack-replay", str(pack_dir), "--summary")
            self.assertEqual(mismatch_summary_result.returncode, 1)
            self.assertEqual(mismatch_summary_result.stderr, "")
            self.assertEqual(
                mismatch_summary_result.stdout,
                "status=error pack=action-plan-pack fixtures=1 matched=0 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:0,expectation_mismatch:1,runtime_error:0 plan=1 resolved_refs=1 mismatch_fields=actions:0,trace:0,action_plan:1,resolved_refs:0\n",
            )

    def test_pack_replay_supports_fixture_selector_subset(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture",
            "new_ops_time_miss",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=1/4 matched=1 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:1,expectation_mismatch:0,runtime_error:0 plan=1 resolved_refs=0\n",
        )

        json_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture",
            "new_ops_time_miss",
        )
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")

        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["selected_fixture_ids"], ["new_ops_time_miss"])
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 1,
                "matched_count": 1,
                "mismatch_count": 0,
                "runtime_error_count": 0,
                "total_fixture_count": 4,
                "fixture_class_counts": {
                    "ok": 1,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": ["new_ops_time_miss"],
                    "expectation_mismatch": [],
                    "runtime_error": [],
                },
                "action_plan_count": 1,
                "resolved_ref_count": 0,
            },
        )
        self.assertEqual([fixture["id"] for fixture in envelope["fixtures"]], ["new_ops_time_miss"])
        self.assertEqual([fixture["fixture_class"] for fixture in envelope["fixtures"]], ["ok"])

    def test_pack_replay_supports_fixture_glob_selector_subset(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--include-fixture",
            "new_*",
            "--exclude-fixture",
            "*security*",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=1/4 matched=1 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:1,expectation_mismatch:0,runtime_error:0 plan=1 resolved_refs=0\n",
        )

        json_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--include-fixture",
            "new_*",
            "--exclude-fixture",
            "*security*",
        )
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")

        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["selected_fixture_ids"], ["new_ops_time_miss"])
        self.assertEqual(envelope["include_fixture_globs"], ["new_*"])
        self.assertEqual(envelope["exclude_fixture_globs"], ["*security*"])
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 1,
                "matched_count": 1,
                "mismatch_count": 0,
                "runtime_error_count": 0,
                "total_fixture_count": 4,
                "fixture_class_counts": {
                    "ok": 1,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": ["new_ops_time_miss"],
                    "expectation_mismatch": [],
                    "runtime_error": [],
                },
                "action_plan_count": 1,
                "resolved_ref_count": 0,
            },
        )
        self.assertEqual([fixture["id"] for fixture in envelope["fixtures"]], ["new_ops_time_miss"])

    def test_pack_replay_supports_exclude_only_fixture_glob_subset(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--exclude-fixture",
            "new_*",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=2/4 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=1 resolved_refs=0\n",
        )

        json_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--exclude-fixture",
            "new_*",
        )
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")

        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["selected_fixture_ids"], ["attach_ops", "no_match_unknown_category"])
        self.assertEqual(envelope["exclude_fixture_globs"], ["new_*"])
        self.assertEqual(
            [fixture["id"] for fixture in envelope["fixtures"]],
            ["attach_ops", "no_match_unknown_category"],
        )

    def test_pack_replay_unions_exact_and_glob_fixture_selectors_in_pack_order(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture",
            "attach_ops",
            "--include-fixture",
            "new_*",
            "--exclude-fixture",
            "*security*",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["selected_fixture_ids"], ["attach_ops", "new_ops_time_miss"])
        self.assertEqual(
            [fixture["id"] for fixture in envelope["fixtures"]],
            ["attach_ops", "new_ops_time_miss"],
        )
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 2,
                "matched_count": 2,
                "mismatch_count": 0,
                "runtime_error_count": 0,
                "total_fixture_count": 4,
                "fixture_class_counts": {
                    "ok": 2,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": ["attach_ops", "new_ops_time_miss"],
                    "expectation_mismatch": [],
                    "runtime_error": [],
                },
                "action_plan_count": 2,
                "resolved_ref_count": 0,
            },
        )

    def test_pack_replay_supports_fixture_class_selector_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            summary_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--fixture-class",
                "runtime_error",
                "--summary",
            )
            json_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--fixture-class",
                "runtime_error",
            )

        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=1/4 matched=0 mismatches=1 runtime_errors=1 rule_source=ok fixture_classes=ok:0,expectation_mismatch:0,runtime_error:1 plan=0 resolved_refs=0\n",
        )

        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(json_result.stderr, "")

        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["selected_fixture_ids"], ["new_ops_time_miss"])
        self.assertEqual(envelope["fixture_class_selectors"], ["runtime_error"])
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 1,
                "matched_count": 0,
                "mismatch_count": 1,
                "runtime_error_count": 1,
                "total_fixture_count": 4,
                "fixture_class_counts": {
                    "ok": 0,
                    "expectation_mismatch": 0,
                    "runtime_error": 1,
                },
                "fixture_class_ids": {
                    "ok": [],
                    "expectation_mismatch": [],
                    "runtime_error": ["new_ops_time_miss"],
                },
                "action_plan_count": 0,
                "resolved_ref_count": 0,
            },
        )
        self.assertEqual([fixture["id"] for fixture in envelope["fixtures"]], ["new_ops_time_miss"])
        self.assertEqual([fixture["fixture_class"] for fixture in envelope["fixtures"]], ["runtime_error"])

    def test_pack_replay_unions_fixture_class_selectors_in_pack_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--fixture-class",
                "expectation_mismatch",
                "--fixture-class",
                "runtime_error",
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["selected_fixture_ids"], ["attach_ops", "new_ops_time_miss"])
        self.assertEqual(
            envelope["fixture_class_selectors"],
            ["expectation_mismatch", "runtime_error"],
        )
        self.assertEqual(
            [fixture["id"] for fixture in envelope["fixtures"]],
            ["attach_ops", "new_ops_time_miss"],
        )
        self.assertEqual(
            [fixture["fixture_class"] for fixture in envelope["fixtures"]],
            ["expectation_mismatch", "runtime_error"],
        )
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 2,
                "matched_count": 0,
                "mismatch_count": 2,
                "runtime_error_count": 1,
                "total_fixture_count": 4,
                "fixture_class_counts": {
                    "ok": 0,
                    "expectation_mismatch": 1,
                    "runtime_error": 1,
                },
                "fixture_class_ids": {
                    "ok": [],
                    "expectation_mismatch": ["attach_ops"],
                    "runtime_error": ["new_ops_time_miss"],
                },
                "mismatch_field_counts": {
                    "actions": 1,
                    "trace": 0,
                    "action_plan": 0,
                    "resolved_refs": 0,
                },
                "mismatch_field_ids": {
                    "actions": ["attach_ops"],
                    "trace": [],
                    "action_plan": [],
                    "resolved_refs": [],
                },
                "action_plan_count": 1,
                "resolved_ref_count": 0,
            },
        )

    def test_pack_replay_supports_mismatch_field_selector_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            summary_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--mismatch-field",
                "actions",
                "--summary",
            )
            json_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--mismatch-field",
                "actions",
            )

        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=1/4 matched=0 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:0,expectation_mismatch:1,runtime_error:0 plan=1 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0\n",
        )

        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(json_result.stderr, "")

        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["selected_fixture_ids"], ["attach_ops"])
        self.assertEqual(envelope["mismatch_field_selectors"], ["actions"])
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 1,
                "matched_count": 0,
                "mismatch_count": 1,
                "runtime_error_count": 0,
                "total_fixture_count": 4,
                "fixture_class_counts": {
                    "ok": 0,
                    "expectation_mismatch": 1,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": [],
                    "expectation_mismatch": ["attach_ops"],
                    "runtime_error": [],
                },
                "mismatch_field_counts": {
                    "actions": 1,
                    "trace": 0,
                    "action_plan": 0,
                    "resolved_refs": 0,
                },
                "mismatch_field_ids": {
                    "actions": ["attach_ops"],
                    "trace": [],
                    "action_plan": [],
                    "resolved_refs": [],
                },
                "action_plan_count": 1,
                "resolved_ref_count": 0,
            },
        )
        self.assertEqual([fixture["id"] for fixture in envelope["fixtures"]], ["attach_ops"])
        self.assertEqual(
            [fixture["mismatch_fields"] for fixture in envelope["fixtures"]],
            [["actions"]],
        )

    def test_pack_replay_supports_action_plan_mismatch_field_selector_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "action-plan-pack"
            pack_dir.mkdir()
            (pack_dir / "program.erz").write_text(
                "\n".join(
                    [
                        "erz{v:1}",
                        'rule{id:"route_ops",when:["event_type_present","payload_has:severity"],then:[{kind:"notify",params:{channel:"ops",severity_ref:"@sev_label"}}]}',
                        'rf{id:"sev_label",v:"high"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (pack_dir / "baseline.json").write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "id": "route_ops",
                                "when": ["event_type_present", "payload_has:severity"],
                                "then": [
                                    {
                                        "kind": "notify",
                                        "params": {"channel": "ops", "severity_ref": "@sev_label"},
                                    }
                                ],
                            }
                        ],
                        "fixtures": [
                            {
                                "id": "fixture-01",
                                "event": {"type": "ingest", "payload": {"severity": "high"}},
                                "expected_actions": [
                                    {
                                        "kind": "notify",
                                        "params": {"channel": "ops", "severity_ref": "@sev_label"},
                                    }
                                ],
                                "expected_trace": [
                                    {
                                        "rule_id": "route_ops",
                                        "matched_clauses": ["event_type_present", "payload_has:severity"],
                                        "score": 1.0,
                                    }
                                ],
                                "expected_action_plan": [
                                    {
                                        "step": 1,
                                        "kind": "notify",
                                        "params": {"channel": "ops", "severity": "critical"},
                                    }
                                ],
                                "expected_resolved_refs": {"sev_label": "high"},
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--mismatch-field",
                "action_plan",
                "--summary",
            )
            json_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--mismatch-field",
                "action_plan",
            )

        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=error pack=action-plan-pack fixtures=1 matched=0 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:0,expectation_mismatch:1,runtime_error:0 plan=1 resolved_refs=1 mismatch_fields=actions:0,trace:0,action_plan:1,resolved_refs:0\n",
        )

        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(json_result.stderr, "")

        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["selected_fixture_ids"], ["fixture-01"])
        self.assertEqual(envelope["mismatch_field_selectors"], ["action_plan"])
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 1,
                "matched_count": 0,
                "mismatch_count": 1,
                "runtime_error_count": 0,
                "total_fixture_count": 1,
                "fixture_class_counts": {
                    "ok": 0,
                    "expectation_mismatch": 1,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": [],
                    "expectation_mismatch": ["fixture-01"],
                    "runtime_error": [],
                },
                "mismatch_field_counts": {
                    "actions": 0,
                    "trace": 0,
                    "action_plan": 1,
                    "resolved_refs": 0,
                },
                "mismatch_field_ids": {
                    "actions": [],
                    "trace": [],
                    "action_plan": ["fixture-01"],
                    "resolved_refs": [],
                },
                "action_plan_count": 1,
                "resolved_ref_count": 1,
            },
        )
        self.assertEqual([fixture["id"] for fixture in envelope["fixtures"]], ["fixture-01"])
        self.assertEqual(
            [fixture["mismatch_fields"] for fixture in envelope["fixtures"]],
            [["action_plan"]],
        )

    def test_pack_replay_fixture_class_summary_file_writes_summary_without_stdout_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            summary_path = Path(tmpdir) / "runtime-error.summary.txt"
            result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--fixture-class",
                "runtime_error",
                "--fixture-class-summary-file",
                str(summary_path),
            )
            summary_text = summary_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["selected_fixture_ids"], ["new_ops_time_miss"])
        self.assertEqual(
            summary_text,
            "status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=1/4 matched=0 mismatches=1 runtime_errors=1 rule_source=ok fixture_classes=ok:0,expectation_mismatch:0,runtime_error:1 plan=0 resolved_refs=0\n",
        )

    def test_pack_replay_fixture_class_summary_file_requires_fixture_class(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture-class-summary-file",
            "/tmp/pack-replay.summary.txt",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --fixture-class-summary-file requires --fixture-class\n",
        )

    def test_pack_replay_fixture_class_summary_file_rejects_empty_path(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture-class",
            "ok",
            "--fixture-class-summary-file",
            "",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --fixture-class-summary-file must be non-empty when provided\n",
        )

    def test_pack_replay_summary_file_writes_summary_without_stdout_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "dedup.summary.txt"
            result = self._run_cli(
                "pack-replay",
                str(DEDUP_CLUSTER_PACK),
                "--summary-file",
                str(summary_path),
            )
            summary_text = summary_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(summary_text, self._run_cli("pack-replay", str(DEDUP_CLUSTER_PACK), "--summary").stdout)

    def test_pack_replay_summary_file_writes_failure_summary_before_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            summary_path = Path(tmpdir) / "dedup.failure.summary.txt"
            result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary-file",
                str(summary_path),
            )
            summary_text = summary_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(
            summary_text,
            "status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=3 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:1,runtime_error:0 plan=3 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0\n",
        )

    def test_pack_replay_json_file_matches_stdout_in_default_json_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "dedup.default.json"
            result = self._run_cli(
                "pack-replay",
                str(DEDUP_CLUSTER_PACK),
                "--json-file",
                str(json_path),
            )
            json_text = json_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json_text, result.stdout)

    def test_pack_replay_json_file_writes_json_without_stdout_drift_in_summary_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "dedup.summary.json"
            result = self._run_cli(
                "pack-replay",
                str(DEDUP_CLUSTER_PACK),
                "--summary",
                "--json-file",
                str(json_path),
            )
            json_text = json_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, self._run_cli("pack-replay", str(DEDUP_CLUSTER_PACK), "--summary").stdout)
        self.assertEqual(json_text, self._run_cli("pack-replay", str(DEDUP_CLUSTER_PACK)).stdout)

    def test_pack_replay_json_file_writes_failure_json_before_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            json_path = Path(tmpdir) / "dedup.failure.json"
            result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--json-file",
                str(json_path),
            )
            json_text = json_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=3 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:1,runtime_error:0 plan=3 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0\n",
        )
        self.assertEqual(json.loads(json_text)["status"], "error")

    def test_pack_replay_json_file_can_coexist_with_summary_stdout_and_output_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "dedup.summary.txt"
            json_path = Path(tmpdir) / "dedup.summary.json"
            result = self._run_cli(
                "pack-replay",
                str(DEDUP_CLUSTER_PACK),
                "--summary",
                "--output",
                str(output_path),
                "--json-file",
                str(json_path),
            )
            output_text = output_path.read_text(encoding="utf-8")
            json_text = json_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(output_text, result.stdout)
        self.assertEqual(output_text, self._run_cli("pack-replay", str(DEDUP_CLUSTER_PACK), "--summary").stdout)
        self.assertEqual(json_text, self._run_cli("pack-replay", str(DEDUP_CLUSTER_PACK)).stdout)

    def test_pack_replay_handoff_bundle_wraps_summary_exit_and_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_path = Path(tmpdir) / "refs-handoff.bundle.json"
            summary_result = self._run_cli("pack-replay", str(REFS_HANDOFF_PACK), "--summary")
            json_result = self._run_cli("pack-replay", str(REFS_HANDOFF_PACK))
            result = self._run_cli(
                "pack-replay",
                str(REFS_HANDOFF_PACK),
                "--summary",
                "--handoff-bundle-file",
                str(bundle_path),
            )
            bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, summary_result.stdout)
        self.assertEqual(
            bundle_payload,
            {
                "kind": "erz.pack_replay.handoff_bundle.v1",
                "surface": "pack_replay",
                "source": {"target": "refs-handoff"},
                "primary": {
                    "key": "pack_replay",
                    "details": json.loads(json_result.stdout),
                },
                "summary_line": summary_result.stdout.strip(),
                "exit": {"code": 0},
                "pack_replay": json.loads(json_result.stdout),
            },
        )

    def test_pack_replay_handoff_bundle_wraps_aggregate_summary_exit_and_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_path = Path(tmpdir) / "program-packs.bundle.json"
            summary_result = self._run_cli("pack-replay", str(PROGRAM_PACK_INDEX), "--summary")
            json_result = self._run_cli("pack-replay", str(PROGRAM_PACK_INDEX))
            result = self._run_cli(
                "pack-replay",
                str(PROGRAM_PACK_INDEX),
                "--summary",
                "--handoff-bundle-file",
                str(bundle_path),
            )
            bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, summary_result.stdout)
        self.assertEqual(bundle_payload["kind"], "erz.pack_replay.handoff_bundle.v1")
        self.assertEqual(bundle_payload["surface"], "pack_replay")
        self.assertEqual(bundle_payload["source"], {"target": "program-pack-index.json"})
        self.assertEqual(bundle_payload["summary_line"], summary_result.stdout.strip())
        self.assertEqual(bundle_payload["exit"], {"code": 0})
        self.assertEqual(bundle_payload["pack_replay"], json.loads(json_result.stdout))
        self.assertEqual(
            bundle_payload["primary"],
            {"key": "pack_replay", "details": json.loads(json_result.stdout)},
        )

    def test_pack_replay_handoff_bundle_is_written_before_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            bundle_path = Path(tmpdir) / "dedup.failure.bundle.json"
            result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--handoff-bundle-file",
                str(bundle_path),
            )
            bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=3 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:1,runtime_error:0 plan=3 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0\n",
        )
        self.assertEqual(bundle_payload["kind"], "erz.pack_replay.handoff_bundle.v1")
        self.assertEqual(bundle_payload["surface"], "pack_replay")
        self.assertEqual(bundle_payload["source"], {"target": "dedup-cluster"})
        self.assertEqual(bundle_payload["summary_line"], result.stdout.strip())
        self.assertEqual(bundle_payload["exit"], {"code": 1})
        self.assertEqual(bundle_payload["pack_replay"]["status"], "error")
        self.assertEqual(bundle_payload["primary"], {"key": "pack_replay", "details": bundle_payload["pack_replay"]})

    def test_pack_replay_handoff_bundle_validates_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_path = Path(tmpdir) / "replay.handoff.json"
            summary_path = Path(tmpdir) / "replay.summary.txt"
            json_path = Path(tmpdir) / "replay.json"
            output_path = Path(tmpdir) / "replay.output.txt"
            fixture_class_summary_path = Path(tmpdir) / "replay.fixture-class-summary.txt"

            cases = [
                (
                    [
                        "pack-replay",
                        str(DEDUP_CLUSTER_PACK),
                        "--handoff-bundle-file",
                        "",
                    ],
                    "error: --handoff-bundle-file must be non-empty when provided\n",
                ),
                (
                    [
                        "pack-replay",
                        str(DEDUP_CLUSTER_PACK),
                        "--handoff-bundle-file",
                        str(summary_path),
                        "--summary-file",
                        str(summary_path),
                    ],
                    "error: --handoff-bundle-file must differ from --summary-file because they export different output shapes\n",
                ),
                (
                    [
                        "pack-replay",
                        str(DEDUP_CLUSTER_PACK),
                        "--handoff-bundle-file",
                        str(json_path),
                        "--json-file",
                        str(json_path),
                    ],
                    "error: --handoff-bundle-file must differ from --json-file because they export different output shapes\n",
                ),
                (
                    [
                        "pack-replay",
                        str(DEDUP_CLUSTER_PACK),
                        "--fixture-class",
                        "ok",
                        "--handoff-bundle-file",
                        str(fixture_class_summary_path),
                        "--fixture-class-summary-file",
                        str(fixture_class_summary_path),
                    ],
                    "error: --handoff-bundle-file must differ from --fixture-class-summary-file because they export different output shapes\n",
                ),
                (
                    [
                        "pack-replay",
                        str(DEDUP_CLUSTER_PACK),
                        "--handoff-bundle-file",
                        str(output_path),
                        "--output",
                        str(output_path),
                    ],
                    "error: --handoff-bundle-file must differ from --output so replay output cannot overwrite the handoff bundle\n",
                ),
            ]

            for argv, expected_stderr in cases:
                with self.subTest(argv=argv):
                    result = self._run_cli(*argv)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, expected_stderr)

    def test_pack_replay_summary_file_rejects_empty_path(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--summary-file",
            "",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --summary-file must be non-empty when provided\n",
        )

    def test_pack_replay_json_file_rejects_empty_path(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--json-file",
            "",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --json-file must be non-empty when provided\n",
        )

    def test_pack_replay_strict_requires_at_least_one_expected_selector_or_profile(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --strict requires at least one --expected-* selector or --strict-profile\n",
        )

    def test_pack_replay_expected_pack_id_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-pack-id",
            "sprint-7-program-pack-2-dedup-cluster",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-pack-id requires --strict\n",
        )

    def test_pack_replay_expected_baseline_shape_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-baseline-shape",
            "fixture-matrix",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-baseline-shape requires --strict\n",
        )

    def test_pack_replay_rejects_empty_expected_pack_id(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-pack-id",
            "",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-pack-id must be non-empty\n",
        )

    def test_pack_replay_strict_can_assert_expected_pack_id(self) -> None:
        green_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--summary",
            "--strict",
            "--expected-pack-id",
            "sprint-7-program-pack-2-dedup-cluster",
            "--expected-mismatch-count",
            "0",
            "--expected-expectation-mismatch-count",
            "0",
            "--expected-runtime-error-count",
            "0",
            "--expected-rule-source-status",
            "ok",
        )
        red_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-pack-id",
            "ingest-normalize",
            "--expected-mismatch-count",
            "0",
            "--expected-expectation-mismatch-count",
            "0",
            "--expected-runtime-error-count",
            "0",
            "--expected-rule-source-status",
            "ok",
        )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        payload = json.loads(red_result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["replay_status"], "ok")
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_pack_id": "ingest-normalize",
                "expected_mismatch_count": 0,
                "expected_expectation_mismatch_count": 0,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            payload["strict_profile_mismatches"],
            [
                {
                    "field": "pack_id",
                    "expected": "ingest-normalize",
                    "actual": "sprint-7-program-pack-2-dedup-cluster",
                }
            ],
        )

    def test_pack_replay_strict_can_assert_expected_baseline_shape(self) -> None:
        green_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--summary",
            "--strict",
            "--expected-baseline-shape",
            "fixture-matrix",
            "--expected-mismatch-count",
            "0",
            "--expected-expectation-mismatch-count",
            "0",
            "--expected-runtime-error-count",
            "0",
            "--expected-rule-source-status",
            "ok",
        )
        red_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-baseline-shape",
            "inline-statements",
            "--expected-mismatch-count",
            "0",
            "--expected-expectation-mismatch-count",
            "0",
            "--expected-runtime-error-count",
            "0",
            "--expected-rule-source-status",
            "ok",
        )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        payload = json.loads(red_result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["replay_status"], "ok")
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_baseline_shape": "inline-statements",
                "expected_mismatch_count": 0,
                "expected_expectation_mismatch_count": 0,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            payload["strict_profile_mismatches"],
            [
                {
                    "field": "baseline_shape",
                    "expected": "inline-statements",
                    "actual": "fixture-matrix",
                }
            ],
        )

    def test_pack_replay_strict_profile_clean_passes_for_checked_in_green_pack(self) -> None:
        summary_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict-profile",
            "clean",
            "--summary",
        )
        json_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict-profile",
            "clean",
        )

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=ok replay_status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0 strict_mismatches=0\n",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        payload = json.loads(json_result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["replay_status"], "ok")
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_mismatch_count": 0,
                "expected_expectation_mismatch_count": 0,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(payload["strict_profile_mismatches"], [])

    def test_pack_replay_strict_profile_clean_detects_fixture_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            summary_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--strict-profile",
                "clean",
                "--summary",
            )
            json_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--strict-profile",
                "clean",
            )

        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=error replay_status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=3 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:1,runtime_error:0 plan=3 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0 strict_mismatches=2\n",
        )

        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(json_result.stderr, "")
        payload = json.loads(json_result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["replay_status"], "error")
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_mismatch_count": 0,
                "expected_expectation_mismatch_count": 0,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            payload["strict_profile_mismatches"],
            [
                {"field": "mismatch_count", "expected": 0, "actual": 1},
                {"field": "expectation_mismatch_count", "expected": 0, "actual": 1},
            ],
        )

    def test_pack_replay_strict_profile_clean_can_merge_with_explicit_overrides(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict-profile",
            "clean",
            "--expected-fixture-count",
            "4",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_fixture_count": 4,
                "expected_mismatch_count": 0,
                "expected_expectation_mismatch_count": 0,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(payload["strict_profile_mismatches"], [])

    def test_pack_replay_strict_profile_clean_can_merge_with_fixture_class_histogram_contract(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict-profile",
            "clean",
            "--expected-fixture-class-counts",
            "ok=4,expectation_mismatch=0,runtime_error=0",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_fixture_class_counts": {
                    "ok": 4,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "expected_mismatch_count": 0,
                "expected_expectation_mismatch_count": 0,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(payload["strict_profile_mismatches"], [])

    def test_pack_replay_strict_profile_pack_specific_clean_presets_pass_for_checked_in_packs(self) -> None:
        cases = [
            (
                INGEST_NORMALIZE_PACK,
                "ingest-normalize-clean",
                "ingest-normalize",
                "inline-statements",
                2,
            ),
            (
                DEDUP_CLUSTER_PACK,
                "dedup-cluster-clean",
                "sprint-7-program-pack-2-dedup-cluster",
                "fixture-matrix",
                4,
            ),
            (
                ALERT_ROUTING_PACK,
                "alert-routing-clean",
                "sprint-7-pack-03-alert-routing",
                "fixture-matrix",
                3,
            ),
            (
                REFS_HANDOFF_PACK,
                "refs-handoff-clean",
                "sprint-7-program-pack-4-refs-handoff",
                "fixture-matrix",
                4,
            ),
        ]

        for pack_path, strict_profile_name, expected_pack_id, expected_baseline_shape, expected_total_fixture_count in cases:
            with self.subTest(strict_profile=strict_profile_name):
                result = self._run_cli(
                    "pack-replay",
                    str(pack_path),
                    "--strict-profile",
                    strict_profile_name,
                )

                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["replay_status"], "ok")
                self.assertEqual(
                    payload["strict_profile"],
                    {
                        "expected_pack_id": expected_pack_id,
                        "expected_baseline_shape": expected_baseline_shape,
                        "expected_total_fixture_count": expected_total_fixture_count,
                        "expected_fixture_class_counts": {
                            "ok": expected_total_fixture_count,
                            "expectation_mismatch": 0,
                            "runtime_error": 0,
                        },
                        "expected_action_plan_count": {
                            "ingest-normalize-clean": 2,
                            "dedup-cluster-clean": 3,
                            "alert-routing-clean": 3,
                            "refs-handoff-clean": 3,
                        }[strict_profile_name],
                        "expected_resolved_refs_count": {
                            "ingest-normalize-clean": 1,
                            "dedup-cluster-clean": 0,
                            "alert-routing-clean": 0,
                            "refs-handoff-clean": 21,
                        }[strict_profile_name],
                        "expected_mismatch_count": 0,
                        "expected_expectation_mismatch_count": 0,
                        "expected_runtime_error_count": 0,
                        "expected_rule_source_status": "ok",
                    },
                )
                self.assertEqual(payload["strict_profile_mismatches"], [])

    def test_pack_replay_strict_profile_pack_specific_clean_detects_wrong_pack(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(ALERT_ROUTING_PACK),
            "--strict-profile",
            "dedup-cluster-clean",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["replay_status"], "ok")
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_pack_id": "sprint-7-program-pack-2-dedup-cluster",
                "expected_baseline_shape": "fixture-matrix",
                "expected_total_fixture_count": 4,
                "expected_fixture_class_counts": {
                    "ok": 4,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "expected_action_plan_count": 3,
                "expected_resolved_refs_count": 0,
                "expected_mismatch_count": 0,
                "expected_expectation_mismatch_count": 0,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            payload["strict_profile_mismatches"],
            [
                {"field": "total_fixture_count", "expected": 4, "actual": 3},
                {
                    "field": "pack_id",
                    "expected": "sprint-7-program-pack-2-dedup-cluster",
                    "actual": "sprint-7-pack-03-alert-routing",
                },
                {
                    "field": "fixture_class_counts",
                    "expected": {"ok": 4, "expectation_mismatch": 0, "runtime_error": 0},
                    "actual": {"ok": 3, "expectation_mismatch": 0, "runtime_error": 0},
                },
            ],
        )

    def test_pack_replay_strict_profile_pack_specific_clean_detects_baseline_shape_drift(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(INGEST_NORMALIZE_PACK),
            "--strict-profile",
            "dedup-cluster-clean",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["replay_status"], "ok")
        self.assertEqual(
            payload["strict_profile_mismatches"],
            [
                {"field": "total_fixture_count", "expected": 4, "actual": 2},
                {
                    "field": "baseline_shape",
                    "expected": "fixture-matrix",
                    "actual": "inline-statements",
                },
                {
                    "field": "pack_id",
                    "expected": "sprint-7-program-pack-2-dedup-cluster",
                    "actual": "ingest-normalize",
                },
                {
                    "field": "fixture_class_counts",
                    "expected": {"ok": 4, "expectation_mismatch": 0, "runtime_error": 0},
                    "actual": {"ok": 2, "expectation_mismatch": 0, "runtime_error": 0},
                },
                {"field": "action_plan_count", "expected": 3, "actual": 2},
                {"field": "resolved_ref_count", "expected": 0, "actual": 1},
            ],
        )

    def test_pack_replay_expected_selector_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-mismatch-count",
            "0",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-mismatch-count requires --strict\n",
        )

    def test_pack_replay_expected_total_fixture_count_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-total-fixture-count",
            "4",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-total-fixture-count requires --strict\n",
        )

    def test_pack_replay_expected_selected_fixture_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-selected-fixture",
            "attach_ops",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-selected-fixture requires --strict\n",
        )

    def test_pack_replay_expected_ok_fixture_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-ok-fixture",
            "attach_ops",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-ok-fixture requires --strict\n",
        )

    def test_pack_replay_expected_expectation_mismatch_fixture_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-expectation-mismatch-fixture",
            "attach_ops",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-expectation-mismatch-fixture requires --strict\n",
        )

    def test_pack_replay_expected_runtime_error_fixture_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-runtime-error-fixture",
            "new_ops_time_miss",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-runtime-error-fixture requires --strict\n",
        )

    def test_pack_replay_expected_fixture_class_counts_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-fixture-class-counts",
            "ok=4,expectation_mismatch=0,runtime_error=0",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-fixture-class-counts requires --strict\n",
        )

    def test_pack_replay_expected_mismatch_field_counts_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-mismatch-field-counts",
            "actions=0,trace=0,action_plan=0,resolved_refs=0",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-mismatch-field-counts requires --strict\n",
        )

    def test_pack_replay_expected_action_plan_mismatch_fixture_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-action-plan-mismatch-fixture",
            "attach_ops",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-action-plan-mismatch-fixture requires --strict\n",
        )

    def test_pack_replay_rejects_incomplete_expected_fixture_class_counts_contract(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-fixture-class-counts",
            "ok=4,runtime_error=0",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-fixture-class-counts must include counts for: expectation_mismatch\n",
        )

    def test_pack_replay_strict_rejects_negative_expected_counts(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-runtime-error-count",
            "-1",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-runtime-error-count must be >= 0\n",
        )

    def test_pack_replay_expected_expectation_mismatch_selector_requires_strict(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--expected-expectation-mismatch-count",
            "0",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --expected-expectation-mismatch-count requires --strict\n",
        )

    def test_pack_replay_strict_expected_counts_can_greenlight_known_fixture_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            summary_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--strict",
                "--expected-fixture-count",
                "4",
                "--expected-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "0",
                "--expected-rule-source-status",
                "ok",
            )
            json_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--strict",
                "--expected-fixture-count",
                "4",
                "--expected-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "0",
                "--expected-rule-source-status",
                "ok",
            )

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=ok replay_status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=3 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:1,runtime_error:0 plan=3 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0 strict_mismatches=0\n",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_fixture_count": 4,
                "expected_mismatch_count": 1,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(envelope["strict_profile_mismatches"], [])
        self.assertEqual(envelope["summary"]["mismatch_count"], 1)

    def test_pack_replay_strict_expected_total_fixture_count_can_hold_subset_replays_to_pack_size(self) -> None:
        green_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture",
            "new_ops_time_miss",
            "--summary",
            "--strict",
            "--expected-fixture-count",
            "1",
            "--expected-total-fixture-count",
            "4",
            "--expected-mismatch-count",
            "0",
            "--expected-runtime-error-count",
            "0",
            "--expected-rule-source-status",
            "ok",
        )
        red_result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture",
            "new_ops_time_miss",
            "--strict",
            "--expected-fixture-count",
            "1",
            "--expected-total-fixture-count",
            "5",
            "--expected-mismatch-count",
            "0",
            "--expected-runtime-error-count",
            "0",
            "--expected-rule-source-status",
            "ok",
        )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=1/4 matched=1 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:1,expectation_mismatch:0,runtime_error:0 plan=1 resolved_refs=0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_fixture_count": 1,
                "expected_total_fixture_count": 5,
                "expected_mismatch_count": 0,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "total_fixture_count",
                    "expected": 5,
                    "actual": 4,
                }
            ],
        )

    def test_pack_replay_strict_expected_selected_fixture_ids_can_hold_class_filtered_slice_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            green_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--fixture-class",
                "expectation_mismatch",
                "--fixture-class",
                "runtime_error",
                "--summary",
                "--strict",
                "--expected-fixture-count",
                "2",
                "--expected-selected-fixture",
                "attach_ops",
                "--expected-selected-fixture",
                "new_ops_time_miss",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--fixture-class",
                "expectation_mismatch",
                "--fixture-class",
                "runtime_error",
                "--strict",
                "--expected-fixture-count",
                "2",
                "--expected-selected-fixture",
                "attach_ops",
                "--expected-selected-fixture",
                "no_match_unknown_category",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=2/4 matched=0 mismatches=2 runtime_errors=1 rule_source=ok fixture_classes=ok:0,expectation_mismatch:1,runtime_error:1 plan=1 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_fixture_count": 2,
                "expected_selected_fixture_ids": ["attach_ops", "no_match_unknown_category"],
                "expected_mismatch_count": 2,
                "expected_expectation_mismatch_count": 1,
                "expected_runtime_error_count": 1,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(envelope["selected_fixture_ids"], ["attach_ops", "new_ops_time_miss"])
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "selected_fixture_ids",
                    "expected": ["attach_ops", "no_match_unknown_category"],
                    "actual": ["attach_ops", "new_ops_time_miss"],
                }
            ],
        )

    def test_pack_replay_strict_expected_failure_partition_fixture_ids_can_hold_exact_class_membership(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            green_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--strict",
                "--expected-fixture-count",
                "4",
                "--expected-expectation-mismatch-fixture",
                "attach_ops",
                "--expected-runtime-error-fixture",
                "new_ops_time_miss",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--strict",
                "--expected-fixture-count",
                "4",
                "--expected-expectation-mismatch-fixture",
                "attach_ops",
                "--expected-runtime-error-fixture",
                "no_match_unknown_category",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=2 mismatches=2 runtime_errors=1 rule_source=ok fixture_classes=ok:2,expectation_mismatch:1,runtime_error:1 plan=2 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_fixture_count": 4,
                "expected_expectation_mismatch_fixture_ids": ["attach_ops"],
                "expected_runtime_error_fixture_ids": ["no_match_unknown_category"],
                "expected_mismatch_count": 2,
                "expected_expectation_mismatch_count": 1,
                "expected_runtime_error_count": 1,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            envelope["summary"]["fixture_class_ids"],
            {
                "ok": ["new_security_geo_miss", "no_match_unknown_category"],
                "expectation_mismatch": ["attach_ops"],
                "runtime_error": ["new_ops_time_miss"],
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "fixture_class_ids.runtime_error",
                    "expected": ["no_match_unknown_category"],
                    "actual": ["new_ops_time_miss"],
                }
            ],
        )

    def test_pack_replay_strict_can_assert_exact_ok_partition_fixture_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            green_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--strict",
                "--expected-fixture-count",
                "4",
                "--expected-ok-fixture",
                "new_security_geo_miss",
                "--expected-ok-fixture",
                "no_match_unknown_category",
                "--expected-expectation-mismatch-fixture",
                "attach_ops",
                "--expected-runtime-error-fixture",
                "new_ops_time_miss",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--strict",
                "--expected-fixture-count",
                "4",
                "--expected-ok-fixture",
                "attach_ops",
                "--expected-ok-fixture",
                "no_match_unknown_category",
                "--expected-expectation-mismatch-fixture",
                "attach_ops",
                "--expected-runtime-error-fixture",
                "new_ops_time_miss",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=2 mismatches=2 runtime_errors=1 rule_source=ok fixture_classes=ok:2,expectation_mismatch:1,runtime_error:1 plan=2 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_fixture_count": 4,
                "expected_ok_fixture_ids": ["attach_ops", "no_match_unknown_category"],
                "expected_expectation_mismatch_fixture_ids": ["attach_ops"],
                "expected_runtime_error_fixture_ids": ["new_ops_time_miss"],
                "expected_mismatch_count": 2,
                "expected_expectation_mismatch_count": 1,
                "expected_runtime_error_count": 1,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            envelope["summary"]["fixture_class_ids"],
            {
                "ok": ["new_security_geo_miss", "no_match_unknown_category"],
                "expectation_mismatch": ["attach_ops"],
                "runtime_error": ["new_ops_time_miss"],
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "fixture_class_ids.ok",
                    "expected": ["attach_ops", "no_match_unknown_category"],
                    "actual": ["new_security_geo_miss", "no_match_unknown_category"],
                }
            ],
        )

    def test_pack_replay_strict_can_assert_exact_fixture_class_histogram(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            green_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--strict",
                "--expected-fixture-class-counts",
                "ok=2,expectation_mismatch=1,runtime_error=1",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--strict",
                "--expected-fixture-class-counts",
                "ok=3,expectation_mismatch=1,runtime_error=0",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=2 mismatches=2 runtime_errors=1 rule_source=ok fixture_classes=ok:2,expectation_mismatch:1,runtime_error:1 plan=2 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_fixture_class_counts": {
                    "ok": 3,
                    "expectation_mismatch": 1,
                    "runtime_error": 0,
                },
                "expected_mismatch_count": 2,
                "expected_expectation_mismatch_count": 1,
                "expected_runtime_error_count": 1,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            envelope["summary"]["fixture_class_counts"],
            {
                "ok": 2,
                "expectation_mismatch": 1,
                "runtime_error": 1,
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "fixture_class_counts",
                    "expected": {
                        "ok": 3,
                        "expectation_mismatch": 1,
                        "runtime_error": 0,
                    },
                    "actual": {
                        "ok": 2,
                        "expectation_mismatch": 1,
                        "runtime_error": 1,
                    },
                }
            ],
        )

    def test_pack_replay_strict_can_assert_exact_mismatch_field_histogram_and_action_plan_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "action-plan-pack"
            pack_dir.mkdir()
            (pack_dir / "program.erz").write_text(
                "\n".join(
                    [
                        "erz{v:1}",
                        'rule{id:"route_ops",when:["event_type_present","payload_has:severity"],then:[{kind:"notify",params:{channel:"ops",severity_ref:"@sev_label"}}]}',
                        'rf{id:"sev_label",v:"high"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (pack_dir / "baseline.json").write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "id": "route_ops",
                                "when": ["event_type_present", "payload_has:severity"],
                                "then": [
                                    {
                                        "kind": "notify",
                                        "params": {"channel": "ops", "severity_ref": "@sev_label"},
                                    }
                                ],
                            }
                        ],
                        "fixtures": [
                            {
                                "id": "fixture-01",
                                "event": {"type": "ingest", "payload": {"severity": "high"}},
                                "expected_actions": [
                                    {
                                        "kind": "notify",
                                        "params": {"channel": "ops", "severity_ref": "@sev_label"},
                                    }
                                ],
                                "expected_trace": [
                                    {
                                        "rule_id": "route_ops",
                                        "matched_clauses": ["event_type_present", "payload_has:severity"],
                                        "score": 1.0,
                                    }
                                ],
                                "expected_action_plan": [
                                    {
                                        "step": 1,
                                        "kind": "notify",
                                        "params": {"channel": "ops", "severity": "critical"},
                                    }
                                ],
                                "expected_resolved_refs": {"sev_label": "high"},
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            green_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--strict",
                "--expected-fixture-count",
                "1",
                "--expected-mismatch-count",
                "1",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "0",
                "--expected-rule-source-status",
                "ok",
                "--expected-mismatch-field-counts",
                "actions=0,trace=0,action_plan=1,resolved_refs=0",
                "--expected-action-plan-mismatch-fixture",
                "fixture-01",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--strict",
                "--expected-fixture-count",
                "1",
                "--expected-mismatch-count",
                "1",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "0",
                "--expected-rule-source-status",
                "ok",
                "--expected-mismatch-field-counts",
                "actions=0,trace=0,action_plan=1,resolved_refs=0",
                "--expected-action-plan-mismatch-fixture",
                "fixture-02",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=error pack=action-plan-pack fixtures=1 matched=0 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:0,expectation_mismatch:1,runtime_error:0 plan=1 resolved_refs=1 mismatch_fields=actions:0,trace:0,action_plan:1,resolved_refs:0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_fixture_count": 1,
                "expected_mismatch_field_counts": {
                    "actions": 0,
                    "trace": 0,
                    "action_plan": 1,
                    "resolved_refs": 0,
                },
                "expected_mismatch_field_ids.action_plan": ["fixture-02"],
                "expected_mismatch_count": 1,
                "expected_expectation_mismatch_count": 1,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            envelope["summary"]["mismatch_field_ids"],
            {
                "actions": [],
                "trace": [],
                "action_plan": ["fixture-01"],
                "resolved_refs": [],
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "mismatch_field_ids.action_plan",
                    "expected": ["fixture-02"],
                    "actual": ["fixture-01"],
                }
            ],
        )

    def test_pack_replay_fixture_class_filter_can_pair_with_strict_partition_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            green_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--fixture-class",
                "runtime_error",
                "--summary",
                "--strict",
                "--expected-fixture-count",
                "1",
                "--expected-selected-fixture",
                "new_ops_time_miss",
                "--expected-runtime-error-fixture",
                "new_ops_time_miss",
                "--expected-mismatch-count",
                "1",
                "--expected-expectation-mismatch-count",
                "0",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--fixture-class",
                "runtime_error",
                "--strict",
                "--expected-fixture-count",
                "1",
                "--expected-selected-fixture",
                "new_ops_time_miss",
                "--expected-runtime-error-fixture",
                "no_match_unknown_category",
                "--expected-mismatch-count",
                "1",
                "--expected-expectation-mismatch-count",
                "0",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=1/4 matched=0 mismatches=1 runtime_errors=1 rule_source=ok fixture_classes=ok:0,expectation_mismatch:0,runtime_error:1 plan=0 resolved_refs=0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(envelope["selected_fixture_ids"], ["new_ops_time_miss"])
        self.assertEqual(
            envelope["summary"]["fixture_class_ids"],
            {
                "ok": [],
                "expectation_mismatch": [],
                "runtime_error": ["new_ops_time_miss"],
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "fixture_class_ids.runtime_error",
                    "expected": ["no_match_unknown_category"],
                    "actual": ["new_ops_time_miss"],
                }
            ],
        )

    def test_pack_replay_strict_can_distinguish_expectation_mismatch_from_runtime_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            green_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--strict",
                "--expected-fixture-count",
                "4",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "1",
                "--expected-runtime-error-count",
                "1",
                "--expected-rule-source-status",
                "ok",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--strict",
                "--expected-fixture-count",
                "4",
                "--expected-mismatch-count",
                "2",
                "--expected-expectation-mismatch-count",
                "2",
                "--expected-runtime-error-count",
                "0",
                "--expected-rule-source-status",
                "ok",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout,
            "status=ok replay_status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=2 mismatches=2 runtime_errors=1 rule_source=ok fixture_classes=ok:2,expectation_mismatch:1,runtime_error:1 plan=2 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0 strict_mismatches=0\n",
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_fixture_count": 4,
                "expected_mismatch_count": 2,
                "expected_expectation_mismatch_count": 2,
                "expected_runtime_error_count": 0,
                "expected_rule_source_status": "ok",
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "expectation_mismatch_count",
                    "expected": 2,
                    "actual": 1,
                },
                {
                    "field": "runtime_error_count",
                    "expected": 0,
                    "actual": 1,
                },
            ],
        )

    def test_pack_replay_strict_rule_source_selector_can_greenlight_inline_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "ingest-normalize"
            shutil.copytree(INGEST_NORMALIZE_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            for statement in baseline:
                if statement.get("tag") == "tr":
                    statement["fields"]["rule_id"] = "totally_wrong_rule"
                    statement["fields"]["seed"] = "wrong-seed"
                    break
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            result = self._run_cli(
                "pack-replay",
                str(pack_dir),
                "--summary",
                "--strict",
                "--expected-fixture-count",
                "2",
                "--expected-mismatch-count",
                "0",
                "--expected-runtime-error-count",
                "0",
                "--expected-rule-source-status",
                "mismatch",
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "status=ok replay_status=error pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=mismatch fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1 strict_mismatches=0\n",
        )

    def test_pack_replay_strict_reports_selector_mismatches_without_hiding_raw_green_replay(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-fixture-count",
            "4",
            "--expected-mismatch-count",
            "1",
            "--expected-runtime-error-count",
            "0",
            "--expected-rule-source-status",
            "ok",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "mismatch_count",
                    "expected": 1,
                    "actual": 0,
                }
            ],
        )

    def test_pack_replay_rejects_duplicate_expected_selected_fixture_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-selected-fixture",
            "attach_ops",
            "--expected-selected-fixture",
            "attach_ops",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: duplicate --expected-selected-fixture selector: attach_ops\n",
        )

    def test_pack_replay_rejects_duplicate_expected_ok_fixture_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-ok-fixture",
            "attach_ops",
            "--expected-ok-fixture",
            "attach_ops",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: duplicate --expected-ok-fixture selector: attach_ops\n",
        )

    def test_pack_replay_rejects_duplicate_expected_expectation_mismatch_fixture_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-expectation-mismatch-fixture",
            "attach_ops",
            "--expected-expectation-mismatch-fixture",
            "attach_ops",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: duplicate --expected-expectation-mismatch-fixture selector: attach_ops\n",
        )

    def test_pack_replay_rejects_duplicate_expected_runtime_error_fixture_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict",
            "--expected-runtime-error-fixture",
            "new_ops_time_miss",
            "--expected-runtime-error-fixture",
            "new_ops_time_miss",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: duplicate --expected-runtime-error-fixture selector: new_ops_time_miss\n",
        )

    def test_pack_replay_rejects_duplicate_fixture_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture",
            "new_ops_time_miss",
            "--fixture",
            "new_ops_time_miss",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: duplicate --fixture selector: new_ops_time_miss\n")

    def test_pack_replay_rejects_duplicate_fixture_class_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture-class",
            "ok",
            "--fixture-class",
            "ok",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: duplicate --fixture-class selector: ok\n")

    def test_pack_replay_rejects_duplicate_mismatch_field_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--mismatch-field",
            "actions",
            "--mismatch-field",
            "actions",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: duplicate --mismatch-field selector: actions\n")

    def test_pack_replay_rejects_unmatched_mismatch_field_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--mismatch-field",
            "action_plan",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: unmatched --mismatch-field selector(s): action_plan\n",
        )

    def test_pack_replay_rejects_unknown_fixture_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture",
            "missing_case",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: unknown --fixture selector(s): missing_case\n")

    def test_pack_replay_rejects_unmatched_include_fixture_glob(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--include-fixture",
            "missing_*",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: unmatched --include-fixture selector(s): missing_*\n")

    def test_pack_replay_rejects_unmatched_exclude_fixture_glob(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--exclude-fixture",
            "missing_*",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: unmatched --exclude-fixture selector(s): missing_*\n")

    def test_pack_replay_rejects_unmatched_fixture_class_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--fixture-class",
            "runtime_error",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: unmatched --fixture-class selector(s): runtime_error\n")

    def test_pack_replay_rejects_selector_sets_that_match_zero_fixtures(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--include-fixture",
            "new_*",
            "--exclude-fixture",
            "new_*",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: fixture selectors matched zero fixtures after applying: --include-fixture new_*; --exclude-fixture new_*\n",
        )

    def test_pack_replay_json_reports_alert_routing_fixture_match(self) -> None:
        result = self._run_cli("pack-replay", str(ALERT_ROUTING_PACK))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["target_path"], str(ALERT_ROUTING_PACK.resolve()))
        self.assertEqual(envelope["pack_id"], "sprint-7-pack-03-alert-routing")
        self.assertEqual(envelope["program"], "alert-routing.erz")
        self.assertEqual(envelope["program_path"], str((ALERT_ROUTING_PACK / "alert-routing.erz").resolve()))
        self.assertEqual(envelope["baseline"], "alert-routing.baseline.json")
        self.assertEqual(
            envelope["baseline_path"],
            str((ALERT_ROUTING_PACK / "alert-routing.baseline.json").resolve()),
        )
        self.assertEqual(envelope["rule_source_status"], "ok")
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 3,
                "matched_count": 3,
                "mismatch_count": 0,
                "runtime_error_count": 0,
                "total_fixture_count": 3,
                "fixture_class_counts": {
                    "ok": 3,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": ["critical_high_conf", "critical_low_conf", "warning_high_conf"],
                    "expectation_mismatch": [],
                    "runtime_error": [],
                },
                "action_plan_count": 3,
                "resolved_ref_count": 0,
            },
        )
        self.assertEqual([fixture["status"] for fixture in envelope["fixtures"]], ["ok", "ok", "ok"])
        self.assertEqual(
            [fixture["fixture_class"] for fixture in envelope["fixtures"]],
            ["ok", "ok", "ok"],
        )
        self.assertEqual(
            envelope["fixtures"][0]["action_plan"],
            [
                {
                    "step": 1,
                    "kind": "route",
                    "params": {
                        "priority": "p1",
                        "reason": "critical+high_confidence",
                        "target": "oncall_primary",
                        "via": "pager",
                    },
                }
            ],
        )

    def test_pack_replay_reports_fixture_mismatch_with_expected_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            result = self._run_cli("pack-replay", str(pack_dir))

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["rule_source_status"], "ok")
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 4,
                "matched_count": 3,
                "mismatch_count": 1,
                "runtime_error_count": 0,
                "total_fixture_count": 4,
                "fixture_class_counts": {
                    "ok": 3,
                    "expectation_mismatch": 1,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": [
                        "new_security_geo_miss",
                        "new_ops_time_miss",
                        "no_match_unknown_category",
                    ],
                    "expectation_mismatch": ["attach_ops"],
                    "runtime_error": [],
                },
                "action_plan_count": 3,
                "resolved_ref_count": 0,
                "mismatch_field_counts": {
                    "actions": 1,
                    "trace": 0,
                    "action_plan": 0,
                    "resolved_refs": 0,
                },
                "mismatch_field_ids": {
                    "actions": ["attach_ops"],
                    "trace": [],
                    "action_plan": [],
                    "resolved_refs": [],
                },
            },
        )
        self.assertEqual(envelope["fixtures"][0]["status"], "mismatch")
        self.assertEqual(envelope["fixtures"][0]["fixture_class"], "expectation_mismatch")
        self.assertEqual(envelope["fixtures"][0]["mismatch_fields"], ["actions"])
        self.assertEqual(envelope["fixtures"][0]["expected_actions"], [])
        self.assertIn("expected_trace", envelope["fixtures"][0])

    def test_pack_replay_reports_fixture_class_ids_for_mismatch_and_runtime_error_mix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "dedup-cluster"
            shutil.copytree(DEDUP_CLUSTER_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline["fixtures"][2]["event"]["payload"] = "oops"
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            summary_result = self._run_cli("pack-replay", str(pack_dir), "--summary")
            json_result = self._run_cli("pack-replay", str(pack_dir))

        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            "status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=2 mismatches=2 runtime_errors=1 rule_source=ok fixture_classes=ok:2,expectation_mismatch:1,runtime_error:1 plan=2 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0\n",
        )

        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(json_result.stderr, "")

        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["rule_source_status"], "ok")
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 4,
                "matched_count": 2,
                "mismatch_count": 2,
                "runtime_error_count": 1,
                "total_fixture_count": 4,
                "fixture_class_counts": {
                    "ok": 2,
                    "expectation_mismatch": 1,
                    "runtime_error": 1,
                },
                "fixture_class_ids": {
                    "ok": ["new_security_geo_miss", "no_match_unknown_category"],
                    "expectation_mismatch": ["attach_ops"],
                    "runtime_error": ["new_ops_time_miss"],
                },
                "action_plan_count": 2,
                "resolved_ref_count": 0,
                "mismatch_field_counts": {
                    "actions": 1,
                    "trace": 0,
                    "action_plan": 0,
                    "resolved_refs": 0,
                },
                "mismatch_field_ids": {
                    "actions": ["attach_ops"],
                    "trace": [],
                    "action_plan": [],
                    "resolved_refs": [],
                },
            },
        )
        self.assertEqual(
            [fixture["fixture_class"] for fixture in envelope["fixtures"]],
            ["expectation_mismatch", "ok", "runtime_error", "ok"],
        )
        self.assertNotIn("error", envelope["fixtures"][0])
        self.assertIn("error", envelope["fixtures"][2])

    def test_pack_replay_supports_inline_statement_baseline_pack(self) -> None:
        result = self._run_cli("pack-replay", str(INGEST_NORMALIZE_PACK))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["pack_id"], "ingest-normalize")
        self.assertEqual(envelope["program"], "program.erz")
        self.assertEqual(envelope["baseline"], "baseline.json")
        self.assertEqual(envelope["baseline_shape"], "inline-statements")
        self.assertEqual(envelope["rule_source_status"], "ok")
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 2,
                "matched_count": 2,
                "mismatch_count": 0,
                "runtime_error_count": 0,
                "total_fixture_count": 2,
                "fixture_class_counts": {
                    "ok": 2,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": ["event-01-ingest", "event-02-normalize"],
                    "expectation_mismatch": [],
                    "runtime_error": [],
                },
                "action_plan_count": 2,
                "resolved_ref_count": 1,
            },
        )
        self.assertEqual(
            [fixture["id"] for fixture in envelope["fixtures"]],
            ["event-01-ingest", "event-02-normalize"],
        )
        self.assertEqual(
            [fixture["fixture_class"] for fixture in envelope["fixtures"]],
            ["ok", "ok"],
        )
        self.assertEqual(
            envelope["fixtures"][0]["actions"],
            [{"kind": "queue_normalize", "params": {"pipeline": "nlp-v1"}}],
        )
        self.assertEqual(
            envelope["fixtures"][1]["actions"],
            [
                {
                    "kind": "notify",
                    "params": {
                        "channel": "ops_dispatch",
                        "template_ref": "@tpl_norm_ready",
                    },
                }
            ],
        )
        self.assertEqual(
            [fixture["trace"][0]["rule_id"] for fixture in envelope["fixtures"]],
            ["r_ingest_to_normalize", "r_normalize_publish"],
        )

    def test_pack_replay_reports_inline_statement_pack_mismatch_when_program_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "ingest-normalize"
            shutil.copytree(INGEST_NORMALIZE_PACK, pack_dir)

            program_path = pack_dir / "program.erz"
            program_path.write_text(
                program_path.read_text(encoding="utf-8").replace(
                    'payload_path_contains:text=Unfall',
                    'payload_path_contains:text=Störung',
                    1,
                ),
                encoding="utf-8",
            )

            result = self._run_cli("pack-replay", str(pack_dir))

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["baseline_shape"], "inline-statements")
        self.assertEqual(envelope["rule_source_status"], "mismatch")
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 2,
                "matched_count": 1,
                "mismatch_count": 1,
                "runtime_error_count": 0,
                "total_fixture_count": 2,
                "fixture_class_counts": {
                    "ok": 1,
                    "expectation_mismatch": 1,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": ["event-02-normalize"],
                    "expectation_mismatch": ["event-01-ingest"],
                    "runtime_error": [],
                },
                "action_plan_count": 1,
                "resolved_ref_count": 1,
                "mismatch_field_counts": {
                    "actions": 1,
                    "trace": 1,
                    "action_plan": 1,
                    "resolved_refs": 0,
                },
                "mismatch_field_ids": {
                    "actions": ["event-01-ingest"],
                    "trace": ["event-01-ingest"],
                    "action_plan": ["event-01-ingest"],
                    "resolved_refs": [],
                },
            },
        )
        self.assertEqual(envelope["fixtures"][0]["status"], "mismatch")
        self.assertEqual(envelope["fixtures"][0]["fixture_class"], "expectation_mismatch")
        self.assertEqual(envelope["fixtures"][1]["status"], "ok")
        self.assertEqual(envelope["fixtures"][1]["fixture_class"], "ok")
        self.assertEqual(
            envelope["fixtures"][0]["expected_actions"],
            [{"kind": "queue_normalize", "params": {"pipeline": "nlp-v1"}}],
        )
        self.assertIn("program_rules", envelope)
        self.assertIn("baseline_rules", envelope)
        self.assertIn("program_statements", envelope)
        self.assertIn("baseline_statements", envelope)

    def test_pack_replay_reports_inline_statement_trace_drift_without_false_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "ingest-normalize"
            shutil.copytree(INGEST_NORMALIZE_PACK, pack_dir)

            baseline_path = pack_dir / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            for statement in baseline:
                if statement.get("tag") == "tr":
                    statement["fields"]["rule_id"] = "totally_wrong_rule"
                    statement["fields"]["seed"] = "wrong-seed"
                    break
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            result = self._run_cli("pack-replay", str(pack_dir))

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["baseline_shape"], "inline-statements")
        self.assertEqual(envelope["rule_source_status"], "mismatch")
        self.assertEqual(
            envelope["summary"],
            {
                "fixture_count": 2,
                "matched_count": 2,
                "mismatch_count": 0,
                "runtime_error_count": 0,
                "total_fixture_count": 2,
                "fixture_class_counts": {
                    "ok": 2,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "fixture_class_ids": {
                    "ok": ["event-01-ingest", "event-02-normalize"],
                    "expectation_mismatch": [],
                    "runtime_error": [],
                },
                "action_plan_count": 2,
                "resolved_ref_count": 1,
            },
        )
        self.assertEqual([fixture["status"] for fixture in envelope["fixtures"]], ["ok", "ok"])
        self.assertIn("program_statements", envelope)
        self.assertIn("baseline_statements", envelope)


    def test_pack_replay_single_pack_invalid_root_preserves_legacy_error_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_baseline_dir = Path(tmpdir) / "missing-baseline"
            missing_baseline_dir.mkdir()
            (missing_baseline_dir / "program.erz").write_text(
                "rl id:r when all() then notify(channel=ops)",
                encoding="utf-8",
            )

            missing_program_dir = Path(tmpdir) / "missing-program"
            missing_program_dir.mkdir()
            (missing_program_dir / "baseline.json").write_text(
                json.dumps({"rules": [], "fixtures": [{"id": "fixture-01", "event": {}, "expected_actions": []}]}, indent=2),
                encoding="utf-8",
            )

            cases = [
                (
                    missing_baseline_dir,
                    "error: program pack directory must contain one baseline JSON file named baseline.json or *.baseline.json\n",
                ),
                (
                    missing_program_dir,
                    "error: program pack directory must contain one .erz program file\n",
                ),
            ]

            for pack_dir, expected_stderr in cases:
                with self.subTest(path=pack_dir.name):
                    result = self._run_cli("pack-replay", str(pack_dir))

                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, expected_stderr)

    def test_pack_replay_collection_directory_summary_reports_aggregate_and_per_pack_lines(self) -> None:
        result = self._run_cli("pack-replay", str(PROGRAM_PACK_FIXTURES), "--summary")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=ok packs=4 ok_packs=4 error_packs=0 fixtures=13 matched=13 mismatches=0 runtime_errors=0 rule_sources=ok:4,mismatch:0 fixture_classes=ok:13,expectation_mismatch:0,runtime_error:0 plan=11 resolved_refs=22",
                "pack[1] path=alert-routing status=ok pack=sprint-7-pack-03-alert-routing fixtures=3 matched=3 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[2] path=dedup-cluster status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[3] path=ingest-normalize status=ok pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1",
                "pack[4] path=refs-handoff status=ok pack=sprint-7-program-pack-4-refs-handoff fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=21",
            ],
        )

    def test_pack_replay_collection_directory_json_envelope_reports_selected_paths_and_summary(self) -> None:
        result = self._run_cli("pack-replay", str(PROGRAM_PACK_FIXTURES))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["collection_kind"], "directory")
        self.assertEqual(envelope["target_path"], str(PROGRAM_PACK_FIXTURES.resolve()))
        self.assertEqual(
            envelope["selected_pack_paths"],
            ["alert-routing", "dedup-cluster", "ingest-normalize", "refs-handoff"],
        )
        self.assertEqual(
            envelope["summary"],
            {
                "pack_count": 4,
                "total_pack_count": 4,
                "ok_pack_count": 4,
                "error_pack_count": 0,
                "fixture_count": 13,
                "matched_count": 13,
                "mismatch_count": 0,
                "runtime_error_count": 0,
                "rule_source_status_counts": {"ok": 4, "mismatch": 0},
                "fixture_class_counts": {
                    "ok": 13,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "action_plan_count": 11,
                "resolved_ref_count": 22,
            },
        )
        self.assertEqual(
            [pack["path"] for pack in envelope["packs"]],
            ["alert-routing", "dedup-cluster", "ingest-normalize", "refs-handoff"],
        )
        self.assertEqual([pack["status"] for pack in envelope["packs"]], ["ok", "ok", "ok", "ok"])
        self.assertEqual(
            [pack["target_path"] for pack in envelope["packs"]],
            [
                str((PROGRAM_PACK_FIXTURES / "alert-routing").resolve()),
                str((PROGRAM_PACK_FIXTURES / "dedup-cluster").resolve()),
                str((PROGRAM_PACK_FIXTURES / "ingest-normalize").resolve()),
                str((PROGRAM_PACK_FIXTURES / "refs-handoff").resolve()),
            ],
        )

    def test_pack_replay_collection_directory_pack_globs_filter_selected_paths_and_summary(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--include-pack",
            "*cluster",
            "--include-pack",
            "*normalize",
            "--exclude-pack",
            "alert*",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=ok packs=2 total_packs=4 ok_packs=2 error_packs=0 fixtures=6 matched=6 mismatches=0 runtime_errors=0 rule_sources=ok:2,mismatch:0 fixture_classes=ok:6,expectation_mismatch:0,runtime_error:0 plan=5 resolved_refs=1",
                "pack[1] path=dedup-cluster status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[2] path=ingest-normalize status=ok pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1",
            ],
        )

        json_result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--include-pack",
            "*cluster",
            "--include-pack",
            "*normalize",
            "--exclude-pack",
            "alert*",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["selected_pack_paths"], ["dedup-cluster", "ingest-normalize"])
        self.assertEqual(envelope["include_pack_globs"], ["*cluster", "*normalize"])
        self.assertEqual(envelope["exclude_pack_globs"], ["alert*"])
        self.assertEqual(envelope["summary"]["pack_count"], 2)
        self.assertEqual(envelope["summary"]["total_pack_count"], 4)
        self.assertEqual([pack["path"] for pack in envelope["packs"]], ["dedup-cluster", "ingest-normalize"])

    def test_pack_replay_collection_directory_exclude_only_pack_glob_preserves_remaining_order(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--exclude-pack",
            "*normalize",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=ok packs=3 total_packs=4 ok_packs=3 error_packs=0 fixtures=11 matched=11 mismatches=0 runtime_errors=0 rule_sources=ok:3,mismatch:0 fixture_classes=ok:11,expectation_mismatch:0,runtime_error:0 plan=9 resolved_refs=21",
                "pack[1] path=alert-routing status=ok pack=sprint-7-pack-03-alert-routing fixtures=3 matched=3 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[2] path=dedup-cluster status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[3] path=refs-handoff status=ok pack=sprint-7-program-pack-4-refs-handoff fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=21",
            ],
        )

        json_result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--exclude-pack",
            "*normalize",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["selected_pack_paths"], ["alert-routing", "dedup-cluster", "refs-handoff"])
        self.assertNotIn("include_pack_globs", envelope)
        self.assertEqual(envelope["exclude_pack_globs"], ["*normalize"])
        self.assertEqual(envelope["summary"]["pack_count"], 3)
        self.assertEqual(envelope["summary"]["total_pack_count"], 4)
        self.assertEqual([pack["path"] for pack in envelope["packs"]], ["alert-routing", "dedup-cluster", "refs-handoff"])

    def test_pack_replay_checked_in_pack_index_replays_relative_paths_in_declared_order(self) -> None:
        result = self._run_cli("pack-replay", str(PROGRAM_PACK_INDEX), "--summary")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=ok packs=4 ok_packs=4 error_packs=0 fixtures=13 matched=13 mismatches=0 runtime_errors=0 rule_sources=ok:4,mismatch:0 fixture_classes=ok:13,expectation_mismatch:0,runtime_error:0 plan=11 resolved_refs=22",
                "pack[1] path=ingest-normalize status=ok pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1",
                "pack[2] path=alert-routing status=ok pack=sprint-7-pack-03-alert-routing fixtures=3 matched=3 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[3] path=dedup-cluster status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[4] path=refs-handoff status=ok pack=sprint-7-program-pack-4-refs-handoff fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=21",
            ],
        )

        json_result = self._run_cli("pack-replay", str(PROGRAM_PACK_INDEX))
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["target_path"], str(PROGRAM_PACK_INDEX.resolve()))
        self.assertEqual(envelope["selected_pack_paths"], ["ingest-normalize", "alert-routing", "dedup-cluster", "refs-handoff"])
        self.assertEqual(
            [pack["path"] for pack in envelope["packs"]],
            ["ingest-normalize", "alert-routing", "dedup-cluster", "refs-handoff"],
        )
        self.assertEqual(
            [pack["target_path"] for pack in envelope["packs"]],
            [
                str((PROGRAM_PACK_FIXTURES / "ingest-normalize").resolve()),
                str((PROGRAM_PACK_FIXTURES / "alert-routing").resolve()),
                str((PROGRAM_PACK_FIXTURES / "dedup-cluster").resolve()),
                str((PROGRAM_PACK_FIXTURES / "refs-handoff").resolve()),
            ],
        )
        self.assertEqual(envelope["summary"]["pack_count"], 4)
        self.assertEqual(envelope["summary"]["total_pack_count"], 4)

    def test_pack_replay_checked_in_pack_index_pack_globs_match_relative_display_paths_in_declared_order(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_INDEX),
            "--include-pack",
            "*alert-routing",
            "--include-pack",
            "*dedup-cluster",
            "--summary",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=ok packs=2 total_packs=4 ok_packs=2 error_packs=0 fixtures=7 matched=7 mismatches=0 runtime_errors=0 rule_sources=ok:2,mismatch:0 fixture_classes=ok:7,expectation_mismatch:0,runtime_error:0 plan=6 resolved_refs=0",
                "pack[1] path=alert-routing status=ok pack=sprint-7-pack-03-alert-routing fixtures=3 matched=3 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[2] path=dedup-cluster status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
            ],
        )

        json_result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_INDEX),
            "--include-pack",
            "*alert-routing",
            "--include-pack",
            "*dedup-cluster",
        )
        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["include_pack_globs"], ["*alert-routing", "*dedup-cluster"])
        self.assertEqual(envelope["selected_pack_paths"], ["alert-routing", "dedup-cluster"])
        self.assertEqual(envelope["summary"]["pack_count"], 2)
        self.assertEqual(envelope["summary"]["total_pack_count"], 4)

    def test_pack_replay_checked_in_pack_index_strict_can_gate_declared_selection_order(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_INDEX),
            "--summary",
            "--strict",
            "--expected-pack-count",
            "4",
            "--expected-total-pack-count",
            "4",
            "--expected-selected-pack",
            "ingest-normalize",
            "--expected-selected-pack",
            "alert-routing",
            "--expected-selected-pack",
            "dedup-cluster",
            "--expected-selected-pack",
            "refs-handoff",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=ok replay_status=ok packs=4 ok_packs=4 error_packs=0 fixtures=13 matched=13 mismatches=0 runtime_errors=0 rule_sources=ok:4,mismatch:0 fixture_classes=ok:13,expectation_mismatch:0,runtime_error:0 plan=11 resolved_refs=22 strict_mismatches=0",
                "pack[1] path=ingest-normalize status=ok pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1",
                "pack[2] path=alert-routing status=ok pack=sprint-7-pack-03-alert-routing fixtures=3 matched=3 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[3] path=dedup-cluster status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[4] path=refs-handoff status=ok pack=sprint-7-program-pack-4-refs-handoff fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=21",
            ],
        )

    def test_pack_replay_checked_in_pack_index_strict_can_gate_action_plan_and_resolved_ref_counts(self) -> None:
        green_result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_INDEX),
            "--strict",
            "--expected-action-plan-count",
            "11",
            "--expected-resolved-refs-count",
            "22",
        )
        red_result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_INDEX),
            "--strict",
            "--expected-action-plan-count",
            "12",
            "--expected-resolved-refs-count",
            "23",
        )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        green_envelope = json.loads(green_result.stdout)
        self.assertEqual(green_envelope["status"], "ok")
        self.assertEqual(green_envelope["replay_status"], "ok")
        self.assertEqual(
            green_envelope["strict_profile"],
            {
                "expected_action_plan_count": 11,
                "expected_resolved_refs_count": 22,
            },
        )
        self.assertEqual(green_envelope["strict_profile_mismatches"], [])

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        red_envelope = json.loads(red_result.stdout)
        self.assertEqual(red_envelope["status"], "error")
        self.assertEqual(red_envelope["replay_status"], "ok")
        self.assertEqual(
            red_envelope["strict_profile"],
            {
                "expected_action_plan_count": 12,
                "expected_resolved_refs_count": 23,
            },
        )
        self.assertEqual(
            red_envelope["strict_profile_mismatches"],
            [
                {"field": "action_plan_count", "expected": 12, "actual": 11},
                {"field": "resolved_ref_count", "expected": 23, "actual": 22},
            ],
        )

    def test_pack_replay_collection_reports_error_when_one_pack_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            collection_dir = Path(tmpdir) / "program-packs"
            shutil.copytree(PROGRAM_PACK_FIXTURES, collection_dir)

            baseline_path = collection_dir / "dedup-cluster" / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            result = self._run_cli("pack-replay", str(collection_dir), "--summary")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=error packs=4 ok_packs=3 error_packs=1 fixtures=13 matched=12 mismatches=1 runtime_errors=0 rule_sources=ok:4,mismatch:0 fixture_classes=ok:12,expectation_mismatch:1,runtime_error:0 plan=11 resolved_refs=22 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0",
                "pack[1] path=alert-routing status=ok pack=sprint-7-pack-03-alert-routing fixtures=3 matched=3 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[2] path=dedup-cluster status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=3 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:1,runtime_error:0 plan=3 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0",
                "pack[3] path=ingest-normalize status=ok pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1",
                "pack[4] path=refs-handoff status=ok pack=sprint-7-program-pack-4-refs-handoff fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=21",
            ],
        )

    def test_pack_replay_collection_fixture_class_selector_filters_visible_packs_and_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            collection_dir = Path(tmpdir) / "program-packs"
            shutil.copytree(PROGRAM_PACK_FIXTURES, collection_dir)

            dedup_baseline_path = collection_dir / "dedup-cluster" / "baseline.json"
            dedup_baseline = json.loads(dedup_baseline_path.read_text(encoding="utf-8"))
            dedup_baseline["fixtures"][0]["expected_actions"] = []
            dedup_baseline_path.write_text(json.dumps(dedup_baseline, indent=2), encoding="utf-8")

            refs_baseline_path = collection_dir / "refs-handoff" / "baseline.json"
            refs_baseline = json.loads(refs_baseline_path.read_text(encoding="utf-8"))
            refs_baseline["fixtures"][0]["expected_action_plan"] = []
            refs_baseline["fixtures"][0]["expected_resolved_refs"] = {}
            refs_baseline_path.write_text(json.dumps(refs_baseline, indent=2), encoding="utf-8")

            summary_result = self._run_cli(
                "pack-replay",
                str(collection_dir),
                "--fixture-class",
                "expectation_mismatch",
                "--summary",
            )
            json_result = self._run_cli(
                "pack-replay",
                str(collection_dir),
                "--fixture-class",
                "expectation_mismatch",
            )

        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout.splitlines(),
            [
                "status=error packs=2 total_packs=4 ok_packs=0 error_packs=2 fixtures=2 matched=0 mismatches=2 runtime_errors=0 rule_sources=ok:2,mismatch:0 fixture_classes=ok:0,expectation_mismatch:2,runtime_error:0 plan=2 resolved_refs=7 mismatch_fields=actions:1,trace:0,action_plan:1,resolved_refs:1",
                "pack[1] path=dedup-cluster status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=1/4 matched=0 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:0,expectation_mismatch:1,runtime_error:0 plan=1 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0",
                "pack[2] path=refs-handoff status=error pack=sprint-7-program-pack-4-refs-handoff fixtures=1/4 matched=0 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:0,expectation_mismatch:1,runtime_error:0 plan=1 resolved_refs=7 mismatch_fields=actions:0,trace:0,action_plan:1,resolved_refs:1",
            ],
        )

        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["selected_pack_paths"], ["dedup-cluster", "refs-handoff"])
        self.assertEqual(envelope["fixture_class_selectors"], ["expectation_mismatch"])
        self.assertEqual(
            envelope["summary"],
            {
                "pack_count": 2,
                "total_pack_count": 4,
                "ok_pack_count": 0,
                "error_pack_count": 2,
                "fixture_count": 2,
                "matched_count": 0,
                "mismatch_count": 2,
                "runtime_error_count": 0,
                "rule_source_status_counts": {"ok": 2, "mismatch": 0},
                "fixture_class_counts": {
                    "ok": 0,
                    "expectation_mismatch": 2,
                    "runtime_error": 0,
                },
                "action_plan_count": 2,
                "resolved_ref_count": 7,
                "mismatch_field_counts": {
                    "actions": 1,
                    "trace": 0,
                    "action_plan": 1,
                    "resolved_refs": 1,
                },
            },
        )
        self.assertEqual([pack["path"] for pack in envelope["packs"]], ["dedup-cluster", "refs-handoff"])
        self.assertEqual(envelope["packs"][0]["selected_fixture_ids"], ["attach_ops"])
        self.assertEqual(envelope["packs"][1]["selected_fixture_ids"], ["ops_primary_page"])

    def test_pack_replay_collection_mismatch_field_selector_filters_visible_packs_and_surfaces_co_located_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            collection_dir = Path(tmpdir) / "program-packs"
            shutil.copytree(PROGRAM_PACK_FIXTURES, collection_dir)

            dedup_baseline_path = collection_dir / "dedup-cluster" / "baseline.json"
            dedup_baseline = json.loads(dedup_baseline_path.read_text(encoding="utf-8"))
            dedup_baseline["fixtures"][0]["expected_actions"] = []
            dedup_baseline_path.write_text(json.dumps(dedup_baseline, indent=2), encoding="utf-8")

            refs_baseline_path = collection_dir / "refs-handoff" / "baseline.json"
            refs_baseline = json.loads(refs_baseline_path.read_text(encoding="utf-8"))
            refs_baseline["fixtures"][0]["expected_action_plan"] = []
            refs_baseline["fixtures"][0]["expected_resolved_refs"] = {}
            refs_baseline_path.write_text(json.dumps(refs_baseline, indent=2), encoding="utf-8")

            summary_result = self._run_cli(
                "pack-replay",
                str(collection_dir),
                "--mismatch-field",
                "action_plan",
                "--summary",
            )
            json_result = self._run_cli(
                "pack-replay",
                str(collection_dir),
                "--mismatch-field",
                "action_plan",
            )

        self.assertEqual(summary_result.returncode, 1)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout.splitlines(),
            [
                "status=error packs=1 total_packs=4 ok_packs=0 error_packs=1 fixtures=1 matched=0 mismatches=1 runtime_errors=0 rule_sources=ok:1,mismatch:0 fixture_classes=ok:0,expectation_mismatch:1,runtime_error:0 plan=1 resolved_refs=7 mismatch_fields=actions:0,trace:0,action_plan:1,resolved_refs:1",
                "pack[1] path=refs-handoff status=error pack=sprint-7-program-pack-4-refs-handoff fixtures=1/4 matched=0 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:0,expectation_mismatch:1,runtime_error:0 plan=1 resolved_refs=7 mismatch_fields=actions:0,trace:0,action_plan:1,resolved_refs:1",
            ],
        )

        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(json_result.stderr, "")
        envelope = json.loads(json_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["selected_pack_paths"], ["refs-handoff"])
        self.assertEqual(envelope["mismatch_field_selectors"], ["action_plan"])
        self.assertEqual(
            envelope["summary"],
            {
                "pack_count": 1,
                "total_pack_count": 4,
                "ok_pack_count": 0,
                "error_pack_count": 1,
                "fixture_count": 1,
                "matched_count": 0,
                "mismatch_count": 1,
                "runtime_error_count": 0,
                "rule_source_status_counts": {"ok": 1, "mismatch": 0},
                "fixture_class_counts": {
                    "ok": 0,
                    "expectation_mismatch": 1,
                    "runtime_error": 0,
                },
                "action_plan_count": 1,
                "resolved_ref_count": 7,
                "mismatch_field_counts": {
                    "actions": 0,
                    "trace": 0,
                    "action_plan": 1,
                    "resolved_refs": 1,
                },
            },
        )
        self.assertEqual(envelope["packs"][0]["path"], "refs-handoff")
        self.assertEqual(envelope["packs"][0]["selected_fixture_ids"], ["ops_primary_page"])
        self.assertEqual(envelope["packs"][0]["mismatch_field_selectors"], ["action_plan"])

    def test_pack_replay_collection_rejects_unmatched_fixture_class_and_mismatch_field_selectors(self) -> None:
        cases = [
            (
                ["--fixture-class", "runtime_error"],
                "error: unmatched --fixture-class selector(s): runtime_error\n",
            ),
            (
                ["--mismatch-field", "action_plan"],
                "error: unmatched --mismatch-field selector(s): action_plan\n",
            ),
        ]

        for extra_args, expected_stderr in cases:
            with self.subTest(args=extra_args):
                result = self._run_cli("pack-replay", str(PROGRAM_PACK_FIXTURES), *extra_args)

                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, expected_stderr)

    def test_pack_replay_aggregate_strict_can_gate_fixture_class_histogram(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            collection_dir = Path(tmpdir) / "program-packs"
            shutil.copytree(PROGRAM_PACK_FIXTURES, collection_dir)

            baseline_path = collection_dir / "dedup-cluster" / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            green_result = self._run_cli(
                "pack-replay",
                str(collection_dir),
                "--strict",
                "--expected-fixture-class-counts",
                "ok=12,expectation_mismatch=1,runtime_error=0",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(collection_dir),
                "--strict",
                "--expected-fixture-class-counts",
                "ok=13,expectation_mismatch=0,runtime_error=0",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        green_envelope = json.loads(green_result.stdout)
        self.assertEqual(green_envelope["status"], "ok")
        self.assertEqual(green_envelope["replay_status"], "error")
        self.assertEqual(
            green_envelope["strict_profile"],
            {
                "expected_fixture_class_counts": {
                    "ok": 12,
                    "expectation_mismatch": 1,
                    "runtime_error": 0,
                }
            },
        )
        self.assertEqual(green_envelope["strict_profile_mismatches"], [])

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        red_envelope = json.loads(red_result.stdout)
        self.assertEqual(red_envelope["status"], "error")
        self.assertEqual(red_envelope["replay_status"], "error")
        self.assertEqual(
            red_envelope["strict_profile"],
            {
                "expected_fixture_class_counts": {
                    "ok": 13,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                }
            },
        )
        self.assertEqual(
            red_envelope["strict_profile_mismatches"],
            [
                {
                    "field": "fixture_class_counts",
                    "expected": {
                        "ok": 13,
                        "expectation_mismatch": 0,
                        "runtime_error": 0,
                    },
                    "actual": {
                        "ok": 12,
                        "expectation_mismatch": 1,
                        "runtime_error": 0,
                    },
                }
            ],
        )

    def test_pack_replay_aggregate_strict_can_greenlight_known_mismatch_field_histogram(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            collection_dir = Path(tmpdir) / "program-packs"
            shutil.copytree(PROGRAM_PACK_FIXTURES, collection_dir)

            baseline_path = collection_dir / "dedup-cluster" / "baseline.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["fixtures"][0]["expected_actions"] = []
            baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

            green_result = self._run_cli(
                "pack-replay",
                str(collection_dir),
                "--summary",
                "--strict",
                "--expected-mismatch-field-counts",
                "actions=1,trace=0,action_plan=0,resolved_refs=0",
            )
            red_result = self._run_cli(
                "pack-replay",
                str(collection_dir),
                "--strict",
                "--expected-mismatch-field-counts",
                "actions=0,trace=0,action_plan=1,resolved_refs=0",
            )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        self.assertEqual(
            green_result.stdout.splitlines(),
            [
                "status=ok replay_status=error packs=4 ok_packs=3 error_packs=1 fixtures=13 matched=12 mismatches=1 runtime_errors=0 rule_sources=ok:4,mismatch:0 fixture_classes=ok:12,expectation_mismatch:1,runtime_error:0 plan=11 resolved_refs=22 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0 strict_mismatches=0",
                "pack[1] path=alert-routing status=ok pack=sprint-7-pack-03-alert-routing fixtures=3 matched=3 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[2] path=dedup-cluster status=error pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=3 mismatches=1 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:1,runtime_error:0 plan=3 resolved_refs=0 mismatch_fields=actions:1,trace:0,action_plan:0,resolved_refs:0",
                "pack[3] path=ingest-normalize status=ok pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1",
                "pack[4] path=refs-handoff status=ok pack=sprint-7-program-pack-4-refs-handoff fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=21",
            ],
        )

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        envelope = json.loads(red_result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "error")
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_mismatch_field_counts": {
                    "actions": 0,
                    "trace": 0,
                    "action_plan": 1,
                    "resolved_refs": 0,
                }
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {
                    "field": "mismatch_field_counts",
                    "expected": {
                        "actions": 0,
                        "trace": 0,
                        "action_plan": 1,
                        "resolved_refs": 0,
                    },
                    "actual": {
                        "actions": 1,
                        "trace": 0,
                        "action_plan": 0,
                        "resolved_refs": 0,
                    },
                }
            ],
        )

    def test_pack_replay_aggregate_strict_summary_reports_replay_status_and_zero_strict_mismatches(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--summary",
            "--strict",
            "--expected-pack-count",
            "4",
            "--expected-selected-pack",
            "alert-routing",
            "--expected-selected-pack",
            "dedup-cluster",
            "--expected-selected-pack",
            "ingest-normalize",
            "--expected-selected-pack",
            "refs-handoff",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=ok replay_status=ok packs=4 ok_packs=4 error_packs=0 fixtures=13 matched=13 mismatches=0 runtime_errors=0 rule_sources=ok:4,mismatch:0 fixture_classes=ok:13,expectation_mismatch:0,runtime_error:0 plan=11 resolved_refs=22 strict_mismatches=0",
                "pack[1] path=alert-routing status=ok pack=sprint-7-pack-03-alert-routing fixtures=3 matched=3 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:3,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[2] path=dedup-cluster status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[3] path=ingest-normalize status=ok pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1",
                "pack[4] path=refs-handoff status=ok pack=sprint-7-program-pack-4-refs-handoff fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=21",
            ],
        )

    def test_pack_replay_aggregate_strict_can_gate_action_plan_and_resolved_ref_counts(self) -> None:
        green_result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--strict",
            "--expected-action-plan-count",
            "11",
            "--expected-resolved-refs-count",
            "22",
        )
        red_result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--strict",
            "--expected-action-plan-count",
            "10",
            "--expected-resolved-refs-count",
            "21",
        )

        self.assertEqual(green_result.returncode, 0)
        self.assertEqual(green_result.stderr, "")
        green_envelope = json.loads(green_result.stdout)
        self.assertEqual(green_envelope["status"], "ok")
        self.assertEqual(green_envelope["replay_status"], "ok")
        self.assertEqual(
            green_envelope["strict_profile"],
            {
                "expected_action_plan_count": 11,
                "expected_resolved_refs_count": 22,
            },
        )
        self.assertEqual(green_envelope["strict_profile_mismatches"], [])

        self.assertEqual(red_result.returncode, 1)
        self.assertEqual(red_result.stderr, "")
        red_envelope = json.loads(red_result.stdout)
        self.assertEqual(red_envelope["status"], "error")
        self.assertEqual(red_envelope["replay_status"], "ok")
        self.assertEqual(
            red_envelope["strict_profile"],
            {
                "expected_action_plan_count": 10,
                "expected_resolved_refs_count": 21,
            },
        )
        self.assertEqual(
            red_envelope["strict_profile_mismatches"],
            [
                {"field": "action_plan_count", "expected": 10, "actual": 11},
                {"field": "resolved_ref_count", "expected": 21, "actual": 22},
            ],
        )

    def test_pack_replay_aggregate_strict_json_reports_pack_selection_drift(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--strict",
            "--expected-pack-count",
            "2",
            "--expected-total-pack-count",
            "2",
            "--expected-selected-pack",
            "alert-routing",
            "--expected-selected-pack",
            "ingest-normalize",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["summary"]["total_pack_count"], 4)
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_pack_count": 2,
                "expected_total_pack_count": 2,
                "expected_selected_pack_paths": ["alert-routing", "ingest-normalize"],
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {"field": "pack_count", "expected": 2, "actual": 4},
                {"field": "total_pack_count", "expected": 2, "actual": 4},
                {
                    "field": "selected_pack_paths",
                    "expected": ["alert-routing", "ingest-normalize"],
                    "actual": ["alert-routing", "dedup-cluster", "ingest-normalize", "refs-handoff"],
                },
            ],
        )

    def test_pack_replay_aggregate_pack_globs_compose_with_strict_selection_contract(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--include-pack",
            "*cluster",
            "--include-pack",
            "*normalize",
            "--summary",
            "--strict",
            "--expected-pack-count",
            "2",
            "--expected-total-pack-count",
            "4",
            "--expected-selected-pack",
            "dedup-cluster",
            "--expected-selected-pack",
            "ingest-normalize",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "status=ok replay_status=ok packs=2 total_packs=4 ok_packs=2 error_packs=0 fixtures=6 matched=6 mismatches=0 runtime_errors=0 rule_sources=ok:2,mismatch:0 fixture_classes=ok:6,expectation_mismatch:0,runtime_error:0 plan=5 resolved_refs=1 strict_mismatches=0",
                "pack[1] path=dedup-cluster status=ok pack=sprint-7-program-pack-2-dedup-cluster fixtures=4 matched=4 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:4,expectation_mismatch:0,runtime_error:0 plan=3 resolved_refs=0",
                "pack[2] path=ingest-normalize status=ok pack=ingest-normalize fixtures=2 matched=2 mismatches=0 runtime_errors=0 rule_source=ok fixture_classes=ok:2,expectation_mismatch:0,runtime_error:0 plan=2 resolved_refs=1",
            ],
        )

    def test_pack_replay_aggregate_pack_globs_strict_can_gate_prefilter_total_pack_count(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--include-pack",
            "*cluster",
            "--include-pack",
            "*normalize",
            "--strict",
            "--expected-pack-count",
            "2",
            "--expected-total-pack-count",
            "2",
            "--expected-selected-pack",
            "dedup-cluster",
            "--expected-selected-pack",
            "ingest-normalize",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["summary"]["pack_count"], 2)
        self.assertEqual(envelope["summary"]["total_pack_count"], 4)
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_pack_count": 2,
                "expected_total_pack_count": 2,
                "expected_selected_pack_paths": ["dedup-cluster", "ingest-normalize"],
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {"field": "total_pack_count", "expected": 2, "actual": 4},
            ],
        )

    def test_pack_replay_aggregate_pack_globs_strict_reports_selected_pack_drift(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_FIXTURES),
            "--include-pack",
            "*cluster",
            "--include-pack",
            "*normalize",
            "--strict",
            "--expected-pack-count",
            "1",
            "--expected-selected-pack",
            "dedup-cluster",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["replay_status"], "ok")
        self.assertEqual(envelope["include_pack_globs"], ["*cluster", "*normalize"])
        self.assertEqual(envelope["selected_pack_paths"], ["dedup-cluster", "ingest-normalize"])
        self.assertEqual(
            envelope["strict_profile"],
            {
                "expected_pack_count": 1,
                "expected_selected_pack_paths": ["dedup-cluster"],
            },
        )
        self.assertEqual(
            envelope["strict_profile_mismatches"],
            [
                {"field": "pack_count", "expected": 1, "actual": 2},
                {
                    "field": "selected_pack_paths",
                    "expected": ["dedup-cluster"],
                    "actual": ["dedup-cluster", "ingest-normalize"],
                },
            ],
        )

    def test_pack_replay_aggregate_expected_selectors_require_strict(self) -> None:
        cases = [
            (["--expected-pack-count", "3"], "--expected-pack-count"),
            (["--expected-total-pack-count", "3"], "--expected-total-pack-count"),
            (["--expected-selected-pack", "alert-routing"], "--expected-selected-pack"),
            (
                [
                    "--expected-fixture-class-counts",
                    "ok=13,expectation_mismatch=0,runtime_error=0",
                ],
                "--expected-fixture-class-counts",
            ),
            (
                [
                    "--expected-mismatch-field-counts",
                    "actions=0,trace=0,action_plan=0,resolved_refs=0",
                ],
                "--expected-mismatch-field-counts",
            ),
            (["--expected-action-plan-count", "11"], "--expected-action-plan-count"),
            (["--expected-resolved-refs-count", "22"], "--expected-resolved-refs-count"),
            (
                ["--expected-rule-source-status-counts", "ok=4,mismatch=0"],
                "--expected-rule-source-status-counts",
            ),
        ]

        for extra_args, expected_flag in cases:
            with self.subTest(flag=expected_flag):
                result = self._run_cli("pack-replay", str(PROGRAM_PACK_FIXTURES), *extra_args)

                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, f"error: {expected_flag} requires --strict\n")

    def test_pack_replay_aggregate_strict_requires_supported_aggregate_contract(self) -> None:
        result = self._run_cli("pack-replay", str(PROGRAM_PACK_FIXTURES), "--strict")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --strict requires at least one --expected-pack-count, --expected-total-pack-count, --expected-selected-pack, --expected-rule-source-status-counts, --expected-fixture-class-counts, --expected-mismatch-field-counts, --expected-action-plan-count, --expected-resolved-refs-count selector, or --strict-profile for aggregate pack-replay\n",
        )

    def test_pack_replay_single_pack_rejects_aggregate_strict_selectors(self) -> None:
        cases = [
            (["--strict", "--expected-pack-count", "1"], "--expected-pack-count"),
            (["--strict", "--expected-total-pack-count", "1"], "--expected-total-pack-count"),
            (
                ["--strict", "--expected-rule-source-status-counts", "ok=1,mismatch=0"],
                "--expected-rule-source-status-counts",
            ),
        ]

        for extra_args, expected_flag in cases:
            with self.subTest(flag=expected_flag):
                result = self._run_cli(
                    "pack-replay",
                    str(DEDUP_CLUSTER_PACK),
                    *extra_args,
                )

                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(
                    result.stderr,
                    f"error: {expected_flag} requires aggregate pack-replay target\n",
                )

    def test_pack_replay_single_pack_rejects_aggregate_pack_glob_selectors(self) -> None:
        cases = [
            (["--include-pack", "*dedup*"], "--include-pack"),
            (["--exclude-pack", "*dedup*"], "--exclude-pack"),
        ]

        for extra_args, expected_flag in cases:
            with self.subTest(flag=expected_flag):
                result = self._run_cli("pack-replay", str(DEDUP_CLUSTER_PACK), *extra_args)

                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(
                    result.stderr,
                    f"error: {expected_flag} requires aggregate pack-replay target\n",
                )

    def test_pack_replay_single_pack_rejects_aggregate_strict_profile(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(DEDUP_CLUSTER_PACK),
            "--strict-profile",
            "program-pack-index-clean",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "error: --strict-profile program-pack-index-clean requires aggregate pack-replay target\n",
        )

    def test_pack_replay_aggregate_pack_globs_reject_unmatched_and_zero_match_selection(self) -> None:
        cases = [
            (
                ["--include-pack", "missing*"],
                "error: unmatched --include-pack selector(s): missing*\n",
            ),
            (
                ["--exclude-pack", "missing*"],
                "error: unmatched --exclude-pack selector(s): missing*\n",
            ),
            (
                ["--include-pack", "dedup-*", "--exclude-pack", "dedup-*"],
                "error: pack selectors matched zero packs after applying: --include-pack dedup-*; --exclude-pack dedup-*\n",
            ),
        ]

        for extra_args, expected_stderr in cases:
            with self.subTest(args=extra_args):
                result = self._run_cli("pack-replay", str(PROGRAM_PACK_FIXTURES), *extra_args)

                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, expected_stderr)

    def test_pack_replay_aggregate_strict_profile_program_pack_index_clean_passes_for_checked_in_index(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_INDEX),
            "--strict-profile",
            "program-pack-index-clean",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["replay_status"], "ok")
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_pack_count": 4,
                "expected_total_pack_count": 4,
                "expected_selected_pack_paths": [
                    "ingest-normalize",
                    "alert-routing",
                    "dedup-cluster",
                    "refs-handoff",
                ],
                "expected_fixture_class_counts": {
                    "ok": 13,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "expected_rule_source_status_counts": {"ok": 4, "mismatch": 0},
                "expected_action_plan_count": 11,
                "expected_resolved_refs_count": 22,
                "expected_mismatch_field_counts": {
                    "actions": 0,
                    "trace": 0,
                    "action_plan": 0,
                    "resolved_refs": 0,
                },
            },
        )
        self.assertEqual(payload["strict_profile_mismatches"], [])

    def test_pack_replay_aggregate_strict_profile_program_pack_index_clean_detects_pack_slice_drift(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_INDEX),
            "--include-pack",
            "*handoff",
            "--strict-profile",
            "program-pack-index-clean",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["replay_status"], "ok")
        self.assertEqual(payload["selected_pack_paths"], ["refs-handoff"])
        self.assertEqual(
            payload["strict_profile"],
            {
                "expected_pack_count": 4,
                "expected_total_pack_count": 4,
                "expected_selected_pack_paths": [
                    "ingest-normalize",
                    "alert-routing",
                    "dedup-cluster",
                    "refs-handoff",
                ],
                "expected_fixture_class_counts": {
                    "ok": 13,
                    "expectation_mismatch": 0,
                    "runtime_error": 0,
                },
                "expected_rule_source_status_counts": {"ok": 4, "mismatch": 0},
                "expected_action_plan_count": 11,
                "expected_resolved_refs_count": 22,
                "expected_mismatch_field_counts": {
                    "actions": 0,
                    "trace": 0,
                    "action_plan": 0,
                    "resolved_refs": 0,
                },
            },
        )
        self.assertEqual(
            payload["strict_profile_mismatches"],
            [
                {"field": "pack_count", "expected": 4, "actual": 1},
                {
                    "field": "selected_pack_paths",
                    "expected": [
                        "ingest-normalize",
                        "alert-routing",
                        "dedup-cluster",
                        "refs-handoff",
                    ],
                    "actual": ["refs-handoff"],
                },
                {
                    "field": "rule_source_status_counts",
                    "expected": {"ok": 4, "mismatch": 0},
                    "actual": {"ok": 1, "mismatch": 0},
                },
                {
                    "field": "fixture_class_counts",
                    "expected": {"ok": 13, "expectation_mismatch": 0, "runtime_error": 0},
                    "actual": {"ok": 4, "expectation_mismatch": 0, "runtime_error": 0},
                },
                {"field": "action_plan_count", "expected": 11, "actual": 3},
                {"field": "resolved_ref_count", "expected": 22, "actual": 21},
            ],
        )

    def test_pack_replay_aggregate_expected_rule_source_status_counts_strict_selector(self) -> None:
        result = self._run_cli(
            "pack-replay",
            str(PROGRAM_PACK_INDEX),
            "--strict",
            "--expected-rule-source-status-counts",
            "ok=3,mismatch=1",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["replay_status"], "ok")
        self.assertEqual(
            payload["strict_profile"],
            {"expected_rule_source_status_counts": {"ok": 3, "mismatch": 1}},
        )
        self.assertEqual(
            payload["strict_profile_mismatches"],
            [
                {
                    "field": "rule_source_status_counts",
                    "expected": {"ok": 3, "mismatch": 1},
                    "actual": {"ok": 4, "mismatch": 0},
                }
            ],
        )

    def test_pack_replay_aggregate_rejects_single_pack_only_flags(self) -> None:
        cases = [
            (["--fixture", "attach_ops"], "--fixture"),
            (["--include-fixture", "new_*"], "--include-fixture"),
            (["--exclude-fixture", "*security*"], "--exclude-fixture"),
            (["--fixture-class", "runtime_error", "--fixture-class-summary-file", "/tmp/aggregate.summary.txt"], "--fixture-class-summary-file"),
            (["--strict-profile", "clean"], "--strict-profile"),
            (["--strict", "--expected-pack-id", "ingest-normalize"], "--expected-pack-id"),
        ]

        for extra_args, expected_flag in cases:
            with self.subTest(flag=expected_flag):
                result = self._run_cli("pack-replay", str(PROGRAM_PACK_FIXTURES), *extra_args)

                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(
                    result.stderr,
                    f"error: aggregate pack-replay does not support {expected_flag}; point to a single pack directory instead\n",
                )


if __name__ == "__main__":
    unittest.main()
