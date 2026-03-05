# Runtime Determinism Contract (Rule Engine v0)

`runtime.eval.eval_policies` is the deterministic, pure-evaluation Rule Engine for the current v0 runtime subset.

## Guarantees

1. **Pure evaluation / no side effects**
   - No I/O, no randomness, no wall-clock reads.
   - No action execution hooks or callbacks are invoked.
   - Inputs are not mutated.

2. **Deterministic ordering**
   - Rules are normalized and evaluated in stable order by `(rule_id, declaration_index)`.
   - Returned `actions` and `trace` follow that same stable order.
   - Within each trace step, `matched_clauses` preserves rule clause declaration order.

3. **Deterministic payload/action normalization**
   - Mapping keys are canonicalized recursively (sorted) for stable output shape.
   - Action params and payload data must be declarative JSON-like data only:
     `str | int | float | bool | null | list | object`.

4. **Explicit trace contract (per fired rule)**
   - Every fired rule emits exactly one trace step.
   - Required fields:
     - `rule_id: non-empty str`
     - `matched_clauses: non-empty list[str]`
   - Optional fields:
     - `score: finite number` (present when `include_score=True`; runtime emits float)
     - `calibrated_probability: finite number in [0.0, 1.0]`
       (present when `calibration=<piecewise_linear_config>` is provided; runtime emits float)
     - `timestamp: string|number` (present when `now` or `event.payload.timestamp` is provided)
     - `seed: string|int` (present when `seed` or `event.payload.seed` is provided)
   - Unknown trace keys are rejected by runtime validation.
   - Stable trace key order:
     `rule_id`, `matched_clauses`, `score`, `calibrated_probability`, `timestamp`, `seed`.
   - Runtime helper APIs: `validate_trace_step` and `validate_trace`.

5. **Deterministic timestamp/seed handling**
   - The evaluator never generates time or seed values.
   - If provided via arguments (`now`, `seed`) or payload fallback, those values are copied into trace unchanged.

6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**
   - Success payload contains exactly `actions`, `trace` and omits `error`.
   - Runtime contract/value failures return deterministic empty payload lanes:
     `actions == []`, `trace == []`, plus stable `error` envelope.
   - Stable code mapping for captured runtime failures:
     - `TypeError -> ERZ_RUNTIME_CONTRACT`
     - `ValueError -> ERZ_RUNTIME_VALUE`
   - Stable runtime parity contract for adapter + direct-builder lanes: adapter failures and direct `build_error_envelope(...)` outputs keep `stage="runtime"` and `details.command="eval"`.
   - Ordered details contract is deterministic: `error.details` serializes `error_type` first, then `command`.
   - Non-contract internal failures are re-raised unchanged (no envelope swallowing).
   - Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer.

## Rule Engine v0 semantics

### Rule form

`rule.when` is interpreted as a **simple AND-clause list**:

- All clauses in `when` must match for the rule to fire.
- If any clause fails, the rule does not fire.
- No expression language is supported (no `&&`, `||`, `and`, `or`, `not`, parentheses).

If `when` is omitted (or empty), v0 uses default clause `event_type_present` for backward compatibility.

### Supported clause grammar

Only these clause forms are valid:

- `event_type_present`
- `event_type_equals:<value>`
- `payload_has:<top_level_key>`

Unsupported clauses raise a `TypeError` (rule evaluation aborts for that policy set).

### Action emission semantics

- `then` actions are emitted as declarative output records only.
- Runtime does **not** execute action kinds.
- Missing `then` defaults to: `{"kind": "act", "params": {"rule_id": <rule.id>}}`.

### Score semantics

- `score` is structural match coverage for fired rules:
  `len(matched_clauses) / len(rule.when)`.
- Because only fully matched AND-rules fire in v0, fired rules currently emit `score = 1.0`.
- If `include_score=False`, `score` is omitted.

### Calibration integration semantics (Sprint-5)

- `eval_policies(..., calibration=<config>)` applies deterministic piecewise-linear mapping
  (`runtime.calibration.map_raw_score_to_probability`) to the structural raw score.
- The mapped value is emitted as `trace[].calibrated_probability`.
- Calibration is optional; when omitted, trace shape remains backward compatible.
- Calibration input affects trace output only; it does not change rule matching or action emission.
- No wall-clock reads or randomness are introduced by calibration flow.

### Separation guard (severity/confidence)

- Runtime does **not** infer probabilistic semantics from payload fields like
  `severity` or `confidence`.
- Both `score` and `calibrated_probability` are derived from structural clause match
  coverage only in v0.

## Current limits

- Clause matching is intentionally narrow and deterministic.
- `payload_has` checks top-level payload keys only.
- No nested/path clause operators.
- No probabilistic or weighted rule scoring.
- No runtime action dispatch/execution in v0.
- Trace shape and fired-rule alignment are validated in-process (no external validator dependency required).
