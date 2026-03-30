from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORT_HELPER = ROOT / "scripts" / "export_eval_handoff.py"
THRESHOLD_HANDOFF_FIXTURES = ROOT / "examples" / "eval" / "threshold-handoff"


class EvalHandoffHelperTests(unittest.TestCase):
    def _run_helper(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(EXPORT_HELPER), "--repo-root", str(ROOT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def _read_provenance(self, out_dir: Path) -> dict[str, object]:
        return json.loads((out_dir / "handoff.provenance.json").read_text(encoding="utf-8"))

    def _read_bundle(self, out_dir: Path) -> dict[str, object]:
        return json.loads((out_dir / "handoff.bundle.json").read_text(encoding="utf-8"))

    def _copy_fixture_tree(self, source: Path, destination: Path) -> Path:
        shutil.copytree(source, destination)
        return destination

    def _corrupt_manifest_hash(self, artifact_dir: Path) -> None:
        summary_path = artifact_dir / "summary.json"
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        payload["artifact_sha256"]["error/03-invalid.envelope.json"] = "0" * 64
        summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_export_eval_handoff_rejects_non_empty_out_dir(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            out_dir.mkdir()
            stale_sidecar = out_dir / "compare.summary.txt"
            stale_sidecar.write_text("stale\n", encoding="utf-8")

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --out-dir must be empty so stale handoff sidecars cannot survive across runs: "
                    f"{out_dir}\n"
                ),
            )
            self.assertEqual(stale_sidecar.read_text(encoding="utf-8"), "stale\n")

    def test_export_eval_handoff_rejects_output_inside_candidate_tree(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        out_dir = candidate_dir / "handoff-sidecars"

        result = self._run_helper(
            "--candidate-dir",
            str(candidate_dir),
            "--out-dir",
            str(out_dir),
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            (
                "export_eval_handoff: --out-dir must be outside --candidate-dir so handoff sidecars cannot "
                f"pollute the artifact tree: {out_dir}\n"
            ),
        )
        self.assertFalse(out_dir.exists())

    def test_export_eval_handoff_rejects_baseline_equal_to_candidate(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "handoff"
            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --baseline-dir must differ from --candidate-dir so handoff compare "
                    "cannot silently self-compare the same artifact tree: "
                    f"{candidate_dir}\n"
                ),
            )
            self.assertFalse(out_dir.exists())

    def test_export_eval_handoff_rejects_reserved_verify_passthrough_flags(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "handoff"
            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
                "--verify-arg=--batch-output-verify-summary-file=/tmp/elsewhere.txt",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --verify-arg cannot include reserved flag "
                    "--batch-output-verify-summary-file because export_eval_handoff already controls "
                    "the verify target, stdout mode, and --out-dir sidecars\n"
                ),
            )
            self.assertFalse(out_dir.exists())

    def test_export_eval_handoff_rejects_reserved_compare_passthrough_flags(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "handoff"
            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--compare-arg=--output=/tmp/compare.json",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --compare-arg cannot include reserved flag --output because "
                    "export_eval_handoff already controls the compare target, stdout mode, and "
                    "--out-dir sidecars\n"
                ),
            )
            self.assertFalse(out_dir.exists())

    def test_export_eval_handoff_rejects_reserved_verify_flag_prefix_passthrough(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "handoff"
            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
                "--verify-arg=--batch-output-verify-json-f=/tmp/elsewhere.json",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --verify-arg cannot include reserved flag prefix "
                    "--batch-output-verify-json-f (would resolve to --batch-output-verify-json-file via argparse abbreviation) because "
                    "export_eval_handoff already controls the verify target, stdout mode, and --out-dir sidecars\n"
                ),
            )
            self.assertFalse(out_dir.exists())
            self.assertFalse(Path("/tmp/elsewhere.json").exists())

    def test_export_eval_handoff_rejects_reserved_compare_flag_prefix_passthrough(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "handoff"
            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--compare-arg=--batch-output-compare-summary-f=/tmp/elsewhere.summary.txt",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --compare-arg cannot include reserved flag prefix "
                    "--batch-output-compare-summary-f (would resolve to --batch-output-compare-summary-file via argparse abbreviation) because "
                    "export_eval_handoff already controls the compare target, stdout mode, and --out-dir sidecars\n"
                ),
            )
            self.assertFalse(out_dir.exists())
            self.assertFalse(Path("/tmp/elsewhere.summary.txt").exists())

    def test_export_eval_handoff_rejects_extra_verify_export_passthrough_flags(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        cases = (
            "--summary-file=/tmp/verify.summary.txt",
            "--json-file=/tmp/verify.json",
        )

        for passthrough_flag in cases:
            with self.subTest(passthrough_flag=passthrough_flag):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    out_dir = Path(tmp_dir) / "handoff"
                    result = self._run_helper(
                        "--candidate-dir",
                        str(candidate_dir),
                        "--out-dir",
                        str(out_dir),
                        f"--verify-arg={passthrough_flag}",
                    )

                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    reserved_flag = passthrough_flag.split("=", 1)[0]
                    self.assertEqual(
                        result.stderr,
                        (
                            f"export_eval_handoff: --verify-arg cannot include reserved flag {reserved_flag} because "
                            "export_eval_handoff already controls the verify target, stdout mode, and "
                            "--out-dir sidecars\n"
                        ),
                    )
                    self.assertFalse(out_dir.exists())

    def test_export_eval_handoff_rejects_extra_compare_export_passthrough_flags(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"

        cases = (
            "--summary-file=/tmp/compare.summary.txt",
            "--json-file=/tmp/compare.json",
        )

        for passthrough_flag in cases:
            with self.subTest(passthrough_flag=passthrough_flag):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    out_dir = Path(tmp_dir) / "handoff"
                    result = self._run_helper(
                        "--candidate-dir",
                        str(candidate_dir),
                        "--baseline-dir",
                        str(baseline_dir),
                        "--out-dir",
                        str(out_dir),
                        f"--compare-arg={passthrough_flag}",
                    )

                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    reserved_flag = passthrough_flag.split("=", 1)[0]
                    self.assertEqual(
                        result.stderr,
                        (
                            f"export_eval_handoff: --compare-arg cannot include reserved flag {reserved_flag} because "
                            "export_eval_handoff already controls the compare target, stdout mode, and "
                            "--out-dir sidecars\n"
                        ),
                    )
                    self.assertFalse(out_dir.exists())

    def test_export_eval_handoff_verify_only_reports_verify_summary(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "handoff"
            resolved_out_dir = out_dir.resolve()
            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
            )

            verify_summary = (resolved_out_dir / "verify.summary.txt").read_text(encoding="utf-8")
            provenance = self._read_provenance(resolved_out_dir)
            bundle = self._read_bundle(resolved_out_dir)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(
                result.stdout,
                (
                    "exported eval handoff sidecars:\n"
                    f"- {resolved_out_dir / 'verify.summary.txt'}\n"
                    f"- {resolved_out_dir / 'verify.json'}\n"
                    f"- {resolved_out_dir / 'handoff.provenance.json'}\n"
                    f"- {resolved_out_dir / 'handoff.bundle.json'}\n"
                    f"verify: {verify_summary.rstrip()}\n"
                ),
            )
            self.assertNotIn("compare:", result.stdout)
            self.assertTrue((resolved_out_dir / "verify.summary.txt").is_file())
            self.assertTrue((resolved_out_dir / "verify.json").is_file())
            self.assertTrue((resolved_out_dir / "handoff.provenance.json").is_file())
            self.assertTrue((resolved_out_dir / "handoff.bundle.json").is_file())
            self.assertFalse((resolved_out_dir / "compare.summary.txt").exists())
            self.assertFalse((resolved_out_dir / "compare.json").exists())
            self.assertEqual(provenance["schema_version"], 1)
            self.assertEqual(provenance["repo_root"], str(ROOT))
            self.assertEqual(provenance["candidate_dir"], str(candidate_dir.resolve()))
            self.assertIsNone(provenance["baseline_dir"])
            self.assertEqual(provenance["out_dir"], str(resolved_out_dir))
            self.assertEqual(
                provenance["path_labels"],
                {
                    "repo_root": ROOT.name,
                    "candidate_dir": "triage-by-status",
                    "baseline_dir": None,
                    "out_dir": "handoff",
                },
            )
            self.assertEqual(
                provenance["helper_command"],
                [
                    sys.executable,
                    str(EXPORT_HELPER.resolve()),
                    "--repo-root",
                    str(ROOT),
                    "--candidate-dir",
                    str(candidate_dir),
                    "--out-dir",
                    str(out_dir),
                ],
            )
            self.assertEqual(
                provenance["sidecars"],
                {
                    "verify_summary": "verify.summary.txt",
                    "verify_json": "verify.json",
                    "compare_summary": None,
                    "compare_json": None,
                    "provenance_json": "handoff.provenance.json",
                    "bundle_json": "handoff.bundle.json",
                },
            )
            self.assertEqual(provenance["verify"]["summary_sidecar"], "verify.summary.txt")
            self.assertEqual(provenance["verify"]["json_sidecar"], "verify.json")
            self.assertIsNone(provenance["compare"])
            self.assertEqual(bundle["schema_version"], 1)
            self.assertEqual(bundle["command_status"], "ok")
            self.assertEqual(bundle["command_exit_code"], 0)
            self.assertEqual(bundle["candidate_root"], "triage-by-status")
            self.assertIsNone(bundle["baseline_root"])
            self.assertEqual(bundle["handoff_root"], "handoff")
            self.assertEqual(
                bundle["candidate_batch_output_summary"],
                json.loads((candidate_dir / "summary.json").read_text(encoding="utf-8")),
            )
            self.assertIsNone(bundle["baseline_batch_output_summary"])
            self.assertEqual(bundle["verify"]["summary"], verify_summary.rstrip())
            self.assertEqual(bundle["verify"]["json"], json.loads((resolved_out_dir / "verify.json").read_text(encoding="utf-8")))
            self.assertIsNone(bundle["compare"])
            self.assertEqual(bundle["provenance"], provenance)
            verify_command = provenance["verify"]["command"]
            self.assertEqual(
                verify_command[:7],
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(candidate_dir.resolve()),
                    "--summary",
                ],
            )
            self.assertIn("--batch-output-verify-summary-file", verify_command)
            self.assertIn("--batch-output-verify-json-file", verify_command)

    def test_export_eval_handoff_skips_compare_when_verify_fails(self) -> None:
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            candidate_dir = self._copy_fixture_tree(
                THRESHOLD_HANDOFF_FIXTURES / "triage-by-status",
                tmp_root / "candidate",
            )
            self._corrupt_manifest_hash(candidate_dir)
            out_dir = tmp_root / "handoff"

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--keep-failed-out-dir",
            )

            provenance = self._read_provenance(out_dir)
            bundle = self._read_bundle(out_dir)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn(
                "verify: status=error checked=2 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=2 selected_manifest=2",
                result.stderr,
            )
            self.assertIn("compare: skipped because verify failed", result.stderr)
            self.assertIn(
                f"command failed: {sys.executable} -m cli.main eval --batch-output-verify",
                result.stderr,
            )
            self.assertNotIn(
                f"command failed: {sys.executable} -m cli.main eval --batch-output-compare",
                result.stderr,
            )
            self.assertTrue((out_dir / "verify.summary.txt").is_file())
            self.assertTrue((out_dir / "verify.json").is_file())
            self.assertTrue((out_dir / "handoff.provenance.json").is_file())
            self.assertTrue((out_dir / "handoff.bundle.json").is_file())
            self.assertFalse((out_dir / "compare.summary.txt").exists())
            self.assertFalse((out_dir / "compare.json").exists())
            self.assertEqual(provenance["compare"]["executed"], False)
            self.assertEqual(provenance["compare"]["skipped_reason"], "verify_failed")
            self.assertEqual(provenance["compare"]["summary_sidecar"], "compare.summary.txt")
            self.assertEqual(provenance["compare"]["json_sidecar"], "compare.json")
            self.assertEqual(bundle["command_status"], "error")
            self.assertEqual(bundle["command_exit_code"], 1)
            self.assertEqual(bundle["verify"]["json"], json.loads((out_dir / "verify.json").read_text(encoding="utf-8")))
            self.assertEqual(bundle["compare"], {"summary": None, "json": None, "executed": False, "skipped_reason": "verify_failed"})
            self.assertEqual(bundle["provenance"], provenance)

    def test_export_eval_handoff_cleans_failed_staging_before_retry(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "handoff"
            failed_result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--compare-arg=--batch-output-compare-strict",
                "--compare-arg=--batch-output-compare-expected-status",
                "--compare-arg=ok",
            )

            self.assertEqual(failed_result.returncode, 1)
            self.assertEqual(failed_result.stdout, "")
            self.assertIn(
                "verify: status=ok checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2",
                failed_result.stderr,
            )
            self.assertIn(
                "compare: status=error compare_status=error compared=0 matched=0 changed=0 baseline_only=3 candidate_only=2 missing_baseline=0 missing_candidate=0 metadata_mismatches=4 selected_baseline=3 selected_candidate=2 strict_mismatches=1",
                failed_result.stderr,
            )
            self.assertIn("command failed:", failed_result.stderr)
            self.assertFalse(out_dir.exists())

            retry_result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--verify-arg=--batch-output-verify-profile",
                "--verify-arg=triage-by-status",
                "--verify-arg=--batch-output-verify-require-run-id",
                "--verify-arg=--batch-output-verify-expected-run-id-pattern",
                "--verify-arg=^threshold-ci-.*$",
                "--verify-arg=--batch-output-verify-expected-event-count",
                "--verify-arg=3",
                "--compare-arg=--batch-output-compare-strict",
                "--compare-arg=--batch-output-compare-profile",
                "--compare-arg=expected-asymmetric-drift",
                "--compare-arg=--batch-output-compare-expected-baseline-only-count",
                "--compare-arg=3",
                "--compare-arg=--batch-output-compare-expected-candidate-only-count",
                "--compare-arg=2",
                "--compare-arg=--batch-output-compare-expected-selected-baseline-count",
                "--compare-arg=3",
                "--compare-arg=--batch-output-compare-expected-selected-candidate-count",
                "--compare-arg=2",
                "--compare-arg=--batch-output-compare-expected-metadata-mismatches-count",
                "--compare-arg=4",
            )

            self.assertEqual(retry_result.returncode, 0)
            self.assertEqual(retry_result.stderr, "")
            self.assertIn("exported eval handoff sidecars:\n", retry_result.stdout)
            self.assertIn(
                "verify: status=ok checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=0\n",
                retry_result.stdout,
            )
            self.assertIn(
                "compare: status=ok compare_status=error compared=0 matched=0 changed=0 baseline_only=3 candidate_only=2 missing_baseline=0 missing_candidate=0 metadata_mismatches=4 selected_baseline=3 selected_candidate=2 strict_mismatches=0\n",
                retry_result.stdout,
            )
            self.assertTrue((out_dir / "verify.summary.txt").is_file())
            self.assertTrue((out_dir / "verify.json").is_file())
            self.assertTrue((out_dir / "compare.summary.txt").is_file())
            self.assertTrue((out_dir / "compare.json").is_file())
            self.assertTrue((out_dir / "handoff.provenance.json").is_file())
            self.assertTrue((out_dir / "handoff.bundle.json").is_file())

    def test_export_eval_handoff_can_preserve_failed_sidecars_for_diagnosis(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--keep-failed-out-dir",
                "--compare-arg=--batch-output-compare-strict",
                "--compare-arg=--batch-output-compare-expected-status",
                "--compare-arg=ok",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn(
                "verify: status=ok checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2",
                result.stderr,
            )
            self.assertIn(
                "compare: status=error compare_status=error compared=0 matched=0 changed=0 baseline_only=3 candidate_only=2 missing_baseline=0 missing_candidate=0 metadata_mismatches=4 selected_baseline=3 selected_candidate=2 strict_mismatches=1",
                result.stderr,
            )
            self.assertIn("preserved failed handoff sidecars:\n", result.stderr)
            self.assertIn(f"- {out_dir / 'verify.summary.txt'}", result.stderr)
            self.assertIn(f"- {out_dir / 'verify.json'}", result.stderr)
            self.assertIn(f"- {out_dir / 'compare.summary.txt'}", result.stderr)
            self.assertIn(f"- {out_dir / 'compare.json'}", result.stderr)
            self.assertIn(f"- {out_dir / 'handoff.provenance.json'}", result.stderr)
            self.assertIn(f"- {out_dir / 'handoff.bundle.json'}", result.stderr)
            self.assertIn("command failed:", result.stderr)
            self.assertTrue((out_dir / "verify.summary.txt").is_file())
            self.assertTrue((out_dir / "verify.json").is_file())
            self.assertTrue((out_dir / "compare.summary.txt").is_file())
            self.assertTrue((out_dir / "compare.json").is_file())
            self.assertTrue((out_dir / "handoff.provenance.json").is_file())
            self.assertTrue((out_dir / "handoff.bundle.json").is_file())
            self.assertEqual(
                (out_dir / "compare.summary.txt").read_text(encoding="utf-8"),
                "status=error compare_status=error compared=0 matched=0 changed=0 baseline_only=3 candidate_only=2 missing_baseline=0 missing_candidate=0 metadata_mismatches=4 selected_baseline=3 selected_candidate=2 strict_mismatches=1\n",
            )
            self.assertEqual(
                json.loads((out_dir / "compare.json").read_text(encoding="utf-8"))["status"],
                "error",
            )
            self.assertEqual(
                json.loads((out_dir / "compare.json").read_text(encoding="utf-8"))["compare_status"],
                "error",
            )
            self.assertEqual(self._read_bundle(out_dir)["command_status"], "error")

    def test_export_eval_handoff_can_reuse_preserved_failed_out_dir(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"
        expected_compare_summary = (
            THRESHOLD_HANDOFF_FIXTURES / "triage-vs-baseline.compare.expected.summary.txt"
        ).read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            failed_result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--keep-failed-out-dir",
                "--compare-arg=--batch-output-compare-strict",
                "--compare-arg=--batch-output-compare-expected-status",
                "--compare-arg=ok",
            )

            self.assertEqual(failed_result.returncode, 1)
            stale_compare_summary = (out_dir / "compare.summary.txt").read_text(encoding="utf-8")
            self.assertIn("strict_mismatches=1", stale_compare_summary)

            retry_result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--reuse-out-dir",
                "--verify-arg=--batch-output-verify-profile",
                "--verify-arg=triage-by-status",
                "--verify-arg=--batch-output-verify-require-run-id",
                "--verify-arg=--batch-output-verify-expected-run-id-pattern",
                "--verify-arg=^threshold-ci-.*$",
                "--verify-arg=--batch-output-verify-expected-event-count",
                "--verify-arg=3",
                "--compare-arg=--batch-output-compare-strict",
                "--compare-arg=--batch-output-compare-profile",
                "--compare-arg=expected-asymmetric-drift",
                "--compare-arg=--batch-output-compare-expected-baseline-only-count",
                "--compare-arg=3",
                "--compare-arg=--batch-output-compare-expected-candidate-only-count",
                "--compare-arg=2",
                "--compare-arg=--batch-output-compare-expected-selected-baseline-count",
                "--compare-arg=3",
                "--compare-arg=--batch-output-compare-expected-selected-candidate-count",
                "--compare-arg=2",
                "--compare-arg=--batch-output-compare-expected-metadata-mismatches-count",
                "--compare-arg=4",
            )

            self.assertEqual(retry_result.returncode, 0)
            self.assertEqual(retry_result.stderr, "")
            self.assertIn("exported eval handoff sidecars:\n", retry_result.stdout)
            self.assertEqual(
                (out_dir / "compare.summary.txt").read_text(encoding="utf-8"),
                expected_compare_summary,
            )
            self.assertNotEqual(
                (out_dir / "compare.summary.txt").read_text(encoding="utf-8"),
                stale_compare_summary,
            )
            self.assertTrue((out_dir / "verify.summary.txt").is_file())
            self.assertTrue((out_dir / "verify.json").is_file())
            self.assertTrue((out_dir / "compare.summary.txt").is_file())
            self.assertTrue((out_dir / "compare.json").is_file())
            self.assertTrue((out_dir / "handoff.provenance.json").is_file())
            self.assertTrue((out_dir / "handoff.bundle.json").is_file())

    def test_export_eval_handoff_rejects_reuse_out_dir_without_helper_provenance(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            out_dir.mkdir()
            (out_dir / "verify.summary.txt").write_text("stale\n", encoding="utf-8")
            (out_dir / "verify.json").write_text("{}\n", encoding="utf-8")

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
                "--reuse-out-dir",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --reuse-out-dir requires an existing helper provenance file so ownership can "
                    "be verified before managed sidecars are cleared: "
                    f"{out_dir / 'handoff.provenance.json'}\n"
                ),
            )
            self.assertEqual((out_dir / "verify.summary.txt").read_text(encoding="utf-8"), "stale\n")
            self.assertEqual((out_dir / "verify.json").read_text(encoding="utf-8"), "{}\n")

    def test_export_eval_handoff_rejects_reuse_out_dir_with_unexpected_entries(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            out_dir.mkdir()
            unexpected_path = out_dir / "notes.txt"
            unexpected_path.write_text("keep me\n", encoding="utf-8")
            (out_dir / "handoff.provenance.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repo_root": str(ROOT),
                        "candidate_dir": str(candidate_dir.resolve()),
                        "baseline_dir": None,
                        "out_dir": str(out_dir),
                        "sidecars": {
                            "verify_summary": "verify.summary.txt",
                            "verify_json": "verify.json",
                            "compare_summary": None,
                            "compare_json": None,
                            "provenance_json": "handoff.provenance.json",
                            "bundle_json": "handoff.bundle.json",
                        }
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
                "--reuse-out-dir",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --reuse-out-dir only works when --out-dir contains the helper-managed "
                    "sidecars declared by handoff.provenance.json, found unexpected entries: "
                    f"{unexpected_path}\n"
                ),
            )
            self.assertEqual(unexpected_path.read_text(encoding="utf-8"), "keep me\n")

    def test_export_eval_handoff_rejects_reuse_out_dir_with_wrong_schema_version(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            out_dir.mkdir()
            (out_dir / "handoff.provenance.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "repo_root": str(ROOT),
                        "candidate_dir": str(candidate_dir.resolve()),
                        "baseline_dir": None,
                        "out_dir": str(out_dir),
                        "sidecars": {
                            "verify_summary": "verify.summary.txt",
                            "verify_json": "verify.json",
                            "compare_summary": None,
                            "compare_json": None,
                            "provenance_json": "handoff.provenance.json",
                            "bundle_json": "handoff.bundle.json",
                        }
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
                "--reuse-out-dir",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --reuse-out-dir requires handoff.provenance.json with schema_version=1 "
                    "so helper ownership can be verified before managed sidecars are cleared: "
                    f"{out_dir / 'handoff.provenance.json'}\n"
                ),
            )

    def test_export_eval_handoff_rejects_reuse_out_dir_with_mismatched_recorded_out_dir(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            out_dir.mkdir()
            recorded_out_dir = str((Path(tmp_dir) / "elsewhere").resolve())
            (out_dir / "handoff.provenance.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repo_root": str(ROOT),
                        "candidate_dir": str(candidate_dir.resolve()),
                        "baseline_dir": None,
                        "out_dir": recorded_out_dir,
                        "sidecars": {
                            "verify_summary": "verify.summary.txt",
                            "verify_json": "verify.json",
                            "compare_summary": None,
                            "compare_json": None,
                            "provenance_json": "handoff.provenance.json",
                            "bundle_json": "handoff.bundle.json",
                        }
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
                "--reuse-out-dir",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --reuse-out-dir requires handoff.provenance.json to record the same "
                    "out_dir before managed sidecars are cleared, found out_dir="
                    f"{recorded_out_dir!r} in {out_dir / 'handoff.provenance.json'}\n"
                ),
            )

    def test_export_eval_handoff_rejects_reuse_out_dir_with_mismatched_recorded_repo_root(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            out_dir.mkdir()
            recorded_repo_root = str((ROOT / "elsewhere").resolve())
            (out_dir / "handoff.provenance.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repo_root": recorded_repo_root,
                        "candidate_dir": str(candidate_dir.resolve()),
                        "baseline_dir": None,
                        "out_dir": str(out_dir),
                        "sidecars": {
                            "verify_summary": "verify.summary.txt",
                            "verify_json": "verify.json",
                            "compare_summary": None,
                            "compare_json": None,
                            "provenance_json": "handoff.provenance.json",
                            "bundle_json": "handoff.bundle.json",
                        }
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
                "--reuse-out-dir",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --reuse-out-dir requires handoff.provenance.json to record the same "
                    "repo_root before managed sidecars are cleared, found repo_root="
                    f"{recorded_repo_root!r} in {out_dir / 'handoff.provenance.json'}\n"
                ),
            )

    def test_export_eval_handoff_rejects_reuse_out_dir_with_mismatched_recorded_candidate_dir(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            out_dir.mkdir()
            recorded_candidate_dir = str((THRESHOLD_HANDOFF_FIXTURES / "baseline").resolve())
            (out_dir / "handoff.provenance.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repo_root": str(ROOT),
                        "candidate_dir": recorded_candidate_dir,
                        "baseline_dir": None,
                        "out_dir": str(out_dir),
                        "sidecars": {
                            "verify_summary": "verify.summary.txt",
                            "verify_json": "verify.json",
                            "compare_summary": None,
                            "compare_json": None,
                            "provenance_json": "handoff.provenance.json",
                            "bundle_json": "handoff.bundle.json",
                        }
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--out-dir",
                str(out_dir),
                "--reuse-out-dir",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --reuse-out-dir requires handoff.provenance.json to record the same "
                    "candidate_dir before managed sidecars are cleared, found candidate_dir="
                    f"{recorded_candidate_dir!r} in {out_dir / 'handoff.provenance.json'}\n"
                ),
            )

    def test_export_eval_handoff_rejects_reuse_out_dir_with_mismatched_recorded_baseline_dir(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = (Path(tmp_dir) / "handoff").resolve()
            out_dir.mkdir()
            (out_dir / "handoff.provenance.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repo_root": str(ROOT),
                        "candidate_dir": str(candidate_dir.resolve()),
                        "baseline_dir": None,
                        "out_dir": str(out_dir),
                        "sidecars": {
                            "verify_summary": "verify.summary.txt",
                            "verify_json": "verify.json",
                            "compare_summary": None,
                            "compare_json": None,
                            "provenance_json": "handoff.provenance.json",
                            "bundle_json": "handoff.bundle.json",
                        }
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--reuse-out-dir",
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                (
                    "export_eval_handoff: --reuse-out-dir requires handoff.provenance.json to record the same "
                    "baseline_dir before managed sidecars are cleared, found baseline_dir=None in "
                    f"{out_dir / 'handoff.provenance.json'}\n"
                ),
            )

    def test_export_eval_handoff_replays_threshold_triage_gold_path(self) -> None:
        candidate_dir = THRESHOLD_HANDOFF_FIXTURES / "triage-by-status"
        baseline_dir = THRESHOLD_HANDOFF_FIXTURES / "baseline"
        candidate_tree_before = {
            str(path.relative_to(candidate_dir)): path.read_text(encoding="utf-8")
            for path in sorted(candidate_dir.rglob("*"))
            if path.is_file()
        }
        baseline_tree_before = {
            str(path.relative_to(baseline_dir)): path.read_text(encoding="utf-8")
            for path in sorted(baseline_dir.rglob("*"))
            if path.is_file()
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "handoff"
            resolved_out_dir = out_dir.resolve()
            result = self._run_helper(
                "--candidate-dir",
                str(candidate_dir),
                "--baseline-dir",
                str(baseline_dir),
                "--out-dir",
                str(out_dir),
                "--verify-arg=--batch-output-verify-profile",
                "--verify-arg=triage-by-status",
                "--verify-arg=--batch-output-verify-require-run-id",
                "--verify-arg=--batch-output-verify-expected-run-id-pattern",
                "--verify-arg=^threshold-ci-.*$",
                "--verify-arg=--batch-output-verify-expected-event-count",
                "--verify-arg=3",
                "--compare-arg=--batch-output-compare-strict",
                "--compare-arg=--batch-output-compare-profile",
                "--compare-arg=expected-asymmetric-drift",
                "--compare-arg=--batch-output-compare-expected-baseline-only-count",
                "--compare-arg=3",
                "--compare-arg=--batch-output-compare-expected-candidate-only-count",
                "--compare-arg=2",
                "--compare-arg=--batch-output-compare-expected-selected-baseline-count",
                "--compare-arg=3",
                "--compare-arg=--batch-output-compare-expected-selected-candidate-count",
                "--compare-arg=2",
                "--compare-arg=--batch-output-compare-expected-metadata-mismatches-count",
                "--compare-arg=4",
            )

            verify_summary = (out_dir / "verify.summary.txt").read_text(encoding="utf-8")
            verify_json = (out_dir / "verify.json").read_text(encoding="utf-8")
            compare_summary = (out_dir / "compare.summary.txt").read_text(encoding="utf-8")
            compare_json = (out_dir / "compare.json").read_text(encoding="utf-8")
            provenance = self._read_provenance(out_dir)
            bundle = self._read_bundle(out_dir)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        expected_verify_summary = (
            THRESHOLD_HANDOFF_FIXTURES / "triage.verify.expected.summary.txt"
        ).read_text(encoding="utf-8")
        expected_compare_summary = (
            THRESHOLD_HANDOFF_FIXTURES / "triage-vs-baseline.compare.expected.summary.txt"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            result.stdout,
            (
                "exported eval handoff sidecars:\n"
                f"- {resolved_out_dir / 'verify.summary.txt'}\n"
                f"- {resolved_out_dir / 'verify.json'}\n"
                f"- {resolved_out_dir / 'compare.summary.txt'}\n"
                f"- {resolved_out_dir / 'compare.json'}\n"
                f"- {resolved_out_dir / 'handoff.provenance.json'}\n"
                f"- {resolved_out_dir / 'handoff.bundle.json'}\n"
                f"verify: {expected_verify_summary.rstrip()}\n"
                f"compare: {expected_compare_summary.rstrip()}\n"
            ),
        )
        self.assertEqual(
            verify_summary,
            expected_verify_summary,
        )
        self.assertEqual(
            verify_json,
            (THRESHOLD_HANDOFF_FIXTURES / "triage.verify.expected.json").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(
            compare_summary,
            (
                THRESHOLD_HANDOFF_FIXTURES
                / "triage-vs-baseline.compare.expected.summary.txt"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            compare_json,
            (THRESHOLD_HANDOFF_FIXTURES / "triage-vs-baseline.compare.expected.json").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(provenance["schema_version"], 1)
        self.assertEqual(provenance["candidate_dir"], str(candidate_dir.resolve()))
        self.assertEqual(provenance["baseline_dir"], str(baseline_dir.resolve()))
        self.assertEqual(
            provenance["path_labels"],
            {
                "repo_root": ROOT.name,
                "candidate_dir": "triage-by-status",
                "baseline_dir": "baseline",
                "out_dir": "handoff",
            },
        )
        self.assertEqual(provenance["sidecars"]["compare_summary"], "compare.summary.txt")
        self.assertEqual(provenance["sidecars"]["compare_json"], "compare.json")
        self.assertEqual(provenance["sidecars"]["bundle_json"], "handoff.bundle.json")
        self.assertEqual(provenance["compare"]["summary_sidecar"], "compare.summary.txt")
        self.assertEqual(provenance["compare"]["json_sidecar"], "compare.json")
        self.assertEqual(bundle["command_status"], "ok")
        self.assertEqual(bundle["command_exit_code"], 0)
        self.assertEqual(bundle["candidate_root"], "triage-by-status")
        self.assertEqual(bundle["baseline_root"], "baseline")
        self.assertEqual(bundle["handoff_root"], "handoff")
        self.assertEqual(bundle["candidate_batch_output_summary"], json.loads((candidate_dir / "summary.json").read_text(encoding="utf-8")))
        self.assertEqual(bundle["baseline_batch_output_summary"], json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8")))
        self.assertEqual(bundle["verify"]["summary"], expected_verify_summary.rstrip())
        self.assertEqual(bundle["verify"]["json"], json.loads(verify_json))
        self.assertEqual(bundle["compare"]["summary"], expected_compare_summary.rstrip())
        self.assertEqual(bundle["compare"]["json"], json.loads(compare_json))
        self.assertEqual(bundle["compare"]["executed"], True)
        self.assertIsNone(bundle["compare"]["skipped_reason"])
        self.assertEqual(bundle["provenance"], provenance)
        compare_command = provenance["compare"]["command"]
        self.assertEqual(
            compare_command[:9],
            [
                sys.executable,
                "-m",
                "cli.main",
                "eval",
                "--batch-output-compare",
                str(candidate_dir.resolve()),
                "--batch-output-compare-against",
                str(baseline_dir.resolve()),
                "--summary",
            ],
        )
        self.assertIn("--batch-output-compare-summary-file", compare_command)
        self.assertIn("--batch-output-compare-json-file", compare_command)
        candidate_tree_after = {
            str(path.relative_to(candidate_dir)): path.read_text(encoding="utf-8")
            for path in sorted(candidate_dir.rglob("*"))
            if path.is_file()
        }
        baseline_tree_after = {
            str(path.relative_to(baseline_dir)): path.read_text(encoding="utf-8")
            for path in sorted(baseline_dir.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(candidate_tree_after, candidate_tree_before)
        self.assertEqual(baseline_tree_after, baseline_tree_before)


if __name__ == "__main__":
    unittest.main()
