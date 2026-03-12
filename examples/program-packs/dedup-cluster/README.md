# Program Pack: Dedup/Cluster (Sprint-7 #2)

This pack demonstrates a deterministic dedup/cluster policy on canonical runtime events.

## Files

- `policy.erz` — compact policy program (rules only).
- `baseline.json` — canonical event fixtures, runtime contract, and expected runtime outputs.

## Deterministic rule encoding with payload paths

Current runtime clause support now includes nested payload path predicates in addition to top-level key checks:

- `event_type_present`
- `event_type_equals:<value>`
- `payload_has:<top_level_key>`
- `payload_path_exists:<dot.path>`
- `payload_path_equals:<dot.path>=<value>`
- `payload_path_gt/gte/lt/lte:<dot.path>=<number>`

This pack keeps thresholding deterministic while reading the real nested numeric payload fields directly.

- Time window attach (`<= 10m`) is `payload_path_lte:window.minutes_since_anchor=10`.
- Geo radius attach (`<= 500m`) is `payload_path_lte:geo.distance_meters=500`.
- Time miss (`> 10m`) is `payload_path_gt:window.minutes_since_anchor=10`.
- Geo miss (`> 500m`) is `payload_path_gt:geo.distance_meters=500`.
- Category conditions match the real payload field `category = ops | security`.
- Cluster identity requires `dedupe.key` via `payload_path_exists:dedupe.key`.

The checked-in fixtures are already in runtime input shape under `fixtures[*].event`, so operators and tests no longer carry a separate raw-to-mapped projection lane.

## Validation

Deterministic expected `actions` + `trace` for sample events are covered in the public slice by runnable fixtures plus `scripts/check.sh`; deeper regression coverage stays in the internal test lane.

Sample matrix in `baseline.json`:

- `attach_ops` -> `cluster_attach`
- `new_security_geo_miss` -> `cluster_new`
- `new_ops_time_miss` -> `cluster_new`
- `no_match_unknown_category` -> no action
