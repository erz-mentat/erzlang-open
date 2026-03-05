# Calibration v0 (Sprint-5)

Status: **runtime-integrated (deterministic path)**

This document defines the v0 calibration model for mapping runtime structural `raw_score` values to calibrated probabilities.

## 1) Object model (minimal)

Implemented in `runtime/calibration.py`:

- `CalibrationPoint`
  - `raw_score: float`
  - `probability: float`
- `PiecewiseLinearCalibration`
  - `points: tuple[CalibrationPoint, ...]`

Persistence shape is now formalized additively in `schema/ir.v0.1.schema.json` via `calibration_config` and `calibration_bundle` (see `docs/ir-contract-v0.1.md`).

## 2) Mapping utility (deterministic)

Implemented in `runtime/calibration.py`:

- `map_raw_score_to_probability(raw_score, calibration) -> float`

Accepted `calibration` inputs:

1. `PiecewiseLinearCalibration`
2. mapping with `{"points": [...]}`
3. sequence of points (`CalibrationPoint`, mapping points, or `(raw_score, probability)` tuples)

Validation/behavior:

- `raw_score` and point values must be numeric in `[0.0, 1.0]` (`bool` rejected)
- at least 2 calibration points
- point `raw_score` values must be unique
- points are sorted by `raw_score`
- below first point => clamp to first probability
- above last point => clamp to last probability
- between two points => linear interpolation

## 3) Runtime integration (`runtime/eval.py`)

`eval_policies` now accepts optional calibration input:

```python
eval_policies(..., calibration=<piecewise_linear_config>)
```

When provided:

- runtime computes deterministic structural raw score per fired rule
- runtime maps that raw score via `map_raw_score_to_probability`
- trace step includes:
  - `calibrated_probability: float` (in `[0.0, 1.0]`)

When omitted:

- no calibration mapping is applied
- trace shape remains backward compatible (no `calibrated_probability` field)

`include_score=False` still omits `score`; calibration can still be emitted independently.

## 4) Determinism and separation guards

Calibration integration keeps runtime deterministic:

- no wall-clock reads
- no randomness
- no side effects

Separation guard remains explicit:

- runtime `score` is structural match coverage
- runtime `calibrated_probability` is derived from structural score only
- payload fields like `severity` / `confidence` are not implicitly interpreted as probabilities
- threshold-like DSL clauses remain unsupported unless explicitly implemented

Guard coverage includes:

- `tests/test_separation_guards.py::test_score_semantics_are_structural_not_severity_or_confidence_based`
- `tests/test_separation_guards.py::test_calibration_semantics_are_structural_not_severity_or_confidence_based`
- `tests/test_separation_guards.py::test_threshold_like_clauses_are_not_implicitly_interpreted`

## 5) Examples

```python
from runtime.eval import eval_policies

calibration = {
    "points": [
        {"raw_score": 0.0, "probability": 0.05},
        {"raw_score": 1.0, "probability": 0.95},
    ]
}

actions, trace = eval_policies(
    event={"type": "ingest", "payload": {"x": 1}},
    rules=[{"id": "r1", "when": ["event_type_present"]}],
    calibration=calibration,
)

# trace[0] contains: rule_id, matched_clauses, optional score, optional calibrated_probability
```

## 6) Current limitations

Still intentionally out of scope for v0:

- calibration fitting/training tooling
- multi-segment monotonicity constraints beyond unique `raw_score` knots
- confidence intervals / uncertainty decomposition
