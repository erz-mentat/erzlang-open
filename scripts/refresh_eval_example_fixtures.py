#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

DEFAULT_FIXTURE_ROOT_REL = Path("examples/eval")


@dataclass(frozen=True)
class EvalSmokeCase:
    program_stem: str
    event_stem: str

    @property
    def program_name(self) -> str:
        return f"program-{self.program_stem}.erz"

    @property
    def ok_event_name(self) -> str:
        return f"event-{self.event_stem}-ok.json"

    @property
    def ok_output_name(self) -> str:
        return f"event-{self.event_stem}-ok.expected.envelope.json"

    @property
    def no_action_event_name(self) -> str:
        return f"event-{self.event_stem}-no-action.json"

    @property
    def no_action_output_name(self) -> str:
        return f"event-{self.event_stem}-no-action.expected.envelope.json"

    @property
    def no_action_summary_name(self) -> str:
        return f"event-{self.event_stem}-no-action.expected.summary.txt"


SMOKE_CASES = [
    EvalSmokeCase("paths", "path"),
    EvalSmokeCase("cross-paths", "cross-path"),
    EvalSmokeCase("cross-path-ci", "cross-path-ci"),
    EvalSmokeCase("cross-path-strings", "cross-path-strings"),
    EvalSmokeCase("cross-path-lists", "cross-path-lists"),
    EvalSmokeCase("cross-path-regex", "cross-path-regex"),
    EvalSmokeCase("types", "type"),
    EvalSmokeCase("event-type-set", "event-type-set"),
    EvalSmokeCase("event-type-ci", "event-type-ci"),
    EvalSmokeCase("event-type-paths", "event-type-paths"),
    EvalSmokeCase("event-type-patterns", "event-type-patterns"),
    EvalSmokeCase("event-type-string", "event-type-string"),
    EvalSmokeCase("missing-paths", "missing-path"),
    EvalSmokeCase("strings", "string"),
    EvalSmokeCase("strings-ci", "string-ci"),
    EvalSmokeCase("equals-ci", "equals-ci"),
    EvalSmokeCase("membership-ci", "membership-ci"),
    EvalSmokeCase("string-negation", "string-negation"),
    EvalSmokeCase("string-negation-ci", "string-negation-ci"),
    EvalSmokeCase("matches", "matches"),
    EvalSmokeCase("matches-ci", "matches-ci"),
    EvalSmokeCase("not-matches", "not-matches"),
    EvalSmokeCase("not-matches-ci", "not-matches-ci"),
    EvalSmokeCase("any-in", "any-in"),
    EvalSmokeCase("all-in", "all-in"),
    EvalSmokeCase("none-in", "none-in"),
    EvalSmokeCase("lengths", "length"),
    EvalSmokeCase("length-exact", "length-exact"),
    EvalSmokeCase("length-paths", "length-paths"),
    EvalSmokeCase("thresholds", "threshold"),
    EvalSmokeCase("emptiness", "emptiness"),
    EvalSmokeCase("negation", "negation"),
    EvalSmokeCase("suffix", "suffix"),
    EvalSmokeCase("object-keys", "object-keys"),
    EvalSmokeCase("object-key-sets", "object-key-sets"),
    EvalSmokeCase("object-key-set-paths", "object-key-set-paths"),
    EvalSmokeCase("priority", "priority"),
]

EXTRA_GENERATED_PATHS = [
    "event-ok.action-plan.expected.envelope.json",
    "event-ok.action-plan.expected.summary.txt",
    "event-sidecar.expected.envelope.json",
    "event-sidecar.expected.summary.txt",
    "event-sidecar.expected.handoff-bundle.json",
    "event-sidecar.action-plan.expected.envelope.json",
    "event-sidecar.action-plan.expected.summary.txt",
    "batch.expected.envelope.json",
    "batch.expected.summary.txt",
    "batch.expected.handoff-bundle.json",
    "batch.action-plan.expected.envelope.json",
    "batch.action-plan.expected.summary.txt",
]

GENERATED_PATHS = [
    path
    for case in SMOKE_CASES
    for path in (
        case.ok_output_name,
        case.no_action_output_name,
        case.no_action_summary_name,
    )
] + EXTRA_GENERATED_PATHS


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"refresh_eval_example_fixtures: {message}")


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        _fail(f"missing {label}: {path}")


def _run_cli(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        command = " ".join(["python3", "-m", "cli.main", *args])
        details = completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}"
        _fail(f"command failed: {command}\n{details}")
    return completed.stdout


def _write_stdout_fixture(repo_root: Path, output_path: Path, *args: str) -> None:
    output_path.write_text(_run_cli(repo_root, *args), encoding="utf-8")


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _refresh_smoke_cases(repo_root: Path, fixture_root: Path) -> None:
    for case in SMOKE_CASES:
        program_path = fixture_root / case.program_name
        ok_event_path = fixture_root / case.ok_event_name
        no_action_event_path = fixture_root / case.no_action_event_name
        _require_file(program_path, label=f"{case.program_stem} program")
        _require_file(ok_event_path, label=f"{case.event_stem} ok event")
        _require_file(no_action_event_path, label=f"{case.event_stem} no-action event")

        _write_stdout_fixture(
            repo_root,
            fixture_root / case.ok_output_name,
            "eval",
            str(program_path),
            "--input",
            str(ok_event_path),
        )
        _write_stdout_fixture(
            repo_root,
            fixture_root / case.no_action_output_name,
            "eval",
            str(program_path),
            "--input",
            str(no_action_event_path),
        )
        _write_stdout_fixture(
            repo_root,
            fixture_root / case.no_action_summary_name,
            "eval",
            str(program_path),
            "--input",
            str(no_action_event_path),
            "--summary",
        )


def _refresh_action_plan_examples(repo_root: Path, fixture_root: Path) -> None:
    program_path = fixture_root / "program.erz"
    ok_event_path = fixture_root / "event-ok.json"
    _require_file(program_path, label="base eval program")
    _require_file(ok_event_path, label="base ok event")

    _write_stdout_fixture(
        repo_root,
        fixture_root / "event-ok.action-plan.expected.envelope.json",
        "eval",
        str(program_path),
        "--input",
        str(ok_event_path),
        "--action-plan",
    )
    _write_stdout_fixture(
        repo_root,
        fixture_root / "event-ok.action-plan.expected.summary.txt",
        "eval",
        str(program_path),
        "--input",
        str(ok_event_path),
        "--action-plan",
        "--summary",
    )


def _refresh_sidecar_examples(repo_root: Path, fixture_root: Path) -> None:
    program_path = fixture_root / "program-sidecar.erz"
    ok_event_path = fixture_root / "event-ok.json"
    refs_path = fixture_root / "refs-sidecar.json"
    handoff_bundle_path = fixture_root / "event-sidecar.expected.handoff-bundle.json"
    _require_file(program_path, label="sidecar program")
    _require_file(ok_event_path, label="sidecar event")
    _require_file(refs_path, label="sidecar refs")

    base_args = (
        "eval",
        str(program_path),
        "--input",
        str(ok_event_path),
        "--refs",
        str(refs_path),
    )
    _write_stdout_fixture(
        repo_root,
        fixture_root / "event-sidecar.expected.envelope.json",
        *base_args,
    )
    _write_stdout_fixture(
        repo_root,
        fixture_root / "event-sidecar.expected.summary.txt",
        *base_args,
        "--summary",
    )
    _run_cli(repo_root, *base_args, "--handoff-bundle-file", str(handoff_bundle_path))
    _write_stdout_fixture(
        repo_root,
        fixture_root / "event-sidecar.action-plan.expected.envelope.json",
        *base_args,
        "--action-plan",
    )
    _write_stdout_fixture(
        repo_root,
        fixture_root / "event-sidecar.action-plan.expected.summary.txt",
        *base_args,
        "--action-plan",
        "--summary",
    )


def _refresh_batch_examples(repo_root: Path, fixture_root: Path) -> None:
    program_path = fixture_root / "program.erz"
    batch_path = fixture_root / "batch"
    handoff_bundle_path = fixture_root / "batch.expected.handoff-bundle.json"
    _require_file(program_path, label="batch program")
    if not batch_path.is_dir():
        _fail(f"missing batch directory: {batch_path}")

    base_args = (
        "eval",
        str(program_path),
        "--batch",
        str(batch_path),
    )
    _write_stdout_fixture(
        repo_root,
        fixture_root / "batch.expected.envelope.json",
        *base_args,
    )
    _write_stdout_fixture(
        repo_root,
        fixture_root / "batch.expected.summary.txt",
        *base_args,
        "--summary",
    )
    _run_cli(repo_root, *base_args, "--handoff-bundle-file", str(handoff_bundle_path))
    _write_stdout_fixture(
        repo_root,
        fixture_root / "batch.action-plan.expected.envelope.json",
        *base_args,
        "--action-plan",
    )
    _write_stdout_fixture(
        repo_root,
        fixture_root / "batch.action-plan.expected.summary.txt",
        *base_args,
        "--action-plan",
        "--summary",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the checked-in top-level eval smoke fixtures, including action-plan and handoff-bundle sidecars, in one deterministic pass."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root path (default: auto-detected from script location).",
    )
    parser.add_argument(
        "--fixture-root",
        default=None,
        help=(
            "Eval fixture root to rewrite. Defaults to <repo-root>/examples/eval. "
            "This helper intentionally refreshes only the top-level smoke fixtures, not the dedicated action-plan-handoff/ or threshold-handoff/ trees."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    fixture_root = (
        Path(args.fixture_root).expanduser().resolve()
        if args.fixture_root is not None
        else (repo_root / DEFAULT_FIXTURE_ROOT_REL)
    )
    if not fixture_root.is_dir():
        _fail(f"missing fixture root: {fixture_root}")

    for relative_path in GENERATED_PATHS:
        _remove_path(fixture_root / relative_path)

    _refresh_smoke_cases(repo_root, fixture_root)
    _refresh_action_plan_examples(repo_root, fixture_root)
    _refresh_sidecar_examples(repo_root, fixture_root)
    _refresh_batch_examples(repo_root, fixture_root)

    print("refreshed top-level eval example fixtures:")
    for relative_path in GENERATED_PATHS:
        print(f"- {_display_path(fixture_root / relative_path, repo_root)}")


if __name__ == "__main__":
    main()
