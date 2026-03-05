from __future__ import annotations

import json
from pathlib import Path
import unittest

from compact import parse_and_format_compact, parse_compact
from runtime.eval import eval_policies

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "examples" / "program-packs" / "alert-routing"
PROGRAM_PATH = PACK_DIR / "alert-routing.erz"
BASELINE_PATH = PACK_DIR / "alert-routing.baseline.json"


class AlertRoutingProgramPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.program_source = PROGRAM_PATH.read_text(encoding="utf-8")
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        cls.program = parse_compact(cls.program_source)

    def test_pack_program_is_canonical_compact(self) -> None:
        self.assertEqual(self.program_source, parse_and_format_compact(self.program_source))

    def test_pack_contains_rules_actions_trace_and_calibration_note(self) -> None:
        rules = [statement["fields"] for statement in self.program if statement["tag"] == "rl"]
        action_expectations = [statement["fields"] for statement in self.program if statement["tag"] == "ac"]
        trace_expectations = [statement["fields"] for statement in self.program if statement["tag"] == "tr"]
        runtime_profiles = [statement["fields"] for statement in self.program if statement["tag"] == "pl"]

        self.assertEqual(rules, self.baseline["rules"])
        self.assertEqual(len(action_expectations), len(self.baseline["fixtures"]))
        self.assertEqual(len(trace_expectations), len(self.baseline["fixtures"]))
        self.assertEqual(action_expectations, [fixture["expected_actions"][0] for fixture in self.baseline["fixtures"]])
        self.assertEqual(trace_expectations, [fixture["expected_trace"][0] for fixture in self.baseline["fixtures"]])

        self.assertEqual(len(runtime_profiles), 1)
        self.assertIn("calibration_note", runtime_profiles[0]["rt"])
        self.assertIn("Calibration", runtime_profiles[0]["rt"]["calibration_note"])
        self.assertIn("calibration_note", self.baseline)

    def test_fixture_routing_outputs_are_deterministic(self) -> None:
        rules = self.baseline["rules"]

        for fixture in self.baseline["fixtures"]:
            with self.subTest(fixture=fixture["id"]):
                first_actions, first_trace = eval_policies(
                    event=fixture["event"],
                    rules=rules,
                    calibration=fixture["calibration"],
                )
                second_actions, second_trace = eval_policies(
                    event=fixture["event"],
                    rules=rules,
                    calibration=fixture["calibration"],
                )

                self.assertEqual(first_actions, second_actions)
                self.assertEqual(first_trace, second_trace)

                self.assertEqual(first_actions, fixture["expected_actions"])
                self.assertEqual(first_trace, fixture["expected_trace"])


if __name__ == "__main__":
    unittest.main()
