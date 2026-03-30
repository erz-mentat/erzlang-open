#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

DEFAULT_FIXTURE_ROOT_REL = Path("examples/program-packs")
PROGRAM_PACK_INDEX_REL = Path("program-pack-index.json")
AGGREGATE_OUTPUT_STEM = "program-pack-index"


def _output_paths_for_stem(stem: str) -> tuple[str, str, str]:
    return (
        f"{stem}.replay.expected.summary.txt",
        f"{stem}.replay.expected.json",
        f"{stem}.replay.handoff-bundle.expected.json",
    )


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"refresh_program_pack_replay_contracts: {message}")


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


def _normalize_path_string(value: str, fixture_root: Path) -> str:
    path = Path(value)
    if not path.is_absolute():
        return value
    try:
        return str(path.relative_to(fixture_root))
    except ValueError:
        return value


def _normalize_replay_payload_paths(node: Any, fixture_root: Path) -> Any:
    if isinstance(node, dict):
        normalized: dict[str, Any] = {}
        for key, value in node.items():
            if key in {"target_path", "program_path", "baseline_path"} and isinstance(value, str):
                normalized[key] = _normalize_path_string(value, fixture_root)
            else:
                normalized[key] = _normalize_replay_payload_paths(value, fixture_root)
        return normalized
    if isinstance(node, list):
        return [_normalize_replay_payload_paths(item, fixture_root) for item in node]
    return node


def _rewrite_json_with_normalized_paths(path: Path, fixture_root: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    normalized = _normalize_replay_payload_paths(payload, fixture_root)
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_index_entry_path(entry: Any, *, index_path: Path, position: int) -> Path:
    if isinstance(entry, str):
        raw_path = entry
    elif isinstance(entry, dict) and isinstance(entry.get("path"), str):
        raw_path = entry["path"]
    else:
        _fail(
            f"invalid program-pack index entry #{position} in {index_path}: expected string or object with string 'path'"
        )
    normalized = raw_path.strip()
    if not normalized:
        _fail(f"invalid program-pack index entry #{position} in {index_path}: empty path")
    pack_rel = Path(normalized)
    if pack_rel.is_absolute() or any(part == ".." for part in pack_rel.parts):
        _fail(
            f"invalid program-pack index entry #{position} in {index_path}: path must stay within the fixture root"
        )
    return pack_rel


def _load_pack_contracts(fixture_root: Path) -> list[dict[str, Any]]:
    pack_index = fixture_root / PROGRAM_PACK_INDEX_REL
    _require_file(pack_index, label="program-pack index")

    payload = json.loads(pack_index.read_text(encoding="utf-8"))
    raw_entries = payload.get("packs") if isinstance(payload, dict) else None
    if not isinstance(raw_entries, list) or not raw_entries:
        _fail(f"program-pack index must contain a non-empty 'packs' array: {pack_index}")

    contracts: list[dict[str, Any]] = []
    seen_pack_paths: set[str] = set()
    seen_output_stems: set[str] = set()
    for index, entry in enumerate(raw_entries, start=1):
        pack_rel = _parse_index_entry_path(entry, index_path=pack_index, position=index)
        pack_rel_text = str(pack_rel)
        if pack_rel_text in seen_pack_paths:
            _fail(f"duplicate pack path in {pack_index}: {pack_rel_text}")
        seen_pack_paths.add(pack_rel_text)

        output_stem = pack_rel.name
        if not output_stem:
            _fail(f"invalid program-pack index entry #{index} in {pack_index}: missing terminal path name")
        if output_stem in seen_output_stems:
            _fail(
                f"program-pack index entries in {pack_index} would collide on output stem '{output_stem}'"
            )
        seen_output_stems.add(output_stem)

        contracts.append(
            {
                "pack_rel": pack_rel,
                "strict_profile": f"{output_stem}-clean",
                "output_stem": output_stem,
            }
        )
    return contracts


def _generated_paths_for_contracts(contracts: list[dict[str, Any]]) -> list[str]:
    return [
        relative_path
        for contract in contracts
        for relative_path in _output_paths_for_stem(str(contract["output_stem"]))
    ] + list(_output_paths_for_stem(AGGREGATE_OUTPUT_STEM))


def _refresh_generated_outputs(repo_root: Path, fixture_root: Path) -> list[str]:
    _require_dir(fixture_root, label="fixture root")
    contracts = _load_pack_contracts(fixture_root)
    generated_paths = _generated_paths_for_contracts(contracts)
    pack_index = fixture_root / PROGRAM_PACK_INDEX_REL

    for contract in contracts:
        pack_dir = fixture_root / contract["pack_rel"]
        _require_dir(pack_dir, label=f"{contract['output_stem']} pack")

    for relative_path in generated_paths:
        _remove_path(fixture_root / relative_path)

    generated_json_paths: list[Path] = []
    for contract in contracts:
        output_stem = contract["output_stem"]
        summary_rel, json_rel, bundle_rel = _output_paths_for_stem(output_stem)
        summary_path = fixture_root / summary_rel
        json_path = fixture_root / json_rel
        bundle_path = fixture_root / bundle_rel
        _run_cli(
            repo_root,
            "pack-replay",
            str(fixture_root / contract["pack_rel"]),
            "--summary",
            "--strict-profile",
            contract["strict_profile"],
            "--summary-file",
            str(summary_path),
            "--json-file",
            str(json_path),
            "--handoff-bundle-file",
            str(bundle_path),
        )
        generated_json_paths.extend([json_path, bundle_path])

    aggregate_summary_rel, aggregate_json_rel, aggregate_bundle_rel = _output_paths_for_stem(
        AGGREGATE_OUTPUT_STEM
    )
    aggregate_summary = fixture_root / aggregate_summary_rel
    aggregate_json = fixture_root / aggregate_json_rel
    aggregate_bundle = fixture_root / aggregate_bundle_rel

    _run_cli(
        repo_root,
        "pack-replay",
        str(pack_index),
        "--summary",
        "--strict-profile",
        "program-pack-index-clean",
        "--summary-file",
        str(aggregate_summary),
        "--json-file",
        str(aggregate_json),
        "--handoff-bundle-file",
        str(aggregate_bundle),
    )

    generated_json_paths.extend([aggregate_json, aggregate_bundle])
    for json_path in generated_json_paths:
        _rewrite_json_with_normalized_paths(json_path, fixture_root)

    return generated_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the checked-in program-pack replay summary/json/handoff snapshots in one deterministic pass."
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
            "Program-pack fixture root to rewrite. Defaults to <repo-root>/examples/program-packs."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    fixture_root = (
        Path(args.fixture_root).expanduser().resolve()
        if args.fixture_root is not None
        else (repo_root / DEFAULT_FIXTURE_ROOT_REL)
    )

    generated_paths = _refresh_generated_outputs(repo_root, fixture_root)

    print("refreshed program-pack replay contract outputs:")
    for relative_path in generated_paths:
        print(f"- {_display_path(fixture_root / relative_path, repo_root)}")


if __name__ == "__main__":
    main()
