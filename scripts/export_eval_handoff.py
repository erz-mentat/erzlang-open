#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn


VERIFY_SUMMARY_NAME = "verify.summary.txt"
VERIFY_JSON_NAME = "verify.json"
COMPARE_SUMMARY_NAME = "compare.summary.txt"
COMPARE_JSON_NAME = "compare.json"
PROVENANCE_JSON_NAME = "handoff.provenance.json"
BUNDLE_JSON_NAME = "handoff.bundle.json"
MANAGED_SIDECAR_NAMES = frozenset(
    {
        VERIFY_SUMMARY_NAME,
        VERIFY_JSON_NAME,
        COMPARE_SUMMARY_NAME,
        COMPARE_JSON_NAME,
        PROVENANCE_JSON_NAME,
        BUNDLE_JSON_NAME,
    }
)


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"export_eval_handoff: {message}")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _relative_label_from_anchor(*, anchor_dir: Path, target_root: Path) -> str:
    relative = Path(
        os.path.relpath(
            target_root.resolve(),
            start=anchor_dir.resolve(),
        )
    ).as_posix()
    if relative == ".":
        return target_root.resolve().name or relative
    if relative == ".." or relative.startswith("../"):
        return target_root.resolve().name or relative
    return relative


def _build_path_labels(
    *,
    repo_root: Path,
    candidate_dir: Path,
    baseline_dir: Path | None,
    out_dir: Path,
) -> dict[str, str | None]:
    return {
        "repo_root": _relative_label_from_anchor(anchor_dir=out_dir, target_root=repo_root),
        "candidate_dir": _relative_label_from_anchor(anchor_dir=out_dir, target_root=candidate_dir),
        "baseline_dir": (
            _relative_label_from_anchor(anchor_dir=out_dir, target_root=baseline_dir)
            if baseline_dir is not None
            else None
        ),
        "out_dir": _relative_label_from_anchor(anchor_dir=out_dir, target_root=out_dir),
    }


def _require_dir(path: Path, *, label: str) -> None:
    if not path.is_dir():
        _fail(f"missing {label}: {path}")


def _validate_reusable_out_dir_provenance(
    *,
    repo_root: Path,
    out_dir: Path,
    candidate_dir: Path,
    baseline_dir: Path | None,
    existing_entries: list[Path],
) -> None:
    provenance_path = out_dir / PROVENANCE_JSON_NAME
    if not provenance_path.is_file():
        _fail(
            "--reuse-out-dir requires an existing helper provenance file so ownership can be verified before "
            f"managed sidecars are cleared: {provenance_path}"
        )

    try:
        provenance_payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(
            "--reuse-out-dir requires a valid helper provenance file so ownership can be verified before "
            f"managed sidecars are cleared: {provenance_path} ({exc})"
        )

    schema_version = provenance_payload.get("schema_version")
    if schema_version != 1:
        _fail(
            "--reuse-out-dir requires handoff.provenance.json with schema_version=1 so helper ownership can be "
            f"verified before managed sidecars are cleared: {provenance_path}"
        )

    recorded_out_dir = provenance_payload.get("out_dir")
    if recorded_out_dir != str(out_dir):
        _fail(
            "--reuse-out-dir requires handoff.provenance.json to record the same out_dir before managed sidecars "
            f"are cleared, found out_dir={recorded_out_dir!r} in {provenance_path}"
        )

    recorded_repo_root = provenance_payload.get("repo_root")
    if recorded_repo_root != str(repo_root):
        _fail(
            "--reuse-out-dir requires handoff.provenance.json to record the same repo_root before managed "
            f"sidecars are cleared, found repo_root={recorded_repo_root!r} in {provenance_path}"
        )

    recorded_candidate_dir = provenance_payload.get("candidate_dir")
    if recorded_candidate_dir != str(candidate_dir):
        _fail(
            "--reuse-out-dir requires handoff.provenance.json to record the same candidate_dir before managed "
            f"sidecars are cleared, found candidate_dir={recorded_candidate_dir!r} in {provenance_path}"
        )

    expected_baseline_dir = str(baseline_dir) if baseline_dir is not None else None
    recorded_baseline_dir = provenance_payload.get("baseline_dir")
    if recorded_baseline_dir != expected_baseline_dir:
        _fail(
            "--reuse-out-dir requires handoff.provenance.json to record the same baseline_dir before managed "
            f"sidecars are cleared, found baseline_dir={recorded_baseline_dir!r} in {provenance_path}"
        )

    sidecars = provenance_payload.get("sidecars")
    if not isinstance(sidecars, dict):
        _fail(
            "--reuse-out-dir requires handoff.provenance.json to declare the managed sidecar contract, "
            f"found invalid sidecars metadata: {provenance_path}"
        )

    expected_sidecars = {
        "verify_summary": VERIFY_SUMMARY_NAME,
        "verify_json": VERIFY_JSON_NAME,
        "compare_summary": COMPARE_SUMMARY_NAME,
        "compare_json": COMPARE_JSON_NAME,
        "provenance_json": PROVENANCE_JSON_NAME,
        "bundle_json": BUNDLE_JSON_NAME,
    }
    for key, expected_name in expected_sidecars.items():
        value = sidecars.get(key)
        if key.startswith("compare_") and value is None:
            continue
        if value != expected_name:
            _fail(
                "--reuse-out-dir requires handoff.provenance.json to match the helper-managed sidecar names, "
                f"found {key}={value!r} in {provenance_path}"
            )

    declared_entries = {
        VERIFY_SUMMARY_NAME,
        VERIFY_JSON_NAME,
        PROVENANCE_JSON_NAME,
        BUNDLE_JSON_NAME,
    }
    if sidecars.get("compare_summary") is not None:
        declared_entries.add(COMPARE_SUMMARY_NAME)
    if sidecars.get("compare_json") is not None:
        declared_entries.add(COMPARE_JSON_NAME)

    unexpected_entries = [
        entry for entry in existing_entries if not entry.is_file() or entry.name not in declared_entries
    ]
    if unexpected_entries:
        unexpected_entry_list = ", ".join(str(entry) for entry in unexpected_entries)
        _fail(
            "--reuse-out-dir only works when --out-dir contains the helper-managed sidecars declared by "
            f"handoff.provenance.json, found unexpected entries: {unexpected_entry_list}"
        )


def _validate_out_dir(
    *,
    repo_root: Path,
    out_dir: Path,
    candidate_dir: Path,
    baseline_dir: Path | None,
    allow_reuse: bool,
) -> None:
    protected_roots = [(candidate_dir, "candidate-dir")]
    if baseline_dir is not None:
        protected_roots.append((baseline_dir, "baseline-dir"))
    for protected_root, label in protected_roots:
        if out_dir == protected_root or _is_within(out_dir, protected_root):
            _fail(
                f"--out-dir must be outside --{label} so handoff sidecars cannot pollute the artifact tree: {out_dir}"
            )

    if out_dir.exists() and not out_dir.is_dir():
        _fail(f"--out-dir must be a directory path: {out_dir}")

    if not out_dir.is_dir():
        return

    existing_entries = sorted(out_dir.iterdir(), key=lambda path: path.name)
    if not existing_entries:
        return

    if not allow_reuse:
        _fail(
            f"--out-dir must be empty so stale handoff sidecars cannot survive across runs: {out_dir}"
        )

    _validate_reusable_out_dir_provenance(
        repo_root=repo_root,
        out_dir=out_dir,
        candidate_dir=candidate_dir,
        baseline_dir=baseline_dir,
        existing_entries=existing_entries,
    )


def _run_cli(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _format_failure(
    command: list[str],
    completed: subprocess.CompletedProcess[str],
    *,
    mirrored_summary: str | None = None,
) -> str:
    stderr_text = completed.stderr.strip()
    stdout_text = completed.stdout.strip()
    details = stderr_text
    if not details and stdout_text and stdout_text != mirrored_summary:
        details = stdout_text
    if not details:
        details = f"exit={completed.returncode}"
    return f"command failed: {' '.join(command)}\n{details}"


def _read_optional_summary(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").rstrip("\n")


def _read_optional_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _build_handoff_bundle_payload(
    *,
    candidate_dir: Path,
    baseline_dir: Path | None,
    command_exit_code: int,
    verify_summary: str | None,
    verify_json: Any | None,
    compare_summary: str | None,
    compare_json: Any | None,
    compare_executed: bool,
    compare_skipped_reason: str | None,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    path_labels = provenance.get("path_labels") if isinstance(provenance, dict) else None
    candidate_root = None
    baseline_root = None
    handoff_root = None
    if isinstance(path_labels, dict):
        candidate_label = path_labels.get("candidate_dir")
        baseline_label = path_labels.get("baseline_dir")
        out_dir_label = path_labels.get("out_dir")
        candidate_root = candidate_label if isinstance(candidate_label, str) else None
        baseline_root = baseline_label if isinstance(baseline_label, str) else None
        handoff_root = out_dir_label if isinstance(out_dir_label, str) else None

    return {
        "schema_version": 1,
        "command_status": "ok" if command_exit_code == 0 else "error",
        "command_exit_code": command_exit_code,
        "candidate_root": candidate_root,
        "baseline_root": baseline_root,
        "handoff_root": handoff_root,
        "candidate_batch_output_summary": json.loads(
            (candidate_dir / "summary.json").read_text(encoding="utf-8")
        ),
        "baseline_batch_output_summary": (
            json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            if baseline_dir is not None
            else None
        ),
        "verify": {
            "summary": verify_summary,
            "json": verify_json,
        },
        "compare": (
            {
                "summary": compare_summary,
                "json": compare_json,
                "executed": compare_executed,
                "skipped_reason": compare_skipped_reason,
            }
            if baseline_dir is not None
            else None
        ),
        "provenance": provenance,
    }


def _flag_name(token: str) -> str | None:
    if not token.startswith("-"):
        return None
    return token.split("=", 1)[0]


def _reject_reserved_passthrough_flags(
    *,
    label: str,
    passthrough_args: list[str],
    reserved_flags: set[str],
    contract_hint: str,
) -> None:
    for token in passthrough_args:
        flag_name = _flag_name(token)
        if flag_name is None:
            continue
        for reserved_flag in sorted(reserved_flags):
            if flag_name == reserved_flag or reserved_flag.startswith(flag_name):
                if flag_name == reserved_flag:
                    detail = f"reserved flag {flag_name}"
                else:
                    detail = (
                        f"reserved flag prefix {flag_name} (would resolve to {reserved_flag} via argparse abbreviation)"
                    )
                _fail(f"--{label} cannot include {detail} because {contract_hint}")


def _move_staged_sidecars(*, stage_dir: Path, out_dir: Path, names: list[str]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    moved_paths: list[Path] = []
    for name in names:
        source = stage_dir / name
        destination = out_dir / name
        source.replace(destination)
        moved_paths.append(destination)
    return moved_paths


def _existing_stage_sidecar_names(*, stage_dir: Path, names: list[str]) -> list[str]:
    return [name for name in names if (stage_dir / name).is_file()]


def _clear_reusable_out_dir(out_dir: Path) -> None:
    if not out_dir.is_dir():
        return
    for entry in sorted(out_dir.iterdir(), key=lambda path: path.name):
        if entry.is_file() and entry.name in MANAGED_SIDECAR_NAMES:
            entry.unlink()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_provenance_payload(
    *,
    repo_root: Path,
    candidate_dir: Path,
    baseline_dir: Path | None,
    out_dir: Path,
    verify_command: list[str],
    compare_command: list[str] | None,
    compare_executed: bool,
    compare_skipped_reason: str | None,
) -> dict[str, Any]:
    path_labels = _build_path_labels(
        repo_root=repo_root,
        candidate_dir=candidate_dir,
        baseline_dir=baseline_dir,
        out_dir=out_dir,
    )
    return {
        "schema_version": 1,
        "helper_command": [sys.executable, str(Path(sys.argv[0]).resolve()), *sys.argv[1:]],
        "repo_root": str(repo_root),
        "candidate_dir": str(candidate_dir),
        "baseline_dir": str(baseline_dir) if baseline_dir is not None else None,
        "out_dir": str(out_dir),
        "path_labels": path_labels,
        "sidecars": {
            "verify_summary": VERIFY_SUMMARY_NAME,
            "verify_json": VERIFY_JSON_NAME,
            "compare_summary": COMPARE_SUMMARY_NAME if baseline_dir is not None else None,
            "compare_json": COMPARE_JSON_NAME if baseline_dir is not None else None,
            "provenance_json": PROVENANCE_JSON_NAME,
            "bundle_json": BUNDLE_JSON_NAME,
        },
        "verify": {
            "command": verify_command,
            "summary_sidecar": VERIFY_SUMMARY_NAME,
            "json_sidecar": VERIFY_JSON_NAME,
        },
        "compare": (
            {
                "command": compare_command,
                "summary_sidecar": COMPARE_SUMMARY_NAME,
                "json_sidecar": COMPARE_JSON_NAME,
                "executed": compare_executed,
                "skipped_reason": compare_skipped_reason,
            }
            if compare_command is not None
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export the operator handoff gold path for an eval batch artifact tree: standalone verify sidecars plus optional compare sidecars against a baseline, with labeled verify/compare summaries mirrored to the terminal and compare automatically skipped when verify fails."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root path (default: auto-detected from script location).",
    )
    parser.add_argument(
        "--candidate-dir",
        required=True,
        help="Batch artifact directory to verify and, if --baseline-dir is set, compare.",
    )
    parser.add_argument(
        "--baseline-dir",
        default=None,
        help="Optional baseline artifact directory for standalone compare exports.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help=(
            "Output directory for handoff sidecars. Must be outside the candidate and baseline artifact trees."
        ),
    )
    parser.add_argument(
        "--verify-arg",
        action="append",
        default=[],
        help=(
            "Extra argument appended to the standalone verify command. Repeat per token, for example "
            "--verify-arg=--batch-output-verify-profile --verify-arg=triage-by-status."
        ),
    )
    parser.add_argument(
        "--compare-arg",
        action="append",
        default=[],
        help=(
            "Extra argument appended to the standalone compare command. Repeat per token, for example "
            "--compare-arg=--batch-output-compare-profile --compare-arg=clean."
        ),
    )
    parser.add_argument(
        "--keep-failed-out-dir",
        action="store_true",
        help=(
            "preserve any generated verify/compare sidecars under --out-dir when verify or compare fails, "
            "so operators can inspect the failed handoff without rerunning the underlying commands"
        ),
    )
    parser.add_argument(
        "--reuse-out-dir",
        action="store_true",
        help=(
            "reuse an existing --out-dir when it contains helper-managed sidecars only, clearing those sidecars "
            "before the next run so operators can retry a preserved handoff without manual cleanup"
        ),
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    candidate_dir = Path(args.candidate_dir).expanduser().resolve()
    baseline_dir = (
        Path(args.baseline_dir).expanduser().resolve()
        if args.baseline_dir is not None
        else None
    )
    out_dir = Path(args.out_dir).expanduser().resolve()

    _require_dir(repo_root, label="repo root")
    _require_dir(candidate_dir, label="candidate artifact directory")
    if baseline_dir is not None:
        _require_dir(baseline_dir, label="baseline artifact directory")
        if baseline_dir == candidate_dir:
            _fail(
                "--baseline-dir must differ from --candidate-dir so handoff compare cannot silently self-compare the same artifact tree: "
                f"{candidate_dir}"
            )
    elif args.compare_arg:
        _fail("--compare-arg requires --baseline-dir")
    _reject_reserved_passthrough_flags(
        label="verify-arg",
        passthrough_args=args.verify_arg,
        reserved_flags={
            "--batch-output-verify",
            "--summary",
            "--output",
            "--summary-file",
            "--json-file",
            "--batch-output-verify-summary-file",
            "--batch-output-verify-json-file",
        },
        contract_hint="export_eval_handoff already controls the verify target, stdout mode, and --out-dir sidecars",
    )
    _reject_reserved_passthrough_flags(
        label="compare-arg",
        passthrough_args=args.compare_arg,
        reserved_flags={
            "--batch-output-compare",
            "--batch-output-compare-against",
            "--summary",
            "--output",
            "--summary-file",
            "--json-file",
            "--batch-output-compare-summary-file",
            "--batch-output-compare-json-file",
        },
        contract_hint="export_eval_handoff already controls the compare target, stdout mode, and --out-dir sidecars",
    )
    _validate_out_dir(
        repo_root=repo_root,
        out_dir=out_dir,
        candidate_dir=candidate_dir,
        baseline_dir=baseline_dir,
        allow_reuse=bool(args.reuse_out_dir),
    )

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if args.reuse_out_dir:
        _clear_reusable_out_dir(out_dir)
    stage_dir = Path(
        tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp-", dir=str(out_dir.parent))
    ).resolve()

    try:
        verify_summary = stage_dir / VERIFY_SUMMARY_NAME
        verify_json = stage_dir / VERIFY_JSON_NAME
        compare_summary = stage_dir / COMPARE_SUMMARY_NAME
        compare_json = stage_dir / COMPARE_JSON_NAME
        provenance_json = stage_dir / PROVENANCE_JSON_NAME
        handoff_bundle_json = stage_dir / BUNDLE_JSON_NAME

        verify_command = [
            sys.executable,
            "-m",
            "cli.main",
            "eval",
            "--batch-output-verify",
            str(candidate_dir),
            "--summary",
            "--batch-output-verify-summary-file",
            str(verify_summary),
            "--batch-output-verify-json-file",
            str(verify_json),
            *args.verify_arg,
        ]
        verify_run = _run_cli(repo_root, *verify_command[3:])

        compare_run: subprocess.CompletedProcess[str] | None = None
        compare_command: list[str] | None = None
        compare_executed = False
        compare_skipped_reason: str | None = None
        if baseline_dir is not None:
            compare_command = [
                sys.executable,
                "-m",
                "cli.main",
                "eval",
                "--batch-output-compare",
                str(candidate_dir),
                "--batch-output-compare-against",
                str(baseline_dir),
                "--summary",
                "--batch-output-compare-summary-file",
                str(compare_summary),
                "--batch-output-compare-json-file",
                str(compare_json),
                *args.compare_arg,
            ]
            if verify_run.returncode == 0:
                compare_run = _run_cli(repo_root, *compare_command[3:])
                compare_executed = True
            else:
                compare_skipped_reason = "verify_failed"

        provenance_payload = _build_provenance_payload(
            repo_root=repo_root,
            candidate_dir=candidate_dir,
            baseline_dir=baseline_dir,
            out_dir=out_dir,
            verify_command=verify_command,
            compare_command=compare_command,
            compare_executed=compare_executed,
            compare_skipped_reason=compare_skipped_reason,
        )
        _write_json(provenance_json, provenance_payload)

        verify_summary_text = _read_optional_summary(verify_summary)
        compare_summary_text = _read_optional_summary(compare_summary)
        verify_json_payload = _read_optional_json(verify_json)
        compare_json_payload = _read_optional_json(compare_json)

        failures: list[str] = []
        if verify_run.returncode != 0:
            failures.append(
                _format_failure(
                    verify_command,
                    verify_run,
                    mirrored_summary=verify_summary_text,
                )
            )
        if compare_run is not None and compare_command is not None and compare_run.returncode != 0:
            failures.append(
                _format_failure(
                    compare_command,
                    compare_run,
                    mirrored_summary=compare_summary_text,
                )
            )

        command_exit_code = 1 if failures else 0
        _write_json(
            handoff_bundle_json,
            _build_handoff_bundle_payload(
                candidate_dir=candidate_dir,
                baseline_dir=baseline_dir,
                command_exit_code=command_exit_code,
                verify_summary=verify_summary_text,
                verify_json=verify_json_payload,
                compare_summary=compare_summary_text,
                compare_json=compare_json_payload,
                compare_executed=compare_executed,
                compare_skipped_reason=compare_skipped_reason,
                provenance=provenance_payload,
            ),
        )

        if failures:
            message_sections: list[str] = []
            if verify_summary_text is not None:
                message_sections.append(f"verify: {verify_summary_text}")
            if compare_summary_text is not None:
                message_sections.append(f"compare: {compare_summary_text}")
            elif compare_skipped_reason == "verify_failed":
                message_sections.append("compare: skipped because verify failed")
            if args.keep_failed_out_dir:
                preserved_sidecar_names = _existing_stage_sidecar_names(
                    stage_dir=stage_dir,
                    names=[
                        VERIFY_SUMMARY_NAME,
                        VERIFY_JSON_NAME,
                        COMPARE_SUMMARY_NAME,
                        COMPARE_JSON_NAME,
                        PROVENANCE_JSON_NAME,
                        BUNDLE_JSON_NAME,
                    ],
                )
                if preserved_sidecar_names:
                    preserved_paths = _move_staged_sidecars(
                        stage_dir=stage_dir,
                        out_dir=out_dir,
                        names=preserved_sidecar_names,
                    )
                    message_sections.append(
                        "preserved failed handoff sidecars:\n"
                        + "\n".join(
                            f"- {_display_path(path, repo_root)}" for path in preserved_paths
                        )
                    )
            message_sections.extend(failures)
            _fail("\n\n".join(message_sections))

        verify_summary_text = verify_summary.read_text(encoding="utf-8").rstrip("\n")
        compare_summary_text = (
            compare_summary.read_text(encoding="utf-8").rstrip("\n")
            if baseline_dir is not None
            else None
        )

        exported_paths = _move_staged_sidecars(
            stage_dir=stage_dir,
            out_dir=out_dir,
            names=[
                VERIFY_SUMMARY_NAME,
                VERIFY_JSON_NAME,
                *(
                    [COMPARE_SUMMARY_NAME, COMPARE_JSON_NAME]
                    if baseline_dir is not None
                    else []
                ),
                PROVENANCE_JSON_NAME,
                BUNDLE_JSON_NAME,
            ],
        )

        print("exported eval handoff sidecars:")
        for exported_path in exported_paths:
            print(f"- {_display_path(exported_path, repo_root)}")
        print(f"verify: {verify_summary_text}")
        if compare_summary_text is not None:
            print(f"compare: {compare_summary_text}")
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
