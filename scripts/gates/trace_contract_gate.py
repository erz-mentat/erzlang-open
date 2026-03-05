from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.eval import TRACE_OPTIONAL_FIELDS, TRACE_REQUIRED_FIELDS


SCHEMA_PATH = Path("schema/ir.v0.1.schema.json")
GATE_NAME = "trace_contract_gate"


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"gate failure [{GATE_NAME}]: {message}")


def main() -> None:
    try:
        raw_schema = SCHEMA_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        _fail(f"Schema file missing: {SCHEMA_PATH}")

    try:
        schema = json.loads(raw_schema)
    except json.JSONDecodeError:
        _fail(f"Schema file is not valid JSON: {SCHEMA_PATH}")

    try:
        trace_schema = schema["$defs"]["trace"]
    except (KeyError, TypeError):
        _fail("Malformed schema: missing `$defs.trace` object")

    if not isinstance(trace_schema, dict):
        _fail("Malformed schema: expected object at `$defs.trace`")

    required_raw = trace_schema.get("required", [])
    if not isinstance(required_raw, list):
        _fail("Malformed schema: expected list at `$defs.trace.required`")

    properties_raw = trace_schema.get("properties", {})
    if not isinstance(properties_raw, dict):
        _fail("Malformed schema: expected object at `$defs.trace.properties`")

    required = set(required_raw)
    properties = set(properties_raw.keys())

    missing_required = sorted(set(TRACE_REQUIRED_FIELDS) - required)
    missing_optional = sorted(set(TRACE_OPTIONAL_FIELDS) - properties)

    if missing_required or missing_optional:
        lines = ["trace contract drift detected"]
        if missing_required:
            lines.append(f"missing required fields: {', '.join(missing_required)}")
        if missing_optional:
            lines.append(f"missing optional fields: {', '.join(missing_optional)}")
        _fail("; ".join(lines))

    print("  ok: runtime trace fields are represented in schema")


if __name__ == "__main__":
    main()
