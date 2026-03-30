from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFRESH_HELPER = ROOT / "scripts" / "refresh_contract_fixtures.py"
EVAL_FIXTURES = ROOT / "examples" / "eval"
ACTION_PLAN_HANDOFF_FIXTURES = ROOT / "examples" / "eval" / "action-plan-handoff"
THRESHOLD_HANDOFF_FIXTURES = ROOT / "examples" / "eval" / "threshold-handoff"
PROGRAM_PACK_FIXTURES = ROOT / "examples" / "program-packs"
PROGRAM_PACK_INDEX = PROGRAM_PACK_FIXTURES / "program-pack-index.json"


def _program_pack_replay_outputs() -> list[str]:
    payload = json.loads(PROGRAM_PACK_INDEX.read_text(encoding="utf-8"))
    raw_entries = payload.get("packs") if isinstance(payload, dict) else None
    if not isinstance(raw_entries, list) or not raw_entries:
        raise AssertionError("expected non-empty program-pack index packs array")

    stems: list[str] = []
    for entry in raw_entries:
        raw_path = entry if isinstance(entry, str) else entry.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise AssertionError("expected string pack path entries in program-pack index")
        stem = Path(raw_path).name
        if not stem:
            raise AssertionError("expected terminal path name in program-pack index")
        stems.append(stem)

    if len(stems) != len(set(stems)):
        raise AssertionError("expected unique pack output stems in program-pack index")

    return [
        relative_path
        for stem in (*stems, "program-pack-index")
        for relative_path in (
            f"{stem}.replay.expected.summary.txt",
            f"{stem}.replay.expected.json",
            f"{stem}.replay.handoff-bundle.expected.json",
        )
    ]


PROGRAM_PACK_REPLAY_OUTPUTS = _program_pack_replay_outputs()


class RefreshContractFixturesTests(unittest.TestCase):
    def _top_level_eval_expected_paths(self) -> list[Path]:
        return sorted(path.relative_to(EVAL_FIXTURES) for path in EVAL_FIXTURES.glob("*.expected.*"))

    def _read_tree(self, root: Path) -> dict[str, str]:
        return {
            str(path.relative_to(root)): path.read_text(encoding="utf-8")
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def _run_refresh_helper(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(REFRESH_HELPER),
                "--repo-root",
                str(ROOT),
                *args,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_refresh_contract_fixtures_regenerates_all_checked_in_contract_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            eval_root = temp_root / "eval"
            action_plan_root = temp_root / "action-plan-handoff"
            threshold_root = temp_root / "threshold-handoff"
            program_pack_root = temp_root / "program-packs"

            shutil.copytree(EVAL_FIXTURES, eval_root)
            shutil.copytree(ACTION_PLAN_HANDOFF_FIXTURES, action_plan_root)
            shutil.copytree(THRESHOLD_HANDOFF_FIXTURES, threshold_root)
            shutil.copytree(PROGRAM_PACK_FIXTURES, program_pack_root)

            for relative_path in self._top_level_eval_expected_paths():
                path = eval_root / relative_path
                if path.exists():
                    path.unlink()

            for relative_path in [
                "baseline",
                "candidate-clean",
                "triage-by-status",
                "baseline.verify.expected.summary.txt",
                "baseline.verify.expected.json",
                "candidate-clean-vs-baseline.compare.expected.summary.txt",
                "candidate-clean-vs-baseline.compare.expected.json",
                "triage-vs-baseline.compare.expected.summary.txt",
                "triage-vs-baseline.compare.expected.json",
                "triage.handoff-bundle.expected.json",
                "candidate-clean-vs-baseline.handoff-bundle.expected.json",
                "triage-by-status-vs-baseline.handoff-bundle.expected.json",
            ]:
                path = action_plan_root / relative_path
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()

            for relative_path in [
                "baseline",
                "candidate-clean",
                "triage-by-status",
                "baseline.verify.expected.summary.txt",
                "baseline.verify.expected.json",
                "triage.verify.expected.summary.txt",
                "triage.verify.expected.json",
                "candidate-clean-vs-baseline.compare.expected.json",
                "triage-vs-baseline.compare.expected.summary.txt",
                "triage-vs-baseline.compare.expected.json",
                "candidate-clean-vs-baseline.handoff-bundle.expected.json",
                "triage-by-status-vs-baseline.handoff-bundle.expected.json",
            ]:
                path = threshold_root / relative_path
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()

            for relative_path in PROGRAM_PACK_REPLAY_OUTPUTS:
                path = program_pack_root / relative_path
                if path.exists():
                    path.unlink()

            result = self._run_refresh_helper(
                "--eval-root",
                str(eval_root),
                "--action-plan-root",
                str(action_plan_root),
                "--threshold-root",
                str(threshold_root),
                "--program-pack-root",
                str(program_pack_root),
            )

            eval_tree = self._read_tree(eval_root)
            action_plan_tree = self._read_tree(action_plan_root)
            threshold_tree = self._read_tree(threshold_root)
            program_pack_tree = self._read_tree(program_pack_root)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("refreshed checked-in contract fixtures:", result.stdout)
        self.assertIn("- eval-smoke:", result.stdout)
        self.assertIn("- action-plan-handoff:", result.stdout)
        self.assertIn("- threshold-handoff:", result.stdout)
        self.assertIn("- program-pack-replay:", result.stdout)
        self.assertEqual(eval_tree, self._read_tree(EVAL_FIXTURES))
        self.assertEqual(action_plan_tree, self._read_tree(ACTION_PLAN_HANDOFF_FIXTURES))
        self.assertEqual(threshold_tree, self._read_tree(THRESHOLD_HANDOFF_FIXTURES))
        self.assertEqual(program_pack_tree, self._read_tree(PROGRAM_PACK_FIXTURES))

    def test_refresh_contract_fixtures_only_program_pack_replay_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            program_pack_root = Path(tmp_dir) / "program-packs"
            shutil.copytree(PROGRAM_PACK_FIXTURES, program_pack_root)

            for relative_path in PROGRAM_PACK_REPLAY_OUTPUTS:
                path = program_pack_root / relative_path
                if path.exists():
                    path.unlink()

            result = self._run_refresh_helper(
                "--only",
                "program-pack-replay",
                "--program-pack-root",
                str(program_pack_root),
            )
            program_pack_tree = self._read_tree(program_pack_root)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("refreshed checked-in contract fixtures:", result.stdout)
        self.assertIn("- program-pack-replay:", result.stdout)
        self.assertNotIn("- eval-smoke:", result.stdout)
        self.assertNotIn("- action-plan-handoff:", result.stdout)
        self.assertNotIn("- threshold-handoff:", result.stdout)
        self.assertEqual(program_pack_tree, self._read_tree(PROGRAM_PACK_FIXTURES))

    def test_refresh_contract_fixtures_only_eval_smoke_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            eval_root = Path(tmp_dir) / "eval"
            shutil.copytree(EVAL_FIXTURES, eval_root)

            for relative_path in self._top_level_eval_expected_paths():
                path = eval_root / relative_path
                if path.exists():
                    path.unlink()

            result = self._run_refresh_helper(
                "--only",
                "eval-smoke",
                "--eval-root",
                str(eval_root),
            )
            eval_tree = self._read_tree(eval_root)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("refreshed checked-in contract fixtures:", result.stdout)
        self.assertIn("- eval-smoke:", result.stdout)
        self.assertNotIn("- action-plan-handoff:", result.stdout)
        self.assertNotIn("- threshold-handoff:", result.stdout)
        self.assertNotIn("- program-pack-replay:", result.stdout)
        self.assertEqual(eval_tree, self._read_tree(EVAL_FIXTURES))

    def test_refresh_contract_fixtures_only_action_plan_handoff_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            action_plan_root = Path(tmp_dir) / "action-plan-handoff"
            shutil.copytree(ACTION_PLAN_HANDOFF_FIXTURES, action_plan_root)

            for relative_path in [
                "baseline",
                "candidate-clean",
                "triage-by-status",
                "baseline.verify.expected.summary.txt",
                "baseline.verify.expected.json",
                "candidate-clean-vs-baseline.compare.expected.summary.txt",
                "candidate-clean-vs-baseline.compare.expected.json",
                "triage-vs-baseline.compare.expected.summary.txt",
                "triage-vs-baseline.compare.expected.json",
                "triage.handoff-bundle.expected.json",
                "candidate-clean-vs-baseline.handoff-bundle.expected.json",
                "triage-by-status-vs-baseline.handoff-bundle.expected.json",
            ]:
                path = action_plan_root / relative_path
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()

            result = self._run_refresh_helper(
                "--only",
                "action-plan-handoff",
                "--action-plan-root",
                str(action_plan_root),
            )
            action_plan_tree = self._read_tree(action_plan_root)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("refreshed checked-in contract fixtures:", result.stdout)
        self.assertIn("- action-plan-handoff:", result.stdout)
        self.assertNotIn("- eval-smoke:", result.stdout)
        self.assertNotIn("- threshold-handoff:", result.stdout)
        self.assertNotIn("- program-pack-replay:", result.stdout)
        self.assertEqual(action_plan_tree, self._read_tree(ACTION_PLAN_HANDOFF_FIXTURES))

    def test_refresh_contract_fixtures_only_threshold_handoff_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            threshold_root = Path(tmp_dir) / "threshold-handoff"
            shutil.copytree(THRESHOLD_HANDOFF_FIXTURES, threshold_root)

            for relative_path in [
                "baseline",
                "candidate-clean",
                "triage-by-status",
                "baseline.verify.expected.summary.txt",
                "baseline.verify.expected.json",
                "triage.verify.expected.summary.txt",
                "triage.verify.expected.json",
                "candidate-clean-vs-baseline.compare.expected.json",
                "triage-vs-baseline.compare.expected.summary.txt",
                "triage-vs-baseline.compare.expected.json",
                "candidate-clean-vs-baseline.handoff-bundle.expected.json",
                "triage-by-status-vs-baseline.handoff-bundle.expected.json",
            ]:
                path = threshold_root / relative_path
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()

            result = self._run_refresh_helper(
                "--only",
                "threshold-handoff",
                "--threshold-root",
                str(threshold_root),
            )
            threshold_tree = self._read_tree(threshold_root)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("refreshed checked-in contract fixtures:", result.stdout)
        self.assertIn("- threshold-handoff:", result.stdout)
        self.assertNotIn("- eval-smoke:", result.stdout)
        self.assertNotIn("- action-plan-handoff:", result.stdout)
        self.assertNotIn("- program-pack-replay:", result.stdout)
        self.assertEqual(threshold_tree, self._read_tree(THRESHOLD_HANDOFF_FIXTURES))


if __name__ == "__main__":
    unittest.main()
