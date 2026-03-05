from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any


REF_ID_PATTERN = r"[A-Za-z_][A-Za-z0-9_-]*"
REF_ID_RE = re.compile(REF_ID_PATTERN)


class RefPolicyError(ValueError):
    """Raised when reference ids or bindings violate ref-system policy."""


def normalize_ref_id(value: Any, *, context: str, allow_literal: bool = True) -> str:
    if not isinstance(value, str):
        raise RefPolicyError(f"{context} must be a string")

    raw = value
    if raw.startswith("@"):
        if not allow_literal:
            raise RefPolicyError(f"{context} must not include '@' prefix")
        raw = raw[1:]

    if not raw:
        raise RefPolicyError(f"{context} must not be empty")

    if not REF_ID_RE.fullmatch(raw):
        raise RefPolicyError(f"{context} has invalid ref id '{value}'")

    return raw


def normalize_ref_literal(value: Any, *, context: str) -> str:
    ref_id = normalize_ref_id(value, context=context, allow_literal=True)
    return f"@{ref_id}"


def canonicalize_ref_bindings(
    refs: Mapping[Any, Any], *, context: str = "refs", allow_literal_keys: bool = True
) -> dict[str, str]:
    bindings: dict[str, str] = {}
    source_keys: dict[str, str] = {}

    for raw_key, raw_value in refs.items():
        if not isinstance(raw_key, str):
            raise RefPolicyError(f"All '{context}' keys must be strings")

        ref_id = normalize_ref_id(
            raw_key,
            context=f"{context} key '{raw_key}'",
            allow_literal=allow_literal_keys,
        )

        if ref_id in bindings:
            previous_key = source_keys[ref_id]
            raise RefPolicyError(
                f"{context} contains colliding ref ids '{previous_key}' and '{raw_key}' "
                f"(canonical id '{ref_id}')"
            )

        if not isinstance(raw_value, str):
            raise RefPolicyError(f"{context}['{raw_key}'] must be a string")

        bindings[ref_id] = raw_value
        source_keys[ref_id] = raw_key

    return {ref_id: bindings[ref_id] for ref_id in sorted(bindings.keys())}


def ensure_ref_literals_resolved(
    ref_literals: Iterable[Any], ref_bindings: Mapping[str, str], *, context: str
) -> None:
    missing_ids: set[str] = set()

    for index, literal in enumerate(ref_literals):
        normalized_literal = normalize_ref_literal(literal, context=f"{context}[{index}]")
        ref_id = normalized_literal[1:]
        if ref_id not in ref_bindings:
            missing_ids.add(ref_id)

    if missing_ids:
        refs = ", ".join(f"@{ref_id}" for ref_id in sorted(missing_ids))
        raise RefPolicyError(f"{context} references missing ref id(s): {refs}")
