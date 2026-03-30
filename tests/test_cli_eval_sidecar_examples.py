from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVAL_FIXTURES = ROOT / "examples" / "eval"
SIDECAR_PROGRAM = EVAL_FIXTURES / "program-sidecar.erz"
SIDECAR_EVENT = EVAL_FIXTURES / "event-ok.json"
SIDECAR_REFS = EVAL_FIXTURES / "refs-sidecar.json"
SIDECAR_ENVELOPE = EVAL_FIXTURES / "event-sidecar.expected.envelope.json"
SIDECAR_SUMMARY = EVAL_FIXTURES / "event-sidecar.expected.summary.txt"
SIDECAR_HANDOFF_BUNDLE = EVAL_FIXTURES / "event-sidecar.expected.handoff-bundle.json"
BATCH_PROGRAM = EVAL_FIXTURES / "program.erz"
BATCH_DIR = EVAL_FIXTURES / "batch"
BATCH_ENVELOPE = EVAL_FIXTURES / "batch.expected.envelope.json"
BATCH_SUMMARY = EVAL_FIXTURES / "batch.expected.summary.txt"
BATCH_HANDOFF_BUNDLE = EVAL_FIXTURES / "batch.expected.handoff-bundle.json"


class CliEvalSidecarExampleTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "cli.main", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_single_eval_sidecar_example_matches_checked_in_handoff_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            summary_file = Path(tmp_dir) / "eval.summary.txt"
            json_file = Path(tmp_dir) / "eval.envelope.json"

            result = self._run_cli(
                "eval",
                str(SIDECAR_PROGRAM),
                "--input",
                str(SIDECAR_EVENT),
                "--refs",
                str(SIDECAR_REFS),
                "--summary",
                "--summary-file",
                str(summary_file),
                "--json-file",
                str(json_file),
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(result.stdout, SIDECAR_SUMMARY.read_text(encoding="utf-8"))
            self.assertEqual(summary_file.read_text(encoding="utf-8"), result.stdout)
            self.assertEqual(
                json_file.read_text(encoding="utf-8"),
                SIDECAR_ENVELOPE.read_text(encoding="utf-8"),
            )

    def test_single_eval_handoff_bundle_example_matches_checked_in_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle_file = Path(tmp_dir) / "eval.handoff-bundle.json"

            result = self._run_cli(
                "eval",
                str(SIDECAR_PROGRAM),
                "--input",
                str(SIDECAR_EVENT),
                "--refs",
                str(SIDECAR_REFS),
                "--handoff-bundle-file",
                str(bundle_file),
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(result.stdout, SIDECAR_ENVELOPE.read_text(encoding="utf-8"))
            self.assertEqual(
                bundle_file.read_text(encoding="utf-8"),
                SIDECAR_HANDOFF_BUNDLE.read_text(encoding="utf-8"),
            )

    def test_batch_eval_sidecar_example_matches_checked_in_handoff_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            summary_file = Path(tmp_dir) / "batch.summary.txt"
            json_file = Path(tmp_dir) / "batch.envelope.json"

            result = self._run_cli(
                "eval",
                str(BATCH_PROGRAM),
                "--batch",
                str(BATCH_DIR),
                "--summary-file",
                str(summary_file),
                "--json-file",
                str(json_file),
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(result.stdout, BATCH_ENVELOPE.read_text(encoding="utf-8"))
            self.assertEqual(json_file.read_text(encoding="utf-8"), result.stdout)
            self.assertEqual(
                summary_file.read_text(encoding="utf-8"),
                BATCH_SUMMARY.read_text(encoding="utf-8"),
            )

    def test_batch_eval_handoff_bundle_example_matches_checked_in_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle_file = Path(tmp_dir) / "batch.handoff-bundle.json"

            result = self._run_cli(
                "eval",
                str(BATCH_PROGRAM),
                "--batch",
                str(BATCH_DIR),
                "--handoff-bundle-file",
                str(bundle_file),
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(result.stdout, BATCH_ENVELOPE.read_text(encoding="utf-8"))
            self.assertEqual(
                bundle_file.read_text(encoding="utf-8"),
                BATCH_HANDOFF_BUNDLE.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
