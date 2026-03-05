# erzlang

A narrow, agent-first DSL for deterministic policy execution.
It turns compact programs into stable actions, trace output, and machine-readable errors.
The language surface stays intentionally small, so behavior stays auditable.

## What this is
- A public DSL/runtime repo focused on deterministic execution contracts.
- A practical base for agent workflows that need repeatable outputs.
- A docs + schema + examples package for builders and reviewers.

## What this is not
- Not a general-purpose programming language.
- Not a feature race around syntax breadth.
- Not a black-box runtime with hidden behavior.

## Public scope in this repository
- `cli/` parsing, validation, formatting, pack/unpack entrypoints
- `runtime/` deterministic runtime behavior + error mapping
- `ir/` compact/IR model primitives
- `schema/ir.v0.1.schema.json` contract surface
- `examples/` runnable sample programs + program packs
- `docs/` design/runtime/scope/migration notes
- `scripts/` check and gate helpers

## Deliberately excluded from this public slice
- Private operational protocol logs and queue histories
- Local automation traces
- Heavy internal test/benchmark lanes (kept private in this publish variant)

## v0.1 boundaries
### In scope
- Deterministic execution
- Canonical IR contract
- Trace-first outputs
- Stable JSON error envelopes for tooling
- Compact references (`rf`) and payload container (`pl`)

### Out of scope
- Functions
- Loops
- Modules
- Type inference

## Problem
Most agent pipelines fail in production for boring reasons: drift, hidden runtime behavior, and non-deterministic error surfaces.
If two runs with the same input produce different shape or semantics, downstream automation becomes fragile.

## Approach
erzlang keeps the language small and the runtime strict.
The primary goal is contract reliability, not language novelty.

```text
compact program -> parse/validate -> canonical IR -> deterministic eval -> actions + trace
```

Errors are first-class outputs when requested (`--json-errors`), so tools can branch on stable fields instead of string parsing.

## Current status
v0.1 work is focused on boundary hardening and deterministic behavior guarantees.
The repo is structured to keep contracts explicit and reviewable.

## Quickstart

```bash
# Parse + validate
python3 -m cli.main parse examples/sample.erz
python3 -m cli.main validate examples/sample.erz

# Canonical formatting
python3 -m cli.main fmt examples/sample.erz

# JSON -> compact+refs
python3 -m cli.main pack examples/program-packs/ingest-normalize/baseline.json

# compact+refs -> canonical JSON
python3 -m cli.main unpack examples/program-packs/ingest-normalize/program.erz
```

## Error envelope (json mode)
With `--json-errors`, commands return a stable envelope with:
- `code`
- `stage`
- `message`
- `span`
- `hint`
- `details`

Without the flag, stderr remains human-readable.

## Key docs
- `docs/scope-v0.md`
- `docs/runtime-determinism.md`
- `docs/ir-contract-v0.1.md`
- `docs/migrations.md`
- `docs/release-artifacts/README.md`

## Known limitations
- v0.1 is intentionally narrow, language surface is constrained by design.
- Lean public slice excludes heavy internal lanes.
- Determinism and contract stability are prioritized over rapid syntax expansion.
