# Sprint-7 Program Pack #3: Alert Routing

Files:
- `alert-routing.erz` — compact policy pack with rules, action expectations (`ac`) and trace expectations (`tr`).
- `alert-routing.baseline.json` — deterministic fixture set used by tests.

Calibration-aware note:
- Routing depends on deterministic bucket keys (`sev_*`, `conf_*`) in payload.
- Calibration is applied only to `trace.calibrated_probability`; rule firing and action routing remain unchanged.
