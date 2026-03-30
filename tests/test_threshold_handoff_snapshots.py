from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
THRESHOLD_HANDOFF_FIXTURES = ROOT / "examples" / "eval" / "threshold-handoff"
PROGRAM_FIXTURE = ROOT / "examples" / "eval" / "program-thresholds.erz"
REFRESH_HELPER = ROOT / "scripts" / "refresh_threshold_handoff.py"


class ThresholdHandoffSnapshotTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "cli.main", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def _read_tree(self, root: Path) -> dict[str, str]:
        return {
            str(path.relative_to(root)): path.read_text(encoding="utf-8")
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def _run_refresh_helper(self, fixture_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(REFRESH_HELPER),
                "--repo-root",
                str(ROOT),
                "--fixture-root",
                str(fixture_root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_threshold_handoff_refresh_helper_regenerates_tracked_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "threshold-handoff"
            shutil.copytree(THRESHOLD_HANDOFF_FIXTURES, replay_root)

            generated_paths = [
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
            ]
            for relative_path in generated_paths:
                path = replay_root / relative_path
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()

            refresh_run = self._run_refresh_helper(replay_root)
            refreshed_tree = self._read_tree(replay_root)

        self.assertEqual(refresh_run.returncode, 0)
        self.assertEqual(refresh_run.stderr, "")
        self.assertIn("refreshed threshold-handoff outputs:", refresh_run.stdout)
        self.assertEqual(refreshed_tree, self._read_tree(THRESHOLD_HANDOFF_FIXTURES))

    def test_threshold_handoff_self_verify_sidecar_snapshots_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "threshold-handoff"
            shutil.copytree(THRESHOLD_HANDOFF_FIXTURES, replay_root)

            triage_candidate_dir = replay_root / "triage-by-status"
            triage_summary_file = replay_root / "triage.verify.expected.summary.txt"
            triage_json_file = replay_root / "triage.verify.expected.json"

            if triage_candidate_dir.exists():
                shutil.rmtree(triage_candidate_dir)
            if triage_summary_file.exists():
                triage_summary_file.unlink()
            if triage_json_file.exists():
                triage_json_file.unlink()

            triage_run = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--batch-output",
                str(triage_candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "threshold-ci-triage-001",
                "--summary",
                "--batch-output-self-verify",
                "--batch-output-self-verify-strict",
                "--batch-output-self-verify-summary-file",
                str(triage_summary_file),
                "--batch-output-self-verify-json-file",
                str(triage_json_file),
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-require-run-id",
                "--batch-output-verify-expected-run-id-pattern",
                "^threshold-ci-.*$",
                "--batch-output-verify-expected-event-count",
                "3",
            )

            triage_summary_text = triage_summary_file.read_text(encoding="utf-8")
            triage_json_text = triage_json_file.read_text(encoding="utf-8")
            triage_tree = self._read_tree(triage_candidate_dir)

        self.assertEqual(triage_run.returncode, 0)
        self.assertEqual(triage_run.stderr, "")
        self.assertEqual(
            triage_run.stdout,
            "status=error events=3 errors=1 no_actions=1 actions=1 trace=1\n",
        )
        self.assertEqual(
            triage_summary_text,
            (
                THRESHOLD_HANDOFF_FIXTURES
                / "triage.verify.expected.summary.txt"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            triage_json_text,
            (
                THRESHOLD_HANDOFF_FIXTURES / "triage.verify.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            triage_tree,
            self._read_tree(THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"),
        )

    def test_threshold_handoff_standalone_verify_json_sidecars_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "threshold-handoff"
            shutil.copytree(THRESHOLD_HANDOFF_FIXTURES, replay_root)

            baseline_json_file = replay_root / "baseline.verify.expected.json"
            triage_json_file = replay_root / "triage.verify.expected.json"

            if baseline_json_file.exists():
                baseline_json_file.unlink()
            if triage_json_file.exists():
                triage_json_file.unlink()

            baseline_run = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(replay_root / "baseline"),
                "--batch-output-verify-json-file",
                str(baseline_json_file),
                "--batch-output-verify-profile",
                "default",
                "--batch-output-verify-require-run-id",
                "--batch-output-verify-expected-run-id-pattern",
                "^threshold-ci-.*$",
                "--batch-output-verify-expected-event-count",
                "3",
            )
            triage_run = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(replay_root / "triage-by-status"),
                "--batch-output-verify-json-file",
                str(triage_json_file),
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-require-run-id",
                "--batch-output-verify-expected-run-id-pattern",
                "^threshold-ci-.*$",
                "--batch-output-verify-expected-event-count",
                "3",
            )

            baseline_json_text = baseline_json_file.read_text(encoding="utf-8")
            triage_json_text = triage_json_file.read_text(encoding="utf-8")
            baseline_tree = self._read_tree(replay_root / "baseline")
            triage_tree = self._read_tree(replay_root / "triage-by-status")

        self.assertEqual(baseline_run.returncode, 0)
        self.assertEqual(baseline_run.stderr, "")
        self.assertEqual(triage_run.returncode, 0)
        self.assertEqual(triage_run.stderr, "")
        self.assertEqual(
            baseline_json_text,
            (
                THRESHOLD_HANDOFF_FIXTURES / "baseline.verify.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            triage_json_text,
            (
                THRESHOLD_HANDOFF_FIXTURES / "triage.verify.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            baseline_tree,
            self._read_tree(THRESHOLD_HANDOFF_FIXTURES / "baseline"),
        )
        self.assertEqual(
            triage_tree,
            self._read_tree(THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"),
        )

    def test_threshold_handoff_standalone_compare_json_sidecars_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "threshold-handoff"
            shutil.copytree(THRESHOLD_HANDOFF_FIXTURES, replay_root)

            clean_json_file = (
                replay_root / "candidate-clean-vs-baseline.compare.expected.json"
            )
            triage_json_file = replay_root / "triage-vs-baseline.compare.expected.json"

            if clean_json_file.exists():
                clean_json_file.unlink()
            if triage_json_file.exists():
                triage_json_file.unlink()

            clean_run = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(replay_root / "candidate-clean"),
                "--batch-output-compare-against",
                str(replay_root / "baseline"),
                "--batch-output-compare-json-file",
                str(clean_json_file),
            )
            triage_run = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(replay_root / "triage-by-status"),
                "--batch-output-compare-against",
                str(replay_root / "baseline"),
                "--batch-output-compare-strict",
                "--batch-output-compare-profile",
                "expected-asymmetric-drift",
                "--batch-output-compare-expected-baseline-only-count",
                "3",
                "--batch-output-compare-expected-candidate-only-count",
                "2",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "4",
                "--batch-output-compare-json-file",
                str(triage_json_file),
            )

            clean_json_text = clean_json_file.read_text(encoding="utf-8")
            triage_json_text = triage_json_file.read_text(encoding="utf-8")
            baseline_tree = self._read_tree(replay_root / "baseline")
            clean_tree = self._read_tree(replay_root / "candidate-clean")
            triage_tree = self._read_tree(replay_root / "triage-by-status")

        self.assertEqual(clean_run.returncode, 0)
        self.assertEqual(clean_run.stderr, "")
        self.assertEqual(triage_run.returncode, 0)
        self.assertEqual(triage_run.stderr, "")
        self.assertEqual(
            clean_json_text,
            (
                THRESHOLD_HANDOFF_FIXTURES
                / "candidate-clean-vs-baseline.compare.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            triage_json_text,
            (
                THRESHOLD_HANDOFF_FIXTURES
                / "triage-vs-baseline.compare.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            baseline_tree,
            self._read_tree(THRESHOLD_HANDOFF_FIXTURES / "baseline"),
        )
        self.assertEqual(
            clean_tree,
            self._read_tree(THRESHOLD_HANDOFF_FIXTURES / "candidate-clean"),
        )
        self.assertEqual(
            triage_tree,
            self._read_tree(THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"),
        )


    def test_threshold_handoff_self_compare_handoff_bundle_snapshots_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "threshold-handoff"
            shutil.copytree(THRESHOLD_HANDOFF_FIXTURES, replay_root)

            clean_candidate_dir = replay_root / "candidate-clean"
            triage_candidate_dir = replay_root / "triage-by-status"
            clean_bundle_file = (
                replay_root / "candidate-clean-vs-baseline.handoff-bundle.expected.json"
            )
            triage_bundle_file = (
                replay_root / "triage-by-status-vs-baseline.handoff-bundle.expected.json"
            )

            if clean_candidate_dir.exists():
                shutil.rmtree(clean_candidate_dir)
            if triage_candidate_dir.exists():
                shutil.rmtree(triage_candidate_dir)
            if clean_bundle_file.exists():
                clean_bundle_file.unlink()
            if triage_bundle_file.exists():
                triage_bundle_file.unlink()

            clean_run = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--batch-output",
                str(clean_candidate_dir),
                "--batch-output-run-id",
                "threshold-ci-candidate-clean-001",
                "--batch-output-manifest",
                "--summary",
                "--batch-output-self-compare-against",
                str(replay_root / "baseline"),
                "--batch-output-handoff-bundle-file",
                str(clean_bundle_file),
            )
            triage_run = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--batch-output",
                str(triage_candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "threshold-ci-triage-001",
                "--batch-output-manifest",
                "--summary",
                "--batch-output-self-compare-against",
                str(replay_root / "baseline"),
                "--batch-output-self-compare-strict",
                "--batch-output-compare-profile",
                "expected-asymmetric-drift",
                "--batch-output-compare-expected-baseline-only-count",
                "3",
                "--batch-output-compare-expected-candidate-only-count",
                "2",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "4",
                "--batch-output-handoff-bundle-file",
                str(triage_bundle_file),
            )

            clean_bundle_text = clean_bundle_file.read_text(encoding="utf-8")
            triage_bundle_text = triage_bundle_file.read_text(encoding="utf-8")
            clean_tree = self._read_tree(clean_candidate_dir)
            triage_tree = self._read_tree(triage_candidate_dir)

        self.assertEqual(clean_run.returncode, 0)
        self.assertEqual(clean_run.stderr, "")
        self.assertEqual(triage_run.returncode, 0)
        self.assertEqual(triage_run.stderr, "")

        self.assertEqual(
            clean_bundle_text,
            (
                THRESHOLD_HANDOFF_FIXTURES
                / "candidate-clean-vs-baseline.handoff-bundle.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            triage_bundle_text,
            (
                THRESHOLD_HANDOFF_FIXTURES
                / "triage-by-status-vs-baseline.handoff-bundle.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            clean_tree,
            self._read_tree(THRESHOLD_HANDOFF_FIXTURES / "candidate-clean"),
        )
        self.assertEqual(
            triage_tree,
            self._read_tree(THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"),
        )


if __name__ == "__main__":
    unittest.main()
