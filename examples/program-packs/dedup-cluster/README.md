# Program Pack: Dedup/Cluster (Sprint-7 #2)

This pack demonstrates a **deterministic dedup/cluster policy** in the current DSL scope.

## Files

- `policy.erz` — compact policy program (rules only).
- `baseline-mapping.json` — deterministic baseline mapping + sample inputs + expected runtime outputs.

## Deterministic rule encoding in current DSL scope

Current runtime clause support is intentionally narrow:

- `event_type_present`
- `event_type_equals:<value>`
- `payload_has:<top_level_key>`

So numeric/logical conditions are represented as **derived payload keys**.

- Time window (`<= 10m`) is mapped to `within_time_window_10m` / `outside_time_window_10m`.
- Geo radius (`<= 500m`) is mapped to `within_geo_radius_500m` / `outside_geo_radius_500m`.
- Category conditions are mapped to category marker keys such as `category_ops`, `category_security`.

Rules then combine those keys via clause-AND semantics.

## Validation

Deterministic expected `actions` + `trace` for sample events are covered by:

- `tests/test_program_pack_dedup_cluster.py`

Sample matrix in `baseline-mapping.json`:

- `attach_ops` -> `cluster_attach`
- `new_security_geo_miss` -> `cluster_new`
- `new_ops_time_miss` -> `cluster_new`
- `no_match_unknown_category` -> no action
