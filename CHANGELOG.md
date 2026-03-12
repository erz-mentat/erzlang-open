# Changelog

## v0.1.1-public (2026-03-12)

Public sync release focused on real runtime-visible progress, not placeholder churn.

### Added
- Current CLI/runtime surface from the private mainline, excluding private protocol/history lanes
- Nested payload-path predicates and richer eval fixture examples
- Batch verify/compare handoff examples with frozen expected outputs
- Program-pack replay docs/examples, including strict-profile green lanes and sidecar handoff paths
- Public-safe `scripts/check.sh` that validates the shipped slice instead of depending on excluded heavy internal lanes

### Still deliberately excluded
- Private operational protocol logs and queue history
- Internal heavy test lane (`tests/`)
- `docs/quality-gates.md` internal gate ledger

## v0.1.0-public (2026-03-05)

Initial public release of the lean `erzlang` slice.

### Added
- Public project framing in `README.md`
- Initial changelog for public releases

### Included in this release
- Deterministic runtime core (`runtime/`)
- CLI entrypoints (`cli/`)
- IR + schema contracts (`ir/`, `schema/`)
- Practical examples and program packs (`examples/`)
- Contract/docs surface (`docs/`)
- Check helpers (`scripts/`)

### Deliberately excluded
- Private operational protocol logs and queue history
- Internal heavy benchmark lane (`bench/`)
- Internal heavy test lane (`tests/`)
