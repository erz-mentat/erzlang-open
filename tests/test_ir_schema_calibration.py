from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from runtime.calibration import map_raw_score_to_probability
from runtime.eval import TRACE_OPTIONAL_FIELDS, TRACE_REQUIRED_FIELDS, validate_trace_step


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "ir.v0.1.schema.json"


class IRSchemaCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_top_level_contract_includes_calibration_variants(self) -> None:
        refs = {
            entry["$ref"]
            for entry in self.schema.get("oneOf", [])
            if isinstance(entry, dict) and "$ref" in entry
        }

        self.assertIn("#/$defs/calibration_config", refs)
        self.assertIn("#/$defs/calibration_bundle", refs)

    def test_calibration_point_examples_are_unit_interval_numbers(self) -> None:
        point_examples = self.schema["$defs"]["calibration_point"]["examples"]
        self.assertGreaterEqual(len(point_examples), 2)

        for point in point_examples:
            self._assert_point_shape(point)

    def test_calibration_config_examples_match_runtime_mapping_contract(self) -> None:
        config_examples = self.schema["$defs"]["calibration_config"]["examples"]
        self.assertGreaterEqual(len(config_examples), 1)

        for config in config_examples:
            self._assert_config_shape(config)

            # Runtime compatibility smoke checks.
            p0 = map_raw_score_to_probability(0.0, config)
            p_mid = map_raw_score_to_probability(0.5, config)
            p1 = map_raw_score_to_probability(1.0, config)

            self.assertGreaterEqual(p0, 0.0)
            self.assertLessEqual(p0, 1.0)
            self.assertGreaterEqual(p_mid, 0.0)
            self.assertLessEqual(p_mid, 1.0)
            self.assertGreaterEqual(p1, 0.0)
            self.assertLessEqual(p1, 1.0)

    def test_calibration_bundle_example_is_selector_safe_and_runtime_compatible(self) -> None:
        bundle_examples = self.schema["$defs"]["calibration_bundle"]["examples"]
        self.assertGreaterEqual(len(bundle_examples), 1)

        for bundle in bundle_examples:
            self.assertEqual(set(bundle.keys()) - {"id", "configs", "default_config", "metadata"}, set())
            self.assertIsInstance(bundle["id"], str)
            self.assertTrue(bundle["id"])

            configs = bundle["configs"]
            self.assertIsInstance(configs, dict)
            self.assertGreaterEqual(len(configs), 1)

            for selector, config in configs.items():
                self.assertIsInstance(selector, str)
                self.assertTrue(selector)
                self._assert_config_shape(config)

                # Runtime accepts all bundled configs.
                value = map_raw_score_to_probability(0.75, config)
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

            if "default_config" in bundle:
                self.assertIn(bundle["default_config"], configs)

    def test_trace_schema_stays_in_sync_with_runtime_trace_contract(self) -> None:
        trace_schema = self.schema["$defs"]["trace"]
        properties = trace_schema["properties"]

        self.assertEqual(set(trace_schema["required"]), set(TRACE_REQUIRED_FIELDS))

        expected_fields = set(TRACE_REQUIRED_FIELDS) | set(TRACE_OPTIONAL_FIELDS)
        self.assertEqual(set(properties.keys()), expected_fields)

        for field in TRACE_OPTIONAL_FIELDS:
            self.assertIn(field, properties)

        calibrated_probability = properties["calibrated_probability"]
        self.assertEqual(calibrated_probability["type"], "number")
        self.assertEqual(calibrated_probability["minimum"], 0.0)
        self.assertEqual(calibrated_probability["maximum"], 1.0)

        examples = trace_schema.get("examples", [])
        self.assertTrue(any("calibrated_probability" not in example for example in examples))
        self.assertTrue(any("calibrated_probability" in example for example in examples))

        for example in examples:
            self.assertEqual(validate_trace_step(example), example)

    def _assert_point_shape(self, point: Any) -> None:
        self.assertIsInstance(point, dict)
        self.assertEqual(set(point.keys()), {"raw_score", "probability"})

        self._assert_unit_number(point["raw_score"])
        self._assert_unit_number(point["probability"])

    def _assert_config_shape(self, config: Any) -> None:
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config.keys()) - {"method", "points", "description"}, set())
        self.assertEqual(config["method"], "piecewise_linear")

        points = config["points"]
        self.assertIsInstance(points, list)
        self.assertGreaterEqual(len(points), 2)

        for point in points:
            self._assert_point_shape(point)

    def _assert_unit_number(self, value: Any) -> None:
        self.assertNotIsInstance(value, bool)
        self.assertIsInstance(value, (int, float))
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
