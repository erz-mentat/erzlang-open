from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVAL_FIXTURES = ROOT / "examples" / "eval"
LENGTH_PATH_PROGRAM = EVAL_FIXTURES / "program-length-paths.erz"
LENGTH_PATH_OK_EVENT = EVAL_FIXTURES / "event-length-paths-ok.json"
LENGTH_PATH_OK_ENVELOPE = EVAL_FIXTURES / "event-length-paths-ok.expected.envelope.json"
LENGTH_PATH_NO_ACTION_EVENT = EVAL_FIXTURES / "event-length-paths-no-action.json"
LENGTH_PATH_NO_ACTION_ENVELOPE = EVAL_FIXTURES / "event-length-paths-no-action.expected.envelope.json"
LENGTH_PATH_NO_ACTION_SUMMARY = EVAL_FIXTURES / "event-length-paths-no-action.expected.summary.txt"


class CliLengthPathExampleTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "cli.main", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_length_path_example_ok_envelope_matches_checked_in_fixture(self) -> None:
        result = self._run_cli("eval", str(LENGTH_PATH_PROGRAM), "--input", str(LENGTH_PATH_OK_EVENT))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, LENGTH_PATH_OK_ENVELOPE.read_text(encoding="utf-8"))

    def test_length_path_example_no_action_outputs_match_checked_in_fixtures(self) -> None:
        json_result = self._run_cli(
            "eval",
            str(LENGTH_PATH_PROGRAM),
            "--input",
            str(LENGTH_PATH_NO_ACTION_EVENT),
        )
        summary_result = self._run_cli(
            "eval",
            str(LENGTH_PATH_PROGRAM),
            "--input",
            str(LENGTH_PATH_NO_ACTION_EVENT),
            "--summary",
        )

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(json_result.stderr, "")
        self.assertEqual(
            json_result.stdout,
            LENGTH_PATH_NO_ACTION_ENVELOPE.read_text(encoding="utf-8"),
        )

        self.assertEqual(summary_result.returncode, 0)
        self.assertEqual(summary_result.stderr, "")
        self.assertEqual(
            summary_result.stdout,
            LENGTH_PATH_NO_ACTION_SUMMARY.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
