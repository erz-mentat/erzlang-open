from __future__ import annotations

import unittest

from runtime.eval import eval_policies


class SeparationGuardTests(unittest.TestCase):
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

    def test_calibration_semantics_are_structural_not_severity_or_confidence_based(self) -> None:
        rules = [
            {
                "id": "r-route",
                "when": ["event_type_present", "payload_has:severity", "payload_has:confidence"],
                "then": [{"kind": "route", "params": {"target": "ops"}}],
            }
        ]

        calibration = {
            "points": [
                {"raw_score": 0.0, "probability": 0.1},
                {"raw_score": 1.0, "probability": 0.9},
            ]
        }

        low_values_event = {"type": "alert", "payload": {"severity": 0.1, "confidence": 0.1}}
        high_values_event = {"type": "alert", "payload": {"severity": 0.9, "confidence": 0.95}}

        _, low_trace = eval_policies(low_values_event, rules, calibration=calibration)
        _, high_trace = eval_policies(high_values_event, rules, calibration=calibration)

        self.assertEqual(low_trace[0]["matched_clauses"], high_trace[0]["matched_clauses"])
        self.assertEqual(low_trace[0]["score"], 1.0)
        self.assertEqual(high_trace[0]["score"], 1.0)
        self.assertEqual(low_trace[0]["calibrated_probability"], 0.9)
        self.assertEqual(high_trace[0]["calibrated_probability"], 0.9)

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


if __name__ == "__main__":
    unittest.main()
