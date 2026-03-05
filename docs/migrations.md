# IR Migrations

This log tracks versioned IR schema changes and how to move data/consumers between versions.

## Migration entry template

Use this template for every new IR version:

```md
## v<from> -> v<to>
- Date:
- Change type: patch-compatible | minor-compatible | breaking
- Summary:
- Schema files:
  - old: schema/ir.v<from>.schema.json
  - new: schema/ir.v<to>.schema.json
- Compatibility:
  - Forward:
  - Backward:
- Required migration steps:
  1.
  2.
- Validation checklist:
  - [ ] Schema is valid JSON
  - [ ] Examples validate against new schema
  - [ ] Canonicalization rules documented
  - [ ] Tests/fixtures updated
```

---

## Active compatibility anchors (checked by `scripts/gates/migration_anchor_gate.py` via `./scripts/check.sh`)

- Gate anchor trace required: `rule_id`, `matched_clauses`
- Gate anchor trace optional: `score`, `calibrated_probability`, `timestamp`, `seed`
- Gate anchor profiles: `Sprint-5 calibration additive profile`, `Sprint-6 compatibility/ref-hardening profile`

These anchors are intentionally machine-checked and must stay aligned with runtime/schema trace fields and quality-gate profile references. Each active profile anchor must map to exactly one migration-entry heading (`## <from> -> <to>`) to avoid ambiguity. Template/example headings are ignored for anchor resolution, including heading-like lines inside fenced code blocks. Matching is normalized exact-match only (collapsed whitespace), either full heading text or trailing parenthetical token, no substring fallback.

## v0.1 release-close freeze (2026-03-02)

- Ship scope remains `v0.1` with no schema-version bump after Sprint-6 hardening.
- Active compatibility anchors are frozen for ship:
  - `Sprint-5 calibration additive profile`
  - `Sprint-6 compatibility/ref-hardening profile`
- Cross-doc gate anchor references are intentionally locked between:
  - `docs/migrations.md` (this file)
  - `docs/quality-gates.md` ("Active compatibility profile references")
- Release-close validation source of truth:
  - `docs/quality-gates.md` ("v0.1 release-close benchmark snapshot")
  - `docs/acceptance-metrics.md` ("v0.1 release-close checklist")

## v0.1 (Sprint-6 compatibility/ref-hardening profile) -> v0.1 (v0.2-prep error-envelope compatibility profile)

- Date: 2026-03-03
- Change type: patch-compatible (behavior/docs additive, no schema version bump)
- Summary:
  - Keeps IR schema file unchanged (`schema/ir.v0.1.schema.json`).
  - Introduces stable machine-readable error envelope for CLI/runtime integration (`code`, `stage`, `message`, `span`, `hint`, `details`).
  - Adds opt-in JSON error mode for `erz parse` / `erz validate` / `erz pack` / `erz unpack` via `--json-errors` with deterministic field order.
  - Preserves default human-readable stderr behavior when JSON mode is not requested.
  - Locks dual transform span-bearing snapshot signatures for unpack failures:
    - `transform_unpack_unexpected_char.stderr` -> `Unexpected character '#' at position 114`
    - `transform_unpack_unexpected_char_secondary.stderr` -> `Unexpected character '!' at position 139`
  - Keeps runtime adapter/direct-builder parity fixture names canonical: `runtime_contract.stderr`, `runtime_value.stderr`.
- Schema files:
  - old: `schema/ir.v0.1.schema.json`
  - new: `schema/ir.v0.1.schema.json` (unchanged)
- Compatibility:
  - Forward:
    - Existing default CLI behavior remains unchanged for users not enabling `--json-errors`.
    - Integrations can adopt JSON errors incrementally across parse/validate/pack/unpack without changing success-path payloads.
    - Runtime integrations using `eval_policies_envelope(...)` keep success payload shape and gain deterministic `error` envelope payloads for captured contract/value failures.
  - Backward:
    - Consumers expecting legacy human-readable stderr remain compatible by default.
    - Consumers needing stable machine parsing should switch to `--json-errors` instead of scraping free-form text.
- Required migration steps:
  1. For machine parsing, move parse/validate/pack/unpack error handling to `--json-errors` and consume envelope fields (`code`, `stage`, `message`, `span`, `hint`, `details`).
  2. For tool consumers adopting `--json-errors`, treat Gate B8 in `docs/quality-gates.md` as the machine-contract reference for envelope invariants (ordered `details` items: `error_type`, `command`; runtime adapter/direct-builder parity: `stage="runtime"`, `details.command="eval"`; canonical runtime parity fixture names remain frozen in this migration profile summary).
  3. For runtime envelope consumers, treat presence of `error` as the failure signal; do not infer failure from empty `actions`/`trace` alone.
  4. Keep existing human-readable handling unchanged where operator-facing stderr is preferred.
  5. Keep transform snapshot canaries pinned to both unpack span-bearing signatures (`transform_unpack_unexpected_char.stderr` at position `114`, `transform_unpack_unexpected_char_secondary.stderr` at position `139`).
  6. Re-run `python3 -m unittest discover -s tests -v` and `./scripts/check.sh`.
- Validation checklist:
  - [x] Schema is valid JSON (unchanged)
  - [x] Error-envelope contract + deterministic ordering documented
  - [x] Default-mode compatibility explicitly documented
  - [x] CLI/integration coverage for JSON error mode exists
  - [x] Dual unpack span-bearing snapshot names/signatures are documented (`114`, `139`)

## v0.1 (Sprint-2 baseline) -> v0.1 (Sprint-5 calibration additive profile)

- Date: 2026-02-25
- Change type: minor-compatible (additive)
- Summary:
  - Adds calibration IR shapes to the existing v0.1 schema:
    - `calibration_config` (`method=piecewise_linear`, `points[]`)
    - `calibration_bundle` (named config map + optional default selector)
  - Extends `trace` additively with optional `calibrated_probability` (unit interval) when runtime calibration is configured.
  - Keeps existing `event` / `rule` / `action` / required `trace` fields unchanged.
  - Documents runtime-vs-schema constraints for calibration knot uniqueness and selector resolution.
- Schema files:
  - old: `schema/ir.v0.1.schema.json` (Sprint-2 baseline content)
  - new: `schema/ir.v0.1.schema.json` (additive calibration section)
- Compatibility:
  - Forward:
    - Older consumers that only validate/consume baseline objects remain compatible for baseline payloads.
    - Older consumers may reject new calibration objects if they do exhaustive type handling.
    - Older strict trace validators may need a patch to allow optional `trace.calibrated_probability`.
  - Backward:
    - Newer consumers remain backward-compatible with baseline v0.1 objects (including trace records without `calibrated_probability`).
- Required migration steps:
  1. Update consumers that switch on top-level IR object shape to either:
     - support `calibration_config` / `calibration_bundle`, or
     - reject them explicitly with clear error messaging.
  2. Update strict trace validators/serializers to allow optional `calibrated_probability` in `trace` objects.
  3. If persisting calibration bundles, ensure `default_config` (when present) points to an existing key in `configs`.
  4. Enforce runtime validation for knot uniqueness/ordering (schema enforces range and minimum count, but not unique `raw_score`).
  5. Re-run tests and `./scripts/check.sh` before shipping.
- Validation checklist:
  - [x] Schema is valid JSON
  - [x] Examples validate against intended contract semantics
  - [x] Canonicalization + compatibility notes documented
  - [x] Calibration-focused schema tests added

## v0.1 (Sprint-5 calibration additive profile) -> v0.1 (Sprint-6 compatibility/ref-hardening profile)

- Date: 2026-02-25
- Change type: patch-compatible (behavior hardening + backward-compat aliases, no schema version bump)
- Summary:
  - Keeps IR schema file unchanged (`schema/ir.v0.1.schema.json`).
  - Hardens transformer/parser ref policy:
    - canonical ref-id grammar enforcement (`[A-Za-z_][A-Za-z0-9_-]*`)
    - duplicate/colliding ref-id rejection (`id` and `@id` canonical collisions)
    - required resolution of referenced `@id` pointers
  - Extends compatibility handling for pack/unpack aliases while preserving canonical output.
- Schema files:
  - old: `schema/ir.v0.1.schema.json`
  - new: `schema/ir.v0.1.schema.json` (unchanged)
- Compatibility:
  - Forward:
    - Canonical v0.1 payloads remain accepted.
    - Previously accepted malformed refs may now fail fast (invalid ids/collisions/unresolved refs).
  - Backward:
    - Legacy alias forms are accepted for transform inputs; outputs remain canonical.
- Required migration steps:
  1. Ensure producers do not emit duplicate/colliding refs (`id` + `@id` for same canonical id).
  2. Ensure all referenced `@id` pointers are backed by declared refs.
  3. If generating compact manually for parser/formatter, keep `rf.id` in raw-id form (without `@`).
  4. Re-run `python3 -m unittest discover -s tests -v` and `./scripts/check.sh`.
- Validation checklist:
  - [x] Schema is valid JSON (unchanged)
  - [x] Examples validate against intended contract semantics
  - [x] Canonicalization + compatibility notes documented
  - [x] Ref-hardening tests documented/covered

## bootstrap -> v0.1

- Date: 2026-02-24
- Change type: breaking (initial formal contract introduction)
- Summary:
  - Introduces first explicit minimal IR contract for `event`, `rule`, `action`, and `trace`.
  - Freezes strict object shapes (`additionalProperties: false` where practical).
  - Documents canonicalization and compatibility policy.
- Schema files:
  - old: _none (pre-versioned IR)_
  - new: `schema/ir.v0.1.schema.json`
- Compatibility:
  - Forward: not guaranteed from pre-versioned artifacts.
  - Backward: v0.1 consumers should only accept v0.1-conformant objects.
- Required migration steps:
  1. Label existing fixtures/artifacts as pre-v0.1 or migrate them to v0.1 objects.
  2. Validate generated IR objects against `schema/ir.v0.1.schema.json`.
  3. Keep canonicalization stable for deterministic replay.
- Validation checklist:
  - [x] Schema is valid JSON
  - [x] Examples validate against new schema
  - [x] Canonicalization rules documented
  - [x] Migration note added
