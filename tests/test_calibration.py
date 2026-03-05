from __future__ import annotations

import unittest

from runtime.calibration import (
    CalibrationPoint,
    PiecewiseLinearCalibration,
    map_raw_score_to_probability,
)


class CalibrationTests(unittest.TestCase):
    def test_exact_knot_returns_exact_probability(self) -> None:
        calibration = PiecewiseLinearCalibration(
            points=(
                CalibrationPoint(raw_score=0.0, probability=0.02),
                CalibrationPoint(raw_score=0.6, probability=0.7),
                CalibrationPoint(raw_score=1.0, probability=0.95),
            )
        )

        self.assertEqual(map_raw_score_to_probability(0.6, calibration), 0.7)

    def test_linear_interpolation_between_knots(self) -> None:
        calibration = {
            "points": [
                {"raw_score": 0.0, "probability": 0.1},
                {"raw_score": 0.5, "probability": 0.5},
                {"raw_score": 1.0, "probability": 0.9},
            ]
        }

        # Midpoint between 0.5 and 1.0 should map to midpoint between 0.5 and 0.9.
        self.assertAlmostEqual(map_raw_score_to_probability(0.75, calibration), 0.7)

    def test_values_outside_knot_range_are_clamped(self) -> None:
        calibration = (
            (0.2, 0.3),
            (0.8, 0.85),
        )

        self.assertEqual(map_raw_score_to_probability(0.0, calibration), 0.3)
        self.assertEqual(map_raw_score_to_probability(1.0, calibration), 0.85)

    def test_invalid_points_fail_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique raw_score"):
            map_raw_score_to_probability(
                0.4,
                {
                    "points": [
                        {"raw_score": 0.1, "probability": 0.2},
                        {"raw_score": 0.1, "probability": 0.25},
                    ]
                },
            )

        with self.assertRaisesRegex(TypeError, "must be a number"):
            map_raw_score_to_probability(
                0.4,
                {
                    "points": [
                        {"raw_score": True, "probability": 0.2},
                        {"raw_score": 1.0, "probability": 0.9},
                    ]
                },
            )


if __name__ == "__main__":
    unittest.main()
