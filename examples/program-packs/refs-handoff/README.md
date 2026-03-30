# Program Pack: Refs-backed action-plan handoff

This pack is the operator-editable fixture-matrix reference for deterministic action-plan materialization with explicit `expected_resolved_refs`.

## Why it exists

The inline `ingest-normalize` pack already proves that ref resolution works. This pack proves the heavier operator lane:

- refs live in the checked-in `.erz` program
- the baseline is a plain fixture matrix that operators can edit directly
- each matching fixture pins both `expected_action_plan` and `expected_resolved_refs`
- `erz pack-replay --strict-profile refs-handoff-clean` becomes a one-line CI contract for the whole pack

## Files

- `policy.erz` — refs-backed policy program
- `baseline.json` — fixture matrix with explicit action-plan and resolved-ref expectations
- `../refs-handoff.replay.expected.*` — checked-in pack-replay summary, JSON envelope, and handoff-bundle sidecars for this pack

## Suggested checks

```bash
erz pack-replay examples/program-packs/refs-handoff --summary
erz pack-replay examples/program-packs/refs-handoff --strict-profile refs-handoff-clean
erz pack-replay examples/program-packs/refs-handoff --summary --json-file /tmp/refs-handoff.replay.json --handoff-bundle-file /tmp/refs-handoff.replay.bundle.json
erz pack-replay examples/program-packs/refs-handoff --fixture ops_primary_page --summary
python3 scripts/refresh_program_pack_replay_contracts.py
```

## Fixture intent

- `ops_primary_page` — heavy refs surface with nested object + list materialization
- `security_triage` — alternate ref bundle on the same runtime shape
- `ops_digest` — lower-severity digest lane with a smaller ref subset
- `no_match_finance` — explicit zero-action / zero-ref contract
