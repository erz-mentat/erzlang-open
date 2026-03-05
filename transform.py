from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from ir.refs import (
    REF_ID_RE,
    RefPolicyError,
    canonicalize_ref_bindings,
    ensure_ref_literals_resolved,
    normalize_ref_id,
)


class TransformError(ValueError):
    """Raised when pack/unpack input violates the supported Sprint-3 subset."""


_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")

_EVENT_TYPE_TO_SHORT = {
    "ingest_event": "ingest",
    "normalize_event": "normalize",
    "act_event": "act",
}
_EVENT_TYPE_FROM_SHORT = {value: key for key, value in _EVENT_TYPE_TO_SHORT.items()}

_ACTION_TYPE_TO_SHORT = {
    "notify_channel": "notify",
    "create_ticket": "ticket",
}
_ACTION_TYPE_FROM_SHORT = {value: key for key, value in _ACTION_TYPE_TO_SHORT.items()}

_MISSING = object()
_REF_VALUE_KEYS = ("v", "value", "text")
_REF_POINTER_KEYS = ("ref", "ref_id", "refId", "id", "$ref")


@dataclass(frozen=True)
class Atom:
    value: str


@dataclass(frozen=True)
class Token:
    kind: str
    value: Any
    position: int


def pack_json_text(text: str) -> str:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TransformError(f"Invalid JSON input: {exc.msg}") from exc
    return pack_document(document)


def unpack_to_json_text(text: str) -> str:
    document = unpack_compact_refs(text)
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)


def pack_document(document: Any) -> str:
    if not isinstance(document, dict):
        raise TransformError("Pack input must be a JSON object")

    _reject_unknown_keys(document, allowed={"event", "decision", "refs"}, context="root")

    if "event" not in document:
        raise TransformError("Pack input is missing required key 'event'")

    packed_event = _pack_event(document["event"])

    statements: list[dict[str, Any]] = [
        {"tag": "erz", "fields": {"v": 0.1}},
        {"tag": "ev", "fields": packed_event},
    ]

    if "decision" in document:
        statements.append({"tag": "dc", "fields": _pack_decision(document["decision"])})

    refs = _normalize_refs(document.get("refs", {}), context="refs")

    used_ref_literals = _collect_packed_event_ref_literals(packed_event)
    _ensure_resolved_refs(used_ref_literals, refs, context="pack event")

    for ref_id, value in refs.items():
        statements.append({"tag": "rf", "fields": {"id": ref_id, "v": value}})

    return _format_statements(statements)


def unpack_compact_refs(text: str) -> dict[str, Any]:
    statements = _parse_statements(text)

    header: dict[str, Any] | None = None
    event_fields: dict[str, Any] | None = None
    decision_fields: dict[str, Any] | None = None
    refs: dict[str, str] = {}

    for statement in statements:
        tag = statement["tag"]
        fields = statement["fields"]

        if tag == "erz":
            if header is not None:
                raise TransformError("Duplicate 'erz' header statement")
            header = fields
            continue

        if tag == "ev":
            if event_fields is not None:
                raise TransformError("Duplicate 'ev' statement")
            event_fields = fields
            continue

        if tag == "dc":
            if decision_fields is not None:
                raise TransformError("Duplicate 'dc' statement")
            decision_fields = fields
            continue

        if tag == "rf":
            _reject_unknown_keys(fields, allowed=set(_REF_POINTER_KEYS) | set(_REF_VALUE_KEYS), context="rf")
            pointer = {key: fields[key] for key in _REF_POINTER_KEYS if key in fields}
            if not pointer:
                raise TransformError(f"'rf' requires one pointer field: {', '.join(_REF_POINTER_KEYS)}")

            ref_id = _extract_ref_id(pointer, context="rf.id")
            ref_value = _resolve_required_value(
                (("rf", fields),),
                keys=_REF_VALUE_KEYS,
                context="rf.v",
                normalize=lambda raw, source: _expect_str(raw, source),
            )

            if ref_id in refs:
                raise TransformError(f"Duplicate ref id '{ref_id}'")
            refs[ref_id] = ref_value
            continue

        raise TransformError(f"Unsupported statement tag '{tag}' in compact+refs input")

    if header is None:
        raise TransformError("Missing required 'erz' header statement")

    _reject_unknown_keys(header, allowed={"v"}, context="erz")
    if "v" not in header or not isinstance(header["v"], (int, float)):
        raise TransformError("'erz.v' must be a number")

    if event_fields is None:
        raise TransformError("Missing required 'ev' statement")

    document: dict[str, Any] = {"event": _unpack_event(event_fields)}

    if decision_fields is not None:
        document["decision"] = _unpack_decision(decision_fields)

    used_ref_literals = _collect_document_ref_literals(document)
    _ensure_resolved_refs(used_ref_literals, refs, context="unpack document")

    if refs:
        document["refs"] = {key: refs[key] for key in sorted(refs.keys())}

    return document


def _pack_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransformError("'event' must be an object")

    if "type" not in value:
        raise TransformError("event.type is required")

    short_type = _normalize_event_tag(value["type"], context="event.type")

    if short_type == "ingest":
        return _pack_ingest_event(value)
    if short_type == "normalize":
        return _pack_normalize_event(value)
    if short_type == "act":
        return _pack_act_event(value)

    raise TransformError(f"Unsupported event type '{value['type']}'")


def _pack_ingest_event(event: dict[str, Any]) -> dict[str, Any]:
    context = "event(ingest_event)"
    _reject_unknown_keys(
        event,
        allowed={
            "id",
            "type",
            "source",
            "src",
            "text_ref",
            "textRef",
            "txt_ref",
            "txtRef",
            "txt",
            "timestamp",
            "ts",
            "geo",
            "payload",
        },
        context=context,
    )

    payload = _extract_payload_map(
        event,
        context=context,
        allowed={
            "source",
            "src",
            "text_ref",
            "textRef",
            "txt_ref",
            "txtRef",
            "txt",
            "timestamp",
            "ts",
            "geo",
        },
    )
    sources = (("event", event), ("event.payload", payload))

    packed_geo = _resolve_required_value(
        sources,
        keys=("geo",),
        context="event.geo",
        normalize=lambda value, source: _normalize_geo(value, context=source),
    )

    return {
        "id": _resolve_required_value(
            sources,
            keys=("id",),
            context="event.id",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "t": Atom("ingest"),
        "src": _atomize(
            _resolve_required_value(
                sources,
                keys=("source", "src"),
                context="event.source",
                normalize=lambda value, source: _expect_str(value, source),
            )
        ),
        "txt": _resolve_required_value(
            sources,
            keys=("text_ref", "textRef", "txt_ref", "txtRef", "txt"),
            context="event.text_ref",
            normalize=lambda value, source: _expect_ref(value, source),
        ),
        "ts": _resolve_required_value(
            sources,
            keys=("timestamp", "ts"),
            context="event.timestamp",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "geo": {
            "la": packed_geo["lat"],
            "lo": packed_geo["lon"],
        },
    }


def _pack_normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    context = "event(normalize_event)"
    _reject_unknown_keys(
        event,
        allowed={
            "id",
            "type",
            "source",
            "src",
            "ingest_ref",
            "ingestRef",
            "ing_ref",
            "ingRef",
            "ing",
            "language",
            "lang",
            "timezone",
            "tz",
            "entities",
            "ent",
            "normalized_text_ref",
            "normalizedTextRef",
            "norm_text_ref",
            "normTextRef",
            "txt",
            "payload",
        },
        context=context,
    )

    payload = _extract_payload_map(
        event,
        context=context,
        allowed={
            "source",
            "src",
            "ingest_ref",
            "ingestRef",
            "ing_ref",
            "ingRef",
            "ing",
            "language",
            "lang",
            "timezone",
            "tz",
            "entities",
            "ent",
            "normalized_text_ref",
            "normalizedTextRef",
            "norm_text_ref",
            "normTextRef",
            "txt",
        },
    )
    sources = (("event", event), ("event.payload", payload))

    packed_entities = _resolve_required_value(
        sources,
        keys=("entities", "ent"),
        context="event.entities",
        normalize=lambda value, source: _normalize_entities(value, context=source),
    )

    return {
        "id": _resolve_required_value(
            sources,
            keys=("id",),
            context="event.id",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "t": Atom("normalize"),
        "src": _atomize(
            _resolve_required_value(
                sources,
                keys=("source", "src"),
                context="event.source",
                normalize=lambda value, source: _expect_str(value, source),
            )
        ),
        "ing": _resolve_required_value(
            sources,
            keys=("ingest_ref", "ingestRef", "ing_ref", "ingRef", "ing"),
            context="event.ingest_ref",
            normalize=lambda value, source: _expect_ref(value, source),
        ),
        "lang": _atomize(
            _resolve_required_value(
                sources,
                keys=("language", "lang"),
                context="event.language",
                normalize=lambda value, source: _expect_str(value, source),
            )
        ),
        "tz": _resolve_required_value(
            sources,
            keys=("timezone", "tz"),
            context="event.timezone",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "ent": packed_entities,
        "txt": _resolve_required_value(
            sources,
            keys=("normalized_text_ref", "normalizedTextRef", "norm_text_ref", "normTextRef", "txt"),
            context="event.normalized_text_ref",
            normalize=lambda value, source: _expect_ref(value, source),
        ),
    }


def _pack_act_event(event: dict[str, Any]) -> dict[str, Any]:
    context = "event(act_event)"
    _reject_unknown_keys(
        event,
        allowed={
            "id",
            "type",
            "decision_ref",
            "decisionRef",
            "dec_ref",
            "decRef",
            "dec",
            "actions",
            "act",
            "deadline_s",
            "deadlineSec",
            "deadline_seconds",
            "ddl",
            "payload",
        },
        context=context,
    )

    payload = _extract_payload_map(
        event,
        context=context,
        allowed={
            "decision_ref",
            "decisionRef",
            "dec_ref",
            "decRef",
            "dec",
            "actions",
            "act",
            "deadline_s",
            "deadlineSec",
            "deadline_seconds",
            "ddl",
        },
    )
    sources = (("event", event), ("event.payload", payload))

    packed_actions = _resolve_required_value(
        sources,
        keys=("actions", "act"),
        context="event.actions",
        normalize=lambda value, source: _normalize_actions(value, context=source),
    )

    return {
        "id": _resolve_required_value(
            sources,
            keys=("id",),
            context="event.id",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "t": Atom("act"),
        "dec": _resolve_required_value(
            sources,
            keys=("decision_ref", "decisionRef", "dec_ref", "decRef", "dec"),
            context="event.decision_ref",
            normalize=lambda value, source: _expect_ref(value, source),
        ),
        "act": packed_actions,
        "ddl": _resolve_required_value(
            sources,
            keys=("deadline_s", "deadlineSec", "deadline_seconds", "ddl"),
            context="event.deadline_s",
            normalize=lambda value, source: _expect_number(value, source),
        ),
    }


def _pack_action(action: Any, index: int) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise TransformError(f"event.actions[{index}] must be an object")

    context = f"event.actions[{index}]"

    _reject_unknown_keys(
        action,
        allowed={
            "type",
            "t",
            "target",
            "template_ref",
            "templateRef",
            "tpl",
            "system",
            "sys",
            "priority",
            "prio",
            "dedupe_key",
            "dedupeKey",
            "ddk",
            "params",
        },
        context=context,
    )

    short = _resolve_required_value(
        ((context, action),),
        keys=("type", "t"),
        context=f"{context}.type",
        normalize=lambda value, source: _normalize_action_tag(value, context=source),
    )

    if short == "notify":
        _reject_unknown_keys(
            action,
            allowed={"type", "t", "target", "template_ref", "templateRef", "tpl", "params"},
            context=context,
        )
        params = _extract_payload_map(
            action,
            context=context,
            allowed={"target", "template_ref", "templateRef", "tpl"},
            payload_key="params",
        )
        sources = ((context, action), (f"{context}.params", params))
        return {
            "t": Atom("notify"),
            "target": _atomize(
                _resolve_required_value(
                    sources,
                    keys=("target",),
                    context=f"{context}.target",
                    normalize=lambda value, source: _expect_str(value, source),
                )
            ),
            "tpl": _resolve_required_value(
                sources,
                keys=("template_ref", "templateRef", "tpl"),
                context=f"{context}.template_ref",
                normalize=lambda value, source: _expect_ref(value, source),
            ),
        }

    if short == "ticket":
        _reject_unknown_keys(
            action,
            allowed={
                "type",
                "t",
                "system",
                "sys",
                "priority",
                "prio",
                "dedupe_key",
                "dedupeKey",
                "ddk",
                "params",
            },
            context=context,
        )
        params = _extract_payload_map(
            action,
            context=context,
            allowed={"system", "sys", "priority", "prio", "dedupe_key", "dedupeKey", "ddk"},
            payload_key="params",
        )
        sources = ((context, action), (f"{context}.params", params))
        return {
            "t": Atom("ticket"),
            "sys": _atomize(
                _resolve_required_value(
                    sources,
                    keys=("system", "sys"),
                    context=f"{context}.system",
                    normalize=lambda value, source: _expect_str(value, source),
                )
            ),
            "prio": _atomize(
                _resolve_required_value(
                    sources,
                    keys=("priority", "prio"),
                    context=f"{context}.priority",
                    normalize=lambda value, source: _expect_str(value, source),
                )
            ),
            "ddk": _resolve_required_value(
                sources,
                keys=("dedupe_key", "dedupeKey", "ddk"),
                context=f"{context}.dedupe_key",
                normalize=lambda value, source: _expect_str(value, source),
            ),
        }

    raise TransformError(f"Unsupported action type '{action_type}'")


def _pack_decision(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransformError("'decision' must be an object")

    _reject_unknown_keys(
        value,
        allowed={"id", "score", "reason_codes", "reasonCodes", "rc"},
        context="decision",
    )
    _require_keys(value, required={"id", "score"}, context="decision")

    reason_codes = _resolve_required_value(
        (("decision", value),),
        keys=("reason_codes", "reasonCodes", "rc"),
        context="decision.reason_codes",
        normalize=lambda raw, source: _normalize_reason_codes(raw, context=source),
    )

    return {
        "id": _expect_str(value["id"], "decision.id"),
        "score": _expect_number(value["score"], "decision.score"),
        "rc": [_atomize(item) for item in reason_codes],
    }


def _unpack_event(fields: dict[str, Any]) -> dict[str, Any]:
    _require_keys(fields, required={"id"}, context="ev")

    short_type = _resolve_required_value(
        (("ev", fields),),
        keys=("t", "type"),
        context="ev.t",
        normalize=lambda value, source: _normalize_event_tag(value, context=source),
    )

    event_type = _EVENT_TYPE_FROM_SHORT.get(short_type)
    if event_type is None:
        supported = ", ".join(sorted(_EVENT_TYPE_FROM_SHORT.keys()))
        raise TransformError(f"Unsupported ev.t '{short_type}'. Supported: {supported}")

    if short_type == "ingest":
        return _unpack_ingest_event(fields, event_type)
    if short_type == "normalize":
        return _unpack_normalize_event(fields, event_type)
    if short_type == "act":
        return _unpack_act_event(fields, event_type)

    raise TransformError(f"Unsupported ev.t '{short_type}'")


def _unpack_ingest_event(fields: dict[str, Any], event_type: str) -> dict[str, Any]:
    context = "ev(ingest)"
    _reject_unknown_keys(
        fields,
        allowed={
            "id",
            "t",
            "type",
            "src",
            "source",
            "txt",
            "text_ref",
            "textRef",
            "ts",
            "timestamp",
            "geo",
            "payload",
        },
        context=context,
    )

    payload = _extract_payload_map(
        fields,
        context=context,
        allowed={"src", "source", "txt", "text_ref", "textRef", "ts", "timestamp", "geo"},
    )
    sources = (("ev", fields), ("ev.payload", payload))

    geo = _resolve_required_value(
        sources,
        keys=("geo",),
        context="ev.geo",
        normalize=lambda value, source: _normalize_compact_geo(value, context=source),
    )

    return {
        "id": _resolve_required_value(
            sources,
            keys=("id",),
            context="ev.id",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "type": event_type,
        "source": _resolve_required_value(
            sources,
            keys=("src", "source"),
            context="ev.src",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "text_ref": _resolve_required_value(
            sources,
            keys=("txt", "text_ref", "textRef"),
            context="ev.txt",
            normalize=lambda value, source: _expect_ref(value, source),
        ),
        "timestamp": _resolve_required_value(
            sources,
            keys=("ts", "timestamp"),
            context="ev.ts",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "geo": {
            "lat": geo["lat"],
            "lon": geo["lon"],
        },
    }


def _unpack_normalize_event(fields: dict[str, Any], event_type: str) -> dict[str, Any]:
    context = "ev(normalize)"
    _reject_unknown_keys(
        fields,
        allowed={
            "id",
            "t",
            "type",
            "src",
            "source",
            "ing",
            "ingest_ref",
            "ingestRef",
            "lang",
            "language",
            "tz",
            "timezone",
            "ent",
            "entities",
            "txt",
            "normalized_text_ref",
            "normalizedTextRef",
            "payload",
        },
        context=context,
    )

    payload = _extract_payload_map(
        fields,
        context=context,
        allowed={
            "src",
            "source",
            "ing",
            "ingest_ref",
            "ingestRef",
            "lang",
            "language",
            "tz",
            "timezone",
            "ent",
            "entities",
            "txt",
            "normalized_text_ref",
            "normalizedTextRef",
        },
    )
    sources = (("ev", fields), ("ev.payload", payload))

    entities = _resolve_required_value(
        sources,
        keys=("ent", "entities"),
        context="ev.ent",
        normalize=lambda value, source: _normalize_compact_entities(value, context=source),
    )

    return {
        "id": _resolve_required_value(
            sources,
            keys=("id",),
            context="ev.id",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "type": event_type,
        "source": _resolve_required_value(
            sources,
            keys=("src", "source"),
            context="ev.src",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "ingest_ref": _resolve_required_value(
            sources,
            keys=("ing", "ingest_ref", "ingestRef"),
            context="ev.ing",
            normalize=lambda value, source: _expect_ref(value, source),
        ),
        "language": _resolve_required_value(
            sources,
            keys=("lang", "language"),
            context="ev.lang",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "timezone": _resolve_required_value(
            sources,
            keys=("tz", "timezone"),
            context="ev.tz",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "entities": entities,
        "normalized_text_ref": _resolve_required_value(
            sources,
            keys=("txt", "normalized_text_ref", "normalizedTextRef"),
            context="ev.txt",
            normalize=lambda value, source: _expect_ref(value, source),
        ),
    }


def _unpack_act_event(fields: dict[str, Any], event_type: str) -> dict[str, Any]:
    context = "ev(act)"
    _reject_unknown_keys(
        fields,
        allowed={
            "id",
            "t",
            "type",
            "dec",
            "decision_ref",
            "decisionRef",
            "act",
            "actions",
            "ddl",
            "deadline_s",
            "deadlineSec",
            "payload",
        },
        context=context,
    )

    payload = _extract_payload_map(
        fields,
        context=context,
        allowed={
            "dec",
            "decision_ref",
            "decisionRef",
            "act",
            "actions",
            "ddl",
            "deadline_s",
            "deadlineSec",
        },
    )
    sources = (("ev", fields), ("ev.payload", payload))

    actions = _resolve_required_value(
        sources,
        keys=("act", "actions"),
        context="ev.act",
        normalize=lambda value, source: _normalize_compact_actions(value, context=source),
    )

    return {
        "id": _resolve_required_value(
            sources,
            keys=("id",),
            context="ev.id",
            normalize=lambda value, source: _expect_str(value, source),
        ),
        "type": event_type,
        "decision_ref": _resolve_required_value(
            sources,
            keys=("dec", "decision_ref", "decisionRef"),
            context="ev.dec",
            normalize=lambda value, source: _expect_ref(value, source),
        ),
        "actions": actions,
        "deadline_s": _resolve_required_value(
            sources,
            keys=("ddl", "deadline_s", "deadlineSec"),
            context="ev.ddl",
            normalize=lambda value, source: _expect_number(value, source),
        ),
    }


def _unpack_action(action: Any, index: int) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise TransformError(f"ev.act[{index}] must be an object")

    context = f"ev.act[{index}]"

    _reject_unknown_keys(
        action,
        allowed={
            "t",
            "type",
            "target",
            "template_ref",
            "templateRef",
            "tpl",
            "system",
            "sys",
            "priority",
            "prio",
            "dedupe_key",
            "dedupeKey",
            "ddk",
            "params",
        },
        context=context,
    )

    params = _extract_payload_map(
        action,
        context=context,
        allowed={
            "target",
            "template_ref",
            "templateRef",
            "tpl",
            "system",
            "sys",
            "priority",
            "prio",
            "dedupe_key",
            "dedupeKey",
            "ddk",
        },
        payload_key="params",
    )
    sources = ((context, action), (f"{context}.params", params))

    short = _resolve_required_value(
        ((context, action),),
        keys=("t", "type"),
        context=f"{context}.t",
        normalize=lambda value, source: _normalize_action_tag(value, context=source),
    )

    action_type = _ACTION_TYPE_FROM_SHORT.get(short)
    if action_type is None:
        supported = ", ".join(sorted(_ACTION_TYPE_FROM_SHORT.keys()))
        raise TransformError(f"Unsupported {context}.t '{short}'. Supported: {supported}")

    if short == "notify":
        return {
            "type": action_type,
            "target": _resolve_required_value(
                sources,
                keys=("target",),
                context=f"{context}.target",
                normalize=lambda value, source: _expect_str(value, source),
            ),
            "template_ref": _resolve_required_value(
                sources,
                keys=("tpl", "template_ref", "templateRef"),
                context=f"{context}.tpl",
                normalize=lambda value, source: _expect_ref(value, source),
            ),
        }

    if short == "ticket":
        return {
            "type": action_type,
            "system": _resolve_required_value(
                sources,
                keys=("sys", "system"),
                context=f"{context}.sys",
                normalize=lambda value, source: _expect_str(value, source),
            ),
            "priority": _resolve_required_value(
                sources,
                keys=("prio", "priority"),
                context=f"{context}.prio",
                normalize=lambda value, source: _expect_str(value, source),
            ),
            "dedupe_key": _resolve_required_value(
                sources,
                keys=("ddk", "dedupe_key", "dedupeKey"),
                context=f"{context}.ddk",
                normalize=lambda value, source: _expect_str(value, source),
            ),
        }

    raise TransformError(f"Unsupported {context}.t '{short}'")


def _unpack_decision(fields: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(fields, allowed={"id", "score", "rc", "reason_codes", "reasonCodes"}, context="dc")
    _require_keys(fields, required={"id", "score"}, context="dc")

    reason_codes = _resolve_required_value(
        (("dc", fields),),
        keys=("rc", "reason_codes", "reasonCodes"),
        context="dc.rc",
        normalize=lambda value, source: _normalize_reason_codes(value, context=source),
    )

    return {
        "id": _expect_str(fields["id"], "dc.id"),
        "score": _expect_number(fields["score"], "dc.score"),
        "reason_codes": list(reason_codes),
    }


def _extract_payload_map(
    mapping: dict[str, Any],
    *,
    context: str,
    allowed: set[str],
    payload_key: str = "payload",
) -> dict[str, Any]:
    payload = mapping.get(payload_key, _MISSING)
    if payload is _MISSING or payload is None:
        return {}
    if not isinstance(payload, dict):
        raise TransformError(f"{context}.{payload_key} must be an object when present")
    _reject_unknown_keys(payload, allowed=allowed, context=f"{context}.{payload_key}")
    return payload


def _resolve_required_value(
    sources: tuple[tuple[str, dict[str, Any]], ...] | list[tuple[str, dict[str, Any]]],
    *,
    keys: tuple[str, ...],
    context: str,
    normalize: Callable[[Any, str], Any],
) -> Any:
    found: list[tuple[str, Any]] = []
    for source_name, mapping in sources:
        for key in keys:
            if key in mapping:
                source = f"{source_name}.{key}"
                found.append((source, normalize(mapping[key], source)))

    if not found:
        raise TransformError(f"Missing required field(s) in {context}: one of {', '.join(keys)}")

    canonical = found[0][1]
    for source, value in found[1:]:
        if value != canonical:
            first_source = found[0][0]
            raise TransformError(
                f"Conflicting values for {context} between {first_source} and {source}"
            )

    return canonical


def _normalize_geo(value: Any, *, context: str) -> dict[str, int | float]:
    if not isinstance(value, dict):
        raise TransformError(f"{context} must be an object")

    _reject_unknown_keys(value, allowed={"lat", "latitude", "la", "lon", "longitude", "lo"}, context=context)

    lat = _resolve_required_value(
        ((context, value),),
        keys=("lat", "latitude", "la"),
        context=f"{context}.lat",
        normalize=lambda raw, source: _expect_number(raw, source),
    )
    lon = _resolve_required_value(
        ((context, value),),
        keys=("lon", "longitude", "lo"),
        context=f"{context}.lon",
        normalize=lambda raw, source: _expect_number(raw, source),
    )

    return {"lat": lat, "lon": lon}


def _normalize_compact_geo(value: Any, *, context: str) -> dict[str, int | float]:
    return _normalize_geo(value, context=context)


def _normalize_entities(value: Any, *, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TransformError(f"{context} must be a list")

    packed_entities: list[dict[str, Any]] = []
    for index, entity in enumerate(value):
        item_context = f"{context}[{index}]"
        if not isinstance(entity, dict):
            raise TransformError(f"{item_context} must be an object")

        _reject_unknown_keys(
            entity,
            allowed={"kind", "type", "k", "value", "text", "v", "confidence", "score", "c"},
            context=item_context,
        )

        sources = ((item_context, entity),)
        packed_entities.append(
            {
                "k": _atomize(
                    _resolve_required_value(
                        sources,
                        keys=("kind", "type", "k"),
                        context=f"{item_context}.kind",
                        normalize=lambda raw, source: _expect_str(raw, source),
                    )
                ),
                "v": _resolve_required_value(
                    sources,
                    keys=("value", "text", "v"),
                    context=f"{item_context}.value",
                    normalize=lambda raw, source: _expect_str(raw, source),
                ),
                "c": _resolve_required_value(
                    sources,
                    keys=("confidence", "score", "c"),
                    context=f"{item_context}.confidence",
                    normalize=lambda raw, source: _expect_number(raw, source),
                ),
            }
        )

    return packed_entities


def _normalize_compact_entities(value: Any, *, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TransformError(f"{context} must be a list")

    entities: list[dict[str, Any]] = []
    for index, entity in enumerate(value):
        item_context = f"{context}[{index}]"
        if not isinstance(entity, dict):
            raise TransformError(f"{item_context} must be an object")

        _reject_unknown_keys(
            entity,
            allowed={"k", "kind", "type", "v", "value", "text", "c", "confidence", "score"},
            context=item_context,
        )

        sources = ((item_context, entity),)
        entities.append(
            {
                "kind": _resolve_required_value(
                    sources,
                    keys=("k", "kind", "type"),
                    context=f"{item_context}.k",
                    normalize=lambda raw, source: _expect_str(raw, source),
                ),
                "value": _resolve_required_value(
                    sources,
                    keys=("v", "value", "text"),
                    context=f"{item_context}.v",
                    normalize=lambda raw, source: _expect_str(raw, source),
                ),
                "confidence": _resolve_required_value(
                    sources,
                    keys=("c", "confidence", "score"),
                    context=f"{item_context}.c",
                    normalize=lambda raw, source: _expect_number(raw, source),
                ),
            }
        )

    return entities


def _normalize_actions(value: Any, *, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TransformError(f"{context} must be a list")
    return [_pack_action(item, index) for index, item in enumerate(value)]


def _normalize_compact_actions(value: Any, *, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TransformError(f"{context} must be a list")
    return [_unpack_action(item, index) for index, item in enumerate(value)]


def _normalize_event_tag(value: Any, *, context: str) -> str:
    raw = _expect_str(value, context)
    if raw in _EVENT_TYPE_FROM_SHORT:
        return raw
    if raw in _EVENT_TYPE_TO_SHORT:
        return _EVENT_TYPE_TO_SHORT[raw]

    supported = ", ".join(sorted(set(_EVENT_TYPE_FROM_SHORT.keys()) | set(_EVENT_TYPE_TO_SHORT.keys())))
    raise TransformError(f"Unsupported event tag '{raw}' in {context}. Supported: {supported}")


def _normalize_action_tag(value: Any, *, context: str) -> str:
    raw = _expect_str(value, context)
    if raw in _ACTION_TYPE_FROM_SHORT:
        return raw
    if raw in _ACTION_TYPE_TO_SHORT:
        return _ACTION_TYPE_TO_SHORT[raw]

    supported = ", ".join(sorted(set(_ACTION_TYPE_FROM_SHORT.keys()) | set(_ACTION_TYPE_TO_SHORT.keys())))
    raise TransformError(f"Unsupported action tag '{raw}' in {context}. Supported: {supported}")


def _normalize_reason_codes(value: Any, *, context: str) -> list[str]:
    if not isinstance(value, list):
        raise TransformError(f"{context} must be a list of strings")

    out: list[str] = []
    for index, item in enumerate(value):
        item_context = f"{context}[{index}]"
        if isinstance(item, str):
            out.append(item)
            continue

        if isinstance(item, dict):
            _reject_unknown_keys(item, allowed={"code", "id", "value"}, context=item_context)
            out.append(
                _resolve_required_value(
                    ((item_context, item),),
                    keys=("code", "id", "value"),
                    context=item_context,
                    normalize=lambda raw, source: _expect_str(raw, source),
                )
            )
            continue

        raise TransformError(f"{item_context} must be a string")

    return out


def _extract_ref_id(value: Any, *, context: str) -> str:
    raw_value = value

    if isinstance(value, dict):
        _reject_unknown_keys(value, allowed=set(_REF_POINTER_KEYS), context=context)
        raw_value = _resolve_required_value(
            ((context, value),),
            keys=_REF_POINTER_KEYS,
            context=context,
            normalize=lambda raw, source: _expect_str(raw, source),
        )

    if not isinstance(raw_value, str):
        raise TransformError(f"{context} must be a reference string")

    try:
        return normalize_ref_id(raw_value, context=context, allow_literal=True)
    except RefPolicyError as exc:
        raise TransformError(str(exc)) from exc


def _normalize_refs(refs: Any, *, context: str) -> dict[str, str]:
    if refs is None:
        return {}

    if isinstance(refs, list):
        refs_map: dict[str, str] = {}
        source_keys: dict[str, str] = {}
        for index, item in enumerate(refs):
            item_context = f"{context}[{index}]"
            if not isinstance(item, dict):
                raise TransformError(f"{item_context} must be an object")

            _reject_unknown_keys(item, allowed=set(_REF_POINTER_KEYS) | set(_REF_VALUE_KEYS), context=item_context)
            pointer = {key: item[key] for key in _REF_POINTER_KEYS if key in item}
            if not pointer:
                raise TransformError(f"Missing required field(s) in {item_context}.id: one of {', '.join(_REF_POINTER_KEYS)}")
            ref_id = _extract_ref_id(pointer, context=f"{item_context}.id")
            ref_value = _resolve_required_value(
                ((item_context, item),),
                keys=_REF_VALUE_KEYS,
                context=f"{item_context}.value",
                normalize=lambda raw, source: _expect_str(raw, source),
            )

            if ref_id in refs_map:
                previous_key = source_keys[ref_id]
                raise TransformError(
                    f"{context} contains colliding ref ids '{previous_key}' and '{item_context}' "
                    f"(canonical id '{ref_id}')"
                )

            refs_map[ref_id] = ref_value
            source_keys[ref_id] = item_context

        return {ref_id: refs_map[ref_id] for ref_id in sorted(refs_map.keys())}

    if not isinstance(refs, dict):
        raise TransformError("'refs' must be an object or list when present")

    refs_map: dict[str, str] = {}
    source_keys: dict[str, str] = {}
    for raw_key, raw_value in refs.items():
        try:
            ref_id = normalize_ref_id(raw_key, context=f"{context} key '{raw_key}'", allow_literal=True)
        except RefPolicyError as exc:
            raise TransformError(str(exc)) from exc

        if isinstance(raw_value, str):
            ref_value = raw_value
        elif isinstance(raw_value, dict):
            value_context = f"{context}['{raw_key}']"
            _reject_unknown_keys(raw_value, allowed=set(_REF_VALUE_KEYS), context=value_context)
            ref_value = _resolve_required_value(
                ((value_context, raw_value),),
                keys=_REF_VALUE_KEYS,
                context=value_context,
                normalize=lambda raw, source: _expect_str(raw, source),
            )
        else:
            raise TransformError(f"{context}['{raw_key}'] must be a string or object")

        if ref_id in refs_map:
            previous_key = source_keys[ref_id]
            raise TransformError(
                f"{context} contains colliding ref ids '{previous_key}' and '{raw_key}' "
                f"(canonical id '{ref_id}')"
            )

        refs_map[ref_id] = ref_value
        source_keys[ref_id] = raw_key

    try:
        return canonicalize_ref_bindings(refs_map, context=context, allow_literal_keys=False)
    except RefPolicyError as exc:
        raise TransformError(str(exc)) from exc


def _ensure_resolved_refs(ref_literals: list[str], refs: dict[str, str], *, context: str) -> None:
    try:
        ensure_ref_literals_resolved(ref_literals, refs, context=context)
    except RefPolicyError as exc:
        raise TransformError(str(exc)) from exc


def _collect_packed_event_ref_literals(fields: dict[str, Any]) -> list[str]:
    event_short = fields.get("t")
    if isinstance(event_short, Atom):
        event_short = event_short.value

    ref_literals: list[str] = []

    if event_short == "ingest":
        ref_literals.append(_expect_ref(fields["txt"], "ev.txt"))
        return ref_literals

    if event_short == "normalize":
        # ingest refs point to prior event ids, not to rf{} bindings
        ref_literals.append(_expect_ref(fields["txt"], "ev.txt"))
        return ref_literals

    if event_short == "act":
        # decision refs point to decision ids, not to rf{} bindings
        actions = fields.get("act", [])
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            action_short = action.get("t")
            if isinstance(action_short, Atom):
                action_short = action_short.value
            if action_short == "notify" and "tpl" in action:
                ref_literals.append(_expect_ref(action["tpl"], f"ev.act[{index}].tpl"))

    return ref_literals


def _collect_document_ref_literals(document: dict[str, Any]) -> list[str]:
    event = document.get("event")
    if not isinstance(event, dict):
        return []

    event_type = event.get("type")
    ref_literals: list[str] = []

    if event_type == "ingest_event" and "text_ref" in event:
        ref_literals.append(_expect_ref(event["text_ref"], "event.text_ref"))

    if event_type == "normalize_event" and "normalized_text_ref" in event:
        # ingest refs point to event ids, not to rf{} bindings
        ref_literals.append(_expect_ref(event["normalized_text_ref"], "event.normalized_text_ref"))

    if event_type == "act_event":
        actions = event.get("actions", [])
        if isinstance(actions, list):
            for index, action in enumerate(actions):
                if not isinstance(action, dict):
                    continue
                if action.get("type") == "notify_channel" and "template_ref" in action:
                    ref_literals.append(
                        _expect_ref(action["template_ref"], f"event.actions[{index}].template_ref")
                    )

    return ref_literals


def _expect_str(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise TransformError(f"{context} must be a string")
    return value


def _expect_ref(value: Any, context: str) -> str:
    ref_id = _extract_ref_id(value, context=context)
    return f"@{ref_id}"


def _expect_number(value: Any, context: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransformError(f"{context} must be a number")
    return value


def _atomize(value: str) -> Atom | str:
    if _IDENTIFIER_RE.fullmatch(value) and value not in {"true", "false", "null"}:
        return Atom(value)
    return value


def _reject_unknown_keys(mapping: dict[str, Any], *, allowed: set[str], context: str) -> None:
    unknown = set(mapping.keys()) - allowed
    if unknown:
        raise TransformError(f"Unknown field(s) in {context}: {', '.join(sorted(unknown))}")


def _require_keys(mapping: dict[str, Any], *, required: set[str], context: str) -> None:
    missing = required - set(mapping.keys())
    if missing:
        raise TransformError(f"Missing required field(s) in {context}: {', '.join(sorted(missing))}")


def _parse_statements(text: str) -> list[dict[str, Any]]:
    tokens = _Tokenizer(text).tokenize()
    parser = _Parser(tokens)
    return parser.parse_program()


class _Tokenizer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.length = len(text)
        self.index = 0

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []

        while self.index < self.length:
            char = self.text[self.index]

            if char.isspace():
                self.index += 1
                continue

            if char in "{}[]:,":
                tokens.append(Token(kind=char, value=char, position=self.index))
                self.index += 1
                continue

            if char == '"':
                start = self.index
                try:
                    value, consumed = json.JSONDecoder().raw_decode(self.text[self.index :])
                except json.JSONDecodeError as exc:
                    raise TransformError(f"Invalid string at position {start}") from exc
                tokens.append(Token(kind="STRING", value=value, position=start))
                self.index += consumed
                continue

            if char == "@":
                tokens.append(self._consume_ref())
                continue

            if char == "-" or char.isdigit():
                tokens.append(self._consume_number())
                continue

            if char.isalpha() or char == "_":
                tokens.append(self._consume_identifier())
                continue

            raise TransformError(f"Unexpected character '{char}' at position {self.index}")

        tokens.append(Token(kind="EOF", value=None, position=self.length))
        return tokens

    def _consume_ref(self) -> Token:
        start = self.index
        self.index += 1
        ident_start = self.index

        if self.index >= self.length or not (self.text[self.index].isalpha() or self.text[self.index] == "_"):
            raise TransformError(f"Invalid ref token at position {start}")

        self.index += 1
        while self.index < self.length and (
            self.text[self.index].isalnum() or self.text[self.index] in {"_", "-"}
        ):
            self.index += 1

        ident = self.text[ident_start : self.index]
        try:
            normalized_id = normalize_ref_id(ident, context=f"ref token at position {start}", allow_literal=False)
        except RefPolicyError as exc:
            raise TransformError(str(exc)) from exc
        return Token(kind="REF", value=f"@{normalized_id}", position=start)

    def _consume_number(self) -> Token:
        start = self.index
        match = _NUMBER_RE.match(self.text, self.index)
        if not match:
            raise TransformError(f"Invalid number at position {start}")

        raw = match.group(0)
        self.index = match.end()
        if "." in raw or "e" in raw or "E" in raw:
            return Token(kind="NUMBER", value=float(raw), position=start)
        return Token(kind="NUMBER", value=int(raw), position=start)

    def _consume_identifier(self) -> Token:
        start = self.index
        self.index += 1
        while self.index < self.length and (self.text[self.index].isalnum() or self.text[self.index] == "_"):
            self.index += 1

        ident = self.text[start : self.index]

        if ident == "true":
            return Token(kind="BOOL", value=True, position=start)
        if ident == "false":
            return Token(kind="BOOL", value=False, position=start)
        if ident == "null":
            return Token(kind="NULL", value=None, position=start)

        return Token(kind="IDENT", value=ident, position=start)


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> list[dict[str, Any]]:
        statements: list[dict[str, Any]] = []
        while not self._check("EOF"):
            statements.append(self._parse_statement())
        return statements

    def _parse_statement(self) -> dict[str, Any]:
        tag = self._consume("IDENT", "Expected statement tag").value
        self._consume("{", "Expected '{' after statement tag")

        fields: dict[str, Any] = {}
        if not self._check("}"):
            while True:
                key_token = self._peek()
                if key_token.kind != "IDENT":
                    raise TransformError(f"Expected field key at position {key_token.position}")
                key = self._advance().value
                if key in fields:
                    raise TransformError(f"Duplicate field '{key}' in statement '{tag}'")

                self._consume(":", "Expected ':' after field key")
                fields[key] = self._parse_value()

                if self._match(","):
                    continue
                break

        self._consume("}", "Expected '}' to close statement")
        return {"tag": tag, "fields": fields}

    def _parse_value(self) -> Any:
        token = self._peek()

        if token.kind in {"STRING", "NUMBER", "BOOL", "NULL", "REF"}:
            self.index += 1
            return token.value

        if token.kind == "IDENT":
            self.index += 1
            return token.value

        if token.kind == "[":
            return self._parse_array()

        if token.kind == "{":
            return self._parse_object()

        raise TransformError(
            f"Unexpected token '{token.kind}' at position {token.position} while parsing value"
        )

    def _parse_array(self) -> list[Any]:
        self._consume("[", "Expected '['")
        values: list[Any] = []

        if not self._check("]"):
            while True:
                values.append(self._parse_value())
                if self._match(","):
                    continue
                break

        self._consume("]", "Expected ']' to close array")
        return values

    def _parse_object(self) -> dict[str, Any]:
        self._consume("{", "Expected '{'")
        values: dict[str, Any] = {}

        if not self._check("}"):
            while True:
                key_token = self._peek()
                if key_token.kind == "IDENT":
                    key = self._advance().value
                elif key_token.kind == "STRING":
                    key = self._advance().value
                else:
                    raise TransformError(f"Expected object key at position {key_token.position}")

                if key in values:
                    raise TransformError(f"Duplicate object key '{key}'")

                self._consume(":", "Expected ':' after object key")
                values[key] = self._parse_value()

                if self._match(","):
                    continue
                break

        self._consume("}", "Expected '}' to close object")
        return values

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _check(self, kind: str) -> bool:
        return self._peek().kind == kind

    def _match(self, kind: str) -> bool:
        if self._check(kind):
            self.index += 1
            return True
        return False

    def _consume(self, kind: str, message: str) -> Token:
        token = self._peek()
        if token.kind != kind:
            raise TransformError(f"{message} at position {token.position}")
        self.index += 1
        return token


def _format_statements(statements: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for statement in statements:
        tag = statement["tag"]
        fields = statement["fields"]
        inner = ",".join(f"{_format_key(key)}:{_format_value(value)}" for key, value in fields.items())
        lines.append(f"{tag}{{{inner}}}")
    return "\n".join(lines) + ("\n" if lines else "")


def _format_key(key: str) -> str:
    if _IDENTIFIER_RE.fullmatch(key):
        return key
    return json.dumps(key, ensure_ascii=False)


def _format_value(value: Any) -> str:
    if isinstance(value, Atom):
        if not _IDENTIFIER_RE.fullmatch(value.value):
            raise TransformError(f"Invalid atom value '{value.value}'")
        return value.value

    if isinstance(value, str):
        if value.startswith("@") and REF_ID_RE.fullmatch(value[1:]):
            return value
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, bool):
        return "true" if value else "false"

    if value is None:
        return "null"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)

    if isinstance(value, list):
        return "[" + ",".join(_format_value(item) for item in value) + "]"

    if isinstance(value, dict):
        return "{" + ",".join(
            f"{_format_key(key)}:{_format_value(item)}" for key, item in value.items()
        ) + "}"

    raise TransformError(f"Unsupported value type during formatting: {type(value).__name__}")
