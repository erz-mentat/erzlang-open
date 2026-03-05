from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from compact import (
    CompactValidationError,
    canonicalize_program,
    parse_and_dump_json,
    parse_and_format_compact,
    parse_compact,
)

ROOT = Path(__file__).resolve().parents[1]


class CompactParserTests(unittest.TestCase):
    def test_parse_valid_compact_subset(self) -> None:
        text = (
            'erz{v:1}'
            'event{type:"ingest",payload:{b:2,a:1}}'
            'rule{id:"r1",when:["event_type_present"],then:[{kind:"act",params:{rule_id:"r1"}}]}'
        )
        program = parse_compact(text)

        self.assertEqual(len(program), 3)
        self.assertEqual(program[0]["tag"], "erz")
        self.assertEqual(program[1]["fields"]["type"], "ingest")
        self.assertEqual(program[2]["fields"]["id"], "r1")

    def test_unknown_statement_field_fails(self) -> None:
        with self.assertRaises(CompactValidationError):
            parse_compact('event{type:"ingest",extra:1}')

    def test_unknown_rule_action_field_fails(self) -> None:
        with self.assertRaises(CompactValidationError):
            parse_compact(
                'rule{id:"r1",when:["ok"],then:[{kind:"act",params:{},extra:true}]}'
            )

    def test_formatter_is_canonical_and_deterministic(self) -> None:
        src_a = 'event{payload:{z:2,a:1},type:"ingest"}'
        src_b = 'event{type:"ingest",payload:{a:1,z:2}}'

        out_a = parse_and_format_compact(src_a)
        out_b = parse_and_format_compact(src_b)

        self.assertEqual(out_a, out_b)
        self.assertEqual(out_a, 'event{type:"ingest",payload:{a:1,z:2}}\n')

    def test_parse_dump_json_is_canonical(self) -> None:
        output = parse_and_dump_json('event{payload:{z:2,a:1},type:"ingest"}')
        self.assertIn('"type": "ingest"', output)
        self.assertIn('"a": 1', output)
        self.assertIn('"z": 2', output)

    def test_roundtrip_parse_format_parse_is_deterministic(self) -> None:
        source = (
            'rule{then:[{params:{y:2,x:1},kind:"act"}],when:["b","a"],id:"r-42"}'
            'event{payload:{z:2,a:1},type:"ingest"}'
            'erz{v:1}'
        )

        canonical_before = canonicalize_program(parse_compact(source))
        formatted_once = parse_and_format_compact(source)
        canonical_after = canonicalize_program(parse_compact(formatted_once))
        formatted_twice = parse_and_format_compact(formatted_once)

        self.assertEqual(canonical_before, canonical_after)
        self.assertEqual(formatted_once, formatted_twice)

    def test_parse_valid_sprint3_short_tags(self) -> None:
        source = (
            'ev{type:"ingest",payload:{b:2,a:1}}'
            'rl{id:"r1",when:["event_type_present"],then:[{kind:"act",params:{rule_id:"r1"}}]}'
            'ac{kind:"notify",params:{channel:"ops"}}'
            'tr{rule_id:"r1",matched_clauses:["event_type_present"],seed:"seed-1"}'
            'rf{id:"tpl_ops",v:"Bitte Einsatzlage prüfen."}'
            'pl{rt:{min_severity:65,min_confidence:75}}'
        )

        program = parse_compact(source)
        self.assertEqual([item["tag"] for item in program], ["ev", "rl", "ac", "tr", "rf", "pl"])
        self.assertEqual(program[0]["fields"]["type"], "ingest")
        self.assertEqual(program[3]["fields"]["rule_id"], "r1")

    def test_trace_accepts_calibrated_probability_and_float_timestamp(self) -> None:
        source = (
            'tr{rule_id:"r1",matched_clauses:["event_type_present"],'
            'score:1.0,calibrated_probability:0.92,timestamp:1735689600.5}'
        )

        parsed = parse_compact(source)
        self.assertEqual(parsed[0]["fields"]["calibrated_probability"], 0.92)
        self.assertEqual(parsed[0]["fields"]["timestamp"], 1735689600.5)

        formatted = parse_and_format_compact(source)
        self.assertEqual(
            formatted,
            'tr{rule_id:"r1",matched_clauses:["event_type_present"],score:1.0,calibrated_probability:0.92,timestamp:1735689600.5}\n',
        )

    def test_trace_rejects_out_of_range_calibrated_probability(self) -> None:
        with self.assertRaisesRegex(CompactValidationError, "within \[0.0, 1.0\]"):
            parse_compact(
                'tr{rule_id:"r1",matched_clauses:["event_type_present"],calibrated_probability:1.2}'
            )

    def test_trace_rejects_non_finite_numeric_fields(self) -> None:
        with self.assertRaisesRegex(CompactValidationError, "finite number"):
            parse_compact('tr{rule_id:"r1",matched_clauses:["event_type_present"],score:1e309}')

    def test_unknown_short_statement_field_fails(self) -> None:
        with self.assertRaises(CompactValidationError):
            parse_compact('rf{id:"tpl",v:"ok",extra:true}')

    def test_rf_rejects_invalid_ref_id(self) -> None:
        with self.assertRaisesRegex(CompactValidationError, "invalid ref id"):
            parse_compact('rf{id:"tpl?ops",v:"ok"}')

    def test_rf_rejects_literal_ref_id_prefix(self) -> None:
        with self.assertRaisesRegex(CompactValidationError, "must not include '@' prefix"):
            parse_compact('rf{id:"@tpl_ops",v:"ok"}')

    def test_rf_rejects_duplicate_ids_across_program(self) -> None:
        with self.assertRaisesRegex(CompactValidationError, "Duplicate ref id"):
            parse_compact('rf{id:"tpl_ops",v:"one"}rf{id:"tpl_ops",v:"two"}')

    def test_formatter_is_canonical_for_short_tags(self) -> None:
        src_a = 'pl{rt:{min_severity:65,min_confidence:75}}rf{v:"ok",id:"tpl"}'
        src_b = 'pl{rt:{min_confidence:75,min_severity:65}}rf{id:"tpl",v:"ok"}'

        out_a = parse_and_format_compact(src_a)
        out_b = parse_and_format_compact(src_b)

        self.assertEqual(out_a, out_b)
        self.assertEqual(out_a, 'pl{rt:{min_confidence:75,min_severity:65}}\nrf{id:"tpl",v:"ok"}\n')

    def test_roundtrip_mixed_long_and_short_program_is_deterministic(self) -> None:
        source = (
            'rf{v:"template",id:"tpl_ops"}'
            'event{payload:{z:2,a:1},type:"ingest"}'
            'rl{then:[{params:{y:2,x:1},kind:"act"}],when:["b","a"],id:"r-short"}'
            'ac{params:{z:9,a:{b:2,a:1}},kind:"notify"}'
            'tr{seed:"s42",matched_clauses:["a","b"],rule_id:"r-short"}'
            'pl{rt:{z:2,a:1}}'
            'erz{v:1}'
        )

        canonical_before = canonicalize_program(parse_compact(source))
        formatted_once = parse_and_format_compact(source)
        canonical_after = canonicalize_program(parse_compact(formatted_once))
        formatted_twice = parse_and_format_compact(formatted_once)

        self.assertEqual(canonical_before, canonical_after)
        self.assertEqual(formatted_once, formatted_twice)

    def test_richer_examples_roundtrip(self) -> None:
        for example_name in ("sprint3_mixed.erz", "sprint3_policy.erz"):
            source = (ROOT / "examples" / example_name).read_text(encoding="utf-8")
            canonical_before = canonicalize_program(parse_compact(source))
            formatted = parse_and_format_compact(source)
            canonical_after = canonicalize_program(parse_compact(formatted))
            self.assertEqual(canonical_before, canonical_after)


class CliCommandTests(unittest.TestCase):
    def test_validate_command_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_file = Path(tmp_dir) / "ok.erz"
            source_file.write_text('erz{v:1}event{type:"ingest"}', encoding="utf-8")

            result = self._run_cli("validate", str(source_file))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "valid")

    def test_fmt_in_place_rewrites_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_file = Path(tmp_dir) / "fmt.erz"
            source_file.write_text('event{payload:{z:2,a:1},type:"ingest"}', encoding="utf-8")

            result = self._run_cli("fmt", str(source_file), "--in-place")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                source_file.read_text(encoding="utf-8"),
                'event{type:"ingest",payload:{a:1,z:2}}\n',
            )
            self.assertEqual(result.stdout, "")

    def test_parse_command_fails_on_unknown_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_file = Path(tmp_dir) / "bad.erz"
            source_file.write_text('event{type:"ingest",oops:1}', encoding="utf-8")

            result = self._run_cli("parse", str(source_file))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unknown field", result.stderr)

    def test_bench_command_prints_concise_summary(self) -> None:
        result = self._run_cli("bench")
        self.assertEqual(result.returncode, 0)
        self.assertIn("token benchmark:", result.stdout)
        self.assertIn("overall tokens:", result.stdout)
        self.assertIn("per-class savings:", result.stdout)
        self.assertIn("- core:", result.stdout)
        self.assertIn("token saving -> PASS", result.stdout)

    def test_bench_command_exits_non_zero_when_target_not_met(self) -> None:
        result = self._run_cli("bench", "--target-pct", "99.99")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target: >= 99.99% token saving -> FAIL", result.stdout)

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cli.main", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
