#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BENCHMARK_RESULT_REL = Path("bench/token-harness/results/latest.json")
ARTIFACT_DIR_REL = Path("docs/release-artifacts")
PAIR_FLOOR = 10
CALIBRATION_PAIR_FLOOR = 2


def _fail(message: str) -> "NoReturn":
    raise SystemExit(f"release_snapshot: {message}")


def _parse_timestamp_utc(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(timezone.utc)

    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        _fail(f"invalid --timestamp-utc value: {raw}")

    if parsed.tzinfo is None:
        _fail("--timestamp-utc must include timezone information")
    return parsed.astimezone(timezone.utc)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _fail(f"benchmark payload missing: {path}")
    except json.JSONDecodeError:
        _fail(f"benchmark payload is not valid JSON: {path}")

    if not isinstance(payload, dict):
        _fail("benchmark payload root must be an object")
    return payload


def _require_object(mapping: dict[str, Any], key: str, *, path: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        _fail(f"missing object at {path}.{key}")
    return value


def _require_number(mapping: dict[str, Any], key: str, *, path: str) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"missing numeric field at {path}.{key}")
    return float(value)


def _require_bool(mapping: dict[str, Any], key: str, *, path: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        _fail(f"missing boolean field at {path}.{key}")
    return value


def _require_list(mapping: dict[str, Any], key: str, *, path: str) -> list[Any]:
    value = mapping.get(key)
    if not isinstance(value, list):
        _fail(f"missing list field at {path}.{key}")
    return value


def _count_calibration_pairs(pairs: list[Any]) -> int:
    count = 0
    for index, row in enumerate(pairs):
        if not isinstance(row, dict):
            _fail(f"pair row must be object at pairs[{index}]")
        name = row.get("name")
        if not isinstance(name, str):
            _fail(f"pair row missing string name at pairs[{index}].name")
        if name.startswith("calibration_"):
            count += 1
    return count


def _build_snapshot_payload(*, benchmark_payload: dict[str, Any], snapshot_time_utc: datetime) -> dict[str, Any]:
    summary = _require_object(benchmark_payload, "summary", path="root")
    totals = _require_object(summary, "totals", path="summary")
    target = _require_object(summary, "target", path="summary")
    pairs = _require_list(benchmark_payload, "pairs", path="root")

    pair_count = int(_require_number(summary, "pair_count", path="summary"))
    if pair_count != len(pairs):
        _fail("summary.pair_count must match len(pairs)")

    baseline_tokens = int(_require_number(totals, "baseline_tokens", path="summary.totals"))
    erz_tokens = int(_require_number(totals, "erz_tokens", path="summary.totals"))
    token_saving_pct = _require_number(totals, "token_saving_pct", path="summary.totals")
    target_pct = _require_number(target, "token_saving_pct", path="summary.target")
    target_met = _require_bool(target, "met", path="summary.target")

    benchmark_meta = benchmark_payload.get("meta")
    benchmark_generated_at = None
    if isinstance(benchmark_meta, dict):
        meta_value = benchmark_meta.get("generated_at_utc")
        if isinstance(meta_value, str):
            benchmark_generated_at = meta_value

    calibration_pair_count = _count_calibration_pairs(pairs)

    return {
        "meta": {
            "snapshot_generated_at_utc": snapshot_time_utc.isoformat(),
            "benchmark_generated_at_utc": benchmark_generated_at,
            "benchmark_result_path": str(BENCHMARK_RESULT_REL),
            "full_lane_entrypoint": "./scripts/check.sh",
            "source_of_truth_rule": (
                "bench/token-harness/results/latest.json is repo-pinned for non-mutating gate runs; "
                "docs/release-artifacts/latest.json is the freshness source-of-truth."
            ),
        },
        "quality_gate_snapshot": {
            "gate": "B4 benchmark harness",
            "baseline_tokens": baseline_tokens,
            "erz_tokens": erz_tokens,
            "token_saving_pct": round(token_saving_pct, 2),
            "target_pct": round(target_pct, 2),
            "target_met": target_met,
            "pair_count": pair_count,
            "pair_floor": PAIR_FLOOR,
            "pair_floor_met": pair_count >= PAIR_FLOOR,
            "calibration_pair_count": calibration_pair_count,
            "calibration_pair_floor": CALIBRATION_PAIR_FLOOR,
            "calibration_pair_floor_met": calibration_pair_count >= CALIBRATION_PAIR_FLOOR,
        },
        "benchmark_summary": summary,
    }


def _render_markdown(snapshot: dict[str, Any]) -> str:
    meta = snapshot["meta"]
    gate = snapshot["quality_gate_snapshot"]

    lines = [
        "# Release Snapshot",
        "",
        f"- Snapshot generated (UTC): `{meta['snapshot_generated_at_utc']}`",
        f"- Benchmark source file: `{meta['benchmark_result_path']}`",
        f"- Benchmark payload generated (UTC): `{meta['benchmark_generated_at_utc'] or 'unknown'}`",
        f"- Full-lane entrypoint: `{meta['full_lane_entrypoint']}`",
        "",
        "## Benchmark Gate (B4)",
        f"- Token saving: `{gate['baseline_tokens']} -> {gate['erz_tokens']}` (`{gate['token_saving_pct']:.2f}%`)",
        f"- Target: `>= {gate['target_pct']:.2f}%` -> `{'met' if gate['target_met'] else 'not met'}`",
        f"- Fixture floor: `{gate['pair_count']}/{gate['pair_floor']}` -> `{'met' if gate['pair_floor_met'] else 'not met'}`",
        (
            f"- Calibration fixture floor: `{gate['calibration_pair_count']}/{gate['calibration_pair_floor']}` "
            f"-> `{'met' if gate['calibration_pair_floor_met'] else 'not met'}`"
        ),
        "",
        "## Source-of-truth rule",
        f"- {meta['source_of_truth_rule']}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export release snapshot artifacts for benchmark + gate evidence.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root path (default: auto-detected from script location).",
    )
    parser.add_argument(
        "--timestamp-utc",
        default=None,
        help="Optional ISO-8601 timestamp with timezone for deterministic snapshots.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    benchmark_path = repo_root / BENCHMARK_RESULT_REL
    artifact_dir = repo_root / ARTIFACT_DIR_REL

    snapshot_time_utc = _parse_timestamp_utc(args.timestamp_utc)
    benchmark_payload = _load_json(benchmark_path)
    snapshot = _build_snapshot_payload(
        benchmark_payload=benchmark_payload,
        snapshot_time_utc=snapshot_time_utc,
    )

    stamp = snapshot_time_utc.strftime("%Y%m%dT%H%M%SZ")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    snapshot_json = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
    snapshot_md = _render_markdown(snapshot)

    dated_json = artifact_dir / f"release-snapshot-{stamp}.json"
    dated_md = artifact_dir / f"release-snapshot-{stamp}.md"
    latest_json = artifact_dir / "latest.json"
    latest_md = artifact_dir / "latest.md"

    dated_json.write_text(snapshot_json, encoding="utf-8")
    dated_md.write_text(snapshot_md, encoding="utf-8")
    latest_json.write_text(snapshot_json, encoding="utf-8")
    latest_md.write_text(snapshot_md, encoding="utf-8")

    print(f"wrote {dated_json.relative_to(repo_root)}")
    print(f"wrote {dated_md.relative_to(repo_root)}")
    print(f"updated {latest_json.relative_to(repo_root)}")
    print(f"updated {latest_md.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
