#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

SURFACE_SPECS = {
    "eval-smoke": {
        "script": Path("scripts/refresh_eval_example_fixtures.py"),
        "default_fixture_root": Path("examples/eval"),
        "display": "top-level eval smoke fixtures",
    },
    "action-plan-handoff": {
        "script": Path("scripts/refresh_action_plan_handoff.py"),
        "default_fixture_root": Path("examples/eval/action-plan-handoff"),
        "display": "refs-backed eval handoff fixtures",
    },
    "threshold-handoff": {
        "script": Path("scripts/refresh_threshold_handoff.py"),
        "default_fixture_root": Path("examples/eval/threshold-handoff"),
        "display": "threshold eval handoff fixtures",
    },
    "program-pack-replay": {
        "script": Path("scripts/refresh_program_pack_replay_contracts.py"),
        "default_fixture_root": Path("examples/program-packs"),
        "display": "program-pack replay contracts",
    },
}
DEFAULT_SURFACE_ORDER = list(SURFACE_SPECS)


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"refresh_contract_fixtures: {message}")


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _run_refresh_script(*, repo_root: Path, script_path: Path, fixture_root: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--repo-root",
            str(repo_root),
            "--fixture-root",
            str(fixture_root),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        command = " ".join(
            [
                "python3",
                str(script_path.relative_to(repo_root)),
                "--repo-root",
                str(repo_root),
                "--fixture-root",
                str(fixture_root),
            ]
        )
        details = completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}"
        _fail(f"command failed: {command}\n{details}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the checked-in eval smoke, eval handoff, and program-pack replay fixtures by delegating to the existing repo-native refresh helpers in one deterministic pass."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root path (default: auto-detected from script location).",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=DEFAULT_SURFACE_ORDER,
        help=(
            "Restrict refresh to one or more surfaces. Valid values: "
            + ", ".join(DEFAULT_SURFACE_ORDER)
            + "."
        ),
    )
    parser.add_argument(
        "--eval-root",
        default=None,
        help=(
            "Optional override for the top-level eval smoke fixture root. "
            "Defaults to <repo-root>/examples/eval."
        ),
    )
    parser.add_argument(
        "--action-plan-root",
        default=None,
        help=(
            "Optional override for the action-plan handoff fixture root. "
            "Defaults to <repo-root>/examples/eval/action-plan-handoff."
        ),
    )
    parser.add_argument(
        "--threshold-root",
        default=None,
        help=(
            "Optional override for the threshold handoff fixture root. "
            "Defaults to <repo-root>/examples/eval/threshold-handoff."
        ),
    )
    parser.add_argument(
        "--program-pack-root",
        default=None,
        help=(
            "Optional override for the program-pack fixture root. "
            "Defaults to <repo-root>/examples/program-packs."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    selected_surfaces = args.only or DEFAULT_SURFACE_ORDER
    override_roots = {
        "eval-smoke": args.eval_root,
        "action-plan-handoff": args.action_plan_root,
        "threshold-handoff": args.threshold_root,
        "program-pack-replay": args.program_pack_root,
    }

    refreshed_surfaces: list[tuple[str, Path, str]] = []
    for surface in selected_surfaces:
        spec = SURFACE_SPECS[surface]
        fixture_root = (
            Path(override_roots[surface]).expanduser().resolve()
            if override_roots[surface] is not None
            else (repo_root / spec["default_fixture_root"]).resolve()
        )
        script_path = (repo_root / spec["script"]).resolve()
        _run_refresh_script(
            repo_root=repo_root,
            script_path=script_path,
            fixture_root=fixture_root,
        )
        refreshed_surfaces.append((surface, fixture_root, spec["display"]))

    print("refreshed checked-in contract fixtures:")
    for surface, fixture_root, display in refreshed_surfaces:
        print(f"- {surface}: {_display_path(fixture_root, repo_root)} ({display})")


if __name__ == "__main__":
    main()
