from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import json
import math
import re
from typing import Any, Iterable, Mapping, NotRequired, TypedDict

from ir.refs import RefPolicyError, canonicalize_ref_bindings, ensure_ref_literals_resolved, normalize_ref_literal
from runtime.calibration import PiecewiseLinearCalibration, map_raw_score_to_probability
from runtime.errors import build_error_envelope


class ActionRecord(TypedDict):
    kind: str
    params: dict[str, Any]


class TraceRecord(TypedDict):
    rule_id: str
    matched_clauses: list[str]
    score: NotRequired[float]
    calibrated_probability: NotRequired[float]
    timestamp: NotRequired[str | int | float]
    seed: NotRequired[str | int]


class EvalResultEnvelope(TypedDict):
    actions: list[ActionRecord]
    trace: list[TraceRecord]
    error: NotRequired[dict[str, Any]]


CalibrationConfig = PiecewiseLinearCalibration | Mapping[str, Any] | Sequence[Any]


TRACE_REQUIRED_FIELDS: tuple[str, ...] = ("rule_id", "matched_clauses")
TRACE_OPTIONAL_FIELDS: tuple[str, ...] = (
    "score",
    "calibrated_probability",
    "timestamp",
    "seed",
)
TRACE_ALLOWED_FIELDS: set[str] = set(TRACE_REQUIRED_FIELDS) | set(TRACE_OPTIONAL_FIELDS)
_INTEGER_LITERAL_RE = re.compile(r"-?(?:0|[1-9]\d*)\Z")
_FLOAT_LITERAL_RE = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+|[eE][+-]?\d+|\.\d+[eE][+-]?\d+)\Z")
_MISSING_PAYLOAD_PATH = object()


@dataclass(frozen=True)
class _Clause:
    text: str
    kind: str
    value: Any = None
    path: tuple[str, ...] = ()


@dataclass(frozen=True)
class _NormalizedRule:
    index: int
    rule_id: str
    when: tuple[_Clause, ...]
    then: tuple[ActionRecord, ...]


def eval_policies(
    event: Any,
    rules: Iterable[Any],
    *,
    now: str | int | float | None = None,
    seed: str | int | None = None,
    include_score: bool = True,
    calibration: CalibrationConfig | None = None,
    refs: Mapping[str, Any] | None = None,
) -> tuple[list[ActionRecord], list[TraceRecord]]:
    """Evaluate rules deterministically and without side effects.

    Rule Engine v0 semantics:
    - `rule.when` is a simple list of clause strings interpreted as logical AND.
    - No expression language is supported.
    - Fired rules emit declarative action payloads only.
    """

    event_type, payload = _normalize_event(event)
    context_timestamp = _coerce_timestamp(now, payload.get("timestamp"))
    context_seed = _coerce_seed(seed, payload.get("seed"))

    normalized_rules = sorted(
        (_normalize_rule(rule, index) for index, rule in enumerate(rules)),
        key=lambda item: (item.rule_id, item.index),
    )

    _validate_runtime_ref_integrity(payload, normalized_rules, refs)

    actions: list[ActionRecord] = []
    raw_trace: list[TraceRecord] = []
    fired_rule_ids: list[str] = []

    for rule in normalized_rules:
        matched_clauses: list[str] = []
        for clause in rule.when:
            if not _evaluate_clause(clause, event_type=event_type, payload=payload):
                matched_clauses = []
                break
            matched_clauses.append(clause.text)

        if rule.when and not matched_clauses:
            continue

        actions.extend(_copy_actions(rule.then))

        trace_step: TraceRecord = {
            "rule_id": rule.rule_id,
            "matched_clauses": matched_clauses,
        }

        denominator = len(rule.when) if rule.when else 1
        raw_score = float(len(matched_clauses) / denominator)

        if include_score:
            trace_step["score"] = raw_score

        if calibration is not None:
            trace_step["calibrated_probability"] = map_raw_score_to_probability(raw_score, calibration)

        if context_timestamp is not None:
            trace_step["timestamp"] = context_timestamp

        if context_seed is not None:
            trace_step["seed"] = context_seed

        raw_trace.append(trace_step)
        fired_rule_ids.append(rule.rule_id)

    trace = validate_trace(raw_trace, fired_rule_ids=fired_rule_ids)
    return actions, trace


def eval_policies_envelope(
    event: Any,
    rules: Iterable[Any],
    *,
    now: str | int | float | None = None,
    seed: str | int | None = None,
    include_score: bool = True,
    calibration: CalibrationConfig | None = None,
    refs: Mapping[str, Any] | None = None,
) -> EvalResultEnvelope:
    """Evaluate policies and return an error-envelope payload on contract failures.

    Contract failures are captured deterministically as machine-readable runtime
    envelopes. Non-contract internal failures are not swallowed.
    """

    try:
        actions, trace = eval_policies(
            event,
            rules,
            now=now,
            seed=seed,
            include_score=include_score,
            calibration=calibration,
            refs=refs,
        )
    except (TypeError, ValueError) as exc:
        return {
            "actions": [],
            "trace": [],
            "error": build_error_envelope(exc, stage="runtime", command="eval"),
        }

    return {
        "actions": actions,
        "trace": trace,
    }


def _normalize_event(event: Any) -> tuple[str | None, dict[str, Any]]:
    event_type = _extract_attr(event, "type")
    if event_type is not None and not isinstance(event_type, str):
        raise TypeError("event.type must be a string when present")

    payload = _extract_attr(event, "payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise TypeError("event.payload must be a mapping when present")

    return event_type, _canonicalize_mapping(payload, context="event.payload")


def _normalize_rule(rule: Any, index: int) -> _NormalizedRule:
    rule_id = _extract_attr(rule, "id")
    if not isinstance(rule_id, str) or not rule_id:
        raise TypeError("rule.id must be a non-empty string")

    raw_when = _extract_attr(rule, "when")
    if raw_when is None:
        raw_when = _extract_attr(rule, "clauses")
    when = _normalize_when(raw_when)

    raw_then = _extract_attr(rule, "then")
    then = _normalize_then(raw_then, rule_id=rule_id)

    return _NormalizedRule(index=index, rule_id=rule_id, when=when, then=then)


def _normalize_when(raw_when: Any) -> tuple[_Clause, ...]:
    if raw_when is None:
        return (_parse_clause("event_type_present"),)

    if not isinstance(raw_when, (list, tuple)):
        raise TypeError("rule.when must be a list of clause strings")

    if len(raw_when) == 0:
        return (_parse_clause("event_type_present"),)

    clauses: list[_Clause] = []
    for clause in raw_when:
        if not isinstance(clause, str):
            raise TypeError("rule.when must contain only strings")
        clauses.append(_parse_clause(clause))

    return tuple(clauses)


def _parse_clause(clause: str) -> _Clause:
    if clause == "event_type_present":
        return _Clause(text=clause, kind="event_type_present")

    if clause.startswith("event_type_equals:"):
        expected = clause.partition(":")[2]
        if not expected:
            raise TypeError("clause 'event_type_equals' requires a non-empty value")
        return _Clause(text=clause, kind="event_type_equals", value=expected)

    if clause.startswith("payload_has:"):
        key = clause.partition(":")[2]
        if not key:
            raise TypeError("clause 'payload_has' requires a non-empty top-level key")
        return _Clause(text=clause, kind="payload_has", value=key)

    if clause.startswith("payload_path_exists:"):
        raw_path = clause.partition(":")[2]
        path = _parse_payload_path(raw_path, operator="payload_path_exists")
        return _Clause(text=clause, kind="payload_path_exists", path=path)

    if clause.startswith("payload_path_equals:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_value = spec.partition("=")
        if not separator or not raw_value:
            raise TypeError(
                "clause 'payload_path_equals' requires a non-empty '<path>=<value>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_equals")
        return _Clause(
            text=clause,
            kind="payload_path_equals",
            path=path,
            value=_parse_clause_scalar(raw_value),
        )

    if clause.startswith("payload_path_in:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_in' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_in")
        return _Clause(
            text=clause,
            kind="payload_path_in",
            path=path,
            value=_parse_clause_members(raw_members, operator="payload_path_in"),
        )

    for operator in ("payload_path_startswith", "payload_path_contains"):
        if clause.startswith(f"{operator}:"):
            spec = clause.partition(":")[2]
            raw_path, separator, raw_value = spec.partition("=")
            if not separator or not raw_value:
                raise TypeError(
                    f"clause '{operator}' requires a non-empty '<path>=<string>' pair"
                )
            path = _parse_payload_path(raw_path, operator=operator)
            return _Clause(text=clause, kind=operator, path=path, value=raw_value)

    for operator in (
        "payload_path_len_gt",
        "payload_path_len_gte",
        "payload_path_len_lt",
        "payload_path_len_lte",
    ):
        if clause.startswith(f"{operator}:"):
            spec = clause.partition(":")[2]
            raw_path, separator, raw_value = spec.partition("=")
            if not separator or not raw_value:
                raise TypeError(
                    f"clause '{operator}' requires a non-empty '<path>=<integer>' pair"
                )
            path = _parse_payload_path(raw_path, operator=operator)
            return _Clause(
                text=clause,
                kind=operator,
                path=path,
                value=_parse_clause_length(raw_value, operator=operator),
            )

    for operator in ("payload_path_gt", "payload_path_gte", "payload_path_lt", "payload_path_lte"):
        if clause.startswith(f"{operator}:"):
            spec = clause.partition(":")[2]
            raw_path, separator, raw_value = spec.partition("=")
            if not separator or not raw_value:
                raise TypeError(
                    f"clause '{operator}' requires a non-empty '<path>=<number>' pair"
                )
            path = _parse_payload_path(raw_path, operator=operator)
            return _Clause(
                text=clause,
                kind=operator,
                path=path,
                value=_parse_clause_number(raw_value, operator=operator),
            )

    if _looks_like_expression_clause(clause):
        raise TypeError(
            "rule.when supports only simple AND clause lists; expression syntax is not supported"
        )

    raise TypeError(
        "unsupported clause "
        f"'{clause}'. Supported clauses: event_type_present, event_type_equals:<value>, payload_has:<key>, payload_path_exists:<path>, payload_path_equals:<path>=<value>, payload_path_in:<path>=<csv-or-json-list>, payload_path_startswith:<path>=<string>, payload_path_contains:<path>=<string>, payload_path_len_gt:<path>=<integer>, payload_path_len_gte:<path>=<integer>, payload_path_len_lt:<path>=<integer>, payload_path_len_lte:<path>=<integer>, payload_path_gt:<path>=<number>, payload_path_gte:<path>=<number>, payload_path_lt:<path>=<number>, payload_path_lte:<path>=<number>"
    )


def _looks_like_expression_clause(clause: str) -> bool:
    lowered = f" {clause.lower()} "
    if " and " in lowered or " or " in lowered or " not " in lowered:
        return True

    for token in ("&&", "||", "!", "(", ")"):
        if token in clause:
            return True

    return False


def _parse_payload_path(raw_path: str, *, operator: str) -> tuple[str, ...]:
    if not raw_path:
        raise TypeError(f"clause '{operator}' requires a non-empty payload path")

    segments = tuple(segment for segment in raw_path.split("."))
    if not segments or any(segment == "" for segment in segments):
        raise TypeError(f"clause '{operator}' requires a dot-separated payload path without empty segments")

    return segments


def _parse_clause_scalar(raw_value: str) -> Any:
    lowered = raw_value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None

    if _INTEGER_LITERAL_RE.fullmatch(raw_value):
        return int(raw_value)

    if _FLOAT_LITERAL_RE.fullmatch(raw_value):
        numeric = float(raw_value)
        if math.isfinite(numeric):
            return numeric

    return raw_value


def _parse_clause_members(raw_members: str, *, operator: str) -> tuple[Any, ...]:
    spec = raw_members.strip()
    if not spec:
        raise TypeError(f"clause '{operator}' requires at least one member")

    if spec[0] in "[{":
        try:
            parsed = json.loads(spec)
        except json.JSONDecodeError as exc:
            raise TypeError(
                f"clause '{operator}' requires a valid JSON array or comma-separated scalar list"
            ) from exc
        if not isinstance(parsed, list):
            raise TypeError(f"clause '{operator}' JSON form must decode to an array")
        if len(parsed) == 0:
            raise TypeError(f"clause '{operator}' requires at least one member")
        return tuple(_normalize_clause_member_value(value, operator=operator) for value in parsed)

    members: list[Any] = []
    for raw_member in spec.split(","):
        member = raw_member.strip()
        if not member:
            raise TypeError(
                f"clause '{operator}' comma-separated form requires non-empty members"
            )
        members.append(_parse_clause_scalar(member))

    return tuple(members)


def _parse_clause_number(raw_value: str, *, operator: str) -> int | float:
    parsed = _parse_clause_scalar(raw_value.strip())
    if isinstance(parsed, bool) or not isinstance(parsed, (int, float)):
        raise TypeError(f"clause '{operator}' requires a finite numeric '<path>=<number>' pair")
    numeric = float(parsed)
    if not math.isfinite(numeric):
        raise TypeError(f"clause '{operator}' requires a finite numeric '<path>=<number>' pair")
    return parsed


def _parse_clause_length(raw_value: str, *, operator: str) -> int:
    parsed = _parse_clause_scalar(raw_value.strip())
    if isinstance(parsed, bool) or not isinstance(parsed, int) or parsed < 0:
        raise TypeError(
            f"clause '{operator}' requires a non-negative integer '<path>=<integer>' pair"
        )
    return parsed


def _normalize_clause_member_value(value: Any, *, operator: str) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"clause '{operator}' members must be finite JSON scalars")
        return value

    raise TypeError(f"clause '{operator}' members must be JSON scalars (string|number|bool|null)")


def _resolve_payload_path(payload: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload

    for segment in path:
        if isinstance(current, Mapping):
            if segment not in current:
                return _MISSING_PAYLOAD_PATH
            current = current[segment]
            continue

        if isinstance(current, list):
            if not segment.isdigit():
                return _MISSING_PAYLOAD_PATH
            index = int(segment)
            if index >= len(current):
                return _MISSING_PAYLOAD_PATH
            current = current[index]
            continue

        return _MISSING_PAYLOAD_PATH

    return current


def _payload_values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual is expected

    if actual is None or expected is None:
        return actual is None and expected is None

    if isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            return float(actual) == float(expected)

    return actual == expected


def _coerce_payload_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    numeric = float(value)
    if not math.isfinite(numeric):
        return None

    return numeric


def _coerce_payload_length(value: Any) -> int | None:
    if isinstance(value, (str, list, Mapping)):
        return len(value)
    return None


def _normalize_then(raw_then: Any, *, rule_id: str) -> tuple[ActionRecord, ...]:
    if raw_then is None:
        return ({"kind": "act", "params": {"rule_id": rule_id}},)

    if not isinstance(raw_then, (list, tuple)):
        raise TypeError("rule.then must be a list of action objects")

    normalized: list[ActionRecord] = []
    for item in raw_then:
        kind = _extract_attr(item, "kind")
        if not isinstance(kind, str) or not kind:
            raise TypeError("action.kind must be a non-empty string")

        raw_params = _extract_attr(item, "params")
        if raw_params is None:
            raw_params = {}
        if not isinstance(raw_params, Mapping):
            raise TypeError("action.params must be a mapping when present")

        normalized.append(
            {
                "kind": kind,
                "params": _canonicalize_mapping(
                    raw_params,
                    context=f"rule.then[{len(normalized)}].params",
                ),
            }
        )

    return tuple(normalized)


def _validate_runtime_ref_integrity(
    payload: Mapping[str, Any],
    normalized_rules: Sequence[_NormalizedRule],
    refs: Mapping[str, Any] | None,
) -> None:
    ref_literals = _collect_runtime_ref_literals_from_mapping(payload, context="event.payload")

    for rule in normalized_rules:
        for index, action in enumerate(rule.then):
            ref_literals.extend(
                _collect_runtime_ref_literals_from_mapping(
                    action["params"],
                    context=f"rule[{rule.rule_id}].then[{index}].params",
                )
            )

    if not ref_literals and refs is None:
        return

    if refs is None:
        raise TypeError("runtime input contains '*_ref' fields but no refs mapping was provided")

    if not isinstance(refs, Mapping):
        raise TypeError("refs must be a mapping when provided")

    try:
        bindings = canonicalize_ref_bindings(refs, context="refs", allow_literal_keys=True)
        ensure_ref_literals_resolved(ref_literals, bindings, context="runtime refs")
    except RefPolicyError as exc:
        raise TypeError(str(exc)) from exc


def _collect_runtime_ref_literals_from_mapping(mapping: Mapping[str, Any], *, context: str) -> list[str]:
    ref_literals: list[str] = []

    for key in sorted(mapping.keys()):
        value = mapping[key]
        path = f"{context}.{key}"

        if key.endswith("_ref"):
            try:
                ref_literals.append(normalize_ref_literal(value, context=path))
            except RefPolicyError as exc:
                raise TypeError(str(exc)) from exc
            continue

        if isinstance(value, Mapping):
            ref_literals.extend(_collect_runtime_ref_literals_from_mapping(value, context=path))
            continue

        if isinstance(value, list):
            ref_literals.extend(_collect_runtime_ref_literals_from_list(value, context=path))

    return ref_literals


def _collect_runtime_ref_literals_from_list(values: list[Any], *, context: str) -> list[str]:
    ref_literals: list[str] = []

    for index, value in enumerate(values):
        path = f"{context}[{index}]"

        if isinstance(value, Mapping):
            ref_literals.extend(_collect_runtime_ref_literals_from_mapping(value, context=path))
            continue

        if isinstance(value, list):
            ref_literals.extend(_collect_runtime_ref_literals_from_list(value, context=path))

    return ref_literals


def _evaluate_clause(clause: _Clause, *, event_type: str | None, payload: Mapping[str, Any]) -> bool:
    if clause.kind == "event_type_present":
        return bool(event_type)

    if clause.kind == "event_type_equals":
        return event_type == clause.value

    if clause.kind == "payload_has":
        key = clause.value
        return key is not None and key in payload

    if clause.kind == "payload_path_exists":
        return _resolve_payload_path(payload, clause.path) is not _MISSING_PAYLOAD_PATH

    if clause.kind == "payload_path_equals":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False
        return _payload_values_equal(actual, clause.value)

    if clause.kind == "payload_path_in":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False
        return any(_payload_values_equal(actual, expected) for expected in clause.value)

    if clause.kind in {"payload_path_startswith", "payload_path_contains"}:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, str):
            return False
        if clause.kind == "payload_path_startswith":
            return actual.startswith(clause.value)
        return clause.value in actual

    if clause.kind in {
        "payload_path_len_gt",
        "payload_path_len_gte",
        "payload_path_len_lt",
        "payload_path_len_lte",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False

        actual_length = _coerce_payload_length(actual)
        if actual_length is None:
            return False

        expected_length = clause.value
        if clause.kind == "payload_path_len_gt":
            return actual_length > expected_length
        if clause.kind == "payload_path_len_gte":
            return actual_length >= expected_length
        if clause.kind == "payload_path_len_lt":
            return actual_length < expected_length
        return actual_length <= expected_length

    if clause.kind in {"payload_path_gt", "payload_path_gte", "payload_path_lt", "payload_path_lte"}:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False

        actual_number = _coerce_payload_number(actual)
        if actual_number is None:
            return False

        expected_number = float(clause.value)
        if clause.kind == "payload_path_gt":
            return actual_number > expected_number
        if clause.kind == "payload_path_gte":
            return actual_number >= expected_number
        if clause.kind == "payload_path_lt":
            return actual_number < expected_number
        return actual_number <= expected_number

    raise RuntimeError(f"Unknown normalized clause kind '{clause.kind}'")


def _extract_attr(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _canonicalize_mapping(mapping: Mapping[Any, Any], *, context: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    ordered_keys = sorted(mapping.keys(), key=lambda item: (str(item), type(item).__name__))

    for key in ordered_keys:
        value = mapping[key]
        out[str(key)] = _canonicalize_declarative_value(value, context=f"{context}.{key}")

    return out


def _canonicalize_list(values: list[Any], *, context: str) -> list[Any]:
    out: list[Any] = []
    for index, value in enumerate(values):
        out.append(_canonicalize_declarative_value(value, context=f"{context}[{index}]"))
    return out


def _canonicalize_declarative_value(value: Any, *, context: str) -> Any:
    if isinstance(value, Mapping):
        return _canonicalize_mapping(value, context=context)

    if isinstance(value, list):
        return _canonicalize_list(value, context=context)

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    raise TypeError(
        f"{context} must be declarative JSON-like data "
        "(str|int|float|bool|null|list|object)"
    )


def _copy_actions(actions: tuple[ActionRecord, ...]) -> list[ActionRecord]:
    copied: list[ActionRecord] = []
    for action in actions:
        copied.append(
            {
                "kind": action["kind"],
                "params": _canonicalize_mapping(
                    action["params"],
                    context=f"action:{action['kind']}.params",
                ),
            }
        )
    return copied


def _coerce_timestamp(primary: Any, fallback: Any) -> str | int | float | None:
    value = primary if primary is not None else fallback
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("timestamp/now must be str|int|float when present")
    if isinstance(value, (str, int, float)):
        return value
    raise TypeError("timestamp/now must be str|int|float when present")


def _coerce_seed(primary: Any, fallback: Any) -> str | int | None:
    value = primary if primary is not None else fallback
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("seed must be str|int when present")
    if isinstance(value, (str, int)):
        return value
    raise TypeError("seed must be str|int when present")


def validate_trace(trace: Iterable[Mapping[str, Any]], *, fired_rule_ids: Iterable[str] | None = None) -> list[TraceRecord]:
    validated = [validate_trace_step(step) for step in trace]

    if fired_rule_ids is None:
        return validated

    expected = list(fired_rule_ids)
    if not all(isinstance(rule_id, str) and rule_id for rule_id in expected):
        raise TypeError("fired_rule_ids must be a sequence of non-empty strings")

    actual = [step["rule_id"] for step in validated]
    if actual != expected:
        raise TypeError("trace rule_id sequence does not match fired rule sequence")

    return validated


def validate_trace_step(step: Mapping[str, Any]) -> TraceRecord:
    unknown = set(step.keys()) - TRACE_ALLOWED_FIELDS
    if unknown:
        raise TypeError(f"trace step has unknown field(s): {', '.join(sorted(unknown))}")

    missing = [field for field in TRACE_REQUIRED_FIELDS if field not in step]
    if missing:
        raise TypeError(f"trace step missing required field(s): {', '.join(missing)}")

    rule_id = step["rule_id"]
    if not isinstance(rule_id, str) or not rule_id:
        raise TypeError("trace rule_id must be a non-empty string")

    matched = step["matched_clauses"]
    if (
        not isinstance(matched, list)
        or len(matched) == 0
        or not all(isinstance(item, str) and item for item in matched)
    ):
        raise TypeError("trace matched_clauses must be a non-empty list of strings")

    normalized: TraceRecord = {
        "rule_id": rule_id,
        "matched_clauses": list(matched),
    }

    if "score" in step:
        score = step["score"]
        if not isinstance(score, float) or not math.isfinite(score):
            raise TypeError("trace score must be finite float when present")
        normalized["score"] = score

    if "calibrated_probability" in step:
        calibrated_probability = step["calibrated_probability"]
        if not isinstance(calibrated_probability, float) or not math.isfinite(calibrated_probability):
            raise TypeError("trace calibrated_probability must be finite float when present")
        if not 0.0 <= calibrated_probability <= 1.0:
            raise TypeError("trace calibrated_probability must be in [0.0, 1.0] when present")
        normalized["calibrated_probability"] = calibrated_probability

    if "timestamp" in step:
        timestamp = step["timestamp"]
        if isinstance(timestamp, bool) or not isinstance(timestamp, (str, int, float)):
            raise TypeError("trace timestamp must be str|int|float when present")
        normalized["timestamp"] = timestamp

    if "seed" in step:
        trace_seed = step["seed"]
        if isinstance(trace_seed, bool) or not isinstance(trace_seed, (str, int)):
            raise TypeError("trace seed must be str|int when present")
        normalized["seed"] = trace_seed

    return normalized


def _validate_trace_step(step: TraceRecord) -> None:
    validate_trace_step(step)
