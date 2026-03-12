# hadrian-closed template scan (read-only)

Source clone:
- `../hadrian-closed-template`
- remote push is disabled locally (`origin pushurl = DISABLED`) to avoid accidental writes.

## Quick inventory
- `pythoncode/` large operational codebase, useful as reference for evaluation/logging patterns.
- `schema/` and the internal test lane were useful for schema-validation and quality-gate patterns during incubation.
- `.githooks/pre-commit` pattern is reusable (run focused boundary tests before commit).

## What we reuse now (v0.1 phase)
- process discipline: strict tests + quality gates
- schema-first validation mindset
- deterministic reporting/bench artifacts

## What we do NOT import
- incident-domain logic
- FastAPI service surface
- ops UI and map stack
- legacy protocols

Goal: keep `erzlang` clean and DSL-focused while borrowing only engineering discipline and testing rigor.
