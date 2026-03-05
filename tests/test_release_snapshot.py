from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_snapshot.py"


class ReleaseSnapshotScriptTests(unittest.TestCase):
    def _write_benchmark_payload(self, repo_root: Path) -> dict[str, object]:
        payload = {
            "meta": {
                "generated_at_utc": "2026-03-02T21:52:00+00:00",
                "token_counter": "approx:utf8_bytes_div_4",
            },
            "pairs": [
                {"name": "ingest_event"},
                {"name": "calibration_underconfident_alert"},
                {"name": "calibration_overconfident_alert"},
            ],
            "summary": {
                "pair_count": 3,
                "totals": {
                    "baseline_tokens": 300,
                    "erz_tokens": 180,
                    "token_saving_pct": 40.0,
                },
                "target": {
                    "token_saving_pct": 25.0,
                    "met": True,
                },
            },
        }

        result_path = repo_root / "bench/token-harness/results/latest.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _run_snapshot_export(self, repo_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--repo-root",
                str(repo_root),
                "--timestamp-utc",
                "2026-03-02T22:00:00+00:00",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def _assert_json_int(self, value: object, *, path: str) -> None:
        self.assertIsInstance(value, int, msg=f"expected integer at {path}")
        self.assertNotIsInstance(value, bool, msg=f"expected integer (not bool) at {path}")

    def _assert_json_number(self, value: object, *, path: str) -> None:
        self.assertIsInstance(value, (int, float), msg=f"expected numeric value at {path}")
        self.assertNotIsInstance(value, bool, msg=f"expected numeric value (not bool) at {path}")

    def test_exports_dated_and_latest_release_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._write_benchmark_payload(repo_root)

            completed = self._run_snapshot_export(repo_root)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            artifact_dir = repo_root / "docs/release-artifacts"
            self.assertTrue((artifact_dir / "release-snapshot-20260302T220000Z.json").exists())
            self.assertTrue((artifact_dir / "release-snapshot-20260302T220000Z.md").exists())
            self.assertTrue((artifact_dir / "latest.json").exists())
            self.assertTrue((artifact_dir / "latest.md").exists())

            latest_payload = json.loads((artifact_dir / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_payload["meta"]["snapshot_generated_at_utc"], "2026-03-02T22:00:00+00:00")
            self.assertEqual(
                latest_payload["meta"]["benchmark_generated_at_utc"],
                "2026-03-02T21:52:00+00:00",
            )
            self.assertEqual(latest_payload["quality_gate_snapshot"]["calibration_pair_count"], 2)
            self.assertTrue(latest_payload["quality_gate_snapshot"]["target_met"])

            latest_md = (artifact_dir / "latest.md").read_text(encoding="utf-8")
            self.assertIn("docs/release-artifacts/latest.json is the freshness source-of-truth", latest_md)

    def test_latest_json_shape_contract_for_release_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            benchmark_payload = self._write_benchmark_payload(repo_root)

            completed = self._run_snapshot_export(repo_root)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            artifact_path = repo_root / "docs/release-artifacts/latest.json"
            latest_payload = json.loads(artifact_path.read_text(encoding="utf-8"))

            self.assertIsInstance(latest_payload, dict)
            self.assertIn("meta", latest_payload)
            self.assertIn("quality_gate_snapshot", latest_payload)
            self.assertIn("benchmark_summary", latest_payload)

            meta = latest_payload["meta"]
            self.assertIsInstance(meta, dict)
            meta_required = {
                "snapshot_generated_at_utc",
                "benchmark_generated_at_utc",
                "benchmark_result_path",
                "full_lane_entrypoint",
                "source_of_truth_rule",
            }
            self.assertTrue(meta_required.issubset(set(meta.keys())))
            self.assertIsInstance(meta["snapshot_generated_at_utc"], str)
            self.assertIsInstance(meta["benchmark_generated_at_utc"], str)
            self.assertIsInstance(meta["benchmark_result_path"], str)
            self.assertIsInstance(meta["full_lane_entrypoint"], str)
            self.assertIsInstance(meta["source_of_truth_rule"], str)
            self.assertEqual(meta["snapshot_generated_at_utc"], "2026-03-02T22:00:00+00:00")

            gate = latest_payload["quality_gate_snapshot"]
            self.assertIsInstance(gate, dict)
            gate_required = {
                "gate",
                "baseline_tokens",
                "erz_tokens",
                "token_saving_pct",
                "target_pct",
                "target_met",
                "pair_count",
                "pair_floor",
                "pair_floor_met",
                "calibration_pair_count",
                "calibration_pair_floor",
                "calibration_pair_floor_met",
            }
            self.assertTrue(gate_required.issubset(set(gate.keys())))
            self.assertIsInstance(gate["gate"], str)
            self._assert_json_int(gate["baseline_tokens"], path="quality_gate_snapshot.baseline_tokens")
            self._assert_json_int(gate["erz_tokens"], path="quality_gate_snapshot.erz_tokens")
            self._assert_json_number(gate["token_saving_pct"], path="quality_gate_snapshot.token_saving_pct")
            self._assert_json_number(gate["target_pct"], path="quality_gate_snapshot.target_pct")
            self.assertIsInstance(gate["target_met"], bool)
            self._assert_json_int(gate["pair_count"], path="quality_gate_snapshot.pair_count")
            self._assert_json_int(gate["pair_floor"], path="quality_gate_snapshot.pair_floor")
            self.assertIsInstance(gate["pair_floor_met"], bool)
            self._assert_json_int(gate["calibration_pair_count"], path="quality_gate_snapshot.calibration_pair_count")
            self._assert_json_int(gate["calibration_pair_floor"], path="quality_gate_snapshot.calibration_pair_floor")
            self.assertIsInstance(gate["calibration_pair_floor_met"], bool)

            self.assertEqual(gate["pair_count"], 3)
            self.assertFalse(gate["pair_floor_met"])
            self.assertEqual(gate["calibration_pair_count"], 2)
            self.assertTrue(gate["calibration_pair_floor_met"])

            benchmark_summary = latest_payload["benchmark_summary"]
            self.assertIsInstance(benchmark_summary, dict)
            summary_required = {"pair_count", "totals", "target"}
            self.assertTrue(summary_required.issubset(set(benchmark_summary.keys())))
            self._assert_json_int(benchmark_summary["pair_count"], path="benchmark_summary.pair_count")
            self.assertIsInstance(benchmark_summary["totals"], dict)
            self.assertIsInstance(benchmark_summary["target"], dict)
            self.assertEqual(benchmark_summary, benchmark_payload["summary"])

    def test_repo_checked_in_latest_md_presence_and_source_markers(self) -> None:
        artifact_path = ROOT / "docs/release-artifacts/latest.md"
        self.assertTrue(artifact_path.exists(), msg="expected checked-in release markdown artifact")

        latest_md = artifact_path.read_text(encoding="utf-8")
        self.assertIn("# Release Snapshot", latest_md)
        self.assertIn("- Benchmark source file: `bench/token-harness/results/latest.json`", latest_md)
        self.assertIn("- Full-lane entrypoint: `./scripts/check.sh`", latest_md)
        self.assertIn(
            "docs/release-artifacts/latest.json is the freshness source-of-truth.",
            latest_md,
        )

    def test_release_evidence_quickstart_command_parity_docs(self) -> None:
        quickstart_command = "./scripts/check.sh && python3 scripts/release_snapshot.py"

        top_level_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        harness_readme = (ROOT / "bench/token-harness/README.md").read_text(encoding="utf-8")

        self.assertIn(quickstart_command, top_level_readme)
        self.assertIn(quickstart_command, harness_readme)

    def test_release_artifact_index_quickstart_command_parity_with_quality_gate_notes(self) -> None:
        quickstart_command = "./scripts/check.sh && python3 scripts/release_snapshot.py"

        artifact_index = (ROOT / "docs/release-artifacts/README.md").read_text(encoding="utf-8")
        quality_gates = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8")

        self.assertIn(quickstart_command, artifact_index)
        self.assertIn(quickstart_command, quality_gates)

    def test_quality_gates_release_hook_literal_singularity(self) -> None:
        quality_gates = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8")
        quickstart_command = "./scripts/check.sh && python3 scripts/release_snapshot.py"

        self.assertEqual(
            quality_gates.count(quickstart_command),
            1,
            msg="expected exactly one release automation hook literal in docs/quality-gates.md",
        )

    def test_quality_gates_error_envelope_gate_heading_singularity(self) -> None:
        quality_gates = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8")
        heading = "### Gate B8: Machine-readable error envelope contract (v0.2 prep)"

        self.assertEqual(
            quality_gates.count(heading),
            1,
            msg="expected exactly one Gate B8 machine-readable error envelope heading in docs/quality-gates.md",
        )

    def test_release_artifact_index_quickstart_heading_singularity(self) -> None:
        artifact_index = (ROOT / "docs/release-artifacts/README.md").read_text(encoding="utf-8")

        self.assertEqual(
            artifact_index.count("## Quickstart pointer"),
            1,
            msg="expected exactly one quickstart heading marker in docs/release-artifacts/README.md",
        )

    def test_release_artifact_index_quickstart_heading_line_boundary(self) -> None:
        artifact_index_lines = (ROOT / "docs/release-artifacts/README.md").read_text(
            encoding="utf-8"
        ).splitlines()

        standalone_matches = [line for line in artifact_index_lines if line.strip() == "## Quickstart pointer"]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone quickstart heading line in docs/release-artifacts/README.md",
        )

    def test_release_artifact_index_retention_preconditions_anchor_marker_singularity(self) -> None:
        artifact_index = (ROOT / "docs/release-artifacts/README.md").read_text(encoding="utf-8")

        self.assertEqual(
            artifact_index.count("Preconditions checklist (execute in order before running commands):"),
            1,
            msg="expected exactly one retention checklist marker in docs/release-artifacts/README.md",
        )

    def test_release_artifact_index_retention_preconditions_anchor_marker_line_boundary(self) -> None:
        artifact_index_lines = (ROOT / "docs/release-artifacts/README.md").read_text(
            encoding="utf-8"
        ).splitlines()

        standalone_matches = [
            line
            for line in artifact_index_lines
            if line.strip() == "Preconditions checklist (execute in order before running commands):"
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone retention checklist marker line in docs/release-artifacts/README.md",
        )

    def test_quality_gates_release_evidence_heading_presence(self) -> None:
        quality_gates = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8")

        self.assertIn("Release evidence automation:", quality_gates)

    def test_quality_gates_release_evidence_heading_singularity(self) -> None:
        quality_gates = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8")

        self.assertEqual(
            quality_gates.count("Release evidence automation:"),
            1,
            msg="expected exactly one release evidence heading marker in docs/quality-gates.md",
        )

    def test_quality_gates_release_evidence_heading_line_boundary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line for line in quality_gates_lines if line.strip() == "Release evidence automation:"
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone release evidence heading line in docs/quality-gates.md",
        )

    def test_rl_040_quality_gates_release_hook_bullet_line_singularity_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Optional post-pass hook")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone optional post-pass hook bullet line in docs/quality-gates.md",
        )

    def test_rl_041_quality_gates_release_hook_before_dated_snapshot_bullet_order_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        hook_line_index = next(
            (
                index
                for index, line in enumerate(quality_gates_lines)
                if line.strip().startswith("- Optional post-pass hook")
            ),
            None,
        )
        dated_snapshot_line_index = next(
            (
                index
                for index, line in enumerate(quality_gates_lines)
                if line.strip().startswith("- Dated snapshots are written")
            ),
            None,
        )

        self.assertIsNotNone(
            hook_line_index,
            msg="expected optional post-pass hook bullet line in docs/quality-gates.md",
        )
        self.assertIsNotNone(
            dated_snapshot_line_index,
            msg="expected dated snapshot bullet line in docs/quality-gates.md",
        )
        assert hook_line_index is not None
        assert dated_snapshot_line_index is not None
        self.assertLess(
            hook_line_index,
            dated_snapshot_line_index,
            msg="expected optional post-pass hook bullet line to appear before dated snapshot bullet line in docs/quality-gates.md",
        )

    def test_rl_043_quality_gates_dated_snapshot_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Dated snapshots are written to "
            "`docs/release-artifacts/release-snapshot-<UTCSTAMP>.{json,md}` and mirrored to "
            "`docs/release-artifacts/latest.{json,md}`."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one dated snapshot bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_044_quality_gates_dated_snapshot_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Dated snapshots are written")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone dated snapshot bullet line in docs/quality-gates.md",
        )

    def test_rl_046_quality_gates_naming_policy_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Naming/latest-pointer/cleanup policy plus manual prune command snippets are indexed in "
            "`docs/release-artifacts/README.md`."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one naming-policy bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_047_quality_gates_naming_policy_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Naming/latest-pointer/cleanup policy")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone naming-policy bullet line in docs/quality-gates.md",
        )

    def test_rl_049_quality_gates_source_of_truth_rule_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Source-of-truth rule: `bench/token-harness/results/latest.json` stays repo-pinned for "
            "non-mutating local gate runs, freshness is tracked via "
            "`docs/release-artifacts/latest.json`."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one source-of-truth-rule bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_050_quality_gates_source_of_truth_rule_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Source-of-truth rule:")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone source-of-truth-rule bullet line in docs/quality-gates.md",
        )

    def test_rl_052_quality_gates_quickstart_pointer_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Quickstart pointers are mirrored in top-level onboarding docs "
            "(`README.md`, `bench/token-harness/README.md`) for discoverability."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one quickstart-pointer bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_053_quality_gates_quickstart_pointer_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Quickstart pointers are mirrored")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone quickstart-pointer bullet line in docs/quality-gates.md",
        )

    def test_rl_055_quality_gates_release_artifact_json_shape_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Release artifact JSON shape contract is locked by `tests/test_release_snapshot.py` "
            "(`test_latest_json_shape_contract_for_release_evidence`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one release-artifact-json-shape bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_056_quality_gates_release_artifact_json_shape_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Release artifact JSON shape contract is locked")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone release-artifact-json-shape bullet line in docs/quality-gates.md",
        )


    def test_rl_058_quality_gates_checked_in_freshness_parity_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Checked-in freshness/parity canary is locked by `tests/test_release_snapshot.py` "
            "(`test_repo_checked_in_latest_json_contract_parity`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one checked-in-freshness/parity bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_059_quality_gates_checked_in_freshness_parity_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Checked-in freshness/parity canary is locked")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone checked-in-freshness/parity bullet line in docs/quality-gates.md",
        )

    def test_rl_061_quality_gates_checked_in_latest_md_presence_source_marker_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Checked-in release markdown presence/source-marker canary is locked by "
            "`tests/test_release_snapshot.py` (`test_repo_checked_in_latest_md_presence_and_source_markers`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one checked-in-latest-md presence/source-marker bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_062_quality_gates_checked_in_latest_md_presence_source_marker_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Checked-in release markdown presence/source-marker canary is locked")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone checked-in-latest-md presence/source-marker bullet line in docs/quality-gates.md",
        )

    def test_rl_064_quality_gates_quickstart_command_parity_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Quickstart command parity canary for onboarding docs is locked by "
            "`tests/test_release_snapshot.py` (`test_release_evidence_quickstart_command_parity_docs`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one quickstart-command-parity bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_065_quality_gates_quickstart_command_parity_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Quickstart command parity canary for onboarding docs is locked")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone quickstart-command-parity bullet line in docs/quality-gates.md",
        )

    def test_rl_067_quality_gates_release_evidence_heading_singularity_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Release-evidence heading singularity canary is locked by "
            "`tests/test_release_snapshot.py` (`test_quality_gates_release_evidence_heading_singularity`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one release-evidence-heading-singularity bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_068_quality_gates_release_evidence_heading_singularity_bullet_line_boundary_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Release-evidence heading singularity canary is locked")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone release-evidence-heading-singularity bullet line in docs/quality-gates.md",
        )

    def test_rl_070_quality_gates_heading_boundary_canaries_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Heading-boundary canaries are locked by `tests/test_release_snapshot.py`, "
            "release-evidence heading must stay standalone "
            "(`test_quality_gates_release_evidence_heading_line_boundary`), and the artifact "
            "index title must remain the first non-empty line "
            "(`test_release_artifact_index_title_first_non_empty_line_boundary`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one heading-boundary-canaries bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_071_quality_gates_heading_boundary_canaries_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Heading-boundary canaries are locked by")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone heading-boundary-canaries bullet line in docs/quality-gates.md",
        )

    def test_rl_073_quality_gates_artifact_index_line_boundary_canaries_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Artifact-index line-boundary canaries are locked by `tests/test_release_snapshot.py`, "
            "quickstart heading must stay standalone "
            "(`test_release_artifact_index_quickstart_heading_line_boundary`), and the retention "
            "checklist marker must stay standalone "
            "(`test_release_artifact_index_retention_preconditions_anchor_marker_line_boundary`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one artifact-index-line-boundary-canaries bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_074_quality_gates_artifact_index_line_boundary_canaries_bullet_line_boundary_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Artifact-index line-boundary canaries are locked by")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone artifact-index-line-boundary-canaries bullet line in docs/quality-gates.md",
        )

    def test_rl_076_quality_gates_artifact_index_order_boundary_contract_bullet_singularity_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Artifact-index order-boundary contract (RL-034/RL-035): keep `## Quickstart pointer` "
            "after `# Release Artifacts Index`, and keep `Preconditions checklist (execute in order "
            "before running commands):` after `## Quickstart pointer` to preserve stable "
            "release-evidence indexing."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg="expected exactly one artifact-index-order-boundary-contract bullet canonical line in docs/quality-gates.md",
        )

    def test_rl_077_quality_gates_artifact_index_order_boundary_contract_bullet_line_boundary_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith("- Artifact-index order-boundary contract (RL-034/RL-035):")
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg="expected exactly one standalone artifact-index-order-boundary-contract bullet line in docs/quality-gates.md",
        )

    def test_rl_079_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_singularity_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Artifact-index line-index order-boundary contract (RL-037/RL-038): keep the first "
            "`## Quickstart pointer` line index after the title heading line index, and keep the first "
            "`Preconditions checklist (execute in order before running commands):` line index after "
            "the quickstart heading line index to preserve stable release-evidence indexing."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg=(
                "expected exactly one artifact-index-line-index-order-boundary-contract bullet canonical "
                "line in docs/quality-gates.md"
            ),
        )

    def test_rl_080_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_line_boundary_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith(
                "- Artifact-index line-index order-boundary contract (RL-037/RL-038):"
            )
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg=(
                "expected exactly one standalone artifact-index-line-index-order-boundary-contract bullet "
                "line in docs/quality-gates.md"
            ),
        )

    def test_rl_082_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_singularity_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Release artifact index title-heading presence/singularity canaries are locked by "
            "`tests/test_release_snapshot.py` (`test_release_artifact_index_title_heading_presence`, "
            "`test_release_artifact_index_title_heading_singularity`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg=(
                "expected exactly one release-artifact-index-title-heading-presence/singularity bullet canonical "
                "line in docs/quality-gates.md"
            ),
        )

    def test_rl_083_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_line_boundary_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith(
                "- Release artifact index title-heading presence/singularity canaries are locked by"
            )
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg=(
                "expected exactly one standalone release-artifact-index-title-heading-presence/singularity "
                "bullet line in docs/quality-gates.md"
            ),
        )

    def test_rl_085_quality_gates_source_of_truth_string_parity_bullet_singularity_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is "
            "locked by `tests/test_release_snapshot.py` "
            "(`test_repo_checked_in_source_of_truth_rule_parity_between_latest_json_and_latest_md`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg=(
                "expected exactly one source-of-truth-string-parity bullet canonical line in "
                "docs/quality-gates.md"
            ),
        )

    def test_rl_086_quality_gates_source_of_truth_string_parity_bullet_line_boundary_canary(self) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith(
                "- Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` "
                "is locked by"
            )
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg=(
                "expected exactly one standalone source-of-truth-string-parity bullet line in "
                "docs/quality-gates.md"
            ),
        )

    def test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Source-of-truth-string-parity bullet boundary contract (RL-088/RL-089): keep exactly "
            "one standalone `Source-of-truth string parity canary between checked-in `latest.json` "
            "and `latest.md` is locked...` bullet, locked by `tests/test_release_snapshot.py` "
            "(`test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary`, "
            "`test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg=(
                "expected exactly one source-of-truth-string-parity boundary-contract bullet canonical "
                "line in docs/quality-gates.md"
            ),
        )

    def test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith(
                "- Source-of-truth-string-parity bullet boundary contract (RL-085/RL-086):"
            )
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg=(
                "expected exactly one standalone source-of-truth-string-parity boundary-contract "
                "bullet line in docs/quality-gates.md"
            ),
        )

    def test_rl_091_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_token_literal_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        boundary_matches = [
            line.strip()
            for line in quality_gates_lines
            if line.strip().startswith(
                "- Source-of-truth-string-parity bullet boundary contract (RL-088/RL-089):"
            )
        ]
        self.assertEqual(
            len(boundary_matches),
            1,
            msg=(
                "expected exactly one RL-088/RL-089 source-of-truth-string-parity boundary-contract "
                "bullet line in docs/quality-gates.md"
            ),
        )

        boundary_line = boundary_matches[0]
        self.assertEqual(
            boundary_line.count("`latest.json`"),
            1,
            msg=(
                "expected RL-088/RL-089 source-of-truth-string-parity boundary-contract bullet to "
                "contain `latest.json` exactly once"
            ),
        )
        self.assertEqual(
            boundary_line.count("`latest.md`"),
            1,
            msg=(
                "expected RL-088/RL-089 source-of-truth-string-parity boundary-contract bullet to "
                "contain `latest.md` exactly once"
            ),
        )

    def test_rl_092_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_test_reference_pair_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        boundary_matches = [
            line.strip()
            for line in quality_gates_lines
            if line.strip().startswith(
                "- Source-of-truth-string-parity bullet boundary contract (RL-088/RL-089):"
            )
        ]
        self.assertEqual(
            len(boundary_matches),
            1,
            msg=(
                "expected exactly one RL-088/RL-089 source-of-truth-string-parity boundary-contract "
                "bullet line in docs/quality-gates.md"
            ),
        )

        boundary_line = boundary_matches[0]
        rl_088_ref = (
            "test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_"
            "bullet_singularity_canary"
        )
        rl_089_ref = (
            "test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_"
            "bullet_line_boundary_canary"
        )

        self.assertEqual(
            boundary_line.count(rl_088_ref),
            1,
            msg=(
                "expected RL-088/RL-089 source-of-truth-string-parity boundary-contract bullet to "
                "reference RL-088 canary exactly once"
            ),
        )
        self.assertEqual(
            boundary_line.count(rl_089_ref),
            1,
            msg=(
                "expected RL-088/RL-089 source-of-truth-string-parity boundary-contract bullet to "
                "reference RL-089 canary exactly once"
            ),
        )

    def test_rl_094_quality_gates_source_of_truth_string_parity_token_reference_note_singularity_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()
        expected_line = (
            "- Source-of-truth-string-parity boundary-contract token/reference canaries "
            "(RL-091/RL-092): keep the RL-088/RL-089 boundary-contract bullet with exactly one "
            "``latest.json`` + ``latest.md`` token pair and exactly one reference each to "
            "`test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary` "
            "and `test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary`, "
            "locked by `tests/test_release_snapshot.py` "
            "(`test_rl_091_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_token_literal_canary`, "
            "`test_rl_092_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_test_reference_pair_canary`)."
        )

        self.assertEqual(
            sum(1 for line in quality_gates_lines if line.strip() == expected_line),
            1,
            msg=(
                "expected exactly one source-of-truth-string-parity token/reference note canonical "
                "line in docs/quality-gates.md"
            ),
        )

    def test_rl_095_quality_gates_source_of_truth_string_parity_token_reference_note_line_boundary_canary(
        self,
    ) -> None:
        quality_gates_lines = (ROOT / "docs/quality-gates.md").read_text(encoding="utf-8").splitlines()

        standalone_matches = [
            line
            for line in quality_gates_lines
            if line.strip().startswith(
                "- Source-of-truth-string-parity boundary-contract token/reference canaries "
                "(RL-091/RL-092):"
            )
        ]
        self.assertEqual(
            len(standalone_matches),
            1,
            msg=(
                "expected exactly one standalone source-of-truth-string-parity token/reference note "
                "bullet line in docs/quality-gates.md"
            ),
        )

    def test_release_artifact_index_title_heading_presence(self) -> None:
        artifact_index = (ROOT / "docs/release-artifacts/README.md").read_text(encoding="utf-8")

        self.assertIn("# Release Artifacts Index", artifact_index)

    def test_release_artifact_index_title_heading_singularity(self) -> None:
        artifact_index = (ROOT / "docs/release-artifacts/README.md").read_text(encoding="utf-8")

        self.assertEqual(
            artifact_index.count("# Release Artifacts Index"),
            1,
            msg="expected exactly one title heading marker in docs/release-artifacts/README.md",
        )

    def test_release_artifact_index_title_first_non_empty_line_boundary(self) -> None:
        artifact_index_lines = (ROOT / "docs/release-artifacts/README.md").read_text(
            encoding="utf-8"
        ).splitlines()

        first_non_empty_line = next((line.strip() for line in artifact_index_lines if line.strip()), None)
        self.assertEqual(
            first_non_empty_line,
            "# Release Artifacts Index",
            msg="expected first non-empty line in docs/release-artifacts/README.md to be the title heading",
        )

    def test_release_artifact_index_quickstart_heading_order_boundary(self) -> None:
        artifact_index = (ROOT / "docs/release-artifacts/README.md").read_text(encoding="utf-8")

        title_position = artifact_index.find("# Release Artifacts Index")
        quickstart_position = artifact_index.find("## Quickstart pointer")

        self.assertNotEqual(
            title_position,
            -1,
            msg="expected title heading marker in docs/release-artifacts/README.md",
        )
        self.assertNotEqual(
            quickstart_position,
            -1,
            msg="expected quickstart heading marker in docs/release-artifacts/README.md",
        )
        self.assertGreater(
            quickstart_position,
            title_position,
            msg="expected quickstart heading marker to appear after title heading marker in docs/release-artifacts/README.md",
        )

    def test_release_artifact_index_retention_preconditions_anchor_marker_order_boundary(self) -> None:
        artifact_index = (ROOT / "docs/release-artifacts/README.md").read_text(encoding="utf-8")

        quickstart_position = artifact_index.find("## Quickstart pointer")
        retention_marker_position = artifact_index.find(
            "Preconditions checklist (execute in order before running commands):"
        )

        self.assertNotEqual(
            quickstart_position,
            -1,
            msg="expected quickstart heading marker in docs/release-artifacts/README.md",
        )
        self.assertNotEqual(
            retention_marker_position,
            -1,
            msg="expected retention checklist marker in docs/release-artifacts/README.md",
        )
        self.assertGreater(
            retention_marker_position,
            quickstart_position,
            msg="expected retention checklist marker to appear after quickstart heading marker in docs/release-artifacts/README.md",
        )

    def test_rl_037_release_artifact_index_heading_order_line_index_boundary_canary(self) -> None:
        artifact_index_lines = (ROOT / "docs/release-artifacts/README.md").read_text(
            encoding="utf-8"
        ).splitlines()

        title_line_index = next(
            (index for index, line in enumerate(artifact_index_lines) if line.strip() == "# Release Artifacts Index"),
            None,
        )
        quickstart_line_index = next(
            (index for index, line in enumerate(artifact_index_lines) if line.strip() == "## Quickstart pointer"),
            None,
        )

        self.assertIsNotNone(
            title_line_index,
            msg="expected title heading line in docs/release-artifacts/README.md",
        )
        self.assertIsNotNone(
            quickstart_line_index,
            msg="expected quickstart heading line in docs/release-artifacts/README.md",
        )
        assert title_line_index is not None
        assert quickstart_line_index is not None
        self.assertGreater(
            quickstart_line_index,
            title_line_index,
            msg="expected first quickstart heading line index to be greater than title heading line index in docs/release-artifacts/README.md",
        )

    def test_rl_038_release_artifact_index_retention_order_line_index_boundary_canary(self) -> None:
        artifact_index_lines = (ROOT / "docs/release-artifacts/README.md").read_text(
            encoding="utf-8"
        ).splitlines()

        quickstart_line_index = next(
            (index for index, line in enumerate(artifact_index_lines) if line.strip() == "## Quickstart pointer"),
            None,
        )
        retention_marker_line_index = next(
            (
                index
                for index, line in enumerate(artifact_index_lines)
                if line.strip() == "Preconditions checklist (execute in order before running commands):"
            ),
            None,
        )

        self.assertIsNotNone(
            quickstart_line_index,
            msg="expected quickstart heading line in docs/release-artifacts/README.md",
        )
        self.assertIsNotNone(
            retention_marker_line_index,
            msg="expected retention checklist marker line in docs/release-artifacts/README.md",
        )
        assert quickstart_line_index is not None
        assert retention_marker_line_index is not None
        self.assertGreater(
            retention_marker_line_index,
            quickstart_line_index,
            msg="expected first retention checklist marker line index to be greater than quickstart heading line index in docs/release-artifacts/README.md",
        )

    def test_release_artifact_index_retention_precondition_token_order(self) -> None:
        artifact_index = (ROOT / "docs/release-artifacts/README.md").read_text(encoding="utf-8")

        tokens_in_order = [
            "`repo-root`",
            "`latest.*`",
            "`matched pair`",
        ]

        cursor = 0
        for token in tokens_in_order:
            position = artifact_index.find(token, cursor)
            self.assertNotEqual(position, -1, msg=f"expected retention token {token} in artifact index")
            cursor = position + len(token)

    def test_repo_checked_in_source_of_truth_rule_parity_between_latest_json_and_latest_md(self) -> None:
        latest_json_path = ROOT / "docs/release-artifacts/latest.json"
        latest_md_path = ROOT / "docs/release-artifacts/latest.md"

        latest_payload = json.loads(latest_json_path.read_text(encoding="utf-8"))
        latest_md_lines = latest_md_path.read_text(encoding="utf-8").splitlines()

        self.assertIn("meta", latest_payload)
        self.assertIsInstance(latest_payload["meta"], dict)
        source_of_truth_rule = latest_payload["meta"].get("source_of_truth_rule")
        self.assertIsInstance(source_of_truth_rule, str)

        try:
            section_index = latest_md_lines.index("## Source-of-truth rule")
        except ValueError:
            self.fail("expected '## Source-of-truth rule' heading in checked-in latest.md")

        md_rule_line = None
        for line in latest_md_lines[section_index + 1 :]:
            if not line.strip():
                continue
            if line.startswith("## "):
                break
            md_rule_line = line
            break

        self.assertIsNotNone(md_rule_line, msg="expected source-of-truth bullet under heading")
        assert md_rule_line is not None
        self.assertTrue(md_rule_line.startswith("- "), msg="expected source-of-truth bullet line")
        self.assertEqual(md_rule_line[2:], source_of_truth_rule)

    def test_repo_checked_in_latest_json_contract_parity(self) -> None:
        artifact_path = ROOT / "docs/release-artifacts/latest.json"
        benchmark_path = ROOT / "bench/token-harness/results/latest.json"

        latest_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        benchmark_payload = json.loads(benchmark_path.read_text(encoding="utf-8"))

        self.assertIsInstance(latest_payload, dict)
        self.assertIsInstance(benchmark_payload, dict)

        self.assertIn("meta", latest_payload)
        self.assertIn("quality_gate_snapshot", latest_payload)
        self.assertIn("benchmark_summary", latest_payload)
        self.assertIn("summary", benchmark_payload)
        self.assertIn("pairs", benchmark_payload)

        meta = latest_payload["meta"]
        self.assertIsInstance(meta, dict)
        self.assertIsInstance(meta.get("snapshot_generated_at_utc"), str)
        self.assertIsInstance(meta.get("benchmark_generated_at_utc"), str)
        self.assertEqual(meta.get("benchmark_result_path"), "bench/token-harness/results/latest.json")
        self.assertEqual(meta.get("full_lane_entrypoint"), "./scripts/check.sh")
        self.assertIsInstance(meta.get("source_of_truth_rule"), str)
        self.assertIn("docs/release-artifacts/latest.json", meta["source_of_truth_rule"])

        benchmark_summary = latest_payload["benchmark_summary"]
        self.assertEqual(benchmark_summary, benchmark_payload["summary"])

        gate = latest_payload["quality_gate_snapshot"]
        self.assertIsInstance(gate, dict)

        summary = benchmark_payload["summary"]
        totals = summary["totals"]
        target = summary["target"]
        pairs = benchmark_payload["pairs"]

        self.assertEqual(gate["baseline_tokens"], totals["baseline_tokens"])
        self.assertEqual(gate["erz_tokens"], totals["erz_tokens"])
        self.assertEqual(gate["token_saving_pct"], totals["token_saving_pct"])
        self.assertEqual(gate["target_pct"], target["token_saving_pct"])
        self.assertEqual(gate["target_met"], target["met"])
        self.assertEqual(gate["pair_count"], summary["pair_count"])
        self.assertEqual(gate["pair_count"], len(pairs))
        self.assertEqual(gate["pair_floor_met"], gate["pair_count"] >= gate["pair_floor"])

        calibration_pair_count = sum(
            1
            for pair in pairs
            if isinstance(pair, dict)
            and isinstance(pair.get("name"), str)
            and pair["name"].startswith("calibration_")
        )
        self.assertEqual(gate["calibration_pair_count"], calibration_pair_count)
        self.assertEqual(
            gate["calibration_pair_floor_met"],
            gate["calibration_pair_count"] >= gate["calibration_pair_floor"],
        )

        self.assertIsInstance(benchmark_payload["meta"].get("generated_at_utc"), str)
        snapshot_generated_at = datetime.fromisoformat(meta["snapshot_generated_at_utc"])
        benchmark_generated_at = datetime.fromisoformat(meta["benchmark_generated_at_utc"])
        self.assertGreaterEqual(snapshot_generated_at, benchmark_generated_at)

    def test_fails_when_benchmark_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            completed = subprocess.run(
                ["python3", str(SCRIPT), "--repo-root", str(repo_root)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("release_snapshot: benchmark payload missing", completed.stderr)


if __name__ == "__main__":
    unittest.main()
