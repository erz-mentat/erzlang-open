from __future__ import annotations

import json
from pathlib import Path
import unittest

from compact import canonicalize_program, parse_and_format_compact, parse_compact
from runtime.eval import validate_trace


ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "examples" / "program-packs" / "ingest-normalize"
PROGRAM_PATH = PACK_DIR / "program.erz"
BASELINE_PATH = PACK_DIR / "baseline.json"
TRACE_PATH = PACK_DIR / "expected-trace.sample.json"


class IngestNormalizeProgramPackTests(unittest.TestCase):
    def test_program_matches_baseline_json_equivalent(self) -> None:
        source = PROGRAM_PATH.read_text(encoding="utf-8")
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

        parsed = canonicalize_program(parse_compact(source))

        self.assertEqual(parsed, baseline)

    def test_program_roundtrip_format_is_stable(self) -> None:
        source = PROGRAM_PATH.read_text(encoding="utf-8")

        formatted_once = parse_and_format_compact(source)
        formatted_twice = parse_and_format_compact(formatted_once)

        self.assertEqual(formatted_once, source)
        self.assertEqual(formatted_twice, formatted_once)

    def test_expected_trace_sample_matches_program_trace_statement_and_contract(self) -> None:
        source = PROGRAM_PATH.read_text(encoding="utf-8")
        expected_trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))

        trace_steps = [statement["fields"] for statement in parse_compact(source) if statement["tag"] == "tr"]

        self.assertEqual(trace_steps, expected_trace)

        fired_rule_ids = [step["rule_id"] for step in expected_trace]
        self.assertEqual(validate_trace(expected_trace, fired_rule_ids=fired_rule_ids), expected_trace)


if __name__ == "__main__":
    unittest.main()
