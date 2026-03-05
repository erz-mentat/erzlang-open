# erzlang IR Contract v0.1

Status: **active (Sprint-5 additive calibration profile)**

This document defines the canonical IR contract for v0.1. It started as the Sprint-2 minimal baseline and was extended additively in Sprint-5 to cover calibration config/bundle representation.

## 1) Scope

Covered IR objects:

- `event`
- `rule`
- `action`
- `trace`
- `calibration_config`
- `calibration_bundle`

Reference schema: `schema/ir.v0.1.schema.json`

Still out of scope for v0.1:

- Full program envelope/schema (kept open for next version)
- Rich clause typing beyond `string[]`
- Side-effect/runtime execution semantics beyond deterministic ordering
- Calibration fitting/training pipeline metadata beyond optional free-form `metadata`

## 2) Required fields

### `event`

Required:

- `type: string`

Optional:

- `payload: object` (map of JSON-like values: string, integer, boolean, null, object, array)

Rules:

- Unknown fields are rejected.

### `action`

Required:

- `kind: string`

Optional:

- `params: object` (map of JSON-like values)

Rules:

- Unknown fields are rejected.

### `rule`

Required:

- `id: string`
- `when: string[]`
- `then: action[]`

Rules:

- Unknown fields are rejected.
- Every entry in `then` must satisfy the same `action` contract.

### `trace`

Required:

- `rule_id: string`
- `matched_clauses: string[]` (non-empty)

Optional:

- `score: finite number` (`bool` disallowed)
- `calibrated_probability: finite number` (`bool` disallowed, inclusive range `[0.0, 1.0]`)
- `timestamp: string | number`
- `seed: string | integer`

Rules:

- Unknown fields are rejected.
- `matched_clauses` must be non-empty and preserve clause declaration order from the fired rule.
- Recommended canonical field order for serialization: `rule_id`, `matched_clauses`, then optional fields in this order: `score`, `calibrated_probability`, `timestamp`, `seed`.

### `calibration_config`

Required:

- `method: "piecewise_linear"`
- `points: calibration_point[]` (at least 2)

Optional:

- `description: string`

`calibration_point` required fields:

- `raw_score: number` (inclusive range `[0.0, 1.0]`)
- `probability: number` (inclusive range `[0.0, 1.0]`)

Rules:

- Unknown fields are rejected at both config and point level.
- v0.1 only allows `piecewise_linear` method.
- Semantic constraints not fully expressible in JSON Schema and therefore runtime-enforced:
  - knot `raw_score` values should be unique
  - runtime normalizes point order by `raw_score`

### `calibration_bundle`

Required:

- `id: string`
- `configs: {<selector>: calibration_config}` with at least one entry

Optional:

- `default_config: string`
- `metadata: object` (JSON-like map for provenance/audit)

Rules:

- Unknown fields are rejected.
- `default_config` should reference an existing key in `configs` (semantic constraint; not fully enforceable by JSON Schema).
- `configs` keys are selector/profile names (non-empty strings).

## 3) Invariants (cross-object / runtime-facing)

These are semantic invariants expected by runtime/tooling. Some are not fully enforceable by JSON Schema alone.

1. **Rule identity uniqueness**: `rule.id` values should be unique within one policy set/program.
2. **Trace referential integrity**: each `trace.rule_id` should reference an existing `rule.id`.
3. **Reference integrity (pack/unpack boundary)**:
   - canonical ref id grammar: `[A-Za-z_][A-Za-z0-9_-]*`
   - pointer form is `@id`; binding form is `rf.id == id`
   - every used `@id` must resolve to a declared ref binding
   - canonical-id collisions (e.g. `id` vs `@id`) are rejected
4. **Deterministic ordering**:
   - Rule evaluation order is stable (runtime subset currently sorts by `(rule_id, declaration_index)`).
   - Exactly one `trace` step is emitted for each fired rule.
   - `trace` entries are emitted in the same stable order as fired rules.
5. **Action shape parity**: action objects embedded in `rule.then` and standalone `action` objects use the exact same field contract.
6. **Calibration semantics parity**:
   - `calibration_config.points` should represent a deterministic piecewise-linear knot sequence.
   - Raw score below first knot clamps to first knot probability.
   - Raw score above last knot clamps to last knot probability.
7. **No unknown keys** in strict objects (`event`, `rule`, `action`, `trace`, `calibration_point`, `calibration_config`, `calibration_bundle`).

## 4) Canonicalization rules

Canonicalization is required for deterministic replay and stable diffs.

1. Validate against the v0.1 contract; reject unknown/missing required fields.
2. Omit optional fields when absent (do not synthesize empty objects by default).
3. Preserve array order for semantic lists (`when`, `then`, `matched_clauses`, `points`).
4. Use stable key order in trace objects: `rule_id`, `matched_clauses`, then optional (`score`, `calibrated_probability`, `timestamp`, `seed`).
5. Use stable key order in calibration objects:
   - `calibration_point`: `raw_score`, `probability`
   - `calibration_config`: `method`, `points`, optional `description`
   - `calibration_bundle`: `id`, `configs`, optional `default_config`, optional `metadata`
6. Sort keys recursively inside free-form maps (`payload`, `params`, `metadata`) for deterministic output.
7. For byte-stable JSON rendering, use deterministic serializer settings (e.g. sorted keys + fixed separators).

## 5) Compatibility + versioning policy

Versioning follows **explicit schema versions**.

- Current version: **v0.1** (`schema/ir.v0.1.schema.json`)
- Sprint-5 calibration support is an additive extension inside the same v0.1 schema file.
- Any change to required fields, field types, object meaning, or canonicalization rules requires a new schema version.

Change classes:

- **Patch-compatible**: clarifications/docs-only, no schema behavior change.
- **Minor-compatible**: additive optional fields or additive object defs/variants (only if consumers can ignore them safely).
- **Breaking**: removing/renaming fields, tightening constraints, changed semantics.

Compatibility notes for the Sprint-5 calibration addition:

- Existing `event`/`rule`/`action`/`trace` payloads remain valid unchanged.
- Consumers doing exhaustive top-level type matching must handle or explicitly reject the new calibration objects.
- Producers should avoid mixing unsupported calibration semantics (e.g. non-piecewise methods) into v0.1 artifacts.

Required process for any future version change:

1. Add new schema file (`schema/ir.vX.Y.schema.json`).
2. Add migration note in `docs/migrations.md`.
3. Document compatibility expectations (forward/backward).
4. Keep v0.1 artifacts available for replay of historical fixtures.

## 6) Minimal valid examples

```json
{
  "type": "ingest",
  "payload": {"source": "sensor-a", "severity": 2}
}
```

```json
{
  "id": "r1",
  "when": ["event_type_present"],
  "then": [{"kind": "act", "params": {"rule_id": "r1"}}]
}
```

```json
{
  "rule_id": "r1",
  "matched_clauses": ["event_type_present"],
  "score": 1.0,
  "calibrated_probability": 0.92,
  "timestamp": "2026-02-25T14:00:00Z",
  "seed": "seed-7"
}
```

```json
{
  "method": "piecewise_linear",
  "points": [
    {"raw_score": 0.0, "probability": 0.05},
    {"raw_score": 0.6, "probability": 0.7},
    {"raw_score": 1.0, "probability": 0.95}
  ]
}
```

```json
{
  "id": "severity-confidence-v1",
  "default_config": "default",
  "configs": {
    "default": {
      "method": "piecewise_linear",
      "points": [
        {"raw_score": 0.0, "probability": 0.05},
        {"raw_score": 0.6, "probability": 0.7},
        {"raw_score": 1.0, "probability": 0.95}
      ]
    }
  },
  "metadata": {
    "source": "offline-fit-2026-02-25"
  }
}
```

## 7) Machine-readable error envelope (v0.2 prep)

For CLI and runtime integration, error reporting now has a stable envelope shape.

Envelope fields (always present, nullable where applicable):

- `code: string`, stable machine code (for example `ERZ_PARSE_SYNTAX`, `ERZ_VALIDATE_SCHEMA`, `ERZ_RUNTIME_CONTRACT`)
- `stage: string`, failing stage (`parse`, `validate`, `runtime`, `transform`, `cli`, ...)
- `message: string`, primary human-readable diagnostic
- `span: object|null`, currently position-style parser span, for example `{ "position": 17 }`
- `hint: string|null`, concise remediation hint
- `details: object`, structured metadata (`error_type`, optional `command`)

Determinism contract:

1. Field order is fixed: `code`, `stage`, `message`, `span`, `hint`, `details`.
2. Serialization is compact JSON (no pretty-print requirement), stable for equivalent failures.
3. Human-readable default mode remains unchanged unless explicit JSON-error mode is enabled.
4. Runtime adapter `eval_policies_envelope(...)` uses stable top-level shape:
   - success: `actions`, `trace` (no `error` key)
   - contract/value failure: `actions: []`, `trace: []`, `error: <envelope>`

Migration note: see `docs/migrations.md` entry `v0.1 (Sprint-6 compatibility/ref-hardening profile) -> v0.1 (v0.2-prep error-envelope compatibility profile)` for adoption/default-mode compatibility guidance.

Example (`erz parse --json-errors`):

```json
{"code":"ERZ_PARSE_SYNTAX","stage":"parse","message":"Expected '}' to close statement at position 12","span":{"position":12},"hint":"Check compact syntax near the reported position.","details":{"error_type":"CompactParseError","command":"parse"}}
```

Runtime adapter example (`runtime.eval.eval_policies_envelope`):

```json
{"actions":[],"trace":[],"error":{"code":"ERZ_RUNTIME_VALUE","stage":"runtime","message":"...","span":null,"hint":"Runtime value violated allowed numeric/range constraints.","details":{"error_type":"ValueError","command":"eval"}}}
```
