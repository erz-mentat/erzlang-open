# Sprint-7 Program Pack #2: Dedup/Cluster

Location:

- `examples/program-packs/dedup-cluster/policy.erz`
- `examples/program-packs/dedup-cluster/baseline-mapping.json`

## Scope-safe encoding

This pack stays within current runtime DSL clause support:

- `event_type_present`
- `event_type_equals:<value>`
- `payload_has:<key>`

Numeric predicates are represented through deterministic, precomputed payload keys:

- time window (`<=10m`): `within_time_window_10m` / `outside_time_window_10m`
- geo radius (`<=500m`): `within_geo_radius_500m` / `outside_geo_radius_500m`
- category conditions: `category_ops`, `category_security`

## Determinism checks

- Sample inputs and expected `actions` + `trace` are embedded in `baseline-mapping.json`.
- Unit test: `tests/test_program_pack_dedup_cluster.py`
- Full gate: `scripts/check.sh`
