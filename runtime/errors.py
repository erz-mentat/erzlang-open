from __future__ import annotations

from collections.abc import Mapping
import json
import re
from typing import Any

from compact import CompactError, CompactParseError, CompactValidationError
from transform import TransformError


ERROR_ENVELOPE_FIELD_ORDER: tuple[str, ...] = (
    "code",
    "stage",
    "message",
    "span",
    "hint",
    "details",
)


def build_error_envelope(
    exc: Exception,
    *,
    stage: str,
    command: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic machine-readable error envelope.

    Envelope shape is stable for v0.2-prep functional track:
    `code`, `stage`, `message`, `span`, `hint`, `details`.
    """

    code, hint = _classify_error(exc, stage=stage)
    span = _extract_span(exc)

    details: dict[str, Any] = {
        "error_type": exc.__class__.__name__,
    }
    if command is not None:
        details["command"] = command

    envelope: dict[str, Any] = {
        "code": code,
        "stage": stage,
        "message": str(exc),
        "span": span,
        "hint": hint,
        "details": details,
    }

    return envelope


def render_error_envelope_json(envelope: Mapping[str, Any]) -> str:
    """Render envelope deterministically for CLI stderr output."""

    ordered_envelope = {
        field: envelope.get(field)
        for field in ERROR_ENVELOPE_FIELD_ORDER
    }
    return json.dumps(ordered_envelope, separators=(",", ":"), ensure_ascii=False)


def _classify_error(exc: Exception, *, stage: str) -> tuple[str, str | None]:
    if isinstance(exc, CompactParseError):
        return (
            "ERZ_PARSE_SYNTAX",
            "Check compact syntax near the reported position.",
        )

    if isinstance(exc, CompactValidationError):
        if stage == "validate":
            return (
                "ERZ_VALIDATE_SCHEMA",
                "Align statement fields with the compact subset contract.",
            )
        return (
            "ERZ_PARSE_SCHEMA",
            "Align statement fields with the compact subset contract.",
        )

    if isinstance(exc, CompactError):
        return (
            "ERZ_COMPACT_ERROR",
            "Review compact input and CLI arguments.",
        )

    if isinstance(exc, TransformError):
        return (
            "ERZ_TRANSFORM_ERROR",
            "Ensure pack/unpack input follows the supported fixture subset.",
        )

    if isinstance(exc, TypeError) and stage == "runtime":
        return (
            "ERZ_RUNTIME_CONTRACT",
            "Runtime input or trace shape violated the runtime contract.",
        )

    if isinstance(exc, ValueError) and stage == "runtime":
        return (
            "ERZ_RUNTIME_VALUE",
            "Runtime value violated allowed numeric/range constraints.",
        )

    if isinstance(exc, OSError):
        return (
            "ERZ_IO_ERROR",
            "Check file path, permissions, and stdin/stdout availability.",
        )

    return (
        "ERZ_INTERNAL_ERROR",
        None,
    )


def _extract_span(exc: Exception) -> dict[str, int] | None:
    match = re.search(r"position\s+(\d+)", str(exc))
    if not match:
        return None
    return {"position": int(match.group(1))}
