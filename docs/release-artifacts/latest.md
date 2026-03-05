# Release Snapshot

- Snapshot generated (UTC): `2026-03-02T21:12:31.642821+00:00`
- Benchmark source file: `bench/token-harness/results/latest.json`
- Benchmark payload generated (UTC): `2026-03-02T21:12:22.661179+00:00`
- Full-lane entrypoint: `./scripts/check.sh`

## Benchmark Gate (B4)
- Token saving: `1389 -> 709` (`48.96%`)
- Target: `>= 25.00%` -> `met`
- Fixture floor: `10/10` -> `met`
- Calibration fixture floor: `2/2` -> `met`

## Source-of-truth rule
- bench/token-harness/results/latest.json is repo-pinned for non-mutating gate runs; docs/release-artifacts/latest.json is the freshness source-of-truth.
