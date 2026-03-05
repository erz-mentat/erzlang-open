from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime.eval import TRACE_OPTIONAL_FIELDS, TRACE_REQUIRED_FIELDS


REPO_ROOT = Path(__file__).resolve().parents[1]
GATES_DIR = REPO_ROOT / "scripts" / "gates"


class QualityGateScriptTests(unittest.TestCase):
    def _run_gate(self, script_name: str, *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GATES_DIR / script_name)],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )

    def _run_gate_from_non_root_cwd(
        self,
        script_name: str,
        *,
        root: Path,
    ) -> subprocess.CompletedProcess[str]:
        nested_cwd = root / "nested" / "cwd"
        nested_cwd.mkdir(parents=True, exist_ok=True)
        return self._run_gate(script_name, cwd=nested_cwd)

    def _write_json(self, root: Path, rel_path: str, payload: dict) -> None:
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")

    def _write_text(self, root: Path, rel_path: str, content: str) -> None:
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def _set_nested(self, mapping: dict, path: list[str], value: object) -> None:
        cursor = mapping
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value

    def _run_check_script_with_fake_python(
        self,
        *,
        failing_script: str,
        failing_message: str,
        entry_script: str = "check.sh",
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "fake-bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            fake_python = fake_bin / "python3"
            fake_python.write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "cli.main" ]]; then
  case "${{3:-}}" in
    validate)
      echo "valid"
      exit 0
      ;;
    parse)
      echo '{{"ast":"ok"}}'
      exit 0
      ;;
    fmt)
      cat "${{4:-}}"
      exit 0
      ;;
    *)
      echo "unexpected cli.main subcommand: ${{3:-}}" >&2
      exit 99
      ;;
  esac
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "unittest" ]]; then
  exit 0
fi
case "${{1:-}}" in
  scripts/validate_fewshot.py)
    echo "fewshot ok"
    exit 0
    ;;
  bench/token-harness/measure.py)
    echo "bench harness ok"
    exit 0
    ;;
  scripts/gates/benchmark_gate.py)
    echo "  token saving: 1000 -> 650 (35.00%)"
    if [[ "{failing_script}" == "scripts/gates/benchmark_gate.py" ]]; then
      echo "{failing_message}" >&2
      exit 1
    fi
    echo "  target >= 20.0%: met"
    echo "  fixture pairs: 10 (min 10)"
    echo "  calibration fixture pairs: 2 (min 2)"
    exit 0
    ;;
  scripts/gates/trace_contract_gate.py)
    if [[ "{failing_script}" == "scripts/gates/trace_contract_gate.py" ]]; then
      echo "{failing_message}" >&2
      exit 1
    fi
    echo "  ok: runtime trace fields are represented in schema"
    exit 0
    ;;
  scripts/gates/migration_anchor_gate.py)
    if [[ "{failing_script}" == "scripts/gates/migration_anchor_gate.py" ]]; then
      echo "{failing_message}" >&2
      exit 1
    fi
    echo "  ok: migration doc anchors match active trace fields and profile references"
    exit 0
    ;;
  *)
    echo "unexpected invocation: $*" >&2
    exit 99
    ;;
esac
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            return subprocess.run(
                ["bash", str(REPO_ROOT / "scripts" / entry_script)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

    def _run_check_script_with_fake_python_invocation_log(
        self,
        *,
        failing_script: str,
        failing_message: str,
        entry_script: str = "check.sh",
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "fake-bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            invocation_log = root / "python-invocations.log"

            fake_python = fake_bin / "python3"
            fake_python.write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
echo "${{1:-}}" >> "{invocation_log}"
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "cli.main" ]]; then
  case "${{3:-}}" in
    validate)
      echo "valid"
      exit 0
      ;;
    parse)
      echo '{{"ast":"ok"}}'
      exit 0
      ;;
    fmt)
      cat "${{4:-}}"
      exit 0
      ;;
    *)
      echo "unexpected cli.main subcommand: ${{3:-}}" >&2
      exit 99
      ;;
  esac
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "unittest" ]]; then
  exit 0
fi
case "${{1:-}}" in
  scripts/validate_fewshot.py)
    echo "fewshot ok"
    exit 0
    ;;
  bench/token-harness/measure.py)
    echo "bench harness ok"
    exit 0
    ;;
  scripts/gates/benchmark_gate.py)
    echo "  token saving: 1000 -> 650 (35.00%)"
    if [[ "{failing_script}" == "scripts/gates/benchmark_gate.py" ]]; then
      echo "{failing_message}" >&2
      exit 1
    fi
    echo "  target >= 20.0%: met"
    echo "  fixture pairs: 10 (min 10)"
    echo "  calibration fixture pairs: 2 (min 2)"
    exit 0
    ;;
  scripts/gates/trace_contract_gate.py)
    if [[ "{failing_script}" == "scripts/gates/trace_contract_gate.py" ]]; then
      echo "{failing_message}" >&2
      exit 1
    fi
    echo "  ok: runtime trace fields are represented in schema"
    exit 0
    ;;
  scripts/gates/migration_anchor_gate.py)
    if [[ "{failing_script}" == "scripts/gates/migration_anchor_gate.py" ]]; then
      echo "{failing_message}" >&2
      exit 1
    fi
    echo "  ok: migration doc anchors match active trace fields and profile references"
    exit 0
    ;;
  *)
    echo "unexpected invocation: $*" >&2
    exit 99
    ;;
esac
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            completed = subprocess.run(
                ["bash", str(REPO_ROOT / "scripts" / entry_script)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            invocations = []
            if invocation_log.exists():
                invocations = [line.strip() for line in invocation_log.read_text(encoding="utf-8").splitlines() if line.strip()]

            return completed, invocations

    def _run_check_unit_script_with_fake_python(
        self,
        *,
        unittest_exit_code: int,
        unittest_stderr: str = "",
        force_unexpected_unittest_invocation: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "fake-bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            invocation_log = root / "python-invocations.log"

            fake_python = fake_bin / "python3"
            fake_python.write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "{invocation_log}"
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "unittest" ]]; then
  if [[ "{'1' if force_unexpected_unittest_invocation else '0'}" == "1" ]]; then
    echo "unexpected invocation: $*" >&2
    exit 99
  fi
  if [[ "{unittest_exit_code}" != "0" ]]; then
    if [[ -n "{unittest_stderr}" ]]; then
      echo "{unittest_stderr}" >&2
    fi
    exit {unittest_exit_code}
  fi
  exit 0
fi
echo "unexpected invocation: $*" >&2
exit 99
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            completed = subprocess.run(
                ["bash", str(REPO_ROOT / "scripts" / "check-unit.sh")],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            invocations = []
            if invocation_log.exists():
                invocations = [line.strip() for line in invocation_log.read_text(encoding="utf-8").splitlines() if line.strip()]

            return completed, invocations

    def _valid_benchmark_payload(self) -> dict:
        return {
            "summary": {
                "totals": {
                    "baseline_tokens": 1000,
                    "erz_tokens": 650,
                    "token_saving_pct": 35.0,
                },
                "target": {"token_saving_pct": 20.0, "met": True},
                "pair_count": 10,
            },
            "pairs": [
                {"name": "calibration_alpha"},
                {"name": "calibration_beta"},
                {"name": "fixture_01"},
                {"name": "fixture_02"},
                {"name": "fixture_03"},
                {"name": "fixture_04"},
                {"name": "fixture_05"},
                {"name": "fixture_06"},
                {"name": "fixture_07"},
                {"name": "fixture_08"},
            ],
        }

    def _trace_schema_payload(self, *, required: list[str] | None = None) -> dict:
        required_fields = list(TRACE_REQUIRED_FIELDS if required is None else required)
        all_fields = list(TRACE_REQUIRED_FIELDS) + list(TRACE_OPTIONAL_FIELDS)
        properties = {name: {"type": "string"} for name in all_fields}
        return {
            "$defs": {
                "trace": {
                    "required": required_fields,
                    "properties": properties,
                }
            }
        }

    def _anchor_line(self, prefix: str, tokens: list[str]) -> str:
        return f"{prefix} " + ", ".join(f"`{token}`" for token in tokens)

    def _assert_full_lane_step_banner_sequence(self, stdout: str) -> None:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        expected_steps = [
            "[1/7] CLI smoke: fmt + parse + validate",
            "[2/7] Unit tests",
            "[3/7] Few-shot parser cases",
            "[4/7] Benchmark harness",
            "[5/7] Runtime/schema trace contract sync",
            "[6/7] Migration/compatibility discipline anchors",
            "[7/7] Quality gates complete",
        ]

        step_indexes: list[int] = []
        for step_line in expected_steps:
            matches = [idx for idx, line in enumerate(lines) if line == step_line]
            self.assertEqual(
                len(matches),
                1,
                msg=f"expected exactly one step banner line: {step_line}",
            )
            step_indexes.append(matches[0])

        self.assertEqual(step_indexes, sorted(step_indexes))

        footer = "All active quality gates passed."
        footer_matches = [idx for idx, line in enumerate(lines) if line == footer]
        self.assertEqual(len(footer_matches), 1)
        footer_index = footer_matches[0]
        self.assertGreater(footer_index, step_indexes[-1])
        self.assertEqual(
            footer_index,
            len(lines) - 1,
            msg="success footer must remain the terminal non-empty stdout line",
        )

    def _assert_step_banner_prefix_boundary(self, stdout: str, expected_prefix_steps: list[str]) -> None:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]

        step_indexes: list[int] = []
        for step_line in expected_prefix_steps:
            matches = [idx for idx, line in enumerate(lines) if line == step_line]
            self.assertEqual(
                len(matches),
                1,
                msg=f"expected exactly one step banner line before boundary: {step_line}",
            )
            step_indexes.append(matches[0])

        self.assertEqual(
            step_indexes,
            sorted(step_indexes),
            msg="expected boundary step banners to be strictly ordered",
        )

        all_steps = [
            "[1/7] CLI smoke: fmt + parse + validate",
            "[2/7] Unit tests",
            "[3/7] Few-shot parser cases",
            "[4/7] Benchmark harness",
            "[5/7] Runtime/schema trace contract sync",
            "[6/7] Migration/compatibility discipline anchors",
            "[7/7] Quality gates complete",
        ]
        allowed_steps = set(expected_prefix_steps)
        disallowed_steps = [step for step in all_steps if step not in allowed_steps]
        for step_line in disallowed_steps:
            self.assertNotIn(
                step_line,
                lines,
                msg=f"unexpected step banner beyond boundary: {step_line}",
            )

    def _assert_terminal_step_banner(self, stdout: str, terminal_step: str) -> None:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        all_steps = [
            "[1/7] CLI smoke: fmt + parse + validate",
            "[2/7] Unit tests",
            "[3/7] Few-shot parser cases",
            "[4/7] Benchmark harness",
            "[5/7] Runtime/schema trace contract sync",
            "[6/7] Migration/compatibility discipline anchors",
            "[7/7] Quality gates complete",
        ]
        emitted_steps = [line for line in lines if line in all_steps]
        self.assertGreater(len(emitted_steps), 0, msg="expected at least one emitted step banner")
        self.assertEqual(
            emitted_steps.count(terminal_step),
            1,
            msg=f"expected terminal step banner exactly once: {terminal_step}",
        )
        self.assertEqual(
            emitted_steps[-1],
            terminal_step,
            msg=f"expected terminal step banner at boundary: {terminal_step}",
        )

    def _assert_success_terminal_step_boundary(self, stdout: str) -> None:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        terminal_step = "[7/7] Quality gates complete"
        footer = "All active quality gates passed."

        terminal_matches = [idx for idx, line in enumerate(lines) if line == terminal_step]
        self.assertEqual(
            len(terminal_matches),
            1,
            msg=f"expected terminal step banner exactly once: {terminal_step}",
        )

        footer_matches = [idx for idx, line in enumerate(lines) if line == footer]
        self.assertEqual(len(footer_matches), 1)
        self.assertLess(
            terminal_matches[0],
            footer_matches[0],
            msg="expected terminal step banner to precede success footer",
        )

        self._assert_terminal_step_banner(stdout, terminal_step)

    def _assert_success_footer_terminal_line(self, stdout: str) -> None:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        terminal_step = "[7/7] Quality gates complete"
        footer = "All active quality gates passed."

        footer_matches = [idx for idx, line in enumerate(lines) if line == footer]
        self.assertEqual(
            len(footer_matches),
            1,
            msg="expected success footer exactly once",
        )
        footer_index = footer_matches[0]
        self.assertEqual(
            footer_index,
            len(lines) - 1,
            msg="expected success footer to remain the terminal non-empty stdout line",
        )
        self.assertGreater(footer_index, 0)
        self.assertEqual(
            lines[footer_index - 1],
            terminal_step,
            msg="expected success footer to follow the [7/7] terminal step banner",
        )

    def _assert_success_footer_exact_text_contract(self, stdout: str) -> None:
        footer = "All active quality gates passed."
        raw_lines = stdout.splitlines()

        exact_matches = [idx for idx, line in enumerate(raw_lines) if line == footer]
        self.assertEqual(
            len(exact_matches),
            1,
            msg="expected success footer literal to appear exactly once",
        )

        trimmed_but_non_exact = [line for line in raw_lines if line.strip() == footer and line != footer]
        self.assertEqual(
            trimmed_but_non_exact,
            [],
            msg="expected success footer to remain byte-identical without surrounding whitespace",
        )

        non_empty_lines = [line for line in raw_lines if line.strip()]
        self.assertGreater(len(non_empty_lines), 0)
        self.assertEqual(
            non_empty_lines[-1],
            footer,
            msg="expected exact success footer literal to remain the terminal non-empty stdout line",
        )

    def _assert_terminal_step_exact_text_contract(self, stdout: str) -> None:
        terminal_step = "[7/7] Quality gates complete"
        raw_lines = stdout.splitlines()

        exact_matches = [idx for idx, line in enumerate(raw_lines) if line == terminal_step]
        self.assertEqual(
            len(exact_matches),
            1,
            msg="expected terminal step literal to appear exactly once",
        )

        trimmed_but_non_exact = [line for line in raw_lines if line.strip() == terminal_step and line != terminal_step]
        self.assertEqual(
            trimmed_but_non_exact,
            [],
            msg="expected terminal step to remain byte-identical without surrounding whitespace",
        )

        self._assert_success_terminal_step_boundary(stdout)

    def _assert_boundary_step_exact_text_contract(self, stdout: str, boundary_step: str) -> None:
        raw_lines = stdout.splitlines()

        exact_matches = [idx for idx, line in enumerate(raw_lines) if line == boundary_step]
        self.assertEqual(
            len(exact_matches),
            1,
            msg=f"expected boundary step literal to appear exactly once: {boundary_step}",
        )

        trimmed_but_non_exact = [line for line in raw_lines if line.strip() == boundary_step and line != boundary_step]
        self.assertEqual(
            trimmed_but_non_exact,
            [],
            msg=f"expected boundary step to remain byte-identical without surrounding whitespace: {boundary_step}",
        )

        self._assert_terminal_step_banner(stdout, boundary_step)

    def _assert_step_banner_exact_text_contract(self, stdout: str, step_banner: str) -> None:
        raw_lines = stdout.splitlines()

        exact_matches = [idx for idx, line in enumerate(raw_lines) if line == step_banner]
        self.assertEqual(
            len(exact_matches),
            1,
            msg=f"expected step banner literal to appear exactly once: {step_banner}",
        )

        trimmed_but_non_exact = [line for line in raw_lines if line.strip() == step_banner and line != step_banner]
        self.assertEqual(
            trimmed_but_non_exact,
            [],
            msg=f"expected step banner to remain byte-identical without surrounding whitespace: {step_banner}",
        )

    def test_benchmark_gate_passes_with_valid_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(
                root,
                "bench/token-harness/results/latest.json",
                self._valid_benchmark_payload(),
            )

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("target >= 20.0%: met", completed.stdout)
            self.assertIn("fixture pairs: 10 (min 10)", completed.stdout)
            self.assertIn("calibration fixture pairs: 2 (min 2)", completed.stdout)

    def test_benchmark_gate_counts_only_exact_lowercase_calibration_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["pairs"][1]["name"] = "Calibration_beta"
            payload["pairs"][2]["name"] = "calibration_gamma"
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("calibration fixture pairs: 2 (min 2)", completed.stdout)

    def test_benchmark_gate_fails_when_calibration_prefix_case_does_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["pairs"][0]["name"] = "Calibration_alpha"
            payload["pairs"][1]["name"] = "CALIBRATION_beta"
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("calibration fixture pairs: 0 (min 2)", completed.stdout)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn("Calibration fixture floor not met: expected at least 2 pairs", completed.stderr)

    def test_benchmark_gate_fails_when_result_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn("Benchmark result file missing:", completed.stderr)

    def test_benchmark_gate_fails_with_invalid_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_text(
                root,
                "bench/token-harness/results/latest.json",
                "{invalid json",
            )

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn("Benchmark result file is not valid JSON:", completed.stderr)

    def test_benchmark_gate_fails_when_root_payload_is_not_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_text(
                root,
                "bench/token-harness/results/latest.json",
                '["not-an-object"]',
            )

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark summary: expected object at `root`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_when_target_not_met(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["summary"]["target"]["met"] = False
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn("Benchmark token-saving target not met", completed.stderr)

    def test_benchmark_gate_threshold_failure_preserves_stdout_metrics_and_stderr_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["summary"]["target"]["met"] = False
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("token saving:", completed.stdout)
            self.assertIn("target >= 20.0%: not met", completed.stdout)
            self.assertIn("fixture pairs: 10 (min 10)", completed.stdout)
            self.assertIn("calibration fixture pairs: 2 (min 2)", completed.stdout)
            self.assertIn(
                "gate failure [benchmark_gate]: Benchmark token-saving target not met",
                completed.stderr,
            )
            self.assertNotIn("token saving:", completed.stderr)

    def test_benchmark_gate_fails_with_missing_summary_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            del payload["summary"]["totals"]["token_saving_pct"]
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark summary: missing key `summary.totals.token_saving_pct`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_when_summary_root_is_not_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["summary"] = ["not-an-object"]
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark summary: expected object at `summary`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_with_non_object_summary_subpaths(self) -> None:
        cases = [
            (["summary", "totals"], [], "summary.totals"),
            (["summary", "target"], [], "summary.target"),
        ]

        for nested_path, malformed_value, field_path in cases:
            with self.subTest(field_path=field_path):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    payload = self._valid_benchmark_payload()
                    self._set_nested(payload, nested_path, malformed_value)
                    self._write_json(root, "bench/token-harness/results/latest.json", payload)

                    completed = self._run_gate("benchmark_gate.py", cwd=root)

                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
                    self.assertIn(
                        f"Malformed benchmark summary: expected object at `{field_path}`",
                        completed.stderr,
                    )

    def test_benchmark_gate_fails_with_non_boolean_target_met(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["summary"]["target"]["met"] = "yes"
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark summary: expected boolean at `summary.target.met`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_with_non_list_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["pairs"] = {"name": "not-a-list"}
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn("Malformed benchmark payload: expected list at `pairs`", completed.stderr)

    def test_benchmark_gate_fails_when_pairs_key_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            del payload["pairs"]
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark payload: missing key `root.pairs`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_with_non_object_pair_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["pairs"][0] = "not-an-object"
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn("Malformed benchmark payload: expected object at `pairs[0]`", completed.stderr)

    def test_benchmark_gate_fails_when_pair_row_name_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            del payload["pairs"][0]["name"]
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark payload: missing key `pairs[0].name`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_when_pair_row_name_is_not_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["pairs"][0]["name"] = 123
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark payload: expected string at `pairs[0].name`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_with_non_integer_pair_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["summary"]["pair_count"] = 10.5
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark summary: expected integer at `summary.pair_count`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_when_pair_count_mismatches_pairs_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._valid_benchmark_payload()
            payload["summary"]["pair_count"] = 9
            self._write_json(root, "bench/token-harness/results/latest.json", payload)

            completed = self._run_gate("benchmark_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
            self.assertIn(
                "Malformed benchmark summary: `summary.pair_count` does not match `len(pairs)`",
                completed.stderr,
            )

    def test_benchmark_gate_fails_when_numeric_fields_are_boolean(self) -> None:
        cases = [
            (["summary", "totals", "baseline_tokens"], "summary.totals.baseline_tokens"),
            (["summary", "totals", "erz_tokens"], "summary.totals.erz_tokens"),
            (["summary", "totals", "token_saving_pct"], "summary.totals.token_saving_pct"),
            (["summary", "target", "token_saving_pct"], "summary.target.token_saving_pct"),
        ]

        for nested_path, field_path in cases:
            with self.subTest(field_path=field_path):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    payload = self._valid_benchmark_payload()
                    self._set_nested(payload, nested_path, True)
                    self._write_json(root, "bench/token-harness/results/latest.json", payload)

                    completed = self._run_gate("benchmark_gate.py", cwd=root)

                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("gate failure [benchmark_gate]:", completed.stderr)
                    self.assertIn(
                        f"Malformed benchmark summary: expected number at `{field_path}`",
                        completed.stderr,
                    )

    def test_gate_helpers_fail_with_repo_root_assumption_when_run_from_non_root_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(
                root,
                "bench/token-harness/results/latest.json",
                self._valid_benchmark_payload(),
            )
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )
            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            cases = [
                (
                    "benchmark_gate.py",
                    "gate failure [benchmark_gate]:",
                    "Benchmark result file missing: bench/token-harness/results/latest.json",
                ),
                (
                    "trace_contract_gate.py",
                    "gate failure [trace_contract_gate]:",
                    "Schema file missing: schema/ir.v0.1.schema.json",
                ),
                (
                    "migration_anchor_gate.py",
                    "gate failure [migration_anchor_gate]:",
                    "Schema file missing: schema/ir.v0.1.schema.json",
                ),
            ]

            for script_name, prefix, detail in cases:
                with self.subTest(script=script_name):
                    completed = self._run_gate_from_non_root_cwd(script_name, root=root)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn(prefix, completed.stderr)
                    self.assertIn(detail, completed.stderr)

    def test_check_script_surfaces_helper_stderr_unmodified(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/benchmark_gate.py",
            failing_message="gate failure [benchmark_gate]: canary helper stderr passthrough",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[4/7] Benchmark harness", completed.stdout)
        self.assertIn("token saving: 1000 -> 650 (35.00%)", completed.stdout)
        self.assertIn(
            "gate failure [benchmark_gate]: canary helper stderr passthrough",
            completed.stderr,
        )

    def test_check_script_surfaces_non_benchmark_helper_stderr_unmodified(self) -> None:
        cases = [
            (
                "scripts/gates/trace_contract_gate.py",
                "gate failure [trace_contract_gate]: canary helper stderr passthrough",
                "[5/7] Runtime/schema trace contract sync",
            ),
            (
                "scripts/gates/migration_anchor_gate.py",
                "gate failure [migration_anchor_gate]: canary helper stderr passthrough",
                "[6/7] Migration/compatibility discipline anchors",
            ),
        ]

        for failing_script, failing_message, expected_step in cases:
            with self.subTest(script=failing_script):
                completed = self._run_check_script_with_fake_python(
                    failing_script=failing_script,
                    failing_message=failing_message,
                )

                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(expected_step, completed.stdout)
                self.assertIn(failing_message, completed.stderr)

    def test_check_script_short_circuits_after_first_failing_helper(self) -> None:
        failing_message = "gate failure [benchmark_gate]: canary helper short-circuit"
        completed, invocations = self._run_check_script_with_fake_python_invocation_log(
            failing_script="scripts/gates/benchmark_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("bench/token-harness/measure.py", invocations)
        self.assertIn("scripts/gates/benchmark_gate.py", invocations)
        self.assertNotIn("scripts/gates/trace_contract_gate.py", invocations)
        self.assertNotIn("scripts/gates/migration_anchor_gate.py", invocations)
        self.assertNotIn("[5/7] Runtime/schema trace contract sync", completed.stdout)
        self.assertNotIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)

        self._assert_step_banner_prefix_boundary(
            completed.stdout,
            [
                "[1/7] CLI smoke: fmt + parse + validate",
                "[2/7] Unit tests",
                "[3/7] Few-shot parser cases",
                "[4/7] Benchmark harness",
            ],
        )
        self._assert_terminal_step_banner(
            completed.stdout,
            "[4/7] Benchmark harness",
        )

        measure_index = invocations.index("bench/token-harness/measure.py")
        benchmark_gate_index = invocations.index("scripts/gates/benchmark_gate.py")
        self.assertLess(measure_index, benchmark_gate_index)

    def test_check_script_short_circuits_after_trace_helper_failure(self) -> None:
        failing_message = "gate failure [trace_contract_gate]: canary helper short-circuit"
        completed, invocations = self._run_check_script_with_fake_python_invocation_log(
            failing_script="scripts/gates/trace_contract_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("scripts/gates/benchmark_gate.py", invocations)
        self.assertIn("scripts/gates/trace_contract_gate.py", invocations)
        self.assertNotIn("scripts/gates/migration_anchor_gate.py", invocations)
        self.assertIn("[5/7] Runtime/schema trace contract sync", completed.stdout)
        self.assertNotIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)

        self._assert_step_banner_prefix_boundary(
            completed.stdout,
            [
                "[1/7] CLI smoke: fmt + parse + validate",
                "[2/7] Unit tests",
                "[3/7] Few-shot parser cases",
                "[4/7] Benchmark harness",
                "[5/7] Runtime/schema trace contract sync",
            ],
        )
        self._assert_terminal_step_banner(
            completed.stdout,
            "[5/7] Runtime/schema trace contract sync",
        )

        benchmark_gate_index = invocations.index("scripts/gates/benchmark_gate.py")
        trace_gate_index = invocations.index("scripts/gates/trace_contract_gate.py")
        self.assertLess(benchmark_gate_index, trace_gate_index)

    def test_check_script_suppresses_terminal_step_after_migration_helper_failure(self) -> None:
        failing_message = "gate failure [migration_anchor_gate]: canary terminal-step suppression"
        completed, invocations = self._run_check_script_with_fake_python_invocation_log(
            failing_script="scripts/gates/migration_anchor_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("scripts/gates/benchmark_gate.py", invocations)
        self.assertIn("scripts/gates/trace_contract_gate.py", invocations)
        self.assertIn("scripts/gates/migration_anchor_gate.py", invocations)
        self.assertIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)

        self._assert_step_banner_prefix_boundary(
            completed.stdout,
            [
                "[1/7] CLI smoke: fmt + parse + validate",
                "[2/7] Unit tests",
                "[3/7] Few-shot parser cases",
                "[4/7] Benchmark harness",
                "[5/7] Runtime/schema trace contract sync",
                "[6/7] Migration/compatibility discipline anchors",
            ],
        )

        benchmark_gate_index = invocations.index("scripts/gates/benchmark_gate.py")
        trace_gate_index = invocations.index("scripts/gates/trace_contract_gate.py")
        migration_gate_index = invocations.index("scripts/gates/migration_anchor_gate.py")
        self.assertLess(benchmark_gate_index, trace_gate_index)
        self.assertLess(trace_gate_index, migration_gate_index)

    def test_check_script_reaches_terminal_step_when_all_helpers_pass(self) -> None:
        completed, invocations = self._run_check_script_with_fake_python_invocation_log(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self.assertIn("[7/7] Quality gates complete", completed.stdout)
        self.assertIn("All active quality gates passed.", completed.stdout)
        self._assert_success_terminal_step_boundary(completed.stdout)
        self._assert_success_footer_terminal_line(completed.stdout)
        self._assert_full_lane_step_banner_sequence(completed.stdout)

        expected_order = [
            "bench/token-harness/measure.py",
            "scripts/gates/benchmark_gate.py",
            "scripts/gates/trace_contract_gate.py",
            "scripts/gates/migration_anchor_gate.py",
        ]
        for script_name in expected_order:
            self.assertEqual(invocations.count(script_name), 1)

        measure_index = invocations.index("bench/token-harness/measure.py")
        benchmark_index = invocations.index("scripts/gates/benchmark_gate.py")
        trace_index = invocations.index("scripts/gates/trace_contract_gate.py")
        migration_index = invocations.index("scripts/gates/migration_anchor_gate.py")
        self.assertLess(measure_index, benchmark_index)
        self.assertLess(benchmark_index, trace_index)
        self.assertLess(trace_index, migration_index)

    def test_check_full_wrapper_matches_check_script_contract(self) -> None:
        completed, invocations = self._run_check_script_with_fake_python_invocation_log(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("[1/7] CLI smoke: fmt + parse + validate", completed.stdout)
        self.assertIn("[7/7] Quality gates complete", completed.stdout)
        self.assertIn("All active quality gates passed.", completed.stdout)
        self._assert_success_terminal_step_boundary(completed.stdout)
        self._assert_success_footer_terminal_line(completed.stdout)
        self._assert_full_lane_step_banner_sequence(completed.stdout)

        expected_order = [
            "bench/token-harness/measure.py",
            "scripts/gates/benchmark_gate.py",
            "scripts/gates/trace_contract_gate.py",
            "scripts/gates/migration_anchor_gate.py",
        ]
        for script_name in expected_order:
            self.assertEqual(invocations.count(script_name), 1)

        measure_index = invocations.index("bench/token-harness/measure.py")
        benchmark_index = invocations.index("scripts/gates/benchmark_gate.py")
        trace_index = invocations.index("scripts/gates/trace_contract_gate.py")
        migration_index = invocations.index("scripts/gates/migration_anchor_gate.py")
        self.assertLess(measure_index, benchmark_index)
        self.assertLess(benchmark_index, trace_index)
        self.assertLess(trace_index, migration_index)

    def test_check_full_wrapper_success_footer_is_single_terminal_stdout_line(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_success_footer_terminal_line(completed.stdout)

    def test_check_script_success_footer_is_single_terminal_stdout_line(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_success_footer_terminal_line(completed.stdout)

    def test_check_full_wrapper_success_footer_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_success_footer_exact_text_contract(completed.stdout)

    def test_check_script_success_footer_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_success_footer_exact_text_contract(completed.stdout)

    def test_check_full_wrapper_terminal_step_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_terminal_step_exact_text_contract(completed.stdout)

    def test_check_script_terminal_step_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_terminal_step_exact_text_contract(completed.stdout)

    def test_check_full_wrapper_step1_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[1/7] CLI smoke: fmt + parse + validate")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_script_step1_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[1/7] CLI smoke: fmt + parse + validate")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_full_wrapper_step2_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[2/7] Unit tests")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_script_step2_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[2/7] Unit tests")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_full_wrapper_step3_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[3/7] Few-shot parser cases")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_script_step3_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[3/7] Few-shot parser cases")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_full_wrapper_step4_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[4/7] Benchmark harness")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_script_step4_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[4/7] Benchmark harness")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_full_wrapper_step5_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[5/7] Runtime/schema trace contract sync")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_script_step5_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[5/7] Runtime/schema trace contract sync")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_full_wrapper_step6_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
            entry_script="check-full.sh",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[6/7] Migration/compatibility discipline anchors")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_script_step6_banner_exact_text_contract(self) -> None:
        completed = self._run_check_script_with_fake_python(
            failing_script="__none__",
            failing_message="unused",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr.strip(), "")
        self._assert_step_banner_exact_text_contract(completed.stdout, "[6/7] Migration/compatibility discipline anchors")
        self._assert_full_lane_step_banner_sequence(completed.stdout)

    def test_check_full_wrapper_benchmark_boundary_step_exact_text_contract(self) -> None:
        failing_message = "gate failure [benchmark_gate]: wrapper benchmark boundary exact-text canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/benchmark_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self._assert_boundary_step_exact_text_contract(completed.stdout, "[4/7] Benchmark harness")

    def test_check_script_benchmark_boundary_step_exact_text_contract(self) -> None:
        failing_message = "gate failure [benchmark_gate]: canonical benchmark boundary exact-text canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/benchmark_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self._assert_boundary_step_exact_text_contract(completed.stdout, "[4/7] Benchmark harness")

    def test_check_full_wrapper_trace_boundary_step_exact_text_contract(self) -> None:
        failing_message = "gate failure [trace_contract_gate]: wrapper trace boundary exact-text canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/trace_contract_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self._assert_boundary_step_exact_text_contract(completed.stdout, "[5/7] Runtime/schema trace contract sync")

    def test_check_script_trace_boundary_step_exact_text_contract(self) -> None:
        failing_message = "gate failure [trace_contract_gate]: canonical trace boundary exact-text canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/trace_contract_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self._assert_boundary_step_exact_text_contract(completed.stdout, "[5/7] Runtime/schema trace contract sync")

    def test_check_full_wrapper_migration_boundary_step_exact_text_contract(self) -> None:
        failing_message = "gate failure [migration_anchor_gate]: wrapper migration boundary exact-text canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/migration_anchor_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self._assert_boundary_step_exact_text_contract(
            completed.stdout,
            "[6/7] Migration/compatibility discipline anchors",
        )

    def test_check_script_migration_boundary_step_exact_text_contract(self) -> None:
        failing_message = "gate failure [migration_anchor_gate]: canonical migration boundary exact-text canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/migration_anchor_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self._assert_boundary_step_exact_text_contract(
            completed.stdout,
            "[6/7] Migration/compatibility discipline anchors",
        )

    def test_check_full_wrapper_short_circuits_after_benchmark_helper_failure(self) -> None:
        failing_message = "gate failure [benchmark_gate]: wrapper short-circuit canary"
        completed, invocations = self._run_check_script_with_fake_python_invocation_log(
            failing_script="scripts/gates/benchmark_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("[4/7] Benchmark harness", completed.stdout)
        self.assertNotIn("[5/7] Runtime/schema trace contract sync", completed.stdout)
        self.assertNotIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)

        self._assert_step_banner_prefix_boundary(
            completed.stdout,
            [
                "[1/7] CLI smoke: fmt + parse + validate",
                "[2/7] Unit tests",
                "[3/7] Few-shot parser cases",
                "[4/7] Benchmark harness",
            ],
        )
        self._assert_terminal_step_banner(
            completed.stdout,
            "[4/7] Benchmark harness",
        )

        self.assertIn("bench/token-harness/measure.py", invocations)
        self.assertIn("scripts/gates/benchmark_gate.py", invocations)
        self.assertNotIn("scripts/gates/trace_contract_gate.py", invocations)
        self.assertNotIn("scripts/gates/migration_anchor_gate.py", invocations)

        measure_index = invocations.index("bench/token-harness/measure.py")
        benchmark_gate_index = invocations.index("scripts/gates/benchmark_gate.py")
        self.assertLess(measure_index, benchmark_gate_index)

    def test_check_full_wrapper_short_circuits_after_trace_helper_failure(self) -> None:
        failing_message = "gate failure [trace_contract_gate]: wrapper short-circuit canary"
        completed, invocations = self._run_check_script_with_fake_python_invocation_log(
            failing_script="scripts/gates/trace_contract_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("[5/7] Runtime/schema trace contract sync", completed.stdout)
        self.assertNotIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)

        self._assert_step_banner_prefix_boundary(
            completed.stdout,
            [
                "[1/7] CLI smoke: fmt + parse + validate",
                "[2/7] Unit tests",
                "[3/7] Few-shot parser cases",
                "[4/7] Benchmark harness",
                "[5/7] Runtime/schema trace contract sync",
            ],
        )
        self._assert_terminal_step_banner(
            completed.stdout,
            "[5/7] Runtime/schema trace contract sync",
        )

        self.assertIn("bench/token-harness/measure.py", invocations)
        self.assertIn("scripts/gates/benchmark_gate.py", invocations)
        self.assertIn("scripts/gates/trace_contract_gate.py", invocations)
        self.assertNotIn("scripts/gates/migration_anchor_gate.py", invocations)

        benchmark_gate_index = invocations.index("scripts/gates/benchmark_gate.py")
        trace_gate_index = invocations.index("scripts/gates/trace_contract_gate.py")
        self.assertLess(benchmark_gate_index, trace_gate_index)

    def test_check_full_wrapper_suppresses_terminal_step_after_migration_helper_failure(self) -> None:
        failing_message = "gate failure [migration_anchor_gate]: wrapper terminal-step suppression"
        completed, invocations = self._run_check_script_with_fake_python_invocation_log(
            failing_script="scripts/gates/migration_anchor_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)

        self._assert_step_banner_prefix_boundary(
            completed.stdout,
            [
                "[1/7] CLI smoke: fmt + parse + validate",
                "[2/7] Unit tests",
                "[3/7] Few-shot parser cases",
                "[4/7] Benchmark harness",
                "[5/7] Runtime/schema trace contract sync",
                "[6/7] Migration/compatibility discipline anchors",
            ],
        )
        self._assert_terminal_step_banner(
            completed.stdout,
            "[6/7] Migration/compatibility discipline anchors",
        )

        self.assertIn("bench/token-harness/measure.py", invocations)
        self.assertIn("scripts/gates/benchmark_gate.py", invocations)
        self.assertIn("scripts/gates/trace_contract_gate.py", invocations)
        self.assertIn("scripts/gates/migration_anchor_gate.py", invocations)

        benchmark_gate_index = invocations.index("scripts/gates/benchmark_gate.py")
        trace_gate_index = invocations.index("scripts/gates/trace_contract_gate.py")
        migration_gate_index = invocations.index("scripts/gates/migration_anchor_gate.py")
        self.assertLess(benchmark_gate_index, trace_gate_index)
        self.assertLess(trace_gate_index, migration_gate_index)

    def test_check_unit_wrapper_runs_unittest_and_emits_pass_banner(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("[unit] Running unittest suite", completed.stdout)
        self.assertIn("[unit] Passed", completed.stdout)
        self.assertIn("-m unittest discover -s tests -v", invocations)
        self.assertNotIn("bench/token-harness/measure.py", invocations)

    def test_check_unit_wrapper_success_path_invokes_unittest_once_with_no_extra_python_entrypoints(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(
            invocations,
            ["-m unittest discover -s tests -v"],
            msg="expected check-unit success path to invoke only unittest exactly once",
        )

    def test_check_unit_wrapper_propagates_unittest_failure_without_pass_banner(self) -> None:
        failing_message = "unit canary failure"
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[unit] Running unittest suite", completed.stdout)
        self.assertNotIn("[unit] Passed", completed.stdout)
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_failure_path_invokes_unittest_once_with_no_extra_python_entrypoints(self) -> None:
        failing_message = "unit canary failure invocation-count parity"
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(failing_message, completed.stderr)
        self.assertEqual(
            invocations,
            ["-m unittest discover -s tests -v"],
            msg="expected check-unit failure path to invoke only unittest exactly once",
        )

    def test_check_unit_wrapper_unexpected_invocation_path_attempts_unittest_once_with_no_retry(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unexpected invocation: -m unittest discover -s tests -v", completed.stderr)
        self.assertEqual(
            invocations,
            ["-m unittest discover -s tests -v"],
            msg="expected unexpected-invocation failure mode to attempt unittest exactly once",
        )

    def test_check_unit_wrapper_preserves_unittest_argv_vector_parity_between_success_and_failure_paths(self) -> None:
        success_completed, success_invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary argv-vector parity"
        failure_completed, failure_invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        expected_invocation_vector = ["-m unittest discover -s tests -v"]

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertIn(failing_message, failure_completed.stderr)
        self.assertEqual(success_invocations, expected_invocation_vector)
        self.assertEqual(failure_invocations, expected_invocation_vector)
        self.assertEqual(
            success_invocations,
            failure_invocations,
            msg="expected byte-identical unittest argv vector parity across pass/fail paths",
        )

    def test_check_unit_wrapper_preserves_unittest_argv_vector_tri_parity_across_success_failure_and_unexpected_invocation_paths(self) -> None:
        success_completed, success_invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary argv-vector tri-parity"
        failure_completed, failure_invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, unexpected_invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        expected_invocation_vector = ["-m unittest discover -s tests -v"]

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertIn(failing_message, failure_completed.stderr)
        self.assertNotEqual(unexpected_completed.returncode, 0)
        self.assertIn("unexpected invocation: -m unittest discover -s tests -v", unexpected_completed.stderr)

        self.assertEqual(success_invocations, expected_invocation_vector)
        self.assertEqual(failure_invocations, expected_invocation_vector)
        self.assertEqual(unexpected_invocations, expected_invocation_vector)
        self.assertEqual(
            success_invocations,
            failure_invocations,
            msg="expected byte-identical unittest argv vector parity across pass/fail/unexpected-invocation paths",
        )
        self.assertEqual(
            failure_invocations,
            unexpected_invocations,
            msg="expected byte-identical unittest argv vector parity across fail/unexpected-invocation paths",
        )

    def test_check_unit_wrapper_invocation_log_cardinality_tri_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, success_invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary invocation-log cardinality tri-parity"
        failure_completed, failure_invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, unexpected_invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        expected_invocation_line = "-m unittest discover -s tests -v"

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertIn(failing_message, failure_completed.stderr)
        self.assertNotEqual(unexpected_completed.returncode, 0)
        self.assertIn(f"unexpected invocation: {expected_invocation_line}", unexpected_completed.stderr)

        for mode, invocations in (
            ("pass", success_invocations),
            ("fail", failure_invocations),
            ("unexpected", unexpected_invocations),
        ):
            with self.subTest(mode=mode):
                self.assertEqual(
                    invocations,
                    [expected_invocation_line],
                    msg=f"expected {mode} mode to emit exactly one invocation-log line for canonical unittest argv",
                )

    def test_check_unit_wrapper_unexpected_invocation_log_preserves_canonical_unittest_argv_token_order(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        expected_tokens = ["-m", "unittest", "discover", "-s", "tests", "-v"]
        expected_invocation_line = " ".join(expected_tokens)

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(
            completed.stderr,
            f"unexpected invocation: {expected_invocation_line}\n",
        )
        self.assertEqual(invocations, [expected_invocation_line])

        observed_tokens = invocations[0].split(" ")
        self.assertEqual(len(observed_tokens), len(expected_tokens))
        for idx, (observed_token, expected_token) in enumerate(zip(observed_tokens, expected_tokens)):
            with self.subTest(token_index=idx):
                self.assertEqual(
                    observed_token,
                    expected_token,
                    msg="expected unexpected-invocation log token ordering to preserve canonical unittest argv order",
                )

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_suffix_matches_invocation_log_terminal_line(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertGreater(len(invocations), 0)

        diagnostic_prefix = "unexpected invocation: "
        self.assertTrue(completed.stderr.startswith(diagnostic_prefix))

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        self.assertEqual(
            diagnostic_suffix,
            invocations[-1],
            msg="expected unexpected-invocation diagnostic suffix to stay byte-identical to invocation-log terminal line",
        )

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_token_count_parity_with_invocation_log(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(len(invocations), 1)

        diagnostic_prefix = "unexpected invocation: "
        self.assertTrue(completed.stderr.startswith(diagnostic_prefix))

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        diagnostic_tokens = diagnostic_suffix.split(" ")
        invocation_tokens = invocations[0].split(" ")

        self.assertEqual(len(diagnostic_tokens), 6)
        self.assertEqual(diagnostic_tokens, invocation_tokens)

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_separator_count_parity_with_invocation_log(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(invocations, ["-m unittest discover -s tests -v"])

        diagnostic_prefix = "unexpected invocation: "
        self.assertTrue(completed.stderr.startswith(diagnostic_prefix))

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        invocation_line = invocations[0]

        self.assertEqual(diagnostic_suffix.count(" "), 5)
        self.assertEqual(invocation_line.count(" "), 5)
        self.assertNotIn("  ", diagnostic_suffix)
        self.assertNotIn("  ", invocation_line)

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_has_no_empty_tokens_and_matches_invocation_log(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(len(invocations), 1)

        diagnostic_prefix = "unexpected invocation: "
        self.assertTrue(completed.stderr.startswith(diagnostic_prefix))

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        diagnostic_tokens = diagnostic_suffix.split(" ")
        invocation_tokens = invocations[0].split(" ")

        self.assertEqual(diagnostic_tokens, invocation_tokens)
        self.assertTrue(all(token != "" for token in diagnostic_tokens))
        self.assertTrue(all(token != "" for token in invocation_tokens))

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_prefix_exact_text_parity_with_invocation_log(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(len(invocations), 1)

        diagnostic_prefix = "unexpected invocation: "
        self.assertEqual(completed.stderr[: len(diagnostic_prefix)], diagnostic_prefix)

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        self.assertEqual(diagnostic_suffix, invocations[-1])
        self.assertEqual(completed.stderr, f"{diagnostic_prefix}{invocations[-1]}\n")

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_prefix_occurs_once_at_line_start_without_suffix_leakage(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(invocations, ["-m unittest discover -s tests -v"])

        diagnostic_prefix = "unexpected invocation: "
        self.assertTrue(completed.stderr.startswith(diagnostic_prefix))
        self.assertEqual(completed.stderr.count(diagnostic_prefix), 1)

        stderr_line_start_prefix_occurrences = sum(
            1 for line in completed.stderr.splitlines() if line.startswith(diagnostic_prefix)
        )
        self.assertEqual(stderr_line_start_prefix_occurrences, 1)

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        self.assertEqual(
            diagnostic_suffix.count(diagnostic_prefix),
            0,
            msg="expected no repeated `unexpected invocation: ` prefix leakage into diagnostic suffix",
        )

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_suffix_is_non_empty_and_token_boundary_stable_with_invocation_log(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(len(invocations), 1)

        diagnostic_prefix = "unexpected invocation: "
        self.assertTrue(completed.stderr.startswith(diagnostic_prefix))

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        invocation_line = invocations[0]

        self.assertNotEqual(diagnostic_suffix, "")
        self.assertEqual(
            diagnostic_suffix,
            diagnostic_suffix.strip(),
            msg="expected diagnostic suffix extraction to avoid boundary whitespace drift",
        )

        diagnostic_tokens = diagnostic_suffix.split(" ")
        invocation_tokens = invocation_line.split(" ")

        self.assertTrue(all(token != "" for token in diagnostic_tokens))
        self.assertTrue(all(token != "" for token in invocation_tokens))
        self.assertEqual(diagnostic_tokens[0], invocation_tokens[0])
        self.assertEqual(diagnostic_tokens[-1], invocation_tokens[-1])

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_suffix_is_single_line_and_matches_invocation_log(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(len(invocations), 1)

        diagnostic_prefix = "unexpected invocation: "
        self.assertTrue(completed.stderr.startswith(diagnostic_prefix))

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        self.assertNotIn("\n", diagnostic_suffix)
        self.assertEqual(len(diagnostic_suffix.splitlines()), 1)
        self.assertEqual(
            diagnostic_suffix,
            invocations[0],
            msg="expected single-line diagnostic suffix parity with invocation-log argv entry",
        )

    def test_check_unit_wrapper_unexpected_invocation_stderr_has_single_terminal_newline_without_trailing_blank_lines(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(len(invocations), 1)

        diagnostic_prefix = "unexpected invocation: "
        expected_stderr = f"{diagnostic_prefix}{invocations[0]}\n"

        self.assertEqual(completed.stderr, expected_stderr)
        self.assertTrue(completed.stderr.endswith("\n"))
        self.assertEqual(completed.stderr.count("\n"), 1)
        self.assertFalse(completed.stderr.endswith("\n\n"))

    def test_check_unit_wrapper_unexpected_invocation_stderr_is_lf_only_without_cr_leakage(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(len(invocations), 1)

        diagnostic_prefix = "unexpected invocation: "
        expected_stderr = f"{diagnostic_prefix}{invocations[0]}\n"

        self.assertEqual(completed.stderr, expected_stderr)
        self.assertNotIn("\r", completed.stderr)
        self.assertEqual(completed.stderr.splitlines(), [f"{diagnostic_prefix}{invocations[0]}"])

    def test_check_unit_wrapper_unexpected_invocation_stdout_is_single_lf_terminated_banner_line_without_cr_leakage(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(invocations, ["-m unittest discover -s tests -v"])

        expected_stdout = "[unit] Running unittest suite\n"
        self.assertEqual(completed.stdout, expected_stdout)
        self.assertTrue(completed.stdout.endswith("\n"))
        self.assertEqual(completed.stdout.count("\n"), 1)
        self.assertNotIn("\r", completed.stdout)
        self.assertEqual(completed.stdout.split("\n"), ["[unit] Running unittest suite", ""])
        self.assertEqual(completed.stdout.splitlines(), ["[unit] Running unittest suite"])

    def test_check_unit_wrapper_unexpected_invocation_stderr_is_single_lf_only_diagnostic_line_after_explicit_segmentation_checks(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(invocations, ["-m unittest discover -s tests -v"])

        expected_diagnostic = "unexpected invocation: -m unittest discover -s tests -v"
        expected_stderr = f"{expected_diagnostic}\n"

        self.assertEqual(completed.stderr, expected_stderr)
        self.assertNotIn("\r", completed.stderr)
        self.assertEqual(completed.stderr.count("\n"), 1)

        self.assertEqual(completed.stderr.split("\n"), [expected_diagnostic, ""])
        self.assertEqual(completed.stderr.splitlines(), [expected_diagnostic])
        self.assertEqual(completed.stderr.splitlines(keepends=True), [expected_stderr])

        segmented_recompose = "\n".join(completed.stderr.splitlines()) + "\n"
        self.assertEqual(segmented_recompose, expected_stderr)

    def test_check_unit_wrapper_unexpected_invocation_diagnostic_and_log_suffix_are_cr_free_and_token_equal(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(len(invocations), 1)

        diagnostic_prefix = "unexpected invocation: "
        self.assertTrue(completed.stderr.startswith(diagnostic_prefix))

        diagnostic_suffix = completed.stderr.removeprefix(diagnostic_prefix).rstrip("\n")
        invocation_line = invocations[0]

        self.assertNotIn("\r", diagnostic_suffix)
        self.assertNotIn("\r", invocation_line)
        self.assertEqual(diagnostic_suffix.encode("utf-8"), invocation_line.encode("utf-8"))
        self.assertEqual(diagnostic_suffix.split(" "), invocation_line.split(" "))

    def test_check_unit_wrapper_unexpected_invocation_log_trim_boundary_parity_with_canonical_token_join(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        expected_tokens = ["-m", "unittest", "discover", "-s", "tests", "-v"]
        expected_invocation_line = " ".join(expected_tokens)

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(invocations, [expected_invocation_line])

        invocation_line = invocations[0]
        self.assertEqual(invocation_line, invocation_line.strip())
        self.assertEqual(invocation_line, " ".join(expected_tokens))

    def test_check_unit_wrapper_fails_on_unexpected_unittest_invocation_without_pass_banner(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[unit] Running unittest suite", completed.stdout)
        self.assertNotIn("[unit] Passed", completed.stdout)
        self.assertIn("unexpected invocation: -m unittest discover -s tests -v", completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_preserves_unittest_stderr_verbatim(self) -> None:
        failing_message = "unit canary stderr passthrough exactness"
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[unit] Running unittest suite", completed.stdout)
        self.assertNotIn("[unit] Passed", completed.stdout)
        self.assertEqual(completed.stderr, f"{failing_message}\n")
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_is_stderr_silent_on_success(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("[unit] Running unittest suite", completed.stdout)
        self.assertIn("[unit] Passed", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_start_banner_exact_text_contract(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self._assert_step_banner_exact_text_contract(completed.stdout, "[unit] Running unittest suite")

        lines = completed.stdout.splitlines()
        self.assertIn("[unit] Running unittest suite", lines)
        self.assertIn("[unit] Passed", lines)
        self.assertLess(lines.index("[unit] Running unittest suite"), lines.index("[unit] Passed"))
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_success_banner_exact_text_contract(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self._assert_step_banner_exact_text_contract(completed.stdout, "[unit] Passed")

        non_empty_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertGreater(len(non_empty_lines), 0)
        self.assertEqual(non_empty_lines[-1], "[unit] Passed")
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_failure_start_banner_exact_text_contract(self) -> None:
        failing_message = "unit canary failure start-banner exact-text"
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self._assert_step_banner_exact_text_contract(completed.stdout, "[unit] Running unittest suite")
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_failure_start_banner_is_terminal_stdout_line(self) -> None:
        failing_message = "unit canary failure stdout boundary"
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self._assert_step_banner_exact_text_contract(completed.stdout, "[unit] Running unittest suite")

        non_empty_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertGreater(len(non_empty_lines), 0)
        self.assertEqual(non_empty_lines[-1], "[unit] Running unittest suite")
        self.assertEqual(non_empty_lines.count("[unit] Running unittest suite"), 1)
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_failure_stderr_passthrough_does_not_mutate_stdout_banner_order(self) -> None:
        failing_message = "unit canary failure ordering"
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self._assert_step_banner_exact_text_contract(completed.stdout, "[unit] Running unittest suite")

        stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(stdout_lines, ["[unit] Running unittest suite"])
        self.assertNotIn(failing_message, completed.stdout)
        self.assertEqual(completed.stderr, f"{failing_message}\n")
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_failure_suppresses_success_banner_variants(self) -> None:
        failing_message = "unit canary failure success-banner suppression"
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        lines = completed.stdout.splitlines()
        self.assertEqual([line for line in lines if line == "[unit] Passed"], [])
        self.assertEqual([line for line in lines if line.strip() == "[unit] Passed"], [])
        self.assertIn(failing_message, completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_failure_terminal_stdout_line_exact_text_contract(self) -> None:
        failing_message = "unit canary failure terminal-line exact-text"
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self._assert_step_banner_exact_text_contract(completed.stdout, "[unit] Running unittest suite")

        non_empty_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertGreater(len(non_empty_lines), 0)
        self.assertEqual(non_empty_lines[-1], "[unit] Running unittest suite")
        self.assertEqual(non_empty_lines.count("[unit] Running unittest suite"), 1)

        trimmed_terminal_variants = [
            line
            for line in non_empty_lines
            if line.strip() == "[unit] Running unittest suite" and line != "[unit] Running unittest suite"
        ]
        self.assertEqual(trimmed_terminal_variants, [])

        self.assertIn(failing_message, completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_unexpected_invocation_keeps_terminal_stdout_boundary(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self._assert_step_banner_exact_text_contract(completed.stdout, "[unit] Running unittest suite")

        non_empty_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(non_empty_lines, ["[unit] Running unittest suite"])
        self.assertEqual([line for line in non_empty_lines if line == "[unit] Passed"], [])
        self.assertEqual([line for line in non_empty_lines if line.strip() == "[unit] Passed"], [])

        self.assertIn("unexpected invocation: -m unittest discover -s tests -v", completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_unexpected_invocation_suppresses_success_banner_variants(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        lines = completed.stdout.splitlines()
        self.assertEqual([line for line in lines if line == "[unit] Passed"], [])
        self.assertEqual([line for line in lines if line.strip() == "[unit] Passed"], [])
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_unexpected_invocation_keeps_diagnostic_on_stderr_only(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)

        diagnostic = "unexpected invocation: -m unittest discover -s tests -v"
        stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(stdout_lines, ["[unit] Running unittest suite"])
        self.assertNotIn(diagnostic, completed.stdout)
        self.assertIn(diagnostic, completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_unexpected_invocation_stderr_terminal_line_exact_text_contract(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)

        diagnostic = "unexpected invocation: -m unittest discover -s tests -v"
        stderr_non_empty_lines = [line for line in completed.stderr.splitlines() if line.strip()]
        self.assertEqual(stderr_non_empty_lines, [diagnostic])
        self.assertEqual(completed.stderr, f"{diagnostic}\n")
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_unexpected_invocation_preserves_stderr_byte_for_byte(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(
            completed.stderr,
            "unexpected invocation: -m unittest discover -s tests -v\n",
        )
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_unexpected_invocation_keeps_invocation_log_terminal_line_byte_exact(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unexpected invocation: -m unittest discover -s tests -v", completed.stderr)

        expected_terminal_line = "-m unittest discover -s tests -v"
        self.assertGreater(len(invocations), 0)
        self.assertEqual(invocations[-1], expected_terminal_line)
        self.assertEqual(invocations[-1:], [expected_terminal_line])
        self.assertEqual(invocations, [expected_terminal_line])
        self.assertEqual(invocations[-1].encode("utf-8"), expected_terminal_line.encode("utf-8"))

    def test_check_unit_wrapper_success_stdout_is_banner_only_and_diagnostic_free(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)

        stdout_non_empty_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(
            stdout_non_empty_lines,
            ["[unit] Running unittest suite", "[unit] Passed"],
        )
        self.assertNotIn("unexpected invocation: -m unittest discover -s tests -v", completed.stdout)
        self.assertNotIn("unexpected invocation: -m unittest discover -s tests -v", completed.stderr)
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_success_stderr_has_no_non_empty_lines(self) -> None:
        completed, invocations = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)

        stderr_non_empty_lines = [line for line in completed.stderr.splitlines() if line.strip()]
        self.assertEqual(
            stderr_non_empty_lines,
            [],
            msg="expected successful check-unit run to keep stderr free of non-empty lines",
        )
        self.assertIn("-m unittest discover -s tests -v", invocations)

    def test_check_unit_wrapper_stdout_line_ending_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout line-ending tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertNotIn("\r", observed_stdout)
                self.assertTrue(observed_stdout.endswith("\n"))
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(observed_stdout.split("\n"), [*expected_non_empty_lines, ""])

    def test_check_unit_wrapper_stderr_line_ending_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr line-ending tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stderr_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                self.assertNotIn("\r", observed_stderr)

                if expected_non_empty_lines:
                    expected_stderr = "\n".join(expected_non_empty_lines) + "\n"
                    self.assertEqual(observed_stderr, expected_stderr)
                    self.assertTrue(observed_stderr.endswith("\n"))
                    self.assertEqual(observed_stderr.splitlines(), expected_non_empty_lines)
                    self.assertEqual(observed_stderr.split("\n"), [*expected_non_empty_lines, ""])
                else:
                    self.assertEqual(observed_stderr, "")

    def test_check_unit_wrapper_stdout_terminal_newline_cardinality_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout terminal-newline cardinality tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"
                expected_terminal_newline_count = len(expected_non_empty_lines)
                expected_keepends = [f"{line}\n" for line in expected_non_empty_lines]

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertNotIn("\r", observed_stdout)
                self.assertTrue(observed_stdout.endswith("\n"))
                self.assertEqual(observed_stdout.count("\n"), expected_terminal_newline_count)
                self.assertFalse(observed_stdout.endswith("\n\n"))
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(observed_stdout.splitlines(keepends=True), expected_keepends)

    def test_check_unit_wrapper_stdout_keepends_recompose_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout keepends recompose tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"
                expected_keepends = [f"{line}\n" for line in expected_non_empty_lines]

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(observed_stdout.splitlines(keepends=True), expected_keepends)
                self.assertEqual("".join(observed_stdout.splitlines(keepends=True)), observed_stdout)

    def test_check_unit_wrapper_stderr_terminal_newline_cardinality_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr terminal-newline cardinality tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_line_by_mode = {
            "pass": None,
            "fail": failing_message,
            "unexpected": "unexpected invocation: -m unittest discover -s tests -v",
        }
        expected_newline_count_by_mode = {
            "pass": 0,
            "fail": 1,
            "unexpected": 1,
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_line in expected_stderr_line_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_newline_count = expected_newline_count_by_mode[mode]

                self.assertEqual(observed_stderr.count("\n"), expected_newline_count)
                self.assertNotIn("\r", observed_stderr)

                if expected_line is None:
                    self.assertEqual(observed_stderr, "")
                    self.assertEqual([line for line in observed_stderr.splitlines() if line.strip()], [])
                    continue

                expected_stderr = f"{expected_line}\n"
                self.assertEqual(observed_stderr, expected_stderr)
                self.assertTrue(observed_stderr.endswith("\n"))
                self.assertFalse(observed_stderr.endswith("\n\n"))
                self.assertEqual([line for line in observed_stderr.splitlines() if line.strip()], [expected_line])

    def test_check_unit_wrapper_stderr_segmentation_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr segmentation tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_line_by_mode = {
            "pass": None,
            "fail": failing_message,
            "unexpected": "unexpected invocation: -m unittest discover -s tests -v",
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_line in expected_stderr_line_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                self.assertNotIn("\r", observed_stderr)

                if expected_line is None:
                    self.assertEqual(observed_stderr, "")
                    self.assertEqual(observed_stderr.splitlines(), [])
                    self.assertEqual(observed_stderr.splitlines(keepends=True), [])
                    continue

                expected_stderr = f"{expected_line}\n"
                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), [expected_line])
                self.assertEqual(observed_stderr.splitlines(keepends=True), [expected_stderr])
                self.assertEqual(observed_stderr.split("\n"), [expected_line, ""])

    def test_check_unit_wrapper_stdout_split_plus_join_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout split-plus-join tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"
                recomposed_stdout = "\n".join(observed_stdout.splitlines()) + ("\n" if observed_stdout else "")

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(
                    [line for line in observed_stdout.splitlines() if line.strip()],
                    expected_non_empty_lines,
                )
                self.assertEqual(recomposed_stdout, observed_stdout)

    def test_check_unit_wrapper_stderr_keepends_recompose_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr keepends recompose tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_line_by_mode = {
            "pass": None,
            "fail": failing_message,
            "unexpected": "unexpected invocation: -m unittest discover -s tests -v",
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_line in expected_stderr_line_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                observed_keepends = observed_stderr.splitlines(keepends=True)

                self.assertEqual("".join(observed_keepends), observed_stderr)

                if expected_line is None:
                    self.assertEqual(observed_stderr, "")
                    self.assertEqual(observed_keepends, [])
                    continue

                expected_stderr = f"{expected_line}\n"
                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), [expected_line])
                self.assertEqual(observed_keepends, [expected_stderr])

    def test_check_unit_wrapper_stderr_split_plus_join_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-plus-join tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_line_by_mode = {
            "pass": None,
            "fail": failing_message,
            "unexpected": "unexpected invocation: -m unittest discover -s tests -v",
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_line in expected_stderr_line_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if expected_line is None else f"{expected_line}\n"
                recomposed_stderr = "\n".join(observed_stderr.splitlines()) + ("\n" if observed_stderr else "")

                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(recomposed_stderr, observed_stderr)
                self.assertNotIn("\r", observed_stderr)

                if expected_line is None:
                    self.assertEqual(observed_stderr.splitlines(), [])
                    self.assertEqual([line for line in observed_stderr.splitlines() if line.strip()], [])
                    continue

                self.assertEqual(observed_stderr.splitlines(), [expected_line])
                self.assertEqual([line for line in observed_stderr.splitlines() if line.strip()], [expected_line])

    def test_check_unit_wrapper_stdout_keepends_to_splitlines_normalization_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout keepends-normalization tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"
                observed_keepends = observed_stdout.splitlines(keepends=True)
                normalized_keepends = [line.removesuffix("\n") for line in observed_keepends]

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(normalized_keepends, observed_stdout.splitlines())
                self.assertEqual(normalized_keepends, expected_non_empty_lines)
                self.assertNotIn("\r", observed_stdout)

    def test_check_unit_wrapper_stderr_keepends_to_splitlines_normalization_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr keepends-normalization tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_line_by_mode = {
            "pass": None,
            "fail": failing_message,
            "unexpected": "unexpected invocation: -m unittest discover -s tests -v",
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_line in expected_stderr_line_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                observed_keepends = observed_stderr.splitlines(keepends=True)
                normalized_keepends = [line.removesuffix("\n") for line in observed_keepends]

                self.assertEqual(normalized_keepends, observed_stderr.splitlines())
                self.assertNotIn("\r", observed_stderr)

                if expected_line is None:
                    self.assertEqual(observed_stderr, "")
                    self.assertEqual(observed_keepends, [])
                    self.assertEqual(normalized_keepends, [])
                    continue

                expected_stderr = f"{expected_line}\n"
                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_keepends, [expected_stderr])
                self.assertEqual(normalized_keepends, [expected_line])

    def test_check_unit_wrapper_stdout_split_segmentation_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout split-segmentation tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(observed_stdout.split("\n"), [*observed_stdout.splitlines(), ""])
                self.assertEqual(observed_stdout.split("\n"), [*expected_non_empty_lines, ""])
                self.assertNotIn("\r", observed_stdout)

    def test_check_unit_wrapper_stderr_split_segmentation_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-segmentation tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), expected_non_empty_lines)
                self.assertEqual(observed_stderr.split("\n"), [*observed_stderr.splitlines(), ""])
                self.assertEqual(observed_stderr.split("\n"), [*expected_non_empty_lines, ""])
                self.assertNotIn("\r", observed_stderr)

    def test_check_unit_wrapper_stdout_split_tail_cardinality_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout split-tail-cardinality tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(
                    len(observed_stdout.split("\n")),
                    len(observed_stdout.splitlines()) + 1,
                )
                self.assertEqual(
                    len(observed_stdout.split("\n")),
                    len(expected_non_empty_lines) + 1,
                )
                self.assertNotIn("\r", observed_stdout)

    def test_check_unit_wrapper_stderr_split_tail_cardinality_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-tail-cardinality tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), expected_non_empty_lines)
                self.assertEqual(
                    len(observed_stderr.split("\n")),
                    len(observed_stderr.splitlines()) + 1,
                )
                self.assertEqual(
                    len(observed_stderr.split("\n")),
                    len(expected_non_empty_lines) + 1,
                )
                self.assertNotIn("\r", observed_stderr)

    def test_check_unit_wrapper_cross_channel_split_tail_cardinality_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-tail-cardinality tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                observed_stderr = completed_by_mode[mode].stderr

                expected_stdout = "\n".join(expected_lines["stdout"]) + "\n"
                expected_stderr = "" if not expected_lines["stderr"] else "\n".join(expected_lines["stderr"]) + "\n"

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(
                    len(observed_stdout.split("\n")),
                    len(observed_stdout.splitlines()) + 1,
                )
                self.assertEqual(
                    len(observed_stdout.split("\n")),
                    len(expected_lines["stdout"]) + 1,
                )
                self.assertEqual(
                    len(observed_stderr.split("\n")),
                    len(observed_stderr.splitlines()) + 1,
                )
                self.assertEqual(
                    len(observed_stderr.split("\n")),
                    len(expected_lines["stderr"]) + 1,
                )
                self.assertNotIn("\r", observed_stdout)
                self.assertNotIn("\r", observed_stderr)

    def test_check_unit_wrapper_stderr_split_trailing_empty_segment_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-trailing-empty-segment tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                split_segments = observed_stderr.split("\n")

                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), expected_non_empty_lines)
                self.assertEqual(split_segments, [*expected_non_empty_lines, ""])
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], observed_stderr.splitlines())
                self.assertEqual(split_segments[:-1], expected_non_empty_lines)
                self.assertNotIn("\r", observed_stderr)

    def test_check_unit_wrapper_stdout_split_trailing_empty_segment_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout split-trailing-empty-segment tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"
                split_segments = observed_stdout.split("\n")

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], observed_stdout.splitlines())
                self.assertEqual(split_segments[:-1], expected_non_empty_lines)
                self.assertNotIn("\r", observed_stdout)

    def test_check_unit_wrapper_cross_channel_split_trailing_empty_segment_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-empty-segment tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        observed_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                        split_segments = observed_output.split("\n")

                        self.assertEqual(observed_output, expected_output)
                        self.assertEqual(observed_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(split_segments, [*expected_non_empty_lines, ""])
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], observed_output.splitlines())
                        self.assertEqual(split_segments[:-1], expected_non_empty_lines)
                        self.assertNotIn("\r", observed_output)

    def test_check_unit_wrapper_cross_channel_split_trailing_tail_identity_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-tail-identity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        observed_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                        split_segments = observed_output.split("\n")

                        self.assertEqual(observed_output, expected_output)
                        self.assertEqual(observed_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], observed_output.splitlines())
                        self.assertEqual(split_segments[:-1], expected_lines[channel])
                        self.assertNotIn("\r", observed_output)

    def test_check_unit_wrapper_stdout_split_trailing_tail_length_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout split-trailing-tail-length tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"
                split_segments = observed_stdout.split("\n")

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(
                    len(split_segments[:-1]),
                    len(observed_stdout.splitlines()),
                )
                self.assertEqual(
                    len(split_segments[:-1]),
                    len(expected_non_empty_lines),
                )
                self.assertEqual(
                    len(observed_stdout.splitlines()),
                    len(expected_non_empty_lines),
                )
                self.assertNotIn("\r", observed_stdout)

    def test_check_unit_wrapper_stderr_split_trailing_tail_boundary_length_pre_tail_cardinality_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-trailing-tail-boundary-length-pre-tail-cardinality tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"
                split_segments = observed_stderr.split("\n")

                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(
                    len(split_segments[:-1]),
                    len(expected_stderr_lines),
                )
                self.assertEqual(split_segments[:-1], observed_stderr.splitlines())
                self.assertEqual(split_segments[:-1], expected_stderr_lines)
                self.assertNotIn("\r", observed_stderr)

    def test_check_unit_wrapper_cross_channel_split_trailing_tail_boundary_length_pre_tail_cardinality_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-tail-boundary-length-pre-tail-cardinality tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                        split_segments = channel_output.split("\n")

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(channel_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(
                            len(split_segments[:-1]),
                            len(expected_lines[channel]),
                        )
                        self.assertEqual(split_segments[:-1], channel_output.splitlines())
                        self.assertEqual(split_segments[:-1], expected_lines[channel])
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_cross_channel_split_trailing_tail_length_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-tail-length tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        observed_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                        split_segments = observed_output.split("\n")

                        self.assertEqual(observed_output, expected_output)
                        self.assertEqual(observed_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(
                            len(split_segments[:-1]),
                            len(expected_lines[channel]),
                        )
                        self.assertEqual(
                            len(observed_output.splitlines()),
                            len(expected_lines[channel]),
                        )
                        self.assertEqual(
                            len(split_segments[:-1]),
                            len(observed_output.splitlines()),
                        )
                        self.assertNotIn("\r", observed_output)

    def test_check_unit_wrapper_stdout_split_trailing_tail_index_boundary_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout split-trailing-tail-index-boundary tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_non_empty_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_non_empty_lines) + "\n"
                split_segments = observed_stdout.split("\n")
                boundary = len(expected_non_empty_lines)

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_non_empty_lines)
                self.assertEqual(split_segments[:boundary], expected_non_empty_lines)
                self.assertEqual(split_segments[boundary], "")
                self.assertEqual(len(split_segments), boundary + 1)
                self.assertEqual(split_segments[-1], "")
                self.assertNotIn("\r", observed_stdout)

    def test_check_unit_wrapper_cross_channel_split_trailing_tail_index_boundary_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-tail-index-boundary tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        observed_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                        split_segments = observed_output.split("\n")
                        boundary = len(expected_non_empty_lines)

                        self.assertEqual(observed_output, expected_output)
                        self.assertEqual(observed_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(split_segments[:boundary], expected_non_empty_lines)
                        self.assertEqual(split_segments[boundary], "")
                        self.assertEqual(len(split_segments), boundary + 1)
                        self.assertEqual(split_segments[-1], "")
                        self.assertNotIn("\r", observed_output)

    def test_check_unit_wrapper_stdout_split_trailing_tail_post_boundary_singleton_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout split-trailing-tail-post-boundary-singleton tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stdout_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_stdout_lines) + "\n"

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_stdout_lines)
                self.assertEqual(
                    observed_stdout.split("\n")[len(expected_stdout_lines) :],
                    [""],
                )
                self.assertNotIn("\r", observed_stdout)

    def test_check_unit_wrapper_cross_channel_split_trailing_tail_post_boundary_singleton_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-tail-post-boundary-singleton tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(channel_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(
                            channel_output.split("\n")[len(expected_lines[channel]) :],
                            [""],
                        )
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stdout_split_trailing_tail_post_boundary_singleton_length_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stdout split-trailing-tail-post-boundary-singleton-length tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stdout_lines_by_mode = {
            "pass": ["[unit] Running unittest suite", "[unit] Passed"],
            "fail": ["[unit] Running unittest suite"],
            "unexpected": ["[unit] Running unittest suite"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stdout_lines in expected_stdout_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stdout = completed_by_mode[mode].stdout
                expected_stdout = "\n".join(expected_stdout_lines) + "\n"
                trailing_tail = observed_stdout.split("\n")[len(expected_stdout_lines) :]

                self.assertEqual(observed_stdout, expected_stdout)
                self.assertEqual(observed_stdout.splitlines(), expected_stdout_lines)
                self.assertEqual(len(trailing_tail), 1)
                self.assertEqual(trailing_tail[0], "")
                self.assertNotIn("\r", observed_stdout)

    def test_check_unit_wrapper_cross_channel_split_trailing_tail_post_boundary_singleton_length_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-tail-post-boundary-singleton-length tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                        trailing_tail = channel_output.split("\n")[len(expected_lines[channel]) :]

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(channel_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(len(trailing_tail), 1)
                        self.assertEqual(trailing_tail[0], "")
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_trailing_tail_post_boundary_singleton_length_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-trailing-tail-post-boundary-singleton-length tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"
                trailing_tail = observed_stderr.split("\n")[len(expected_stderr_lines) :]

                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), expected_stderr_lines)
                self.assertEqual(len(trailing_tail), 1)
                self.assertEqual(trailing_tail[0], "")
                self.assertNotIn("\r", observed_stderr)

    def test_check_unit_wrapper_cross_channel_split_trailing_tail_post_boundary_singleton_length_boundary_index_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-tail-post-boundary-singleton-length-boundary-index tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                        split_segments = channel_output.split("\n")
                        boundary = len(expected_non_empty_lines)
                        trailing_tail = split_segments[boundary:]

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(channel_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(len(trailing_tail), 1)
                        self.assertEqual(split_segments[boundary], "")
                        self.assertEqual(trailing_tail[0], "")
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_trailing_tail_post_boundary_singleton_boundary_index_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-trailing-tail-post-boundary-singleton-boundary-index tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"
                split_segments = observed_stderr.split("\n")
                boundary = len(expected_stderr_lines)

                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), expected_stderr_lines)
                self.assertEqual(split_segments[:boundary], expected_stderr_lines)
                self.assertEqual(split_segments[boundary], "")
                self.assertEqual(split_segments[boundary:], [""])
                self.assertEqual(len(split_segments), boundary + 1)
                self.assertNotIn("\r", observed_stderr)

    def test_check_unit_wrapper_cross_channel_split_trailing_tail_boundary_index_length_equality_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-trailing-tail-boundary-index-length-equality tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"
                        split_segments = channel_output.split("\n")
                        boundary = len(expected_non_empty_lines)

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(channel_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(split_segments[:boundary], expected_non_empty_lines)
                        self.assertEqual(split_segments[boundary], "")
                        self.assertEqual(split_segments[boundary:], [""])
                        self.assertEqual(len(split_segments), boundary + 1)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_boundary_closure_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-boundary-closure tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                observed_stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(observed_stderr, expected_stderr)
                self.assertEqual(observed_stderr.splitlines(), expected_stderr_lines)
                self.assertEqual(observed_stderr.split("\n"), [*expected_stderr_lines, ""])
                self.assertNotIn("\r", observed_stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_boundary_closure_tri_mode_parity_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-boundary-closure tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        observed_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(observed_output, expected_output)
                        self.assertEqual(observed_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(observed_output.split("\n"), [*expected_non_empty_lines, ""])
                        self.assertNotIn("\r", observed_output)

    def test_check_unit_wrapper_stderr_split_full_vector_boundary_closure_tail_index_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-boundary-closure-tail-index-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(stderr.splitlines(), expected_stderr_lines)
                self.assertEqual(stderr.split("\n")[-1], "")
                self.assertEqual(stderr.split("\n")[:-1], expected_stderr_lines)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_boundary_closure_tail_index_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-boundary-closure-tail-index-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(channel_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(channel_output.split("\n")[-1], "")
                        self.assertEqual(channel_output.split("\n")[:-1], expected_lines[channel])
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_tail_index_length_coupling_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-tail-index-length-coupling tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(stderr.splitlines(), expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], expected_stderr_lines)
                self.assertEqual(len(split_segments), len(expected_stderr_lines) + 1)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_tail_index_length_coupling_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-tail-index-length-coupling tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(channel_output.splitlines(), expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], expected_non_empty_lines)
                        self.assertEqual(len(split_segments), len(expected_non_empty_lines) + 1)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_tail_index_length_coupling_splitlines_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-tail-index-length-coupling-splitlines-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], expected_stderr_lines)
                self.assertEqual(len(split_segments), len(split_lines) + 1)
                self.assertEqual(len(split_lines), len(expected_stderr_lines))
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_tail_index_length_coupling_splitlines_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-tail-index-length-coupling-splitlines-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], expected_non_empty_lines)
                        self.assertEqual(len(split_segments), len(split_lines) + 1)
                        self.assertEqual(len(split_lines), len(expected_non_empty_lines))
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_tail_index_length_coupling_splitlines_pre_tail_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-tail-index-length-coupling-splitlines-pre-tail-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                self.assertEqual(split_segments[:-1], expected_stderr_lines)
                self.assertEqual(len(split_segments[:-1]), len(expected_stderr_lines))
                self.assertEqual(len(split_segments), len(split_lines) + 1)
                self.assertEqual(len(split_lines), len(expected_stderr_lines))
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_tail_index_length_coupling_splitlines_pre_tail_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-tail-index-length-coupling-splitlines-pre-tail-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        self.assertEqual(split_segments[:-1], expected_non_empty_lines)
                        self.assertEqual(len(split_segments[:-1]), len(expected_non_empty_lines))
                        self.assertEqual(len(split_segments), len(split_lines) + 1)
                        self.assertEqual(len(split_lines), len(expected_non_empty_lines))
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_length_delta_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-length-delta-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], expected_stderr_lines)
                self.assertEqual(len(split_segments[:-1]), len(split_segments) - 1)
                self.assertEqual(len(split_segments[:-1]), len(split_lines))
                self.assertEqual(len(split_segments), len(split_lines) + 1)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_length_delta_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-length-delta-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], expected_non_empty_lines)
                        self.assertEqual(len(split_segments[:-1]), len(split_segments) - 1)
                        self.assertEqual(len(split_segments[:-1]), len(split_lines))
                        self.assertEqual(len(split_segments), len(split_lines) + 1)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_length_delta_identity_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-length-delta-identity-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                self.assertEqual(len(stderr.split("\n")) - len(stderr.splitlines()), 1)
                self.assertEqual(len(stderr.split("\n")[:-1]), len(stderr.splitlines()))
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_length_delta_identity_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-length-delta-identity-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        self.assertEqual(len(channel_output.split("\n")) - len(channel_output.splitlines()), 1)
                        self.assertEqual(len(channel_output.split("\n")[:-1]), len(channel_output.splitlines()))
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_length_delta_signed_inverse_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-length-delta-signed-inverse-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                self.assertEqual(len(stderr.splitlines()) - len(stderr.split("\n")), -1)
                self.assertEqual(len(stderr.splitlines()) - len(stderr.split("\n")[:-1]), 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_length_delta_signed_inverse_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-length-delta-signed-inverse-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        self.assertEqual(len(channel_output.splitlines()) - len(channel_output.split("\n")), -1)
                        self.assertEqual(len(channel_output.splitlines()) - len(channel_output.split("\n")[:-1]), 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_signed_inverse_plus_identity_zero_sum_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-signed-inverse-plus-identity-zero-sum-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                self.assertEqual(len(split_lines) - len(split_segments), -1)
                self.assertEqual(len(split_segments) - len(split_lines), 1)
                self.assertEqual((len(split_lines) - len(split_segments)) + (len(split_segments) - len(split_lines)), 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_signed_inverse_plus_identity_zero_sum_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-signed-inverse-plus-identity-zero-sum-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        self.assertEqual(len(split_lines) - len(split_segments), -1)
                        self.assertEqual(len(split_segments) - len(split_lines), 1)
                        self.assertEqual((len(split_lines) - len(split_segments)) + (len(split_segments) - len(split_lines)), 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_signed_inverse_and_identity_absolute_delta_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-signed-inverse-and-identity-absolute-delta-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                self.assertEqual(abs(len(stderr.splitlines()) - len(stderr.split("\n"))), 1)
                self.assertEqual(abs(len(stderr.split("\n")) - len(stderr.splitlines())), 1)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_signed_inverse_and_identity_absolute_delta_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-signed-inverse-and-identity-absolute-delta-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        self.assertEqual(abs(len(channel_output.splitlines()) - len(channel_output.split("\n"))), 1)
                        self.assertEqual(abs(len(channel_output.split("\n")) - len(channel_output.splitlines())), 1)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_signed_inverse_and_identity_absolute_delta_zero_difference_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-signed-inverse-and-identity-absolute-delta-zero-difference-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                rhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                self.assertEqual(lhs_absolute_delta - rhs_absolute_delta, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_signed_inverse_and_identity_absolute_delta_zero_difference_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-signed-inverse-and-identity-absolute-delta-zero-difference-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        rhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        self.assertEqual(lhs_absolute_delta - rhs_absolute_delta, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_signed_inverse_and_identity_absolute_delta_reverse_order_zero_difference_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-signed-inverse-and-identity-absolute-delta-reverse-order-zero-difference-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                self.assertEqual(lhs_absolute_delta - rhs_absolute_delta, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_signed_inverse_and_identity_absolute_delta_reverse_order_zero_difference_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-signed-inverse-and-identity-absolute-delta-reverse-order-zero-difference-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        self.assertEqual(lhs_absolute_delta - rhs_absolute_delta, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_signed_inverse_and_identity_absolute_delta_reverse_order_symmetric_sum_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-signed-inverse-and-identity-absolute-delta-reverse-order-symmetric-sum-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                self.assertEqual(lhs_reverse_order_delta + rhs_reverse_order_delta, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_signed_inverse_and_identity_absolute_delta_reverse_order_symmetric_sum_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-signed-inverse-and-identity-absolute-delta-reverse-order-symmetric-sum-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        self.assertEqual(lhs_reverse_order_delta + rhs_reverse_order_delta, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)


    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)


    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_absolute_commutativity_delta_closure = abs(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_absolute_commutativity_delta_closure = abs(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_absolute_commutativity_delta_closure = abs(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_absolute_commutativity_delta_closure = abs(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_absolute_commutativity_delta_closure = abs(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_absolute_commutativity_delta_closure = abs(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_absolute_commutativity_delta_closure = abs(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_absolute_commutativity_delta_closure = abs(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_absolute_commutativity_delta_closure = abs(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)

    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_absolute_commutativity_delta_closure = abs(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_unit_wrapper_stderr_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure stderr split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_stderr_lines_by_mode = {
            "pass": [],
            "fail": [failing_message],
            "unexpected": ["unexpected invocation: -m unittest discover -s tests -v"],
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_stderr_lines in expected_stderr_lines_by_mode.items():
            with self.subTest(mode=mode):
                stderr = completed_by_mode[mode].stderr
                split_segments = stderr.split("\n")
                split_lines = stderr.splitlines()
                expected_stderr = "" if not expected_stderr_lines else "\n".join(expected_stderr_lines) + "\n"

                self.assertEqual(stderr, expected_stderr)
                self.assertEqual(split_lines, expected_stderr_lines)
                self.assertEqual(split_segments[-1], "")
                self.assertEqual(split_segments[:-1], split_lines)
                lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                self.assertEqual(lhs_absolute_delta, 1)
                self.assertEqual(rhs_absolute_delta, 1)
                lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                self.assertEqual(lhs_symmetric_sum, 0)
                self.assertEqual(commutativity_delta_closure, 0)
                self.assertEqual(absolute_commutativity_delta_closure, 0)
                self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                    idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotent_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                self.assertEqual(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_absolute_commutativity_delta_closure = abs(
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_absolute_commutativity_delta_closure,
                    fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure
                )
                self.assertEqual(
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                    next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                )
                self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                self.assertNotIn("\r", stderr)


    def test_check_unit_wrapper_cross_channel_split_full_vector_splitlines_pre_tail_reverse_order_symmetric_sum_commutativity_zero_difference_absolute_value_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_parity_canary_tri_mode_across_pass_fail_and_unexpected_invocation_paths(self) -> None:
        success_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
        )
        failing_message = "unit canary failure cross-channel split-full-vector-splitlines-pre-tail-reverse-order-symmetric-sum-commutativity-zero-difference-absolute-value-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-idempotence-fixed-point-parity tri-parity"
        failure_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=1,
            unittest_stderr=failing_message,
        )
        unexpected_completed, _ = self._run_check_unit_script_with_fake_python(
            unittest_exit_code=0,
            force_unexpected_unittest_invocation=True,
        )

        self.assertEqual(success_completed.returncode, 0, msg=success_completed.stderr)
        self.assertNotEqual(failure_completed.returncode, 0)
        self.assertNotEqual(unexpected_completed.returncode, 0)

        expected_lines_by_mode = {
            "pass": {
                "stdout": ["[unit] Running unittest suite", "[unit] Passed"],
                "stderr": [],
            },
            "fail": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": [failing_message],
            },
            "unexpected": {
                "stdout": ["[unit] Running unittest suite"],
                "stderr": ["unexpected invocation: -m unittest discover -s tests -v"],
            },
        }
        completed_by_mode = {
            "pass": success_completed,
            "fail": failure_completed,
            "unexpected": unexpected_completed,
        }

        for mode, expected_lines in expected_lines_by_mode.items():
            with self.subTest(mode=mode):
                completed = completed_by_mode[mode]
                for channel in ("stdout", "stderr"):
                    with self.subTest(mode=mode, channel=channel):
                        channel_output = getattr(completed, channel)
                        expected_non_empty_lines = expected_lines[channel]
                        split_segments = channel_output.split("\n")
                        split_lines = channel_output.splitlines()
                        expected_output = "" if not expected_non_empty_lines else "\n".join(expected_non_empty_lines) + "\n"

                        self.assertEqual(channel_output, expected_output)
                        self.assertEqual(split_lines, expected_non_empty_lines)
                        self.assertEqual(split_segments[-1], "")
                        self.assertEqual(split_segments[:-1], split_lines)
                        lhs_absolute_delta = abs(len(split_segments) - len(split_lines))
                        rhs_absolute_delta = abs(len(split_lines) - len(split_segments))
                        self.assertEqual(lhs_absolute_delta, 1)
                        self.assertEqual(rhs_absolute_delta, 1)
                        lhs_reverse_order_delta = abs(len(split_segments) - len(split_lines)) - abs(len(split_lines) - len(split_segments))
                        rhs_reverse_order_delta = abs(len(split_lines) - len(split_segments)) - abs(len(split_segments) - len(split_lines))
                        lhs_symmetric_sum = lhs_reverse_order_delta + rhs_reverse_order_delta
                        rhs_symmetric_sum = rhs_reverse_order_delta + lhs_reverse_order_delta
                        commutativity_delta_closure = (lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)
                        absolute_commutativity_delta_closure = abs(commutativity_delta_closure)
                        idempotent_absolute_commutativity_delta_closure = abs(absolute_commutativity_delta_closure)
                        fixed_point_idempotent_absolute_commutativity_delta_closure = abs(idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotent_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure)
                        fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure)
                        self.assertEqual(lhs_symmetric_sum, 0)
                        self.assertEqual(commutativity_delta_closure, 0)
                        self.assertEqual(absolute_commutativity_delta_closure, 0)
                        self.assertEqual(idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                            idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotent_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotent_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)

                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        self.assertEqual(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_absolute_commutativity_delta_closure = abs(
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_absolute_commutativity_delta_closure,
                            fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure, 0)
                        next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure = abs(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure
                        )
                        self.assertEqual(
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure,
                            next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_absolute_commutativity_delta_closure,
                        )
                        self.assertEqual(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_absolute_commutativity_delta_closure, 0)
                        self.assertNotIn("\r", channel_output)

    def test_check_full_wrapper_preserves_helper_failure_passthrough(self) -> None:
        failing_message = "gate failure [migration_anchor_gate]: wrapper passthrough canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/migration_anchor_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)
        self.assertEqual(completed.stderr.strip(), failing_message)

    def test_check_full_wrapper_preserves_migration_helper_stderr_byte_for_byte(self) -> None:
        failing_message = "gate failure [migration_anchor_gate]: wrapper exact stderr canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/migration_anchor_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)
        self.assertEqual(completed.stderr, f"{failing_message}\n")

    def test_check_script_preserves_migration_helper_stderr_byte_for_byte(self) -> None:
        failing_message = "gate failure [migration_anchor_gate]: canonical exact stderr canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/migration_anchor_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)
        self.assertEqual(completed.stderr, f"{failing_message}\n")

    def test_check_full_wrapper_preserves_trace_helper_stderr_byte_for_byte(self) -> None:
        failing_message = "gate failure [trace_contract_gate]: wrapper exact stderr canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/trace_contract_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[5/7] Runtime/schema trace contract sync", completed.stdout)
        self.assertNotIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)
        self.assertEqual(completed.stderr, f"{failing_message}\n")

    def test_check_script_preserves_trace_helper_stderr_byte_for_byte(self) -> None:
        failing_message = "gate failure [trace_contract_gate]: canonical exact stderr canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/trace_contract_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[5/7] Runtime/schema trace contract sync", completed.stdout)
        self.assertNotIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)
        self.assertEqual(completed.stderr, f"{failing_message}\n")

    def test_check_full_wrapper_preserves_benchmark_helper_stderr_byte_for_byte(self) -> None:
        failing_message = "gate failure [benchmark_gate]: wrapper exact stderr canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/benchmark_gate.py",
            failing_message=failing_message,
            entry_script="check-full.sh",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[4/7] Benchmark harness", completed.stdout)
        self.assertNotIn("[5/7] Runtime/schema trace contract sync", completed.stdout)
        self.assertNotIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)
        self.assertEqual(completed.stderr, f"{failing_message}\n")

    def test_check_script_preserves_benchmark_helper_stderr_byte_for_byte(self) -> None:
        failing_message = "gate failure [benchmark_gate]: canonical exact stderr canary"
        completed = self._run_check_script_with_fake_python(
            failing_script="scripts/gates/benchmark_gate.py",
            failing_message=failing_message,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[4/7] Benchmark harness", completed.stdout)
        self.assertNotIn("[5/7] Runtime/schema trace contract sync", completed.stdout)
        self.assertNotIn("[6/7] Migration/compatibility discipline anchors", completed.stdout)
        self.assertNotIn("[7/7] Quality gates complete", completed.stdout)
        self.assertNotIn("All active quality gates passed.", completed.stdout)
        self.assertEqual(completed.stderr, f"{failing_message}\n")

    def test_trace_contract_gate_passes_when_schema_matches_runtime_constants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("ok: runtime trace fields are represented in schema", completed.stdout)

    def test_trace_contract_gate_fails_when_schema_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [trace_contract_gate]:", completed.stderr)
            self.assertIn("Schema file missing: schema/ir.v0.1.schema.json", completed.stderr)

    def test_trace_contract_gate_fails_with_invalid_schema_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_text(root, "schema/ir.v0.1.schema.json", "{invalid json")

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [trace_contract_gate]:", completed.stderr)
            self.assertIn("Schema file is not valid JSON: schema/ir.v0.1.schema.json", completed.stderr)

    def test_trace_contract_gate_fails_when_trace_schema_object_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", {"$defs": {}})

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [trace_contract_gate]:", completed.stderr)
            self.assertIn("Malformed schema: missing `$defs.trace` object", completed.stderr)

    def test_trace_contract_gate_fails_with_malformed_trace_schema_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", {"$defs": {"trace": "bad"}})

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [trace_contract_gate]:", completed.stderr)
            self.assertIn("Malformed schema: expected object at `$defs.trace`", completed.stderr)

    def test_trace_contract_gate_fails_when_required_shape_is_not_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._trace_schema_payload()
            payload["$defs"]["trace"]["required"] = "not-a-list"
            self._write_json(root, "schema/ir.v0.1.schema.json", payload)

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [trace_contract_gate]:", completed.stderr)
            self.assertIn("Malformed schema: expected list at `$defs.trace.required`", completed.stderr)

    def test_trace_contract_gate_fails_when_properties_shape_is_not_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._trace_schema_payload()
            payload["$defs"]["trace"]["properties"] = ["not-an-object"]
            self._write_json(root, "schema/ir.v0.1.schema.json", payload)

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [trace_contract_gate]:", completed.stderr)
            self.assertIn("Malformed schema: expected object at `$defs.trace.properties`", completed.stderr)

    def test_trace_contract_gate_fails_when_required_field_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required_fields = list(TRACE_REQUIRED_FIELDS)
            missing = required_fields[0]
            self._write_json(
                root,
                "schema/ir.v0.1.schema.json",
                self._trace_schema_payload(required=required_fields[1:]),
            )

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [trace_contract_gate]:", completed.stderr)
            self.assertIn("trace contract drift detected", completed.stderr)
            self.assertIn(f"missing required fields: {missing}", completed.stderr)

    def test_trace_contract_gate_fails_when_optional_field_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self._trace_schema_payload()
            missing = TRACE_OPTIONAL_FIELDS[0]
            del payload["$defs"]["trace"]["properties"][missing]
            self._write_json(root, "schema/ir.v0.1.schema.json", payload)

            completed = self._run_gate("trace_contract_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [trace_contract_gate]:", completed.stderr)
            self.assertIn("trace contract drift detected", completed.stderr)
            self.assertIn(f"missing optional fields: {missing}", completed.stderr)

    def test_migration_anchor_gate_passes_with_matching_anchor_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn(
                "ok: migration doc anchors match active trace fields and profile references",
                completed.stdout,
            )

    def test_migration_anchor_gate_fails_with_malformed_schema_object_paths(self) -> None:
        cases = [
            ([], "root"),
            ({"$defs": []}, "$defs"),
            ({"$defs": {"trace": []}}, "$defs.trace"),
        ]

        for schema_payload, path in cases:
            with self.subTest(path=path):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self._write_json(root, "schema/ir.v0.1.schema.json", schema_payload)

                    completed = self._run_gate("migration_anchor_gate.py", cwd=root)

                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
                    self.assertIn(
                        f"Malformed migration gate input: expected object at `{path}`",
                        completed.stderr,
                    )

    def test_migration_anchor_gate_fails_when_profile_anchors_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            migrations_profiles = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            quality_profiles = [
                "Sprint-5 calibration additive profile",
                "Sprint-X incompatible profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", migrations_profiles),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", quality_profiles),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "active profile anchor drift between docs/migrations.md and docs/quality-gates.md",
                completed.stderr,
            )

    def test_migration_anchor_gate_fails_when_required_anchor_line_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "docs/migrations.md: missing required anchor line: - Gate anchor trace optional:",
                completed.stderr,
            )

    def test_migration_anchor_gate_fails_when_anchor_line_has_no_backticked_tokens_in_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    "- Gate anchor trace optional: no_tokens_here",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "docs/migrations.md: anchor line has no backticked tokens: "
                "- Gate anchor trace optional:",
                completed.stderr,
            )

    def test_migration_anchor_gate_fails_when_anchor_line_has_no_backticked_tokens_in_quality_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    "- Gate anchor profiles: no_tokens_here",
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "docs/quality-gates.md: anchor line has no backticked tokens: "
                "- Gate anchor profiles:",
                completed.stderr,
            )

    def test_migration_anchor_gate_fails_when_anchor_line_has_duplicate_tokens_in_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            required_tokens = list(TRACE_REQUIRED_FIELDS)
            optional_tokens = list(TRACE_OPTIONAL_FIELDS)
            duplicated_optional_tokens = [optional_tokens[0], optional_tokens[0]] + optional_tokens[1:]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", required_tokens),
                    self._anchor_line("- Gate anchor trace optional:", duplicated_optional_tokens),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "docs/migrations.md: anchor line has duplicate tokens: "
                "- Gate anchor trace optional:",
                completed.stderr,
            )

    def test_migration_anchor_gate_fails_when_anchor_line_has_duplicate_tokens_in_quality_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            duplicated_profiles = [profile_tokens[0], profile_tokens[0], profile_tokens[1]]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", duplicated_profiles),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "docs/quality-gates.md: anchor line has duplicate tokens: "
                "- Gate anchor profiles:",
                completed.stderr,
            )

    def test_migration_anchor_gate_fails_when_migrations_doc_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn("Required doc missing: docs/migrations.md", completed.stderr)

    def test_migration_anchor_gate_fails_when_quality_gates_doc_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            self._write_text(root, "docs/migrations.md", migrations_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn("Required doc missing: docs/quality-gates.md", completed.stderr)

    def test_migration_anchor_gate_fails_when_profile_heading_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-6 compatibility/ref-hardening profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_fails_when_template_heading_only_matches_profile_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## Migration entry template",
                    "```md",
                    "## v<from> -> v<to> (Sprint-5 calibration additive profile)",
                    "```",
                    "",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-5 calibration additive profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_ignores_tilde_and_language_tagged_fenced_heading_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "~~~markdown",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "~~~",
                    "",
                    "```python",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "```",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-5 calibration additive profile, Sprint-6 compatibility/ref-hardening profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_keeps_quad_fence_open_when_closed_with_shorter_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "````md",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "```",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-5 calibration additive profile, Sprint-6 compatibility/ref-hardening profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_keeps_fence_open_when_closing_marker_has_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "```md",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "```python",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-5 calibration additive profile, Sprint-6 compatibility/ref-hardening profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_keeps_fence_open_when_multiple_suffix_close_markers_are_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "```md",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "````markdown",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "```md",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-5 calibration additive profile, Sprint-6 compatibility/ref-hardening profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_keeps_backtick_fence_open_when_closed_with_tilde_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "```md",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "~~~",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-5 calibration additive profile, Sprint-6 compatibility/ref-hardening profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_keeps_tilde_fence_open_when_closed_with_backtick_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "~~~markdown",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "```",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-5 calibration additive profile, Sprint-6 compatibility/ref-hardening profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_closes_quad_fence_with_longer_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "````md",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "`````",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn(
                "ok: migration doc anchors match active trace fields and profile references",
                completed.stdout,
            )

    def test_migration_anchor_gate_passes_with_normalized_whitespace_heading_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5   calibration   additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn(
                "ok: migration doc anchors match active trace fields and profile references",
                completed.stdout,
            )

    def test_migration_anchor_gate_fails_when_profile_anchor_only_matches_heading_substring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile extended)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor missing from migration headings: "
                "Sprint-5 calibration additive profile",
                completed.stderr,
            )

    def test_migration_anchor_gate_fails_when_profile_anchor_maps_to_duplicate_headings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(root, "schema/ir.v0.1.schema.json", self._trace_schema_payload())

            profile_tokens = [
                "Sprint-5 calibration additive profile",
                "Sprint-6 compatibility/ref-hardening profile",
            ]
            migrations_doc = "\n".join(
                [
                    "# Migrations",
                    self._anchor_line("- Gate anchor trace required:", list(TRACE_REQUIRED_FIELDS)),
                    self._anchor_line("- Gate anchor trace optional:", list(TRACE_OPTIONAL_FIELDS)),
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                    "",
                    "## v0.1 -> v0.1 (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 compat note -> v0.1 compat note (Sprint-5 calibration additive profile)",
                    "notes",
                    "## v0.1 -> v0.1 (Sprint-6 compatibility/ref-hardening profile)",
                    "notes",
                ]
            )
            quality_doc = "\n".join(
                [
                    "# Quality gates",
                    self._anchor_line("- Gate anchor profiles:", profile_tokens),
                ]
            )

            self._write_text(root, "docs/migrations.md", migrations_doc)
            self._write_text(root, "docs/quality-gates.md", quality_doc)

            completed = self._run_gate("migration_anchor_gate.py", cwd=root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("gate failure [migration_anchor_gate]:", completed.stderr)
            self.assertIn(
                "profile anchor maps to multiple migration headings: "
                "Sprint-5 calibration additive profile (2)",
                completed.stderr,
            )


if __name__ == "__main__":
    unittest.main()
