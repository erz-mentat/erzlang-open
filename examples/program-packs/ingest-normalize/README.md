# Program Pack #1: Ingest + Normalize (with Trace)

This pack is a compact, deterministic reference for a two-step flow:

1. **Ingest** event enters the pipeline with raw text reference and metadata.
2. **Normalize** event carries extracted entities + normalized text reference.
3. Rules describe expected transitions/actions.
4. A trace sample captures one fired normalization rule.

## Files

- `program.erz` — canonical compact DSL program
- `baseline.json` — canonical JSON equivalent (`erz parse` shape)
- `expected-trace.sample.json` — expected trace step list for the normalization fire

## Constraints (scope-fixed)

- Uses only existing DSL tags/fields (`erz`, `ev`, `rl`, `pl`, `rf`, `tr`).
- No expression language in `when` clauses (only simple clause strings).
- No new runtime semantics added; trace shape stays within current v0 contract.
- Program is already canonical-formatted (`erz fmt` should be no-op).
