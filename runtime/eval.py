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


class ActionPlanStep(TypedDict):
    step: int
    kind: str
    params: dict[str, Any]


class EvalResultEnvelope(TypedDict):
    actions: list[ActionRecord]
    trace: list[TraceRecord]
    action_plan: NotRequired[list[ActionPlanStep]]
    resolved_refs: NotRequired[dict[str, str]]
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
    other_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class _NormalizedRule:
    index: int
    rule_id: str
    priority: int
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
        key=lambda item: (-item.priority, item.rule_id, item.index),
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
    include_action_plan: bool = False,
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
        error_envelope: EvalResultEnvelope = {
            "actions": [],
            "trace": [],
            "error": build_error_envelope(exc, stage="runtime", command="eval"),
        }
        if include_action_plan:
            error_envelope["action_plan"] = []
            error_envelope["resolved_refs"] = {}
        return error_envelope

    envelope: EvalResultEnvelope = {
        "actions": actions,
        "trace": trace,
    }
    if not include_action_plan:
        return envelope

    try:
        action_plan, resolved_refs = materialize_action_plan(actions, refs=refs)
    except (TypeError, ValueError) as exc:
        envelope["action_plan"] = []
        envelope["resolved_refs"] = {}
        envelope["error"] = build_error_envelope(exc, stage="runtime", command="eval")
        return envelope

    envelope["action_plan"] = action_plan
    envelope["resolved_refs"] = resolved_refs
    return envelope


def materialize_action_plan(
    actions: Sequence[ActionRecord],
    *,
    refs: Mapping[str, Any] | None,
) -> tuple[list[ActionPlanStep], dict[str, str]]:
    canonical_refs = _canonicalize_runtime_refs_for_action_plan(refs)
    action_plan: list[ActionPlanStep] = []
    used_ref_ids: set[str] = set()

    for step_index, action in enumerate(actions, start=1):
        materialized_params, step_ref_ids = _materialize_action_plan_value(
            action["params"],
            refs=canonical_refs,
            context=f"action_plan[{step_index}].params",
        )
        if not isinstance(materialized_params, dict):
            raise TypeError(f"action_plan[{step_index}].params must materialize to an object")
        action_plan.append(
            {
                "step": step_index,
                "kind": action["kind"],
                "params": materialized_params,
            }
        )
        used_ref_ids.update(step_ref_ids)

    resolved_refs = {ref_id: canonical_refs[ref_id] for ref_id in sorted(used_ref_ids)}
    return action_plan, resolved_refs


def _canonicalize_runtime_refs_for_action_plan(refs: Mapping[str, Any] | None) -> dict[str, str]:
    if refs is None:
        return {}
    if not isinstance(refs, Mapping):
        raise TypeError("refs must be a mapping when provided")
    try:
        return canonicalize_ref_bindings(refs, context="refs", allow_literal_keys=True)
    except RefPolicyError as exc:
        raise TypeError(str(exc)) from exc


def _materialize_action_plan_value(
    value: Any,
    *,
    refs: Mapping[str, str],
    context: str,
) -> tuple[Any, set[str]]:
    if isinstance(value, Mapping):
        return _materialize_action_plan_mapping(value, refs=refs, context=context)
    if isinstance(value, list):
        return _materialize_action_plan_list(value, refs=refs, context=context)
    return value, set()


def _materialize_action_plan_mapping(
    mapping: Mapping[str, Any],
    *,
    refs: Mapping[str, str],
    context: str,
) -> tuple[dict[str, Any], set[str]]:
    materialized: dict[str, Any] = {}
    used_ref_ids: set[str] = set()

    for key in sorted(mapping.keys()):
        value = mapping[key]
        path = f"{context}.{key}"

        if key.endswith("_ref"):
            normalized_literal = normalize_ref_literal(value, context=path)
            ref_id = normalized_literal[1:]
            if ref_id not in refs:
                raise TypeError(f"{path} references missing ref id '{normalized_literal}'")
            materialized_key = key[:-4]
            if not materialized_key:
                raise TypeError(f"{path} must keep a non-empty key prefix before '_ref'")
            if materialized_key in materialized:
                raise TypeError(
                    f"{path} materializes duplicate action-plan key '{materialized_key}'"
                )
            materialized[materialized_key] = refs[ref_id]
            used_ref_ids.add(ref_id)
            continue

        materialized_value, child_ref_ids = _materialize_action_plan_value(
            value,
            refs=refs,
            context=path,
        )
        materialized[key] = materialized_value
        used_ref_ids.update(child_ref_ids)

    return materialized, used_ref_ids


def _materialize_action_plan_list(
    values: list[Any],
    *,
    refs: Mapping[str, str],
    context: str,
) -> tuple[list[Any], set[str]]:
    materialized: list[Any] = []
    used_ref_ids: set[str] = set()

    for index, value in enumerate(values):
        item, child_ref_ids = _materialize_action_plan_value(
            value,
            refs=refs,
            context=f"{context}[{index}]",
        )
        materialized.append(item)
        used_ref_ids.update(child_ref_ids)

    return materialized, used_ref_ids


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

    priority = _normalize_rule_priority(_extract_attr(rule, "priority"))

    raw_when = _extract_attr(rule, "when")
    if raw_when is None:
        raw_when = _extract_attr(rule, "clauses")
    when = _normalize_when(raw_when)

    raw_then = _extract_attr(rule, "then")
    then = _normalize_then(raw_then, rule_id=rule_id)

    return _NormalizedRule(index=index, rule_id=rule_id, priority=priority, when=when, then=then)


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

    if clause.startswith("event_type_equals_ci:"):
        expected = clause.partition(":")[2]
        if not expected:
            raise TypeError("clause 'event_type_equals_ci' requires a non-empty value")
        return _Clause(text=clause, kind="event_type_equals_ci", value=expected)

    if clause.startswith("event_type_in:"):
        raw_members = clause.partition(":")[2]
        return _Clause(
            text=clause,
            kind="event_type_in",
            value=_parse_event_type_members(raw_members, operator="event_type_in"),
        )

    if clause.startswith("event_type_not_in:"):
        raw_members = clause.partition(":")[2]
        return _Clause(
            text=clause,
            kind="event_type_not_in",
            value=_parse_event_type_members(raw_members, operator="event_type_not_in"),
        )

    if clause.startswith("event_type_in_ci:"):
        raw_members = clause.partition(":")[2]
        return _Clause(
            text=clause,
            kind="event_type_in_ci",
            value=_parse_event_type_members(raw_members, operator="event_type_in_ci"),
        )

    if clause.startswith("event_type_not_in_ci:"):
        raw_members = clause.partition(":")[2]
        return _Clause(
            text=clause,
            kind="event_type_not_in_ci",
            value=_parse_event_type_members(raw_members, operator="event_type_not_in_ci"),
        )

    for operator in (
        "event_type_equals_path",
        "event_type_not_equals_path",
        "event_type_equals_path_ci",
        "event_type_not_equals_path_ci",
        "event_type_startswith_path",
        "event_type_contains_path",
        "event_type_endswith_path",
        "event_type_not_startswith_path",
        "event_type_not_contains_path",
        "event_type_not_endswith_path",
        "event_type_startswith_path_ci",
        "event_type_contains_path_ci",
        "event_type_endswith_path_ci",
        "event_type_not_startswith_path_ci",
        "event_type_not_contains_path_ci",
        "event_type_not_endswith_path_ci",
        "event_type_matches_path",
        "event_type_not_matches_path",
        "event_type_matches_path_ci",
        "event_type_not_matches_path_ci",
        "event_type_in_path",
        "event_type_not_in_path",
        "event_type_in_path_ci",
        "event_type_not_in_path_ci",
    ):
        if clause.startswith(f"{operator}:"):
            raw_path = clause.partition(":")[2]
            path = _parse_payload_path(raw_path, operator=operator)
            return _Clause(text=clause, kind=operator, path=path)

    for operator in (
        "event_type_startswith",
        "event_type_contains",
        "event_type_endswith",
        "event_type_not_startswith",
        "event_type_not_contains",
        "event_type_not_endswith",
        "event_type_startswith_ci",
        "event_type_contains_ci",
        "event_type_endswith_ci",
        "event_type_not_startswith_ci",
        "event_type_not_contains_ci",
        "event_type_not_endswith_ci",
        "event_type_matches",
        "event_type_not_matches",
        "event_type_matches_ci",
        "event_type_not_matches_ci",
    ):
        if clause.startswith(f"{operator}:"):
            expected = clause.partition(":")[2]
            if not expected:
                expected_value_kind = (
                    "regex"
                    if operator in {
                        "event_type_matches",
                        "event_type_not_matches",
                        "event_type_matches_ci",
                        "event_type_not_matches_ci",
                    }
                    else "value"
                )
                raise TypeError(
                    f"clause '{operator}' requires a non-empty {expected_value_kind}"
                )
            value = (
                _parse_clause_regex(
                    expected,
                    operator=operator,
                    case_insensitive=operator in {"event_type_matches_ci", "event_type_not_matches_ci"},
                    expected_spec="'<regex>' value",
                )
                if operator in {
                    "event_type_matches",
                    "event_type_not_matches",
                    "event_type_matches_ci",
                    "event_type_not_matches_ci",
                }
                else expected
            )
            return _Clause(text=clause, kind=operator, value=value)

    if clause.startswith("payload_has:"):
        key = clause.partition(":")[2]
        if not key:
            raise TypeError("clause 'payload_has' requires a non-empty top-level key")
        return _Clause(text=clause, kind="payload_has", value=key)

    for operator in ("payload_path_empty", "payload_path_not_empty"):
        if clause.startswith(f"{operator}:"):
            raw_path = clause.partition(":")[2]
            path = _parse_payload_path(raw_path, operator=operator)
            return _Clause(text=clause, kind=operator, path=path)

    if clause.startswith("payload_path_exists:"):
        raw_path = clause.partition(":")[2]
        path = _parse_payload_path(raw_path, operator="payload_path_exists")
        return _Clause(text=clause, kind="payload_path_exists", path=path)

    if clause.startswith("payload_path_not_exists:"):
        raw_path = clause.partition(":")[2]
        path = _parse_payload_path(raw_path, operator="payload_path_not_exists")
        return _Clause(text=clause, kind="payload_path_not_exists", path=path)

    for operator in (
        "payload_path_is_null",
        "payload_path_is_bool",
        "payload_path_is_number",
        "payload_path_is_string",
        "payload_path_is_list",
        "payload_path_is_object",
    ):
        if clause.startswith(f"{operator}:"):
            raw_path = clause.partition(":")[2]
            path = _parse_payload_path(raw_path, operator=operator)
            return _Clause(text=clause, kind=operator, path=path)

    for operator in (
        "payload_path_has_key_path",
        "payload_path_not_has_key_path",
        "payload_path_has_key_path_ci",
        "payload_path_not_has_key_path_ci",
        "payload_path_equals_path",
        "payload_path_not_equals_path",
        "payload_path_equals_path_ci",
        "payload_path_not_equals_path_ci",
        "payload_path_startswith_path",
        "payload_path_contains_path",
        "payload_path_endswith_path",
        "payload_path_not_startswith_path",
        "payload_path_not_contains_path",
        "payload_path_not_endswith_path",
        "payload_path_startswith_path_ci",
        "payload_path_contains_path_ci",
        "payload_path_endswith_path_ci",
        "payload_path_not_startswith_path_ci",
        "payload_path_not_contains_path_ci",
        "payload_path_not_endswith_path_ci",
        "payload_path_matches_path",
        "payload_path_not_matches_path",
        "payload_path_matches_path_ci",
        "payload_path_not_matches_path_ci",
        "payload_path_in_path",
        "payload_path_not_in_path",
        "payload_path_in_path_ci",
        "payload_path_not_in_path_ci",
        "payload_path_any_in_path",
        "payload_path_all_in_path",
        "payload_path_none_in_path",
        "payload_path_any_in_path_ci",
        "payload_path_all_in_path_ci",
        "payload_path_none_in_path_ci",
        "payload_path_len_eq_path",
        "payload_path_len_not_eq_path",
        "payload_path_len_gt_path",
        "payload_path_len_gte_path",
        "payload_path_len_lt_path",
        "payload_path_len_lte_path",
        "payload_path_gt_path",
        "payload_path_gte_path",
        "payload_path_lt_path",
        "payload_path_lte_path",
    ):
        if clause.startswith(f"{operator}:"):
            spec = clause.partition(":")[2]
            path, other_path = _parse_payload_path_pair(spec, operator=operator)
            return _Clause(text=clause, kind=operator, path=path, other_path=other_path)

    for operator in (
        "payload_path_has_key",
        "payload_path_not_has_key",
        "payload_path_has_key_ci",
        "payload_path_not_has_key_ci",
    ):
        if clause.startswith(f"{operator}:"):
            spec = clause.partition(":")[2]
            raw_path, separator, raw_key = spec.partition("=")
            if not separator or not raw_key:
                raise TypeError(
                    f"clause '{operator}' requires a non-empty '<path>=<string>' pair"
                )
            path = _parse_payload_path(raw_path, operator=operator)
            key = raw_key.strip()
            if not key:
                raise TypeError(
                    f"clause '{operator}' requires a non-empty '<path>=<string>' pair"
                )
            return _Clause(
                text=clause,
                kind=operator,
                path=path,
                value=key,
            )

    for operator in (
        "payload_path_has_keys",
        "payload_path_missing_keys",
        "payload_path_has_keys_ci",
        "payload_path_missing_keys_ci",
    ):
        if clause.startswith(f"{operator}:"):
            spec = clause.partition(":")[2]
            raw_path, separator, raw_members = spec.partition("=")
            if not separator or not raw_members:
                raise TypeError(
                    f"clause '{operator}' requires a non-empty '<path>=<csv-or-json-list>' pair"
                )
            path = _parse_payload_path(raw_path, operator=operator)
            return _Clause(
                text=clause,
                kind=operator,
                path=path,
                value=_parse_clause_string_members(raw_members, operator=operator),
            )

    for operator in (
        "payload_path_has_keys_path",
        "payload_path_missing_keys_path",
        "payload_path_has_keys_path_ci",
        "payload_path_missing_keys_path_ci",
    ):
        if clause.startswith(f"{operator}:"):
            path, other_path = _parse_payload_path_pair(
                clause.partition(":")[2],
                operator=operator,
            )
            return _Clause(
                text=clause,
                kind=operator,
                path=path,
                other_path=other_path,
            )

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

    if clause.startswith("payload_path_not_equals:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_value = spec.partition("=")
        if not separator or not raw_value:
            raise TypeError(
                "clause 'payload_path_not_equals' requires a non-empty '<path>=<value>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_not_equals")
        return _Clause(
            text=clause,
            kind="payload_path_not_equals",
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

    if clause.startswith("payload_path_not_in:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_not_in' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_not_in")
        return _Clause(
            text=clause,
            kind="payload_path_not_in",
            path=path,
            value=_parse_clause_members(raw_members, operator="payload_path_not_in"),
        )

    if clause.startswith("payload_path_in_ci:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_in_ci' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_in_ci")
        return _Clause(
            text=clause,
            kind="payload_path_in_ci",
            path=path,
            value=_parse_clause_string_members(raw_members, operator="payload_path_in_ci"),
        )

    if clause.startswith("payload_path_not_in_ci:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_not_in_ci' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_not_in_ci")
        return _Clause(
            text=clause,
            kind="payload_path_not_in_ci",
            path=path,
            value=_parse_clause_string_members(raw_members, operator="payload_path_not_in_ci"),
        )

    if clause.startswith("payload_path_any_in:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_any_in' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_any_in")
        return _Clause(
            text=clause,
            kind="payload_path_any_in",
            path=path,
            value=_parse_clause_members(raw_members, operator="payload_path_any_in"),
        )

    if clause.startswith("payload_path_all_in:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_all_in' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_all_in")
        return _Clause(
            text=clause,
            kind="payload_path_all_in",
            path=path,
            value=_parse_clause_members(raw_members, operator="payload_path_all_in"),
        )

    if clause.startswith("payload_path_none_in:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_none_in' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_none_in")
        return _Clause(
            text=clause,
            kind="payload_path_none_in",
            path=path,
            value=_parse_clause_members(raw_members, operator="payload_path_none_in"),
        )

    if clause.startswith("payload_path_any_in_ci:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_any_in_ci' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_any_in_ci")
        return _Clause(
            text=clause,
            kind="payload_path_any_in_ci",
            path=path,
            value=_parse_clause_string_members(raw_members, operator="payload_path_any_in_ci"),
        )

    if clause.startswith("payload_path_all_in_ci:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_all_in_ci' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_all_in_ci")
        return _Clause(
            text=clause,
            kind="payload_path_all_in_ci",
            path=path,
            value=_parse_clause_string_members(raw_members, operator="payload_path_all_in_ci"),
        )

    if clause.startswith("payload_path_none_in_ci:"):
        spec = clause.partition(":")[2]
        raw_path, separator, raw_members = spec.partition("=")
        if not separator or not raw_members:
            raise TypeError(
                "clause 'payload_path_none_in_ci' requires a non-empty '<path>=<csv-or-json-list>' pair"
            )
        path = _parse_payload_path(raw_path, operator="payload_path_none_in_ci")
        return _Clause(
            text=clause,
            kind="payload_path_none_in_ci",
            path=path,
            value=_parse_clause_string_members(raw_members, operator="payload_path_none_in_ci"),
        )

    for operator in (
        "payload_path_equals_ci",
        "payload_path_not_equals_ci",
        "payload_path_startswith",
        "payload_path_contains",
        "payload_path_endswith",
        "payload_path_not_startswith",
        "payload_path_not_contains",
        "payload_path_not_endswith",
        "payload_path_startswith_ci",
        "payload_path_contains_ci",
        "payload_path_endswith_ci",
        "payload_path_not_startswith_ci",
        "payload_path_not_contains_ci",
        "payload_path_not_endswith_ci",
        "payload_path_matches",
        "payload_path_not_matches",
        "payload_path_matches_ci",
        "payload_path_not_matches_ci",
    ):
        if clause.startswith(f"{operator}:"):
            spec = clause.partition(":")[2]
            raw_path, separator, raw_value = spec.partition("=")
            if not separator or not raw_value:
                expected_value_kind = "regex" if operator in {"payload_path_matches", "payload_path_not_matches", "payload_path_matches_ci", "payload_path_not_matches_ci"} else "string"
                raise TypeError(
                    f"clause '{operator}' requires a non-empty '<path>=<{expected_value_kind}>' pair"
                )
            path = _parse_payload_path(raw_path, operator=operator)
            value = (
                _parse_clause_regex(
                    raw_value,
                    operator=operator,
                    case_insensitive=operator in {"payload_path_matches_ci", "payload_path_not_matches_ci"},
                )
                if operator in {
                    "payload_path_matches",
                    "payload_path_not_matches",
                    "payload_path_matches_ci",
                    "payload_path_not_matches_ci",
                }
                else raw_value
            )
            return _Clause(text=clause, kind=operator, path=path, value=value)

    for operator in (
        "payload_path_len_eq",
        "payload_path_len_not_eq",
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
        f"'{clause}'. Supported clauses: event_type_present, event_type_equals:<value>, event_type_equals_ci:<value>, event_type_in:<csv-or-json-list>, event_type_not_in:<csv-or-json-list>, event_type_in_ci:<csv-or-json-list>, event_type_not_in_ci:<csv-or-json-list>, event_type_startswith:<value>, event_type_contains:<value>, event_type_endswith:<value>, event_type_not_startswith:<value>, event_type_not_contains:<value>, event_type_not_endswith:<value>, event_type_startswith_ci:<value>, event_type_contains_ci:<value>, event_type_endswith_ci:<value>, event_type_not_startswith_ci:<value>, event_type_not_contains_ci:<value>, event_type_not_endswith_ci:<value>, event_type_matches:<regex>, event_type_not_matches:<regex>, event_type_matches_ci:<regex>, event_type_not_matches_ci:<regex>, event_type_equals_path:<path>, event_type_not_equals_path:<path>, event_type_equals_path_ci:<path>, event_type_not_equals_path_ci:<path>, event_type_startswith_path:<path>, event_type_contains_path:<path>, event_type_endswith_path:<path>, event_type_not_startswith_path:<path>, event_type_not_contains_path:<path>, event_type_not_endswith_path:<path>, event_type_startswith_path_ci:<path>, event_type_contains_path_ci:<path>, event_type_endswith_path_ci:<path>, event_type_not_startswith_path_ci:<path>, event_type_not_contains_path_ci:<path>, event_type_not_endswith_path_ci:<path>, event_type_matches_path:<path>, event_type_not_matches_path:<path>, event_type_matches_path_ci:<path>, event_type_not_matches_path_ci:<path>, event_type_in_path:<path>, event_type_not_in_path:<path>, event_type_in_path_ci:<path>, event_type_not_in_path_ci:<path>, payload_has:<key>, payload_path_empty:<path>, payload_path_not_empty:<path>, payload_path_exists:<path>, payload_path_not_exists:<path>, payload_path_is_null:<path>, payload_path_is_bool:<path>, payload_path_is_number:<path>, payload_path_is_string:<path>, payload_path_is_list:<path>, payload_path_is_object:<path>, payload_path_has_key:<path>=<string>, payload_path_not_has_key:<path>=<string>, payload_path_has_key_ci:<path>=<string>, payload_path_not_has_key_ci:<path>=<string>, payload_path_has_keys:<path>=<csv-or-json-list>, payload_path_missing_keys:<path>=<csv-or-json-list>, payload_path_has_keys_ci:<path>=<csv-or-json-list>, payload_path_missing_keys_ci:<path>=<csv-or-json-list>, payload_path_has_keys_path:<path>=<other.path>, payload_path_missing_keys_path:<path>=<other.path>, payload_path_has_keys_path_ci:<path>=<other.path>, payload_path_missing_keys_path_ci:<path>=<other.path>, payload_path_equals:<path>=<value>, payload_path_not_equals:<path>=<value>, payload_path_has_key_path:<path>=<other.path>, payload_path_not_has_key_path:<path>=<other.path>, payload_path_has_key_path_ci:<path>=<other.path>, payload_path_not_has_key_path_ci:<path>=<other.path>, payload_path_equals_path:<path>=<other.path>, payload_path_not_equals_path:<path>=<other.path>, payload_path_equals_path_ci:<path>=<other.path>, payload_path_not_equals_path_ci:<path>=<other.path>, payload_path_startswith_path:<path>=<other.path>, payload_path_contains_path:<path>=<other.path>, payload_path_endswith_path:<path>=<other.path>, payload_path_not_startswith_path:<path>=<other.path>, payload_path_not_contains_path:<path>=<other.path>, payload_path_not_endswith_path:<path>=<other.path>, payload_path_startswith_path_ci:<path>=<other.path>, payload_path_contains_path_ci:<path>=<other.path>, payload_path_endswith_path_ci:<path>=<other.path>, payload_path_not_startswith_path_ci:<path>=<other.path>, payload_path_not_contains_path_ci:<path>=<other.path>, payload_path_not_endswith_path_ci:<path>=<other.path>, payload_path_matches_path:<path>=<other.path>, payload_path_not_matches_path:<path>=<other.path>, payload_path_matches_path_ci:<path>=<other.path>, payload_path_not_matches_path_ci:<path>=<other.path>, payload_path_in_path:<path>=<other.path>, payload_path_not_in_path:<path>=<other.path>, payload_path_in_path_ci:<path>=<other.path>, payload_path_not_in_path_ci:<path>=<other.path>, payload_path_any_in_path:<path>=<other.path>, payload_path_all_in_path:<path>=<other.path>, payload_path_none_in_path:<path>=<other.path>, payload_path_any_in_path_ci:<path>=<other.path>, payload_path_all_in_path_ci:<path>=<other.path>, payload_path_none_in_path_ci:<path>=<other.path>, payload_path_in:<path>=<csv-or-json-list>, payload_path_not_in:<path>=<csv-or-json-list>, payload_path_in_ci:<path>=<csv-or-json-list>, payload_path_not_in_ci:<path>=<csv-or-json-list>, payload_path_any_in:<path>=<csv-or-json-list>, payload_path_all_in:<path>=<csv-or-json-list>, payload_path_none_in:<path>=<csv-or-json-list>, payload_path_any_in_ci:<path>=<csv-or-json-list>, payload_path_all_in_ci:<path>=<csv-or-json-list>, payload_path_none_in_ci:<path>=<csv-or-json-list>, payload_path_equals_ci:<path>=<string>, payload_path_not_equals_ci:<path>=<string>, payload_path_startswith:<path>=<string>, payload_path_contains:<path>=<string>, payload_path_endswith:<path>=<string>, payload_path_not_startswith:<path>=<string>, payload_path_not_contains:<path>=<string>, payload_path_not_endswith:<path>=<string>, payload_path_startswith_ci:<path>=<string>, payload_path_contains_ci:<path>=<string>, payload_path_endswith_ci:<path>=<string>, payload_path_not_startswith_ci:<path>=<string>, payload_path_not_contains_ci:<path>=<string>, payload_path_not_endswith_ci:<path>=<string>, payload_path_matches:<path>=<regex>, payload_path_not_matches:<path>=<regex>, payload_path_matches_ci:<path>=<regex>, payload_path_not_matches_ci:<path>=<regex>, payload_path_len_eq:<path>=<integer>, payload_path_len_not_eq:<path>=<integer>, payload_path_len_gt:<path>=<integer>, payload_path_len_gte:<path>=<integer>, payload_path_len_lt:<path>=<integer>, payload_path_len_lte:<path>=<integer>, payload_path_len_eq_path:<path>=<other.path>, payload_path_len_not_eq_path:<path>=<other.path>, payload_path_len_gt_path:<path>=<other.path>, payload_path_len_gte_path:<path>=<other.path>, payload_path_len_lt_path:<path>=<other.path>, payload_path_len_lte_path:<path>=<other.path>, payload_path_gt:<path>=<number>, payload_path_gte:<path>=<number>, payload_path_lt:<path>=<number>, payload_path_lte:<path>=<number>, payload_path_gt_path:<path>=<other.path>, payload_path_gte_path:<path>=<other.path>, payload_path_lt_path:<path>=<other.path>, payload_path_lte_path:<path>=<other.path>"
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


def _parse_payload_path_pair(
    raw_spec: str,
    *,
    operator: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    raw_path, separator, raw_other_path = raw_spec.partition("=")
    if not separator or not raw_other_path:
        raise TypeError(
            f"clause '{operator}' requires a non-empty '<path>=<other.path>' pair"
        )
    path = _parse_payload_path(raw_path, operator=operator)
    other_path = _parse_payload_path(raw_other_path, operator=operator)
    return path, other_path


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


def _parse_event_type_members(raw_members: str, *, operator: str) -> tuple[str, ...]:
    spec = raw_members.strip()
    if not spec:
        raise TypeError(f"clause '{operator}' requires at least one member")

    if spec[0] in "[{":
        try:
            parsed = json.loads(spec)
        except json.JSONDecodeError as exc:
            raise TypeError(
                f"clause '{operator}' requires a valid JSON array or comma-separated string list"
            ) from exc
        if not isinstance(parsed, list):
            raise TypeError(f"clause '{operator}' JSON form must decode to an array")
        if len(parsed) == 0:
            raise TypeError(f"clause '{operator}' requires at least one member")

        members: list[str] = []
        for value in parsed:
            if not isinstance(value, str) or not value:
                raise TypeError(f"clause '{operator}' members must be non-empty strings")
            members.append(value)
        return tuple(members)

    members: list[str] = []
    for raw_member in spec.split(","):
        member = raw_member.strip()
        if not member:
            raise TypeError(
                f"clause '{operator}' comma-separated form requires non-empty members"
            )
        members.append(member)

    return tuple(members)


def _parse_clause_string_members(raw_members: str, *, operator: str) -> tuple[str, ...]:
    members = _parse_clause_members(raw_members, operator=operator)
    normalized: list[str] = []
    for member in members:
        if not isinstance(member, str):
            raise TypeError(f"clause '{operator}' members must be strings")
        normalized.append(member)
    return tuple(normalized)


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


def _parse_clause_regex(
    raw_value: str,
    *,
    operator: str,
    case_insensitive: bool = False,
    expected_spec: str = "'<path>=<regex>' pair",
) -> re.Pattern[str]:
    try:
        flags = re.IGNORECASE if case_insensitive else 0
        return re.compile(raw_value, flags)
    except re.error as exc:
        raise TypeError(
            f"clause '{operator}' requires a valid {expected_spec}: {exc}"
        ) from exc


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


def _mapping_has_key(mapping: Mapping[Any, Any], key: str) -> bool:
    return key in mapping


def _mapping_has_key_ci(mapping: Mapping[Any, Any], key: str) -> bool:
    key_casefold = _casefold_string(key)
    return any(
        isinstance(candidate, str) and _casefold_string(candidate) == key_casefold
        for candidate in mapping.keys()
    )


def _payload_values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual is expected

    if actual is None or expected is None:
        return actual is None and expected is None

    if isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            return float(actual) == float(expected)

    return actual == expected


def _payload_strings_equal_ci(actual: Any, expected: Any) -> bool:
    return (
        isinstance(actual, str)
        and isinstance(expected, str)
        and _casefold_string(actual) == _casefold_string(expected)
    )


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


def _casefold_string(value: str) -> str:
    return value.casefold()


def _payload_string_member_matches(actual: str, expected_members: tuple[str, ...]) -> bool:
    actual_casefold = _casefold_string(actual)
    return any(actual_casefold == _casefold_string(expected) for expected in expected_members)


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


def _normalize_rule_priority(raw_priority: Any) -> int:
    if raw_priority is None:
        return 0

    if isinstance(raw_priority, bool) or not isinstance(raw_priority, int):
        raise TypeError("rule.priority must be an integer when present")

    return raw_priority


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

    if clause.kind == "event_type_equals_ci":
        return bool(event_type) and _casefold_string(event_type) == _casefold_string(clause.value)

    if clause.kind == "event_type_in":
        return bool(event_type) and event_type in clause.value

    if clause.kind == "event_type_not_in":
        return bool(event_type) and all(event_type != expected for expected in clause.value)

    if clause.kind == "event_type_in_ci":
        return bool(event_type) and _payload_string_member_matches(event_type, clause.value)

    if clause.kind == "event_type_not_in_ci":
        return bool(event_type) and not _payload_string_member_matches(event_type, clause.value)

    if clause.kind in {
        "event_type_startswith",
        "event_type_contains",
        "event_type_endswith",
        "event_type_not_startswith",
        "event_type_not_contains",
        "event_type_not_endswith",
        "event_type_startswith_ci",
        "event_type_contains_ci",
        "event_type_endswith_ci",
        "event_type_not_startswith_ci",
        "event_type_not_contains_ci",
        "event_type_not_endswith_ci",
        "event_type_matches",
        "event_type_not_matches",
        "event_type_matches_ci",
        "event_type_not_matches_ci",
    }:
        if not event_type:
            return False
        if clause.kind == "event_type_startswith":
            return event_type.startswith(clause.value)
        if clause.kind == "event_type_contains":
            return clause.value in event_type
        if clause.kind == "event_type_endswith":
            return event_type.endswith(clause.value)
        if clause.kind == "event_type_not_startswith":
            return not event_type.startswith(clause.value)
        if clause.kind == "event_type_not_contains":
            return clause.value not in event_type
        if clause.kind == "event_type_not_endswith":
            return not event_type.endswith(clause.value)
        if clause.kind in {
            "event_type_startswith_ci",
            "event_type_contains_ci",
            "event_type_endswith_ci",
            "event_type_not_startswith_ci",
            "event_type_not_contains_ci",
            "event_type_not_endswith_ci",
        }:
            actual_casefold = _casefold_string(event_type)
            expected_casefold = _casefold_string(clause.value)
            if clause.kind == "event_type_startswith_ci":
                return actual_casefold.startswith(expected_casefold)
            if clause.kind == "event_type_contains_ci":
                return expected_casefold in actual_casefold
            if clause.kind == "event_type_endswith_ci":
                return actual_casefold.endswith(expected_casefold)
            if clause.kind == "event_type_not_startswith_ci":
                return not actual_casefold.startswith(expected_casefold)
            if clause.kind == "event_type_not_contains_ci":
                return expected_casefold not in actual_casefold
            return not actual_casefold.endswith(expected_casefold)

        matched = clause.value.search(event_type) is not None
        if clause.kind in {"event_type_matches", "event_type_matches_ci"}:
            return matched
        return not matched

    if clause.kind in {
        "event_type_equals_path",
        "event_type_not_equals_path",
        "event_type_equals_path_ci",
        "event_type_not_equals_path_ci",
    }:
        if not event_type:
            return False
        other = _resolve_payload_path(payload, clause.path)
        if other is _MISSING_PAYLOAD_PATH:
            return False
        if clause.kind in {"event_type_equals_path_ci", "event_type_not_equals_path_ci"}:
            matched = _payload_strings_equal_ci(event_type, other)
            if clause.kind == "event_type_equals_path_ci":
                return matched
            return not matched
        matched = _payload_values_equal(event_type, other)
        if clause.kind == "event_type_equals_path":
            return matched
        return not matched

    if clause.kind in {
        "event_type_startswith_path",
        "event_type_contains_path",
        "event_type_endswith_path",
        "event_type_not_startswith_path",
        "event_type_not_contains_path",
        "event_type_not_endswith_path",
        "event_type_startswith_path_ci",
        "event_type_contains_path_ci",
        "event_type_endswith_path_ci",
        "event_type_not_startswith_path_ci",
        "event_type_not_contains_path_ci",
        "event_type_not_endswith_path_ci",
    }:
        if not event_type:
            return False
        other = _resolve_payload_path(payload, clause.path)
        if other is _MISSING_PAYLOAD_PATH or not isinstance(other, str):
            return False

        if clause.kind in {
            "event_type_startswith_path_ci",
            "event_type_contains_path_ci",
            "event_type_endswith_path_ci",
            "event_type_not_startswith_path_ci",
            "event_type_not_contains_path_ci",
            "event_type_not_endswith_path_ci",
        }:
            actual_value = _casefold_string(event_type)
            other_value = _casefold_string(other)
        else:
            actual_value = event_type
            other_value = other

        if clause.kind in {
            "event_type_startswith_path",
            "event_type_startswith_path_ci",
            "event_type_not_startswith_path",
            "event_type_not_startswith_path_ci",
        }:
            matched = actual_value.startswith(other_value)
        elif clause.kind in {
            "event_type_contains_path",
            "event_type_contains_path_ci",
            "event_type_not_contains_path",
            "event_type_not_contains_path_ci",
        }:
            matched = other_value in actual_value
        else:
            matched = actual_value.endswith(other_value)

        if clause.kind in {
            "event_type_not_startswith_path",
            "event_type_not_contains_path",
            "event_type_not_endswith_path",
            "event_type_not_startswith_path_ci",
            "event_type_not_contains_path_ci",
            "event_type_not_endswith_path_ci",
        }:
            return not matched
        return matched

    if clause.kind in {
        "event_type_matches_path",
        "event_type_not_matches_path",
        "event_type_matches_path_ci",
        "event_type_not_matches_path_ci",
    }:
        if not event_type:
            return False
        other = _resolve_payload_path(payload, clause.path)
        if other is _MISSING_PAYLOAD_PATH or not isinstance(other, str):
            return False
        try:
            pattern = re.compile(
                other,
                re.IGNORECASE
                if clause.kind in {"event_type_matches_path_ci", "event_type_not_matches_path_ci"}
                else 0,
            )
        except re.error:
            return False
        matched = pattern.search(event_type) is not None
        if clause.kind in {"event_type_matches_path", "event_type_matches_path_ci"}:
            return matched
        return not matched

    if clause.kind in {
        "event_type_in_path",
        "event_type_not_in_path",
        "event_type_in_path_ci",
        "event_type_not_in_path_ci",
    }:
        if not event_type:
            return False
        other = _resolve_payload_path(payload, clause.path)
        if other is _MISSING_PAYLOAD_PATH or not isinstance(other, list) or not other:
            return False
        if clause.kind in {"event_type_in_path_ci", "event_type_not_in_path_ci"}:
            if any(not isinstance(member, str) for member in other):
                return False
            matched = _payload_string_member_matches(event_type, tuple(other))
            if clause.kind == "event_type_in_path_ci":
                return matched
            return not matched
        matched = any(_payload_values_equal(event_type, expected) for expected in other)
        if clause.kind == "event_type_in_path":
            return matched
        return not matched

    if clause.kind == "payload_has":
        key = clause.value
        return key is not None and key in payload

    if clause.kind in {"payload_path_empty", "payload_path_not_empty"}:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False

        actual_length = _coerce_payload_length(actual)
        if actual_length is None:
            return False

        if clause.kind == "payload_path_empty":
            return actual_length == 0
        return actual_length > 0

    if clause.kind == "payload_path_exists":
        return _resolve_payload_path(payload, clause.path) is not _MISSING_PAYLOAD_PATH

    if clause.kind == "payload_path_not_exists":
        return _resolve_payload_path(payload, clause.path) is _MISSING_PAYLOAD_PATH

    if clause.kind in {
        "payload_path_is_null",
        "payload_path_is_bool",
        "payload_path_is_number",
        "payload_path_is_string",
        "payload_path_is_list",
        "payload_path_is_object",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False
        if clause.kind == "payload_path_is_null":
            return actual is None
        if clause.kind == "payload_path_is_bool":
            return isinstance(actual, bool)
        if clause.kind == "payload_path_is_number":
            return _coerce_payload_number(actual) is not None
        if clause.kind == "payload_path_is_string":
            return isinstance(actual, str)
        if clause.kind == "payload_path_is_list":
            return isinstance(actual, list)
        return isinstance(actual, Mapping)

    if clause.kind in {
        "payload_path_has_key",
        "payload_path_not_has_key",
        "payload_path_has_key_ci",
        "payload_path_not_has_key_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, Mapping):
            return False
        if clause.kind in {"payload_path_has_key_ci", "payload_path_not_has_key_ci"}:
            matched = _mapping_has_key_ci(actual, clause.value)
            if clause.kind == "payload_path_has_key_ci":
                return matched
            return not matched
        matched = _mapping_has_key(actual, clause.value)
        if clause.kind == "payload_path_has_key":
            return matched
        return not matched

    if clause.kind in {
        "payload_path_has_keys",
        "payload_path_missing_keys",
        "payload_path_has_keys_ci",
        "payload_path_missing_keys_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, Mapping):
            return False
        expected_keys = clause.value
        if not isinstance(expected_keys, tuple) or not expected_keys:
            return False
        matcher = _mapping_has_key_ci if clause.kind.endswith("_ci") else _mapping_has_key
        if clause.kind in {"payload_path_has_keys", "payload_path_has_keys_ci"}:
            return all(matcher(actual, key) for key in expected_keys)
        return all(not matcher(actual, key) for key in expected_keys)

    if clause.kind in {
        "payload_path_has_keys_path",
        "payload_path_missing_keys_path",
        "payload_path_has_keys_path_ci",
        "payload_path_missing_keys_path_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if actual is _MISSING_PAYLOAD_PATH or other is _MISSING_PAYLOAD_PATH:
            return False
        if not isinstance(actual, Mapping) or not isinstance(other, list) or not other:
            return False
        if any(not isinstance(member, str) for member in other):
            return False
        expected_keys = tuple(other)
        matcher = _mapping_has_key_ci if clause.kind.endswith("_ci") else _mapping_has_key
        if clause.kind in {"payload_path_has_keys_path", "payload_path_has_keys_path_ci"}:
            return all(matcher(actual, key) for key in expected_keys)
        return all(not matcher(actual, key) for key in expected_keys)

    if clause.kind == "payload_path_equals":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False
        return _payload_values_equal(actual, clause.value)

    if clause.kind == "payload_path_not_equals":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False
        return not _payload_values_equal(actual, clause.value)

    if clause.kind in {
        "payload_path_has_key_path",
        "payload_path_not_has_key_path",
        "payload_path_has_key_path_ci",
        "payload_path_not_has_key_path_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if actual is _MISSING_PAYLOAD_PATH or other is _MISSING_PAYLOAD_PATH:
            return False
        if not isinstance(actual, Mapping) or not isinstance(other, str):
            return False
        if clause.kind in {"payload_path_has_key_path_ci", "payload_path_not_has_key_path_ci"}:
            matched = _mapping_has_key_ci(actual, other)
            if clause.kind == "payload_path_has_key_path_ci":
                return matched
            return not matched
        matched = _mapping_has_key(actual, other)
        if clause.kind == "payload_path_has_key_path":
            return matched
        return not matched

    if clause.kind in {
        "payload_path_equals_path",
        "payload_path_not_equals_path",
        "payload_path_equals_path_ci",
        "payload_path_not_equals_path_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if actual is _MISSING_PAYLOAD_PATH or other is _MISSING_PAYLOAD_PATH:
            return False
        if clause.kind in {"payload_path_equals_path_ci", "payload_path_not_equals_path_ci"}:
            matched = _payload_strings_equal_ci(actual, other)
            if clause.kind == "payload_path_equals_path_ci":
                return matched
            return not matched
        matched = _payload_values_equal(actual, other)
        if clause.kind == "payload_path_equals_path":
            return matched
        return not matched

    if clause.kind in {
        "payload_path_startswith_path",
        "payload_path_contains_path",
        "payload_path_endswith_path",
        "payload_path_not_startswith_path",
        "payload_path_not_contains_path",
        "payload_path_not_endswith_path",
        "payload_path_startswith_path_ci",
        "payload_path_contains_path_ci",
        "payload_path_endswith_path_ci",
        "payload_path_not_startswith_path_ci",
        "payload_path_not_contains_path_ci",
        "payload_path_not_endswith_path_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if actual is _MISSING_PAYLOAD_PATH or other is _MISSING_PAYLOAD_PATH:
            return False
        if not isinstance(actual, str) or not isinstance(other, str):
            return False

        if clause.kind in {
            "payload_path_startswith_path_ci",
            "payload_path_contains_path_ci",
            "payload_path_endswith_path_ci",
            "payload_path_not_startswith_path_ci",
            "payload_path_not_contains_path_ci",
            "payload_path_not_endswith_path_ci",
        }:
            actual_value = _casefold_string(actual)
            other_value = _casefold_string(other)
        else:
            actual_value = actual
            other_value = other

        if clause.kind in {
            "payload_path_startswith_path",
            "payload_path_startswith_path_ci",
            "payload_path_not_startswith_path",
            "payload_path_not_startswith_path_ci",
        }:
            matched = actual_value.startswith(other_value)
        elif clause.kind in {
            "payload_path_contains_path",
            "payload_path_contains_path_ci",
            "payload_path_not_contains_path",
            "payload_path_not_contains_path_ci",
        }:
            matched = other_value in actual_value
        else:
            matched = actual_value.endswith(other_value)

        if clause.kind in {
            "payload_path_not_startswith_path",
            "payload_path_not_contains_path",
            "payload_path_not_endswith_path",
            "payload_path_not_startswith_path_ci",
            "payload_path_not_contains_path_ci",
            "payload_path_not_endswith_path_ci",
        }:
            return not matched
        return matched

    if clause.kind in {
        "payload_path_matches_path",
        "payload_path_not_matches_path",
        "payload_path_matches_path_ci",
        "payload_path_not_matches_path_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if actual is _MISSING_PAYLOAD_PATH or other is _MISSING_PAYLOAD_PATH:
            return False
        if not isinstance(actual, str) or not isinstance(other, str):
            return False
        try:
            pattern = re.compile(
                other,
                re.IGNORECASE
                if clause.kind in {
                    "payload_path_matches_path_ci",
                    "payload_path_not_matches_path_ci",
                }
                else 0,
            )
        except re.error:
            return False
        matched = pattern.search(actual) is not None
        if clause.kind in {"payload_path_matches_path", "payload_path_matches_path_ci"}:
            return matched
        return not matched

    if clause.kind in {
        "payload_path_in_path",
        "payload_path_not_in_path",
        "payload_path_in_path_ci",
        "payload_path_not_in_path_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if actual is _MISSING_PAYLOAD_PATH or other is _MISSING_PAYLOAD_PATH:
            return False
        if not isinstance(other, list) or not other:
            return False
        if clause.kind in {"payload_path_in_path_ci", "payload_path_not_in_path_ci"}:
            if not isinstance(actual, str) or any(not isinstance(member, str) for member in other):
                return False
            matched = _payload_string_member_matches(actual, tuple(other))
            if clause.kind == "payload_path_in_path_ci":
                return matched
            return not matched
        matched = any(_payload_values_equal(actual, expected) for expected in other)
        if clause.kind == "payload_path_in_path":
            return matched
        return not matched

    if clause.kind in {
        "payload_path_any_in_path",
        "payload_path_all_in_path",
        "payload_path_none_in_path",
        "payload_path_any_in_path_ci",
        "payload_path_all_in_path_ci",
        "payload_path_none_in_path_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if (
            actual is _MISSING_PAYLOAD_PATH
            or other is _MISSING_PAYLOAD_PATH
            or not isinstance(actual, list)
            or not actual
            or not isinstance(other, list)
            or not other
        ):
            return False
        if clause.kind in {
            "payload_path_any_in_path_ci",
            "payload_path_all_in_path_ci",
            "payload_path_none_in_path_ci",
        }:
            if any(not isinstance(member, str) for member in actual) or any(
                not isinstance(member, str) for member in other
            ):
                return False
            other_members = tuple(other)
            if clause.kind == "payload_path_any_in_path_ci":
                return any(
                    _payload_string_member_matches(member, other_members)
                    for member in actual
                )
            if clause.kind == "payload_path_all_in_path_ci":
                return all(
                    _payload_string_member_matches(member, other_members)
                    for member in actual
                )
            return all(
                not _payload_string_member_matches(member, other_members)
                for member in actual
            )
        if clause.kind == "payload_path_any_in_path":
            return any(
                any(_payload_values_equal(member, expected) for expected in other)
                for member in actual
            )
        if clause.kind == "payload_path_all_in_path":
            return all(
                any(_payload_values_equal(member, expected) for expected in other)
                for member in actual
            )
        return all(
            all(not _payload_values_equal(member, expected) for expected in other)
            for member in actual
        )

    if clause.kind == "payload_path_in":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False
        return any(_payload_values_equal(actual, expected) for expected in clause.value)

    if clause.kind == "payload_path_not_in":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH:
            return False
        return all(not _payload_values_equal(actual, expected) for expected in clause.value)

    if clause.kind in {"payload_path_in_ci", "payload_path_not_in_ci"}:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, str):
            return False
        matched = _payload_string_member_matches(actual, clause.value)
        if clause.kind == "payload_path_in_ci":
            return matched
        return not matched

    if clause.kind == "payload_path_any_in":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, list):
            return False
        return any(
            _payload_values_equal(member, expected)
            for member in actual
            for expected in clause.value
        )

    if clause.kind == "payload_path_all_in":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, list) or not actual:
            return False
        return all(
            any(_payload_values_equal(member, expected) for expected in clause.value)
            for member in actual
        )

    if clause.kind == "payload_path_none_in":
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, list) or not actual:
            return False
        return all(
            all(not _payload_values_equal(member, expected) for expected in clause.value)
            for member in actual
        )

    if clause.kind in {"payload_path_any_in_ci", "payload_path_all_in_ci", "payload_path_none_in_ci"}:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, list) or not actual:
            return False
        if any(not isinstance(member, str) for member in actual):
            return False
        if clause.kind == "payload_path_any_in_ci":
            return any(
                _payload_string_member_matches(member, clause.value)
                for member in actual
            )
        if clause.kind == "payload_path_all_in_ci":
            return all(
                _payload_string_member_matches(member, clause.value)
                for member in actual
            )
        return all(
            not _payload_string_member_matches(member, clause.value)
            for member in actual
        )

    if clause.kind in {
        "payload_path_equals_ci",
        "payload_path_not_equals_ci",
        "payload_path_startswith",
        "payload_path_contains",
        "payload_path_endswith",
        "payload_path_not_startswith",
        "payload_path_not_contains",
        "payload_path_not_endswith",
        "payload_path_startswith_ci",
        "payload_path_contains_ci",
        "payload_path_endswith_ci",
        "payload_path_not_startswith_ci",
        "payload_path_not_contains_ci",
        "payload_path_not_endswith_ci",
        "payload_path_matches",
        "payload_path_not_matches",
        "payload_path_matches_ci",
        "payload_path_not_matches_ci",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        if actual is _MISSING_PAYLOAD_PATH or not isinstance(actual, str):
            return False
        if clause.kind in {"payload_path_equals_ci", "payload_path_not_equals_ci"}:
            actual_casefold = _casefold_string(actual)
            expected_casefold = _casefold_string(clause.value)
            if clause.kind == "payload_path_equals_ci":
                return actual_casefold == expected_casefold
            return actual_casefold != expected_casefold
        if clause.kind == "payload_path_startswith":
            return actual.startswith(clause.value)
        if clause.kind == "payload_path_endswith":
            return actual.endswith(clause.value)
        if clause.kind == "payload_path_contains":
            return clause.value in actual
        if clause.kind == "payload_path_not_startswith":
            return not actual.startswith(clause.value)
        if clause.kind == "payload_path_not_endswith":
            return not actual.endswith(clause.value)
        if clause.kind == "payload_path_not_contains":
            return clause.value not in actual
        if clause.kind in {
            "payload_path_startswith_ci",
            "payload_path_contains_ci",
            "payload_path_endswith_ci",
            "payload_path_not_startswith_ci",
            "payload_path_not_contains_ci",
            "payload_path_not_endswith_ci",
        }:
            actual_casefold = _casefold_string(actual)
            expected_casefold = _casefold_string(clause.value)
            if clause.kind == "payload_path_startswith_ci":
                return actual_casefold.startswith(expected_casefold)
            if clause.kind == "payload_path_endswith_ci":
                return actual_casefold.endswith(expected_casefold)
            if clause.kind == "payload_path_contains_ci":
                return expected_casefold in actual_casefold
            if clause.kind == "payload_path_not_startswith_ci":
                return not actual_casefold.startswith(expected_casefold)
            if clause.kind == "payload_path_not_endswith_ci":
                return not actual_casefold.endswith(expected_casefold)
            return expected_casefold not in actual_casefold

        matched = clause.value.search(actual) is not None
        if clause.kind in {"payload_path_matches", "payload_path_matches_ci"}:
            return matched
        return not matched

    if clause.kind in {
        "payload_path_len_eq",
        "payload_path_len_not_eq",
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
        if clause.kind == "payload_path_len_eq":
            return actual_length == expected_length
        if clause.kind == "payload_path_len_not_eq":
            return actual_length != expected_length
        if clause.kind == "payload_path_len_gt":
            return actual_length > expected_length
        if clause.kind == "payload_path_len_gte":
            return actual_length >= expected_length
        if clause.kind == "payload_path_len_lt":
            return actual_length < expected_length
        return actual_length <= expected_length

    if clause.kind in {
        "payload_path_len_eq_path",
        "payload_path_len_not_eq_path",
        "payload_path_len_gt_path",
        "payload_path_len_gte_path",
        "payload_path_len_lt_path",
        "payload_path_len_lte_path",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if actual is _MISSING_PAYLOAD_PATH or other is _MISSING_PAYLOAD_PATH:
            return False

        actual_length = _coerce_payload_length(actual)
        other_length = _coerce_payload_length(other)
        if actual_length is None or other_length is None:
            return False

        if clause.kind == "payload_path_len_eq_path":
            return actual_length == other_length
        if clause.kind == "payload_path_len_not_eq_path":
            return actual_length != other_length
        if clause.kind == "payload_path_len_gt_path":
            return actual_length > other_length
        if clause.kind == "payload_path_len_gte_path":
            return actual_length >= other_length
        if clause.kind == "payload_path_len_lt_path":
            return actual_length < other_length
        return actual_length <= other_length

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

    if clause.kind in {
        "payload_path_gt_path",
        "payload_path_gte_path",
        "payload_path_lt_path",
        "payload_path_lte_path",
    }:
        actual = _resolve_payload_path(payload, clause.path)
        other = _resolve_payload_path(payload, clause.other_path)
        if actual is _MISSING_PAYLOAD_PATH or other is _MISSING_PAYLOAD_PATH:
            return False

        actual_number = _coerce_payload_number(actual)
        other_number = _coerce_payload_number(other)
        if actual_number is None or other_number is None:
            return False

        if clause.kind == "payload_path_gt_path":
            return actual_number > other_number
        if clause.kind == "payload_path_gte_path":
            return actual_number >= other_number
        if clause.kind == "payload_path_lt_path":
            return actual_number < other_number
        return actual_number <= other_number

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
