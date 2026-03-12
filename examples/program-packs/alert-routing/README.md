# Sprint-7 Program Pack #3: Alert Routing

This pack demonstrates deterministic alert routing on real nested numeric payload paths, not projected bucket fields.

## Files

- `alert-routing.erz` — compact pack with fixture event, rules, expected actions (`ac`) and expected trace (`tr`).
- `alert-routing.baseline.json` — deterministic fixture set used by tests.

## Numeric payload predicates in use

The routing rules now match directly on nested measurements:

- `payload_path_exists:alert.id`
- `payload_path_gte:measurements.severity=0.9`
- `payload_path_gte:measurements.confidence=0.85`
- `payload_path_lt:measurements.confidence=0.85`
- `payload_path_gte:measurements.severity=0.6`
- `payload_path_lt:measurements.severity=0.9`

That keeps rule evaluation purely structural and deterministic while removing the need for upstream severity/confidence bucket projection.

Calibration still affects only `trace.calibrated_probability`, never rule firing or emitted actions.

## Validation

- Public smoke gate: `scripts/check.sh`
- Deeper regression coverage exists in the internal test lane, the public slice ships the runnable fixtures and strict replay lane.
