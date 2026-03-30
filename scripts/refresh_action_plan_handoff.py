#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

DEFAULT_FIXTURE_ROOT_REL = Path("examples/eval/action-plan-handoff")
PROGRAM_REL = Path("examples/eval/program.erz")

BASELINE_RUN_ID = "action-plan-ci-baseline-001"
CLEAN_RUN_ID = "action-plan-ci-candidate-clean-001"
TRIAGE_RUN_ID = "action-plan-ci-triage-001"
RUN_ID_PATTERN = "^action-plan-ci-.*$"
EXPECTED_EVENT_COUNT = "3"
EXPECTED_ACTION_PLAN_COUNT = "1"
EXPECTED_RESOLVED_REFS_COUNT = "1"

GENERATED_PATHS = [
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

STALE_GENERATED_PATHS = [
    "triage.verify.expected.summary.txt",
    "triage.verify.expected.json",
    "candidate-clean-vs-baseline.self-compare.expected.summary.txt",
    "triage-by-status-vs-baseline.self-compare.expected.summary.txt",
    "self-compare-vs-baseline.expected.json",
    "self-compare-triage-vs-baseline.expected.json",
]


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"refresh_action_plan_handoff: {message}")


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        _fail(f"missing {label}: {path}")


def _require_dir(path: Path, *, label: str) -> None:
    if not path.is_dir():
        _fail(f"missing {label}: {path}")


def _run_cli(repo_root: Path, *args: str) -> None:
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


def _refresh_generated_outputs(repo_root: Path, fixture_root: Path) -> None:
    program_path = repo_root / PROGRAM_REL
    batch_dir = fixture_root / "batch"
    baseline_dir = fixture_root / "baseline"
    clean_dir = fixture_root / "candidate-clean"
    triage_dir = fixture_root / "triage-by-status"

    baseline_verify_summary = fixture_root / "baseline.verify.expected.summary.txt"
    baseline_verify_json = fixture_root / "baseline.verify.expected.json"
    triage_handoff_bundle = fixture_root / "triage.handoff-bundle.expected.json"
    clean_compare_summary = fixture_root / "candidate-clean-vs-baseline.compare.expected.summary.txt"
    clean_compare_json = fixture_root / "candidate-clean-vs-baseline.compare.expected.json"
    triage_compare_summary = fixture_root / "triage-vs-baseline.compare.expected.summary.txt"
    triage_compare_json = fixture_root / "triage-vs-baseline.compare.expected.json"
    clean_handoff_bundle = fixture_root / "candidate-clean-vs-baseline.handoff-bundle.expected.json"
    triage_handoff_bundle_compare = fixture_root / "triage-by-status-vs-baseline.handoff-bundle.expected.json"

    _require_file(program_path, label="program fixture")
    _require_dir(fixture_root, label="fixture root")
    _require_dir(batch_dir, label="batch input directory")

    for relative_path in [*GENERATED_PATHS, *STALE_GENERATED_PATHS]:
        _remove_path(fixture_root / relative_path)

    _run_cli(
        repo_root,
        "eval",
        str(program_path),
        "--batch",
        str(batch_dir),
        "--action-plan",
        "--batch-output",
        str(baseline_dir),
        "--batch-output-run-id",
        BASELINE_RUN_ID,
        "--batch-output-manifest",
    )

    _run_cli(
        repo_root,
        "eval",
        "--batch-output-verify",
        str(baseline_dir),
        "--summary",
        "--batch-output-verify-summary-file",
        str(baseline_verify_summary),
        "--batch-output-verify-json-file",
        str(baseline_verify_json),
        "--batch-output-verify-profile",
        "default",
        "--batch-output-verify-require-run-id",
        "--batch-output-verify-expected-run-id-pattern",
        RUN_ID_PATTERN,
        "--batch-output-verify-expected-event-count",
        EXPECTED_EVENT_COUNT,
        "--batch-output-verify-expected-action-plan-count",
        EXPECTED_ACTION_PLAN_COUNT,
        "--batch-output-verify-expected-resolved-refs-count",
        EXPECTED_RESOLVED_REFS_COUNT,
    )

    _run_cli(
        repo_root,
        "eval",
        str(program_path),
        "--batch",
        str(batch_dir),
        "--action-plan",
        "--batch-output",
        str(clean_dir),
        "--batch-output-run-id",
        CLEAN_RUN_ID,
        "--batch-output-manifest",
    )

    _run_cli(
        repo_root,
        "eval",
        str(program_path),
        "--batch",
        str(batch_dir),
        "--action-plan",
        "--batch-output",
        str(triage_dir),
        "--batch-output-errors-only",
        "--batch-output-layout",
        "by-status",
        "--batch-output-run-id",
        TRIAGE_RUN_ID,
        "--summary",
        "--batch-output-self-verify",
        "--batch-output-self-verify-strict",
        "--batch-output-handoff-bundle-file",
        str(triage_handoff_bundle),
        "--batch-output-verify-profile",
        "triage-by-status",
        "--batch-output-verify-require-run-id",
        "--batch-output-verify-expected-run-id-pattern",
        RUN_ID_PATTERN,
        "--batch-output-verify-expected-event-count",
        EXPECTED_EVENT_COUNT,
        "--batch-output-verify-expected-action-plan-count",
        EXPECTED_ACTION_PLAN_COUNT,
        "--batch-output-verify-expected-resolved-refs-count",
        EXPECTED_RESOLVED_REFS_COUNT,
    )

    clean_compare_expectation_args = [
        "--batch-output-compare-expected-status",
        "ok",
        "--batch-output-compare-expected-compared-count",
        EXPECTED_EVENT_COUNT,
        "--batch-output-compare-expected-matched-count",
        EXPECTED_EVENT_COUNT,
        "--batch-output-compare-expected-changed-count",
        "0",
        "--batch-output-compare-expected-metadata-mismatches-count",
        "0",
        "--batch-output-compare-expected-selected-baseline-count",
        EXPECTED_EVENT_COUNT,
        "--batch-output-compare-expected-selected-candidate-count",
        EXPECTED_EVENT_COUNT,
        "--batch-output-compare-expected-baseline-action-plan-count",
        EXPECTED_ACTION_PLAN_COUNT,
        "--batch-output-compare-expected-candidate-action-plan-count",
        EXPECTED_ACTION_PLAN_COUNT,
        "--batch-output-compare-expected-baseline-resolved-refs-count",
        EXPECTED_RESOLVED_REFS_COUNT,
        "--batch-output-compare-expected-candidate-resolved-refs-count",
        EXPECTED_RESOLVED_REFS_COUNT,
    ]

    triage_compare_expectation_args = [
        "--batch-output-compare-expected-baseline-only-count",
        EXPECTED_EVENT_COUNT,
        "--batch-output-compare-expected-candidate-only-count",
        "2",
        "--batch-output-compare-expected-selected-baseline-count",
        EXPECTED_EVENT_COUNT,
        "--batch-output-compare-expected-selected-candidate-count",
        "2",
        "--batch-output-compare-expected-metadata-mismatches-count",
        "4",
        "--batch-output-compare-expected-baseline-action-plan-count",
        EXPECTED_ACTION_PLAN_COUNT,
        "--batch-output-compare-expected-candidate-action-plan-count",
        EXPECTED_ACTION_PLAN_COUNT,
        "--batch-output-compare-expected-baseline-resolved-refs-count",
        EXPECTED_RESOLVED_REFS_COUNT,
        "--batch-output-compare-expected-candidate-resolved-refs-count",
        EXPECTED_RESOLVED_REFS_COUNT,
    ]

    _run_cli(
        repo_root,
        "eval",
        "--batch-output-compare",
        str(clean_dir),
        "--batch-output-compare-against",
        str(baseline_dir),
        "--summary",
        "--batch-output-compare-summary-file",
        str(clean_compare_summary),
        "--batch-output-compare-json-file",
        str(clean_compare_json),
        "--batch-output-compare-strict",
        *clean_compare_expectation_args,
    )

    _run_cli(
        repo_root,
        "eval",
        "--batch-output-compare",
        str(triage_dir),
        "--batch-output-compare-against",
        str(baseline_dir),
        "--summary",
        "--batch-output-compare-summary-file",
        str(triage_compare_summary),
        "--batch-output-compare-json-file",
        str(triage_compare_json),
        "--batch-output-compare-strict",
        "--batch-output-compare-profile",
        "expected-asymmetric-drift",
        *triage_compare_expectation_args,
    )

    _run_cli(
        repo_root,
        "eval",
        str(program_path),
        "--batch",
        str(batch_dir),
        "--action-plan",
        "--batch-output",
        str(clean_dir),
        "--batch-output-run-id",
        CLEAN_RUN_ID,
        "--batch-output-manifest",
        "--summary",
        "--batch-output-self-compare-against",
        str(baseline_dir),
        "--batch-output-self-compare-strict",
        "--batch-output-handoff-bundle-file",
        str(clean_handoff_bundle),
        *clean_compare_expectation_args,
    )

    _run_cli(
        repo_root,
        "eval",
        str(program_path),
        "--batch",
        str(batch_dir),
        "--action-plan",
        "--batch-output",
        str(triage_dir),
        "--batch-output-errors-only",
        "--batch-output-layout",
        "by-status",
        "--batch-output-run-id",
        TRIAGE_RUN_ID,
        "--batch-output-manifest",
        "--summary",
        "--batch-output-self-compare-against",
        str(baseline_dir),
        "--batch-output-self-compare-strict",
        "--batch-output-compare-profile",
        "expected-asymmetric-drift",
        "--batch-output-handoff-bundle-file",
        str(triage_handoff_bundle_compare),
        *triage_compare_expectation_args,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the checked-in action-plan-handoff artifact trees, compare sidecars, and generation-time handoff bundles in one deterministic pass."
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
            "Action-plan-handoff fixture root to rewrite. Defaults to <repo-root>/examples/eval/action-plan-handoff."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    fixture_root = (
        Path(args.fixture_root).expanduser().resolve()
        if args.fixture_root is not None
        else (repo_root / DEFAULT_FIXTURE_ROOT_REL)
    )

    _refresh_generated_outputs(repo_root, fixture_root)

    print("refreshed action-plan-handoff outputs:")
    for relative_path in GENERATED_PATHS:
        print(f"- {_display_path(fixture_root / relative_path, repo_root)}")


if __name__ == "__main__":
    main()
