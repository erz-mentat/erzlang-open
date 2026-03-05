from __future__ import annotations

from pathlib import Path
import unittest

from scripts.validate_fewshot import load_cases, validate_cases

ROOT = Path(__file__).resolve().parents[1]


class FewshotCasesTests(unittest.TestCase):
    def test_fewshot_cases_are_in_sync_with_parser(self) -> None:
        cases_path = ROOT / "examples" / "fewshot" / "cases.json"
        cases = load_cases(cases_path)

        failures = validate_cases(cases)

        self.assertEqual(len(cases), 12)
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
