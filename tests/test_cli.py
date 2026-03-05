from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from runtime.errors import ERROR_ENVELOPE_FIELD_ORDER


ROOT = Path(__file__).resolve().parents[1]
ERROR_FIXTURES = ROOT / "tests" / "fixtures" / "errors"


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


if __name__ == "__main__":
    unittest.main()
