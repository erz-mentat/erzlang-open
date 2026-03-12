# Sprint-7 Program Pack #2: Dedup/Cluster

Location:

- `examples/program-packs/dedup-cluster/policy.erz`
- `examples/program-packs/dedup-cluster/baseline.json`

## Scope-safe encoding

This pack stays within the deterministic runtime clause subset while using explicit payload paths instead of synthetic boolean marker keys:

- `event_type_present`
- `event_type_equals:<value>`
- `payload_has:<top_level_key>`
- `payload_path_exists:<dot.path>`
- `payload_path_equals:<dot.path>=<value>`
- `payload_path_gt/gte/lt/lte:<dot.path>=<number>`

Threshold decisions now stay inside the runtime contract while still reading the real event structure directly:

- time window (`<=10m`): `payload_path_lte:window.minutes_since_anchor=10`
- geo radius (`<=500m`): `payload_path_lte:geo.distance_meters=500`
- time miss (`>10m`): `payload_path_gt:window.minutes_since_anchor=10`
- geo miss (`>500m`): `payload_path_gt:geo.distance_meters=500`
- category conditions: `category = ops | security`
- cluster identity presence: `dedupe.key`

The pack baseline now centers canonical runtime events under `fixtures[*].event`, so operators, tests, and docs all exercise the same nested payload shape with no duplicate raw-to-mapped fixture layer.

## Determinism checks

- Sample runtime events and expected `actions` + `trace` are embedded in `baseline.json`.
- Public smoke gate: `scripts/check.sh`
- Deeper regression coverage exists in the internal test lane, the public slice ships the runnable fixtures and strict replay lane.

## Operator quickstart

For a smaller copy-paste path-predicate smoke test outside the full pack, use the checked-in eval fixtures:

```bash
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-ok.json
erz eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-ok.json
erz eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-no-action.json --summary
```
