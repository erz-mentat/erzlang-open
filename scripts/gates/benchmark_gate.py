from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NoReturn


RESULT_PATH = Path("bench/token-harness/results/latest.json")
MIN_PAIR_COUNT = 10
MIN_CALIBRATION_PAIR_COUNT = 2
CALIBRATION_PREFIX = "calibration_"
GATE_NAME = "benchmark_gate"


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"gate failure [{GATE_NAME}]: {message}")


def _require_object(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"Malformed benchmark summary: expected object at `{path}`")
    return value


def _require_key(
    mapping: dict[str, Any],
    key: str,
    *,
    path: str,
    category: str = "Malformed benchmark summary",
) -> Any:
    if key not in mapping:
        _fail(f"{category}: missing key `{path}.{key}`")
    return mapping[key]


def _require_number(value: Any, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"Malformed benchmark summary: expected number at `{path}`")
    return float(value)


def _require_int(value: Any, *, path: str) -> int:
    number = _require_number(value, path=path)
    if int(number) != number:
        _fail(f"Malformed benchmark summary: expected integer at `{path}`")
    return int(number)


def _require_bool(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"Malformed benchmark summary: expected boolean at `{path}`")
    return value


def _require_string(value: Any, *, path: str, category: str = "Malformed benchmark payload") -> str:
    if not isinstance(value, str):
        _fail(f"{category}: expected string at `{path}`")
    return value


def _is_calibration_fixture(name: str) -> bool:
    # Policy is intentionally strict/case-sensitive for stable fixture naming:
    # only names starting with the exact lowercase `calibration_` prefix count.
    return name.startswith(CALIBRATION_PREFIX)


def _load_payload() -> dict[str, Any]:
    try:
        raw = RESULT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        _fail(f"Benchmark result file missing: {RESULT_PATH}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _fail(f"Benchmark result file is not valid JSON: {RESULT_PATH}")

    return _require_object(payload, path="root")


def main() -> None:
    payload = _load_payload()

    summary = _require_object(_require_key(payload, "summary", path="root"), path="summary")
    totals = _require_object(_require_key(summary, "totals", path="summary"), path="summary.totals")
    target = _require_object(_require_key(summary, "target", path="summary"), path="summary.target")

    baseline_tokens = _require_number(
        _require_key(totals, "baseline_tokens", path="summary.totals"),
        path="summary.totals.baseline_tokens",
    )
    erz_tokens = _require_number(
        _require_key(totals, "erz_tokens", path="summary.totals"),
        path="summary.totals.erz_tokens",
    )
    token_saving_pct = _require_number(
        _require_key(totals, "token_saving_pct", path="summary.totals"),
        path="summary.totals.token_saving_pct",
    )

    target_pct = _require_number(
        _require_key(target, "token_saving_pct", path="summary.target"),
        path="summary.target.token_saving_pct",
    )
    target_met = _require_bool(
        _require_key(target, "met", path="summary.target"),
        path="summary.target.met",
    )

    pair_count = _require_int(
        _require_key(summary, "pair_count", path="summary"),
        path="summary.pair_count",
    )

    pairs = _require_key(
        payload,
        "pairs",
        path="root",
        category="Malformed benchmark payload",
    )
    if not isinstance(pairs, list):
        _fail("Malformed benchmark payload: expected list at `pairs`")

    if pair_count != len(pairs):
        _fail(
            "Malformed benchmark summary: `summary.pair_count` does not match `len(pairs)`"
        )

    calibration_pair_count = 0
    for index, row in enumerate(pairs):
        if not isinstance(row, dict):
            _fail(f"Malformed benchmark payload: expected object at `pairs[{index}]`")

        if "name" not in row:
            _fail(f"Malformed benchmark payload: missing key `pairs[{index}].name`")
        pair_name = _require_string(row["name"], path=f"pairs[{index}].name")
        if _is_calibration_fixture(pair_name):
            calibration_pair_count += 1

    print(
        "  token saving: "
        f"{baseline_tokens:g} -> {erz_tokens:g} "
        f"({token_saving_pct:.2f}%)"
    )
    print(f"  target >= {target_pct:.1f}%: {'met' if target_met else 'not met'}")
    print(f"  fixture pairs: {pair_count} (min {MIN_PAIR_COUNT})")
    print(f"  calibration fixture pairs: {calibration_pair_count} (min {MIN_CALIBRATION_PAIR_COUNT})")

    if not target_met:
        _fail("Benchmark token-saving target not met")
    if pair_count < MIN_PAIR_COUNT:
        _fail(f"Benchmark fixture floor not met: expected at least {MIN_PAIR_COUNT} pairs")
    if calibration_pair_count < MIN_CALIBRATION_PAIR_COUNT:
        _fail(
            "Calibration fixture floor not met: "
            f"expected at least {MIN_CALIBRATION_PAIR_COUNT} pairs"
        )


if __name__ == "__main__":
    main()
