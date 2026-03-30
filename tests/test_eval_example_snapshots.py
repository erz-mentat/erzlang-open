from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVAL_FIXTURES = ROOT / "examples" / "eval"
EVAL_FIXTURE_README = EVAL_FIXTURES / "README.md"
REFRESH_SCRIPT = ROOT / "scripts" / "refresh_eval_example_fixtures.py"


def _load_refresh_helper_module():
    spec = importlib.util.spec_from_file_location("refresh_eval_example_fixtures", REFRESH_SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load refresh helper module from {REFRESH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvalExampleSnapshotTests(unittest.TestCase):
    def test_eval_example_refresh_helper_regenerates_top_level_expected_outputs(self) -> None:
        expected_paths = sorted(path.relative_to(EVAL_FIXTURES) for path in EVAL_FIXTURES.glob("*.expected.*"))
        self.assertTrue(expected_paths, "expected checked-in top-level eval outputs")

        with tempfile.TemporaryDirectory() as tmp_dir:
            copied_fixture_root = Path(tmp_dir) / "eval"
            shutil.copytree(EVAL_FIXTURES, copied_fixture_root)

            for relative_path in expected_paths:
                target_path = copied_fixture_root / relative_path
                if target_path.exists():
                    target_path.unlink()

            result = subprocess.run(
                [
                    sys.executable,
                    str(REFRESH_SCRIPT),
                    "--repo-root",
                    str(ROOT),
                    "--fixture-root",
                    str(copied_fixture_root),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertEqual(result.stderr, "")

            for relative_path in expected_paths:
                with self.subTest(path=str(relative_path)):
                    refreshed_text = (copied_fixture_root / relative_path).read_text(encoding="utf-8")
                    checked_in_text = (EVAL_FIXTURES / relative_path).read_text(encoding="utf-8")
                    self.assertEqual(refreshed_text, checked_in_text)

    def test_eval_fixture_readme_mentions_every_checked_in_smoke_case(self) -> None:
        helper = _load_refresh_helper_module()
        readme_text = EVAL_FIXTURE_README.read_text(encoding="utf-8")

        self.assertIn("python3 scripts/refresh_eval_example_fixtures.py", readme_text)
        self.assertIn("python3 scripts/refresh_contract_fixtures.py", readme_text)

        for case in helper.SMOKE_CASES:
            with self.subTest(program=case.program_name):
                self.assertIn(case.program_name, readme_text)
                self.assertIn(case.ok_event_name, readme_text)
                self.assertIn(case.no_action_event_name, readme_text)
                self.assertIn(case.ok_output_name, readme_text)
                self.assertIn(case.no_action_output_name, readme_text)
                self.assertIn(case.no_action_summary_name, readme_text)


if __name__ == "__main__":
    unittest.main()
