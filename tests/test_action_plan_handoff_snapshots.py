from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ACTION_PLAN_HANDOFF_FIXTURES = ROOT / "examples" / "eval" / "action-plan-handoff"
PROGRAM_FIXTURE = ROOT / "examples" / "eval" / "program.erz"
REFRESH_HELPER = ROOT / "scripts" / "refresh_action_plan_handoff.py"


class ActionPlanHandoffSnapshotTests(unittest.TestCase):
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

    def test_action_plan_handoff_refresh_helper_regenerates_tracked_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "action-plan-handoff"
            shutil.copytree(ACTION_PLAN_HANDOFF_FIXTURES, replay_root)

            generated_paths = [
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
        self.assertIn("refreshed action-plan-handoff outputs:", refresh_run.stdout)
        self.assertEqual(refreshed_tree, self._read_tree(ACTION_PLAN_HANDOFF_FIXTURES))

    def test_action_plan_handoff_standalone_verify_sidecars_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "action-plan-handoff"
            shutil.copytree(ACTION_PLAN_HANDOFF_FIXTURES, replay_root)

            baseline_dir = replay_root / "baseline"
            summary_file = replay_root / "baseline.verify.expected.summary.txt"
            json_file = replay_root / "baseline.verify.expected.json"

            if baseline_dir.exists():
                shutil.rmtree(baseline_dir)
            if summary_file.exists():
                summary_file.unlink()
            if json_file.exists():
                json_file.unlink()

            emit_run = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--action-plan",
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "action-plan-ci-baseline-001",
                "--batch-output-manifest",
            )
            verify_run = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(baseline_dir),
                "--summary",
                "--batch-output-verify-summary-file",
                str(summary_file),
                "--batch-output-verify-json-file",
                str(json_file),
                "--batch-output-verify-profile",
                "default",
                "--batch-output-verify-require-run-id",
                "--batch-output-verify-expected-run-id-pattern",
                "^action-plan-ci-.*$",
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )

            summary_text = summary_file.read_text(encoding="utf-8")
            json_text = json_file.read_text(encoding="utf-8")
            baseline_tree = self._read_tree(baseline_dir)

        self.assertEqual(emit_run.returncode, 0)
        self.assertEqual(emit_run.stderr, "")
        self.assertEqual(verify_run.returncode, 0)
        self.assertEqual(verify_run.stderr, "")
        self.assertEqual(
            summary_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES / "baseline.verify.expected.summary.txt"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            json_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES / "baseline.verify.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            baseline_tree,
            self._read_tree(ACTION_PLAN_HANDOFF_FIXTURES / "baseline"),
        )

    def test_action_plan_handoff_triage_self_verify_handoff_bundle_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "action-plan-handoff"
            shutil.copytree(ACTION_PLAN_HANDOFF_FIXTURES, replay_root)

            triage_dir = replay_root / "triage-by-status"
            bundle_file = replay_root / "triage.handoff-bundle.expected.json"

            if triage_dir.exists():
                shutil.rmtree(triage_dir)
            if bundle_file.exists():
                bundle_file.unlink()

            triage_run = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--action-plan",
                "--batch-output",
                str(triage_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "action-plan-ci-triage-001",
                "--summary",
                "--batch-output-self-verify",
                "--batch-output-self-verify-strict",
                "--batch-output-handoff-bundle-file",
                str(bundle_file),
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-require-run-id",
                "--batch-output-verify-expected-run-id-pattern",
                "^action-plan-ci-.*$",
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )
            standalone_verify_summary = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(triage_dir),
                "--summary",
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-require-run-id",
                "--batch-output-verify-expected-run-id-pattern",
                "^action-plan-ci-.*$",
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )
            standalone_verify_json = self._run_cli(
                "eval",
                "--batch-output-verify",
                str(triage_dir),
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-require-run-id",
                "--batch-output-verify-expected-run-id-pattern",
                "^action-plan-ci-.*$",
                "--batch-output-verify-expected-event-count",
                "3",
                "--batch-output-verify-expected-action-plan-count",
                "1",
                "--batch-output-verify-expected-resolved-refs-count",
                "1",
            )

            bundle_text = bundle_file.read_text(encoding="utf-8")
            triage_summary_text = (triage_dir / "summary.json").read_text(encoding="utf-8")
            triage_tree = self._read_tree(triage_dir)

        self.assertEqual(triage_run.returncode, 0)
        self.assertEqual(triage_run.stderr, "")
        self.assertEqual(standalone_verify_summary.returncode, 0)
        self.assertEqual(standalone_verify_summary.stderr, "")
        self.assertEqual(standalone_verify_json.returncode, 0)
        self.assertEqual(standalone_verify_json.stderr, "")
        self.assertEqual(
            triage_run.stdout,
            "status=error events=3 errors=1 no_actions=1 actions=1 trace=1 plan=1 resolved_refs=1\n",
        )
        self.assertEqual(
            bundle_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES / "triage.handoff-bundle.expected.json"
            ).read_text(encoding="utf-8"),
        )
        bundle_payload = json.loads(bundle_text)
        expected_batch_output_summary = json.loads(triage_summary_text)
        self.assertEqual(bundle_payload["kind"], "erz.eval.batch_output_handoff_bundle.v1")
        self.assertEqual(bundle_payload["surface"], "batch_output")
        self.assertEqual(
            bundle_payload["primary"],
            {"key": "batch_output_summary", "details": expected_batch_output_summary},
        )
        self.assertEqual(bundle_payload["summary_line"], triage_run.stdout.rstrip("\n"))
        self.assertEqual(bundle_payload["exit"], {"policy": "default", "code": 0})
        self.assertEqual(bundle_payload["batch_output_root"], "triage-by-status")
        self.assertEqual(bundle_payload["batch_output_summary"], expected_batch_output_summary)
        self.assertEqual(
            bundle_payload["self_verify"]["summary_line"],
            standalone_verify_summary.stdout.rstrip("\n"),
        )
        self.assertEqual(
            bundle_payload["self_verify"]["details"],
            json.loads(standalone_verify_json.stdout),
        )
        self.assertIsNone(bundle_payload["self_compare"])
        self.assertEqual(
            triage_tree,
            self._read_tree(ACTION_PLAN_HANDOFF_FIXTURES / "triage-by-status"),
        )

    def test_action_plan_handoff_compare_sidecars_and_self_compare_handoff_bundles_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "action-plan-handoff"
            shutil.copytree(ACTION_PLAN_HANDOFF_FIXTURES, replay_root)

            baseline_dir = replay_root / "baseline"
            clean_dir = replay_root / "candidate-clean"
            triage_dir = replay_root / "triage-by-status"
            clean_compare_summary_file = replay_root / "candidate-clean-vs-baseline.compare.expected.summary.txt"
            clean_compare_json_file = replay_root / "candidate-clean-vs-baseline.compare.expected.json"
            triage_compare_summary_file = replay_root / "triage-vs-baseline.compare.expected.summary.txt"
            triage_compare_json_file = replay_root / "triage-vs-baseline.compare.expected.json"
            clean_bundle_file = replay_root / "candidate-clean-vs-baseline.handoff-bundle.expected.json"
            triage_bundle_file = replay_root / "triage-by-status-vs-baseline.handoff-bundle.expected.json"

            for path in [
                baseline_dir,
                clean_dir,
                triage_dir,
                clean_compare_summary_file,
                clean_compare_json_file,
                triage_compare_summary_file,
                triage_compare_json_file,
                clean_bundle_file,
                triage_bundle_file,
            ]:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()

            emit_baseline = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--action-plan",
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "action-plan-ci-baseline-001",
                "--batch-output-manifest",
            )
            emit_clean = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--action-plan",
                "--batch-output",
                str(clean_dir),
                "--batch-output-run-id",
                "action-plan-ci-candidate-clean-001",
                "--batch-output-manifest",
            )
            emit_triage = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--action-plan",
                "--batch-output",
                str(triage_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "action-plan-ci-triage-001",
                "--batch-output-manifest",
            )

            clean_compare_run = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(clean_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
                "--batch-output-compare-summary-file",
                str(clean_compare_summary_file),
                "--batch-output-compare-json-file",
                str(clean_compare_json_file),
                "--batch-output-compare-strict",
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-compared-count",
                "3",
                "--batch-output-compare-expected-matched-count",
                "3",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "0",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "3",
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
            )
            triage_compare_run = self._run_cli(
                "eval",
                "--batch-output-compare",
                str(triage_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
                "--batch-output-compare-summary-file",
                str(triage_compare_summary_file),
                "--batch-output-compare-json-file",
                str(triage_compare_json_file),
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
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
            )
            clean_self_compare_run = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--action-plan",
                "--batch-output",
                str(clean_dir),
                "--batch-output-run-id",
                "action-plan-ci-candidate-clean-001",
                "--batch-output-manifest",
                "--summary",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-self-compare-strict",
                "--batch-output-handoff-bundle-file",
                str(clean_bundle_file),
                "--batch-output-compare-expected-status",
                "ok",
                "--batch-output-compare-expected-compared-count",
                "3",
                "--batch-output-compare-expected-matched-count",
                "3",
                "--batch-output-compare-expected-changed-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "0",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "3",
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
            )
            triage_self_compare_run = self._run_cli(
                "eval",
                str(PROGRAM_FIXTURE),
                "--batch",
                str(replay_root / "batch"),
                "--action-plan",
                "--batch-output",
                str(triage_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "action-plan-ci-triage-001",
                "--batch-output-manifest",
                "--summary",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-self-compare-strict",
                "--batch-output-compare-profile",
                "expected-asymmetric-drift",
                "--batch-output-handoff-bundle-file",
                str(triage_bundle_file),
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
                "--batch-output-compare-expected-baseline-action-plan-count",
                "1",
                "--batch-output-compare-expected-candidate-action-plan-count",
                "1",
                "--batch-output-compare-expected-baseline-resolved-refs-count",
                "1",
                "--batch-output-compare-expected-candidate-resolved-refs-count",
                "1",
            )

            clean_compare_summary_text = clean_compare_summary_file.read_text(encoding="utf-8")
            clean_compare_json_text = clean_compare_json_file.read_text(encoding="utf-8")
            triage_compare_summary_text = triage_compare_summary_file.read_text(encoding="utf-8")
            triage_compare_json_text = triage_compare_json_file.read_text(encoding="utf-8")
            clean_bundle_text = clean_bundle_file.read_text(encoding="utf-8")
            triage_bundle_text = triage_bundle_file.read_text(encoding="utf-8")
            clean_summary_text = (clean_dir / "summary.json").read_text(encoding="utf-8")
            triage_summary_text = (triage_dir / "summary.json").read_text(encoding="utf-8")
            baseline_tree = self._read_tree(baseline_dir)
            clean_tree = self._read_tree(clean_dir)
            triage_tree = self._read_tree(triage_dir)

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_clean.returncode, 0)
        self.assertEqual(emit_clean.stderr, "")
        self.assertEqual(emit_triage.returncode, 0)
        self.assertEqual(emit_triage.stderr, "")
        self.assertEqual(clean_compare_run.returncode, 0)
        self.assertEqual(clean_compare_run.stderr, "")
        self.assertEqual(triage_compare_run.returncode, 0)
        self.assertEqual(triage_compare_run.stderr, "")
        self.assertEqual(clean_self_compare_run.returncode, 0)
        self.assertEqual(clean_self_compare_run.stderr, "")
        self.assertEqual(triage_self_compare_run.returncode, 0)
        self.assertEqual(triage_self_compare_run.stderr, "")
        self.assertEqual(
            clean_self_compare_run.stdout,
            "status=error events=3 errors=1 no_actions=1 actions=1 trace=1 plan=1 resolved_refs=1\n",
        )
        self.assertEqual(
            triage_self_compare_run.stdout,
            "status=error events=3 errors=1 no_actions=1 actions=1 trace=1 plan=1 resolved_refs=1\n",
        )
        self.assertEqual(
            clean_compare_summary_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES
                / "candidate-clean-vs-baseline.compare.expected.summary.txt"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            clean_compare_json_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES
                / "candidate-clean-vs-baseline.compare.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            triage_compare_summary_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES
                / "triage-vs-baseline.compare.expected.summary.txt"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            triage_compare_json_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES / "triage-vs-baseline.compare.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            clean_bundle_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES
                / "candidate-clean-vs-baseline.handoff-bundle.expected.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            triage_bundle_text,
            (
                ACTION_PLAN_HANDOFF_FIXTURES
                / "triage-by-status-vs-baseline.handoff-bundle.expected.json"
            ).read_text(encoding="utf-8"),
        )
        clean_bundle_payload = json.loads(clean_bundle_text)
        triage_bundle_payload = json.loads(triage_bundle_text)
        expected_clean_batch_output_summary = json.loads(clean_summary_text)
        expected_triage_batch_output_summary = json.loads(triage_summary_text)
        self.assertEqual(clean_bundle_payload["kind"], "erz.eval.batch_output_handoff_bundle.v1")
        self.assertEqual(triage_bundle_payload["kind"], "erz.eval.batch_output_handoff_bundle.v1")
        self.assertEqual(clean_bundle_payload["surface"], "batch_output")
        self.assertEqual(triage_bundle_payload["surface"], "batch_output")
        self.assertEqual(
            clean_bundle_payload["primary"],
            {"key": "batch_output_summary", "details": expected_clean_batch_output_summary},
        )
        self.assertEqual(
            triage_bundle_payload["primary"],
            {"key": "batch_output_summary", "details": expected_triage_batch_output_summary},
        )
        self.assertEqual(
            clean_bundle_payload["summary_line"],
            "status=error events=3 errors=1 no_actions=1 actions=1 trace=1 plan=1 resolved_refs=1",
        )
        self.assertEqual(
            triage_bundle_payload["summary_line"],
            "status=error events=3 errors=1 no_actions=1 actions=1 trace=1 plan=1 resolved_refs=1",
        )
        self.assertEqual(clean_bundle_payload["exit"], {"policy": "default", "code": 0})
        self.assertEqual(triage_bundle_payload["exit"], {"policy": "default", "code": 0})
        self.assertEqual(clean_bundle_payload["batch_output_root"], "candidate-clean")
        self.assertEqual(clean_bundle_payload["self_compare_against_root"], "baseline")
        self.assertEqual(triage_bundle_payload["batch_output_root"], "triage-by-status")
        self.assertEqual(triage_bundle_payload["self_compare_against_root"], "baseline")
        self.assertEqual(clean_bundle_payload["batch_output_summary"], expected_clean_batch_output_summary)
        self.assertEqual(triage_bundle_payload["batch_output_summary"], expected_triage_batch_output_summary)
        self.assertIsNone(clean_bundle_payload["self_verify"])
        self.assertIsNone(triage_bundle_payload["self_verify"])
        self.assertEqual(
            clean_bundle_payload["self_compare"]["summary_line"],
            clean_compare_summary_text.rstrip("\n"),
        )
        self.assertEqual(
            clean_bundle_payload["self_compare"]["details"],
            json.loads(clean_compare_json_text),
        )
        self.assertEqual(
            triage_bundle_payload["self_compare"]["summary_line"],
            triage_compare_summary_text.rstrip("\n"),
        )
        self.assertEqual(
            triage_bundle_payload["self_compare"]["details"],
            json.loads(triage_compare_json_text),
        )
        self.assertEqual(
            baseline_tree,
            self._read_tree(ACTION_PLAN_HANDOFF_FIXTURES / "baseline"),
        )
        self.assertEqual(
            clean_tree,
            self._read_tree(ACTION_PLAN_HANDOFF_FIXTURES / "candidate-clean"),
        )
        self.assertEqual(
            triage_tree,
            self._read_tree(ACTION_PLAN_HANDOFF_FIXTURES / "triage-by-status"),
        )


if __name__ == "__main__":
    unittest.main()
