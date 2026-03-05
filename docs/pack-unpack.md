# Pack / Unpack (Sprint-3)

Sprint-3 adds a deterministic transformer between:

- **Baseline JSON fixtures** (`*.baseline.json`)
- **compact+refs text** (`*.erz`)

## CLI

```bash
# JSON -> compact+refs
python3 -m cli.main pack bench/token-harness/fixtures/ingest_event.baseline.json

# compact+refs -> canonical JSON (sorted keys, pretty-printed)
python3 -m cli.main unpack bench/token-harness/fixtures/ingest_event.erz

# stdin usage
cat bench/token-harness/fixtures/act_event.baseline.json | python3 -m cli.main pack -
cat bench/token-harness/fixtures/act_event.erz | python3 -m cli.main unpack -
```

Both commands return exit code `0` on success and `1` with an error message on invalid/unsupported input.

## Supported subset (strict)

### Top-level JSON object

Allowed keys:

- `event` (required)
- `decision` (optional)
- `refs` (optional)

Unknown keys fail hard.

### Event types

Supported JSON event types:

- `ingest_event`
- `normalize_event`
- `act_event`

They map to compact `ev.t` atoms:

- `ingest_event` -> `ingest`
- `normalize_event` -> `normalize`
- `act_event` -> `act`

### Action types (inside `act_event.actions`)

- `notify_channel` -> `notify`
- `create_ticket` -> `ticket`

### Compatibility aliases (backward compatibility)

`pack` and `unpack` both normalize aliases to the canonical schema.

- event `type`: canonical (`ingest_event`, `normalize_event`, `act_event`) or short (`ingest`, `normalize`, `act`)
- action `type`/`t`: canonical (`notify_channel`, `create_ticket`) or short (`notify`, `ticket`)
- ingest: `source/src`, `text_ref/textRef/txt_ref/txtRef/txt`, `timestamp/ts`
- normalize: `source/src`, `ingest_ref/ingestRef/ing_ref/ingRef/ing`, `language/lang`, `timezone/tz`, `entities/ent`, `normalized_text_ref/normalizedTextRef/norm_text_ref/normTextRef/txt`
- act: `decision_ref/decisionRef/dec_ref/decRef/dec`, `actions/act`, `deadline_s/deadlineSec/deadline_seconds/ddl`
- notify action: `template_ref/templateRef/tpl`
- ticket action: `system/sys`, `priority/prio`, `dedupe_key/dedupeKey/ddk`
- decision: `reason_codes/reasonCodes/rc`
- compact ref statement fields: pointer `id/ref/ref_id/refId/$ref`, value `v/value/text`

### Nested payload normalization

For supported event/action shapes, fields can be provided either:

- directly on the object (canonical style), or
- in nested payload wrappers (`event.payload`, `ev.payload`, action `params`).

Normalization rules are deterministic:

1. Canonical + alias keys are scanned in a fixed order.
2. If a value is present in multiple locations, values must match semantically.
3. Conflicting duplicates fail hard.
4. Output is always canonical.

### Ref extraction strategy

Ref-typed fields accept deterministic input variants:

- string literal: `"@txt_1"` or `"txt_1"`
- object pointer forms: `{id:"txt_1"}`, `{ref:"@txt_1"}`, `{ref_id:"txt_1"}`

`refs` container forms accepted by `pack`:

- object map: `{ "txt_1": "..." }`
- object map with wrapped values: `{ "txt_1": {"value":"..."} }`
- list form: `[{"id":"@txt_1","text":"..."}]`

Canonicalization policy:

- canonical id grammar: `[A-Za-z_][A-Za-z0-9_-]*`
- optional `@` is stripped from ids in bindings
- `pack` emits sorted `rf` statements by canonical id
- colliding ids after canonicalization fail hard
- missing bindings for used refs fail hard

### Supported / unsupported matrix

| Shape | Status |
|---|---|
| `event` + supported `type` + canonical fields | ✅ supported |
| supported aliases (see above) | ✅ supported |
| nested payload wrappers for supported fields | ✅ supported |
| action `params` wrappers for notify/ticket | ✅ supported |
| ref object/literal extraction variants | ✅ supported |
| refs as map / wrapped map / list | ✅ supported |
| unknown top-level keys | ❌ rejected |
| unknown keys inside strict event/action/decision objects | ❌ rejected |
| unsupported event types (`alert_event`, etc.) in `pack` | ❌ rejected |
| unsupported action types | ❌ rejected |
| arbitrary GP-style payload passthrough | ❌ rejected |

## Determinism guarantees

`pack` output is deterministic for the supported subset:

- fixed statement order: `erz`, `ev`, optional `dc`, sorted `rf*`
- fixed field order per statement shape
- no optional whitespace
- canonical scalar formatting (`true/false/null`, numeric, string escaping)
- canonical ref-id normalization before sorting (`id` and `@id` map to the same canonical id)

Ref integrity guarantees:

- all `@id` references used by packed/unpacked event fields must resolve to declared refs
- duplicate `rf` ids fail hard
- colliding ids after canonicalization fail hard
- invalid ref ids fail hard

`unpack` is lossless for the regression fixture subset used in tests (`ingest_event`, `normalize_event`, `act_event`, plus `*_nested_payload` fixture variants).
