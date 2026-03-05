from __future__ import annotations

import json
import re
from pathlib import Path
import sys
from typing import Any, NoReturn

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.eval import TRACE_OPTIONAL_FIELDS, TRACE_REQUIRED_FIELDS


SCHEMA_PATH = Path("schema/ir.v0.1.schema.json")
MIGRATIONS_DOC_PATH = Path("docs/migrations.md")
QUALITY_GATES_DOC_PATH = Path("docs/quality-gates.md")
GATE_NAME = "migration_anchor_gate"


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"gate failure [{GATE_NAME}]: {message}")


def _require_object(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"Malformed migration gate input: expected object at `{path}`")
    return value


def parse_anchor_tokens(*, text: str, prefix: str, doc_name: str) -> list[str]:
    for line in text.splitlines():
        if line.startswith(prefix):
            tokens = re.findall(r"`([^`]+)`", line)
            if not tokens:
                _fail(f"{doc_name}: anchor line has no backticked tokens: {prefix}")

            duplicates: list[str] = []
            seen: set[str] = set()
            for token in tokens:
                if token in seen and token not in duplicates:
                    duplicates.append(token)
                seen.add(token)
            if duplicates:
                duplicate_text = ", ".join(duplicates)
                _fail(
                    f"{doc_name}: anchor line has duplicate tokens: {prefix} -> {duplicate_text}"
                )

            return tokens
    _fail(f"{doc_name}: missing required anchor line: {prefix}")


def _normalize_heading_token(value: str) -> str:
    return " ".join(value.strip().split())


def _profile_matches_heading(*, profile: str, heading: str) -> bool:
    normalized_profile = _normalize_heading_token(profile)
    normalized_heading = _normalize_heading_token(heading)
    if normalized_heading == normalized_profile:
        return True

    parenthetical_tokens = re.findall(r"\(([^()]+)\)", heading)
    return bool(parenthetical_tokens) and _normalize_heading_token(parenthetical_tokens[-1]) == normalized_profile


def _iter_level2_headings_outside_fenced_code_blocks(text: str) -> list[str]:
    # Fence handling intentionally supports both backtick and tilde fences,
    # including language-tagged openers (for example ```md or ~~~markdown).
    headings: list[str] = []
    in_fenced_code_block = False
    fence_char = ""
    fence_len = 0

    for line in text.splitlines():
        stripped = line.lstrip()
        fence_match = re.match(r"^([`~]{3,})(.*)$", stripped)
        if fence_match:
            marker = fence_match.group(1)
            marker_char = marker[0]
            marker_len = len(marker)
            marker_suffix = fence_match.group(2)

            if not in_fenced_code_block:
                in_fenced_code_block = True
                fence_char = marker_char
                fence_len = marker_len
                continue

            if (
                marker_char == fence_char
                and marker_len >= fence_len
                and marker_suffix.strip() == ""
            ):
                in_fenced_code_block = False
                fence_char = ""
                fence_len = 0
                continue

        if in_fenced_code_block:
            continue

        if line.startswith("## "):
            headings.append(line[3:].strip())

    return headings


def _is_migration_entry_heading(heading: str) -> bool:
    return bool(re.search(r"\S\s*->\s*\S", heading))


def main() -> None:
    try:
        schema_raw = SCHEMA_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        _fail(f"Schema file missing: {SCHEMA_PATH}")

    try:
        schema = json.loads(schema_raw)
    except json.JSONDecodeError:
        _fail(f"Schema file is not valid JSON: {SCHEMA_PATH}")

    schema_obj = _require_object(schema, path="root")
    defs = _require_object(schema_obj.get("$defs", {}), path="$defs")
    trace_schema = _require_object(defs.get("trace", {}), path="$defs.trace")

    required_in_schema = set(trace_schema.get("required", []))
    properties_in_schema = set(trace_schema.get("properties", {}).keys())

    active_required = [field for field in TRACE_REQUIRED_FIELDS if field in required_in_schema]
    active_optional = [field for field in TRACE_OPTIONAL_FIELDS if field in properties_in_schema]

    try:
        migrations_doc = MIGRATIONS_DOC_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        _fail(f"Required doc missing: {MIGRATIONS_DOC_PATH}")

    try:
        quality_gates_doc = QUALITY_GATES_DOC_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        _fail(f"Required doc missing: {QUALITY_GATES_DOC_PATH}")

    required_in_migrations = parse_anchor_tokens(
        text=migrations_doc,
        prefix="- Gate anchor trace required:",
        doc_name=str(MIGRATIONS_DOC_PATH),
    )
    optional_in_migrations = parse_anchor_tokens(
        text=migrations_doc,
        prefix="- Gate anchor trace optional:",
        doc_name=str(MIGRATIONS_DOC_PATH),
    )
    profiles_in_migrations = parse_anchor_tokens(
        text=migrations_doc,
        prefix="- Gate anchor profiles:",
        doc_name=str(MIGRATIONS_DOC_PATH),
    )
    profiles_in_quality_gates = parse_anchor_tokens(
        text=quality_gates_doc,
        prefix="- Gate anchor profiles:",
        doc_name=str(QUALITY_GATES_DOC_PATH),
    )

    errors: list[str] = []
    if required_in_migrations != active_required:
        errors.append(
            "trace required field anchor drift: "
            f"expected {active_required}, got {required_in_migrations}"
        )
    if optional_in_migrations != active_optional:
        errors.append(
            "trace optional field anchor drift: "
            f"expected {active_optional}, got {optional_in_migrations}"
        )
    if profiles_in_migrations != profiles_in_quality_gates:
        errors.append(
            "active profile anchor drift between docs/migrations.md and docs/quality-gates.md: "
            f"{profiles_in_migrations} vs {profiles_in_quality_gates}"
        )

    migration_headings = [
        heading
        for heading in _iter_level2_headings_outside_fenced_code_blocks(migrations_doc)
        if _is_migration_entry_heading(heading)
    ]
    missing_profile_headings = [
        profile
        for profile in profiles_in_migrations
        if not any(_profile_matches_heading(profile=profile, heading=heading) for heading in migration_headings)
    ]
    if missing_profile_headings:
        errors.append(
            "profile anchor missing from migration headings: " + ", ".join(missing_profile_headings)
        )

    duplicated_profile_heading_refs: list[str] = []
    for profile in profiles_in_migrations:
        match_count = sum(
            1
            for heading in migration_headings
            if _profile_matches_heading(profile=profile, heading=heading)
        )
        if match_count > 1:
            duplicated_profile_heading_refs.append(f"{profile} ({match_count})")
    if duplicated_profile_heading_refs:
        errors.append(
            "profile anchor maps to multiple migration headings: "
            + ", ".join(duplicated_profile_heading_refs)
        )

    if errors:
        _fail("; ".join(errors))

    print("  ok: migration doc anchors match active trace fields and profile references")


if __name__ == "__main__":
    main()
