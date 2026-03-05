from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from compact import CompactError, parse_compact


DEFAULT_CASES_PATH = Path("examples/fewshot/cases.json")


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("fewshot cases file must contain a JSON array")
    return payload


def validate_cases(cases: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []

    if len(cases) != 12:
        failures.append(f"Expected exactly 12 cases, found {len(cases)}")

    seen_ids: set[str] = set()

    for index, case in enumerate(cases):
        label = f"case[{index}]"
        case_id = case.get("id")

        if not isinstance(case_id, str) or not case_id:
            failures.append(f"{label}: missing non-empty string 'id'")
            continue

        if case_id in seen_ids:
            failures.append(f"{case_id}: duplicate id")
            continue
        seen_ids.add(case_id)

        valid = case.get("valid")
        source = case.get("source")
        reason = case.get("reason")

        if not isinstance(valid, bool):
            failures.append(f"{case_id}: field 'valid' must be boolean")
            continue
        if not isinstance(source, str):
            failures.append(f"{case_id}: field 'source' must be string")
            continue
        if not isinstance(reason, str) or not reason.strip():
            failures.append(f"{case_id}: field 'reason' must be non-empty string")
            continue

        error_fragment = case.get("expect_error_contains")
        if not valid and (not isinstance(error_fragment, str) or not error_fragment):
            failures.append(
                f"{case_id}: invalid case must include non-empty 'expect_error_contains'"
            )
            continue

        try:
            parse_compact(source)
        except CompactError as exc:
            if valid:
                failures.append(f"{case_id}: expected valid, got error: {exc}")
                continue
            assert isinstance(error_fragment, str)
            if error_fragment not in str(exc):
                failures.append(
                    f"{case_id}: expected error containing {error_fragment!r}, got {str(exc)!r}"
                )
        else:
            if not valid:
                failures.append(f"{case_id}: expected invalid but parse succeeded")

    valid_count = sum(1 for c in cases if c.get("valid") is True)
    invalid_count = sum(1 for c in cases if c.get("valid") is False)
    if valid_count == 0 or invalid_count == 0:
        failures.append("Need both valid and invalid cases")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate few-shot compact DSL examples")
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help=f"path to few-shot cases JSON (default: {DEFAULT_CASES_PATH})",
    )
    args = parser.parse_args()

    cases = load_cases(args.cases)
    failures = validate_cases(cases)

    if failures:
        print("fewshot validation: FAILED", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"fewshot validation: ok ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
