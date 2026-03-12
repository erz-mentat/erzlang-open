# Program Pack #1: Ingest + Normalize (with Trace)

This pack is a compact, deterministic reference for a two-step flow:

1. **Ingest** event enters the pipeline with inline raw text and metadata.
2. **Normalize** event carries extracted entities + inline normalized text.
3. Rules describe expected transitions/actions.
4. The ingest rule now matches real payload text via `payload_path_contains:text=Unfall`, so the pack no longer depends on placeholder `text_ref` gating.
5. The publish rule requires normalized text to start with `Verkehrsunfall` and at least one extracted entity before notifying ops, via `payload_path_startswith:normalized_text=Verkehrsunfall` and `payload_path_len_gte:entities=1`.
6. A trace sample captures one fired normalization rule.

## Files

- `program.erz` — canonical compact DSL program
- `baseline.json` — canonical JSON equivalent (`erz parse` shape)
- `expected-trace.sample.json` — expected trace step list for the normalization fire

## Constraints (scope-fixed)

- Uses only existing DSL tags/fields (`erz`, `ev`, `rl`, `pl`, `rf`, `tr`).
- No expression language in `when` clauses, only simple clause strings.
- Runtime behavior stays within the current deterministic v0 contract, including payload-path string and length predicates.
- Program is already canonical-formatted (`erz fmt` should be no-op).
