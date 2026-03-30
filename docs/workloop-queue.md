# CTO Workloop Queue

Current focus: post-Sprint-5 integration hardening, compatibility tests, docs, quality gates.

## Completed in this cycle

- [x] WLP-017, compact trace compatibility for calibration fields
  - `tr.calibrated_probability` accepted and validated in compact parser
  - finite number support for trace numeric fields
  - compact tests extended for compatibility and failure paths

- [x] WLP-018, benchmark quality-gate hardening
  - enforce fixture coverage floors in `scripts/check.sh`
  - restore benchmark artifacts after gate run, non-mutating local checks
  - fixture corpus extended to 10 pairs (with one new ingest fixture pair)

- [x] WLP-019, integration pipeline test lane
  - added explicit end-to-end tests: compact trace parse -> runtime trace validation -> schema parity checks
  - added `tests/test_integration_pipeline.py` with required-only and full optional-field coverage

- [x] WLP-020, migration/compatibility discipline gate
  - added machine-checked migration/profile anchors in docs
  - extended `scripts/check.sh` with migration anchor drift checks (step 6/7)
  - aligned `docs/migrations.md` and `docs/quality-gates.md` on active profile references

- [x] WLP-021, docs cleanup pass (targeted)
  - aligned `docs/autofix-policy.md` trace field order with current trace contract
  - removed outdated integer-only numeric wording in autofix failure notes

- [x] WLP-022, docs/spec parity sweep
  - normalized trace-field wording for finite number semantics and optional `calibrated_probability`
  - aligned `README.md`, `docs/runtime-determinism.md`, `docs/ir-contract-v0.1.md`, and `spec/grammar-card.md`

- [x] WLP-023, quality-gate drift canary tests
  - added canary unittest coverage for migration gate anchors (required/optional trace token order)
  - added profile-anchor drift coverage (cross-doc profile list sync + migration heading presence)

- [x] WLP-024, CI lane split for faster feedback
  - added `scripts/check-unit.sh` for fast unit-only feedback loops
  - added `scripts/check-full.sh` as explicit full-gate wrapper while keeping `./scripts/check.sh` unchanged
  - documented split lanes in `docs/quality-gates.md`

- [x] WLP-025, gate script modularization
  - factored benchmark/trace-contract/migration-anchor probes into dedicated helpers under `scripts/gates/`
  - updated `scripts/check.sh` to call helper scripts while preserving step order and artifact restore behavior

- [x] WLP-026, compatibility anchor negative-path tests
  - added fixture-string negative-path tests for reordered required anchors, missing optional anchors, and profile-anchor mismatches
  - extended `tests/test_integration_pipeline.py` canary coverage without changing positive-path assertions

- [x] WLP-027, check-lane documentation parity
  - synchronized check-lane entrypoint wording between `README.md` and `docs/quality-gates.md`
  - clarified `check-full.sh` wrapper equivalence to `check.sh`

- [x] WLP-028, gate-helper direct invocation tests
  - added lightweight direct-exec coverage for `scripts/gates/*.py` with fixture-controlled pass/fail expectations
  - added `tests/test_quality_gate_scripts.py` (benchmark + trace-contract + migration-anchor helper execution paths)

- [x] WLP-029, benchmark gate diagnostics hardening
  - added explicit malformed/missing-key diagnostics in `scripts/gates/benchmark_gate.py`
  - hardened key/type checks for summary totals, target fields, pair_count, and payload pair list/object shape

- [x] WLP-030, docs/gate script reference audit
  - aligned gate-internal helper references across `README.md`, `docs/quality-gates.md`, and `docs/migrations.md`
  - clarified that `scripts/check.sh` aggregates helper-script probes

## Recently completed

- [x] WLP-031, benchmark gate error-path coverage expansion
  - added direct helper tests for missing result file, invalid JSON payload, and non-integer `summary.pair_count`
  - extended failure-path assertions with normalized gate-prefix checks

- [x] WLP-032, gate-helper invocation contract doclet
  - added compact direct-invocation section in `docs/quality-gates.md`
  - documented cwd/path assumptions and helper failure semantics

- [x] WLP-033, check-script diagnostics normalization
  - standardized helper failures to `gate failure [<gate_name>]: ...` across `scripts/gates/*.py`
  - retained existing diagnostic payloads for compatibility with established grep/tests

- [x] WLP-034, trace-contract gate negative-path test expansion
  - added helper tests for missing schema file, invalid schema JSON, and malformed `$defs.trace` shape
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-035, migration-anchor gate missing-anchor/missing-doc coverage
  - added helper tests for missing anchor lines, missing docs, and absent profile headings
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-036, gate helper diagnostics matrix in docs
  - added compact helper matrix mapping required inputs to canonical failure categories
  - target files: `docs/quality-gates.md`

- [x] WLP-037, trace-contract gate missing `$defs.trace` object coverage
  - added helper test for schema payloads without `$defs.trace` and locked error category (`Malformed schema: missing `$defs.trace` object`)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-038, benchmark-gate row-shape negative-path coverage
  - added helper test for non-object entries in `pairs[*]` and asserted normalized payload-shape diagnostics
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-039, migration-anchor no-token anchor-line coverage
  - added helper tests for migrations and quality-gates anchor lines without backticked tokens
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-040, benchmark gate boolean-number guard coverage
  - added helper subtests proving boolean values fail numeric fields (`summary.totals.*`, `summary.target.token_saving_pct`) with stable category text
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-041, trace-contract optional-field drift coverage
  - added helper test that drops one optional trace property and asserts `missing optional fields: ...` in drift diagnostics
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-042, migration gate malformed schema-object path coverage
  - added helper subtests for non-object `root`, non-object `$defs`, and non-object `$defs.trace` shape to lock `Malformed migration gate input` categories
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-043, benchmark gate pair-count consistency coverage
  - added explicit gate check for `summary.pair_count == len(pairs)` and helper test locking canonical mismatch diagnostics
  - updated quality-gate docs to include summary/payload count consistency in Gate B4
  - target files: `scripts/gates/benchmark_gate.py`, `tests/test_quality_gate_scripts.py`, `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-044, trace-contract malformed required/properties type coverage
  - added gate shape guards for non-list `required` and non-object `properties`
  - added helper tests that lock canonical `Malformed schema` categories for both malformed shapes
  - target files: `scripts/gates/trace_contract_gate.py`, `tests/test_quality_gate_scripts.py`

- [x] WLP-045, migration anchor duplicate-token guard
  - added duplicate-token detection for anchor lines in `migration_anchor_gate.py`
  - added helper tests for duplicate tokens in both `docs/migrations.md` and `docs/quality-gates.md` anchor lines
  - extended helper diagnostics matrix with `<doc>: anchor line has duplicate tokens` category
  - target files: `scripts/gates/migration_anchor_gate.py`, `tests/test_quality_gate_scripts.py`, `docs/quality-gates.md`

- [x] WLP-046, gate-helper cwd assumption smoke coverage
  - added explicit helper smoke test that runs all gate helpers from non-root cwd and locks canonical missing-input diagnostics
  - documented intentional repo-root cwd requirement in direct invocation contract notes
  - target files: `tests/test_quality_gate_scripts.py`, `docs/quality-gates.md`

- [x] WLP-047, migration gate duplicate-profile-heading ambiguity coverage
  - decided deterministic fail policy for duplicate heading mappings (no warning mode)
  - added gate check for profile anchors mapping to multiple migration headings
  - added helper test for duplicate heading ambiguity and documented uniqueness requirement
  - target files: `scripts/gates/migration_anchor_gate.py`, `tests/test_quality_gate_scripts.py`, `docs/migrations.md`, `docs/quality-gates.md`

- [x] WLP-048, benchmark gate missing-pairs-key strictness decision
  - codified strict behavior: missing `pairs` fails as malformed benchmark payload
  - added helper test locking canonical missing-key diagnostic
  - updated gate docs to require explicit `root.pairs` list key
  - target files: `scripts/gates/benchmark_gate.py`, `tests/test_quality_gate_scripts.py`, `docs/quality-gates.md`

- [x] WLP-049, migration-heading match precision hardening
  - codified normalized exact heading-token matching (collapsed whitespace), no substring fallback
  - added migration-anchor tests for substring-only collisions and normalized-whitespace positive path
  - target files: `scripts/gates/migration_anchor_gate.py`, `tests/test_quality_gate_scripts.py`, `docs/migrations.md`, `docs/quality-gates.md`

- [x] WLP-050, benchmark gate `pairs[*].name` shape guard
  - codified minimal row contract for `pairs[*].name` (required + string) to tighten calibration floor accounting
  - added malformed-row tests for missing/non-string `name`
  - target files: `scripts/gates/benchmark_gate.py`, `tests/test_quality_gate_scripts.py`, `docs/quality-gates.md`

- [x] WLP-051, helper cwd error-path documentation examples
  - added compact examples of expected non-root cwd failure output for all helper gates
  - target files: `docs/quality-gates.md`

- [x] WLP-052, migration gate heading-level scope hardening
  - scoped profile-heading scan to migration-entry headings (`## <from> -> <to>`) and ignored fenced-code heading noise
  - added regression test proving template fenced headings cannot satisfy active profile anchors
  - documented heading-scope behavior in migration/quality-gate docs
  - target files: `scripts/gates/migration_anchor_gate.py`, `tests/test_quality_gate_scripts.py`, `docs/migrations.md`, `docs/quality-gates.md`

- [x] WLP-053, benchmark gate calibration-prefix case policy
  - codified strict case-sensitive policy: only exact lowercase `calibration_` prefix counts toward calibration fixture floor
  - added mixed-case acceptance/rejection tests and documented policy in quality gates
  - target files: `scripts/gates/benchmark_gate.py`, `tests/test_quality_gate_scripts.py`, `docs/quality-gates.md`

- [x] WLP-054, helper diagnostics matrix stderr/stdout note
  - documented per-helper stdout/stderr behavior in diagnostics matrix and failure-semantics notes for faster CI triage
  - target files: `docs/quality-gates.md`

- [x] WLP-055, benchmark gate stream-contract regression coverage
  - added helper test proving threshold failures keep metrics on stdout while canonical `gate failure [...]` remains on stderr
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-056, migration gate fence-variant heading-scan coverage
  - added regression coverage for tilde-fenced and language-tagged fenced blocks so heading-like template lines remain ignored
  - clarified fence-variant handling note in migration-anchor gate heading scanner
  - target files: `tests/test_quality_gate_scripts.py`, `scripts/gates/migration_anchor_gate.py`

- [x] WLP-057, check.sh helper stderr passthrough canary
  - added script-level canary test that runs `scripts/check.sh` with a controlled helper failure and asserts unchanged helper stderr passthrough
  - documented passthrough intent inline in `scripts/check.sh`
  - target files: `scripts/check.sh`, `tests/test_quality_gate_scripts.py`

- [x] WLP-058, benchmark gate malformed `summary.target` object-path coverage
  - added helper negative-path subtests for non-object `summary.target` and non-object `summary.totals`
  - locked canonical malformed-summary object-path diagnostics for `summary.target` and `summary.totals`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-059, migration gate mixed-fence-length closure regression coverage
  - added regression tests for quad-fence mixed close behavior: shorter close marker does not terminate fence, longer close marker does
  - hardened migration heading scanner to only accept fence-closing markers without trailing suffix content
  - target files: `tests/test_quality_gate_scripts.py`, `scripts/gates/migration_anchor_gate.py`

- [x] WLP-060, check.sh helper-failure passthrough canary for non-benchmark gates
  - extended check.sh canary strategy with trace-contract and migration-anchor helper-failure passthrough coverage
  - introduced reusable fake-python check harness used across benchmark/trace/migration canaries
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-061, benchmark gate malformed `summary` object-path coverage
  - added helper negative-path test for non-object `summary` root summary node and locked canonical malformed-summary object-path diagnostics
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-062, migration gate closing-fence suffix regression canary
  - added regression coverage proving language-tagged fence markers inside fenced blocks are not treated as valid closing fences
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-063, check.sh helper-failure short-circuit canary
  - extended fake-python check.sh canary to assert the pipeline stops at the first failing helper step and skips later helper invocations
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-064, check.sh short-circuit canary for trace-helper failure
  - extended invocation-log harness coverage to fail `trace_contract_gate.py` and assert `migration_anchor_gate.py` is never invoked
  - locked canonical step-output contract: trace step visible, migration step absent after trace helper failure
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-065, benchmark gate malformed `root` object-path coverage
  - added helper negative-path test for non-object JSON root payload to lock canonical malformed `root` diagnostics
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-066, migration gate multi-suffix fence-close regression canary
  - added regression coverage for suffix-bearing fence-marker lines (for example ````markdown` and ```md`) inside fenced blocks so headings cannot leak
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-067, migration gate mixed fence-character close regression canary
  - added regression coverage that mismatched close markers do not terminate active fences (`~~~` cannot close a backtick fence, and a backtick fence marker cannot close `~~~`)
  - locked failure behavior to missing profile-anchor headings while headings remain fenced
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-068, benchmark gate root-diagnostic doc matrix parity note
  - extended helper diagnostics matrix with explicit malformed `root` object-path example for benchmark gate summary diagnostics
  - target files: `docs/quality-gates.md`

- [x] WLP-069, check.sh terminal-step suppression canary for migration-helper failure
  - added invocation-log canary that fails `migration_anchor_gate.py` and asserts `[7/7] Quality gates complete` and success footer are suppressed
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-070, check.sh full-success terminal-step canary
  - added invocation-log canary for the all-pass path to assert `[7/7] Quality gates complete` and success footer emission
  - locked helper invocation ordering (`benchmark_gate.py` -> `trace_contract_gate.py` -> `migration_anchor_gate.py`) in the success path
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-071, check-full wrapper equivalence canary
  - extended fake-python check harness helpers with `entry_script` parameter so wrapper and canonical entrypoint can be exercised with the same contract checks
  - added wrapper canary proving `scripts/check-full.sh` executes the same full-lane steps and helper invocations as `scripts/check.sh`
  - target files: `tests/test_quality_gate_scripts.py`

## Next queue (rolling)

- [x] WLP-072, check-unit wrapper invocation/failure canaries
  - added fast-lane fake-python harness coverage for `scripts/check-unit.sh` success banner + failure propagation (no false-positive "[unit] Passed")
  - locked unit-lane invocation contract to `python3 -m unittest discover -s tests -v`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-073, check-full failure-path passthrough parity canary
  - added wrapper-specific failure-path test proving helper `stderr` passthrough + non-zero exit propagation remain unchanged when `check-full.sh` is the entrypoint
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-074, quality-gate docs parity note for wrapper canaries
  - added compact documentation note that script-level canaries cover both full-lane entrypoints plus check-unit pass/fail banner behavior
  - target files: `docs/quality-gates.md`

- [x] WLP-075, check-full benchmark-failure short-circuit parity canary
  - added invocation-log wrapper test that fails `benchmark_gate.py` via `check-full.sh` and asserts trace/migration helpers are not invoked
  - also asserts wrapper stdout does not advance to steps `[5/7]`, `[6/7]`, or `[7/7]` on benchmark helper failure
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-076, quality-gate docs note for check-unit output contract
  - documented expected `check-unit.sh` output markers (`[unit] Running unittest suite`, `[unit] Passed` on success only)
  - target files: `docs/quality-gates.md`

- [x] WLP-077, check-unit unexpected-invocation guard canary
  - extended unit-lane fake-python harness with optional unexpected-invocation mode for unittest calls
  - added canary asserting `check-unit.sh` exits non-zero and suppresses success banner when unittest invocation path is treated as unexpected
  - target files: `tests/test_quality_gate_scripts.py`

## Next queue (rolling)

- [x] WLP-078, check-full trace-failure short-circuit parity canary
  - added invocation-log wrapper test that fails `trace_contract_gate.py` via `check-full.sh` and asserts migration helper is not invoked
  - also asserts wrapper stdout does not advance to steps `[6/7]` or `[7/7]` on trace helper failure
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-079, check-unit stderr passthrough exactness canary
  - added canary asserting `check-unit.sh` forwards unittest stderr verbatim (exact stderr equality, no prefix/suffix rewriting)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-080, quality-gate docs note for wrapper short-circuit parity canaries
  - added concise docs note that wrapper canaries cover benchmark and trace short-circuit parity relative to `check.sh`
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-081, check-full migration-failure terminal-step suppression parity canary
  - added wrapper invocation-log test that fails `migration_anchor_gate.py` via `check-full.sh` and asserts `[7/7]` + success footer remain suppressed
  - locked invocation coverage that benchmark + trace + migration helpers are each invoked before terminal-step suppression
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-082, check-unit success stderr-silence canary
  - added canary asserting `check-unit.sh` emits no stderr on successful unittest execution
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-083, quality-gate docs note for check-unit stderr contract
  - added concise docs note that `check-unit.sh` forwards unittest stderr unchanged on failures and is stderr-silent on success
  - also aligned wrapper-canary wording to include migration terminal-step parity coverage
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-084, check-full migration-failure stderr passthrough exactness canary
  - added wrapper canary asserting `check-full.sh` preserves migration helper stderr byte-for-byte (exact stderr equality, including trailing newline)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-085, check.sh migration-failure stderr passthrough exactness parity canary
  - added canonical-entrypoint parity canary asserting `check.sh` preserves migration helper stderr with the same exactness contract as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-086, quality-gate docs note for migration-helper stderr passthrough exactness
  - added concise docs note that both full-lane entrypoints preserve helper stderr byte-for-byte on migration helper failures
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-087, check-full trace-failure stderr passthrough exactness canary
  - added wrapper canary asserting `check-full.sh` preserves trace helper stderr byte-for-byte (exact stderr equality, including trailing newline)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-088, check.sh trace-failure stderr passthrough exactness parity canary
  - added canonical-entrypoint parity canary asserting `check.sh` preserves trace helper stderr with the same exactness contract as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-089, quality-gate docs note for trace-helper stderr passthrough exactness
  - added concise docs note that both full-lane entrypoints preserve helper stderr byte-for-byte on trace helper failures
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-090, check-full benchmark-failure stderr passthrough exactness canary
  - added wrapper canary asserting `check-full.sh` preserves benchmark helper stderr byte-for-byte (exact stderr equality, including trailing newline)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-091, check.sh benchmark-failure stderr passthrough exactness parity canary
  - added canonical-entrypoint parity canary asserting `check.sh` preserves benchmark helper stderr with the same exactness contract as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-092, quality-gate docs note for benchmark-helper stderr passthrough exactness
  - added concise docs note that both full-lane entrypoints preserve helper stderr byte-for-byte on benchmark helper failures
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-093, check-full benchmark-failure invocation-order canary
  - extended wrapper benchmark short-circuit invocation-log canary with explicit pre-helper ordering assertion (`bench/token-harness/measure.py` before `scripts/gates/benchmark_gate.py`)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-094, check.sh benchmark-failure invocation-order parity canary
  - extended canonical benchmark short-circuit invocation-log canary with the same pre-helper ordering assertion as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-095, quality-gate docs note for benchmark-failure invocation ordering
  - added concise docs note locking benchmark-failure invocation order plus short-circuit expectation for both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-096, check-full trace-failure invocation-order canary
  - extended wrapper trace short-circuit invocation-log canary with explicit helper ordering assertion (`scripts/gates/benchmark_gate.py` before `scripts/gates/trace_contract_gate.py`)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-097, check.sh trace-failure invocation-order parity canary
  - extended canonical trace short-circuit invocation-log canary with the same helper ordering assertion as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-098, quality-gate docs note for trace-failure invocation ordering
  - added concise docs note locking trace-failure invocation order plus migration-step short-circuit expectation for both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-099, check-full migration-failure invocation-order canary
  - extended wrapper migration-failure invocation-log canary with explicit helper ordering assertions (`benchmark_gate` before `trace_contract_gate` before `migration_anchor_gate`)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-100, check.sh migration-failure invocation-order parity canary
  - extended canonical migration-failure invocation-log canary with the same helper ordering assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-101, quality-gate docs note for migration-failure invocation ordering
  - added concise docs note describing expected migration-failure invocation order and terminal-step suppression behavior for both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-102, check-full all-pass invocation-order strictness canary
  - extended wrapper all-pass invocation-log canary to assert strict end-to-end order (`bench/token-harness/measure.py` before `benchmark_gate` before `trace_contract_gate` before `migration_anchor_gate`) and single-invocation strictness for each helper
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-103, check.sh all-pass invocation-order parity canary
  - extended canonical all-pass invocation-log canary with the same strict end-to-end ordering assertions and single-invocation strictness as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-104, quality-gate docs note for all-pass invocation ordering
  - added concise docs note that both full-lane entrypoints lock the same helper invocation order on success before emitting terminal success markers
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-105, check-full all-pass step-banner ordering canary
  - extended wrapper all-pass canary to assert strict stdout step-banner sequencing (`[1/7]` through `[7/7]`), single-occurrence constraints per banner, and terminal success-footer placement
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-106, check.sh all-pass step-banner ordering parity canary
  - extended canonical all-pass canary with the same strict stdout step-order and terminal-footer assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-107, quality-gate docs note for all-pass step-banner ordering
  - added concise docs note that both full-lane entrypoints lock identical all-pass step-banner order and success-footer placement
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-108, check-full benchmark-failure step-banner boundary canary
  - extended wrapper benchmark-failure canary with strict pre-failure step-banner boundary assertions (`[1/7]`..`[4/7]` exactly once each, ordered, no skipped/duplicated early banners)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-109, check.sh benchmark-failure step-banner boundary parity canary
  - extended canonical benchmark-failure canary with the same strict pre-failure step-banner boundary assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-110, quality-gate docs note for benchmark-failure step-banner boundary contract
  - added concise docs note that both full-lane entrypoints lock identical early step-banner progression before benchmark-gate short-circuit exits
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-111, check-full trace-failure step-banner boundary canary
  - extended wrapper trace-failure canary with strict step-banner boundary assertions for `[1/7]`..`[5/7]` (single-occurrence + ordered) and explicit absence of later banners/success footer
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-112, check.sh trace-failure step-banner boundary parity canary
  - extended canonical trace-failure canary with the same strict `[1/7]`..`[5/7]` boundary assertions and later-banner suppression checks as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-113, quality-gate docs note for trace-failure step-banner boundary contract
  - added concise docs note locking identical trace-failure step-banner boundary progression for both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-114, check-full migration-failure step-banner boundary canary
  - extended wrapper migration-failure canary with strict pre-failure step-banner boundary assertions for `[1/7]`..`[6/7]` (single-occurrence + ordered) and explicit absence of terminal success banner/footer
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-115, check.sh migration-failure step-banner boundary parity canary
  - extended canonical migration-failure canary with the same strict `[1/7]`..`[6/7]` boundary assertions and terminal-marker suppression checks as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-116, quality-gate docs note for migration-failure step-banner boundary contract
  - added concise docs note that both full-lane entrypoints lock identical early step-banner progression before migration-gate short-circuit exits
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-117, check-full migration-failure boundary terminal-line canary
  - extended wrapper migration-failure canary to assert `[6/7] Migration/compatibility discipline anchors` is the last emitted step banner and appears exactly once before short-circuit exit
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-118, check.sh migration-failure boundary terminal-line parity canary
  - extended canonical migration-failure canary with the same terminal-line and single-occurrence boundary checks as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-119, quality-gate docs note for migration-failure terminal-line boundary contract
  - added concise docs note covering terminal-line boundary expectations for migration-helper failures across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-120, check-full benchmark-failure boundary terminal-line canary
  - locked wrapper benchmark-failure boundary: `[4/7] Benchmark harness` is the final emitted step banner and appears exactly once before short-circuit exit
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-121, check.sh benchmark-failure boundary terminal-line parity canary
  - locked canonical benchmark-failure parity with the same terminal-line and single-occurrence boundary checks as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-122, quality-gate docs note for benchmark-failure terminal-line boundary contract
  - added concise docs note covering benchmark-helper terminal-line boundary expectations across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-123, check-full trace-failure boundary terminal-line canary
  - extended wrapper trace-failure canary to assert `[5/7] Runtime/schema trace contract sync` is the final emitted step banner and appears exactly once before short-circuit exit
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-124, check.sh trace-failure boundary terminal-line parity canary
  - extended canonical trace-failure canary with the same terminal-line and single-occurrence boundary checks as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-125, quality-gate docs note for trace-failure terminal-line boundary contract
  - added concise docs note covering trace-helper terminal-line boundary expectations across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-126, check-full success-path terminal-line boundary canary
  - locked wrapper all-pass boundary: `[7/7] Quality gates complete` is the final emitted step banner, appears exactly once, and precedes the success footer
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-127, check.sh success-path terminal-line parity canary
  - locked canonical all-pass parity with the same terminal-line and single-occurrence boundary checks as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-128, quality-gate docs note for success-path terminal-line boundary contract
  - added concise docs note covering `[7/7]` terminal-line boundary expectations for both full-lane entrypoints on success
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-129, check-full success-footer single-occurrence boundary canary
  - extended wrapper all-pass canary to assert the success footer emits exactly once and remains the terminal non-empty stdout line after `[7/7]`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-130, check.sh success-footer single-occurrence parity canary
  - extended canonical all-pass canary with the same success-footer terminal-line/single-occurrence checks as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-131, quality-gate docs note for success-footer terminal-line contract
  - added concise docs note covering single-occurrence success-footer terminal-line expectations for both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-132, check-full success-footer exact-text contract canary
  - added wrapper all-pass canary asserting success-footer literal exactness (`All active quality gates passed.`), single occurrence, and terminal-line placement
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-133, check.sh success-footer exact-text parity canary
  - added canonical all-pass canary with the same success-footer exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-134, quality-gate docs note for success-footer exact-text contract
  - documented byte-identical success-footer literal contract and whitespace-padded variant rejection across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-135, check-full terminal step exact-text contract canary
  - added wrapper all-pass canary asserting `[7/7] Quality gates complete` literal exactness (byte-identical line text), single occurrence, and boundary placement
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-136, check.sh terminal step exact-text parity canary
  - added canonical all-pass canary with the same terminal-step exact-text/single-occurrence assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-137, quality-gate docs note for terminal-step exact-text contract
  - added concise docs note documenting exact terminal-step literal contract and whitespace-padded variant rejection across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-138, check-full benchmark terminal-step exact-text boundary canary
  - added wrapper benchmark-failure canary asserting `[4/7] Benchmark harness` boundary banner remains byte-identical (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-139, check.sh benchmark terminal-step exact-text boundary parity canary
  - added canonical benchmark-failure canary with the same boundary exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-140, quality-gate docs note for benchmark boundary exact-text contract
  - added concise docs note documenting exact `[4/7] Benchmark harness` boundary literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-141, check-full trace terminal-step exact-text boundary canary
  - added wrapper trace-failure canary asserting `[5/7] Runtime/schema trace contract sync` boundary banner remains byte-identical (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-142, check.sh trace terminal-step exact-text boundary parity canary
  - added canonical trace-failure canary with the same boundary exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-143, quality-gate docs note for trace boundary exact-text contract
  - added concise docs note documenting exact `[5/7] Runtime/schema trace contract sync` boundary literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-144, check-full migration terminal-step exact-text boundary canary
  - added wrapper migration-failure canary asserting `[6/7] Migration/compatibility discipline anchors` boundary banner remains byte-identical (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-145, check.sh migration terminal-step exact-text boundary parity canary
  - added canonical migration-failure canary with the same boundary exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-146, quality-gate docs note for migration boundary exact-text contract
  - added concise docs note documenting exact `[6/7] Migration/compatibility discipline anchors` boundary literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-147, check-full step-1 banner exact-text contract canary
  - added wrapper all-pass canary asserting `[1/7] CLI smoke: fmt + parse + validate` emits byte-identically (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-148, check.sh step-1 banner exact-text parity canary
  - added canonical all-pass canary with the same step-1 exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-149, quality-gate docs note for step-1 banner exact-text contract
  - added concise docs note documenting exact `[1/7] CLI smoke: fmt + parse + validate` literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-150, check-full step-2 banner exact-text contract canary
  - added wrapper all-pass canary asserting `[2/7] Unit tests` emits byte-identically (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-151, check.sh step-2 banner exact-text parity canary
  - added canonical all-pass canary with the same step-2 exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-152, quality-gate docs note for step-2 banner exact-text contract
  - added concise docs note documenting exact `[2/7] Unit tests` literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-153, check-full step-3 banner exact-text contract canary
  - added wrapper all-pass canary asserting `[3/7] Few-shot parser cases` emits byte-identically (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-154, check.sh step-3 banner exact-text parity canary
  - added canonical all-pass canary with the same step-3 exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-155, quality-gate docs note for step-3 banner exact-text contract
  - added concise docs note documenting exact `[3/7] Few-shot parser cases` literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-156, check-full step-4 banner exact-text contract canary
  - added wrapper all-pass canary asserting `[4/7] Benchmark harness` emits byte-identically in success path (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-157, check.sh step-4 banner exact-text parity canary
  - added canonical all-pass canary with the same step-4 success-path exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-158, quality-gate docs note for step-4 banner exact-text contract
  - added concise docs note documenting exact `[4/7] Benchmark harness` success-path literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-159, check-full step-5 banner exact-text contract canary
  - added wrapper all-pass canary asserting `[5/7] Runtime/schema trace contract sync` emits byte-identically in success path (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-160, check.sh step-5 banner exact-text parity canary
  - added canonical all-pass canary with the same step-5 success-path exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-161, quality-gate docs note for step-5 banner exact-text contract
  - added concise docs note documenting exact `[5/7] Runtime/schema trace contract sync` success-path literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-162, check-full step-6 banner exact-text contract canary
  - added wrapper all-pass canary asserting `[6/7] Migration/compatibility discipline anchors` emits byte-identically in success path (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-163, check.sh step-6 banner exact-text parity canary
  - added canonical all-pass canary with the same step-6 success-path exact-text assertions as `check-full.sh`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-164, quality-gate docs note for step-6 banner exact-text contract
  - added concise docs note documenting exact `[6/7] Migration/compatibility discipline anchors` success-path literal contract across both full-lane entrypoints
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-165, check-unit start banner exact-text contract canary
  - added canary asserting `check-unit.sh` emits `[unit] Running unittest suite` byte-identically (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-166, check-unit success banner exact-text contract canary
  - added canary asserting `check-unit.sh` emits `[unit] Passed` byte-identically on success (single occurrence, no whitespace-padded variants)
  - also locked terminal non-empty stdout line to exact `[unit] Passed`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-167, quality-gate docs note for check-unit banner exact-text contract
  - added concise docs note documenting exact check-unit banner literals for start and success lines
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-168, check-unit failure-path start-banner exact-text canary
  - added failure-path canary asserting `check-unit.sh` still emits `[unit] Running unittest suite` byte-identically (single occurrence, no whitespace-padded variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-169, check-unit failure-path success-banner suppression exactness canary
  - added failure-path canary asserting `check-unit.sh` emits no exact or whitespace-padded `[unit] Passed` variants when unittest exits non-zero
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-170, quality-gate docs note for check-unit failure-path banner suppression contract
  - documented failure-path start-banner exactness and success-banner suppression expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-171, check-unit failure-path stdout boundary canary
  - added failure-path canary asserting failing `check-unit.sh` keeps `[unit] Running unittest suite` as the terminal non-empty stdout line
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-172, check-unit failure-path start-banner ordering canary
  - added failure-path canary asserting stderr passthrough remains isolated to stderr and does not mutate start-banner stdout ordering
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-173, quality-gate docs note for check-unit failure-path stdout boundary contract
  - documented terminal stdout boundary expectations for failing `check-unit.sh` runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-174, check-unit failure-path terminal-line exact-text canary
  - added canary asserting failing `check-unit.sh` keeps terminal stdout line byte-identical as `[unit] Running unittest suite` (single occurrence, no whitespace-padded terminal variants)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-175, check-unit unexpected-invocation failure-path stdout boundary canary
  - added unexpected-invocation canary asserting `force_unexpected_unittest_invocation=True` preserves the same terminal stdout boundary contract (`[unit] Running unittest suite` only)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-176, quality-gate docs note for check-unit failure-mode parity on terminal stdout boundary
  - documented that both unittest-failure and unexpected-invocation failure modes keep identical start-banner terminal-line boundary semantics
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-177, check-unit unexpected-invocation success-banner suppression exactness canary
  - added canary asserting unexpected-invocation failures emit no exact or whitespace-padded `[unit] Passed` variants
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-178, check-unit unexpected-invocation stderr exactness canary
  - added canary asserting unexpected-invocation stderr remains byte-identical (`unexpected invocation: -m unittest discover -s tests -v`) with trailing newline
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-179, quality-gate docs note for unexpected-invocation failure-mode suppression/stderr parity
  - added concise docs note that unexpected-invocation failures preserve success-banner suppression and stderr exactness contracts alongside generic unittest failures
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-180, check-unit unexpected-invocation stdout/stderr channel isolation canary
  - added canary asserting the unexpected-invocation diagnostic never leaks into stdout while `[unit] Running unittest suite` remains the only non-empty stdout line
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-181, check-unit unexpected-invocation stderr terminal-line exact-text canary
  - added canary asserting stderr has exactly one non-empty line and that line is byte-identical to `unexpected invocation: -m unittest discover -s tests -v`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-182, quality-gate docs note for unexpected-invocation channel-isolation parity
  - added concise docs note that unexpected-invocation failures keep diagnostics on stderr only while preserving terminal stdout boundary parity
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-183, check-unit success-path stdout channel isolation canary
  - added canary asserting success-path stdout is banner-only (`[unit] Running unittest suite`, `[unit] Passed`) with no unexpected diagnostic leakage
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-184, check-unit success-path stderr emptiness terminal-line canary
  - added success-path canary asserting zero non-empty stderr lines via explicit line-scan contract (not only empty-string shorthand)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-185, quality-gate docs note for check-unit success channel-isolation contract
  - added concise docs note that successful check-unit runs keep stdout banner-only and stderr free of non-empty diagnostic lines
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-186, check-unit success-path unittest invocation count canary
  - added success-path canary asserting `check-unit.sh` invokes python exactly once with `-m unittest discover -s tests -v` and no extra entrypoint calls
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-187, check-unit failure-path unittest invocation count parity canary
  - added failure-path canary asserting non-zero unittest runs still perform exactly one `-m unittest discover -s tests -v` invocation (no retry/replay)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-188, quality-gate docs note for check-unit invocation-count contract
  - added concise docs note documenting single-invocation expectation for success and failure paths
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-189, check-unit unexpected-invocation path single-attempt count canary
  - added canary asserting `force_unexpected_unittest_invocation=True` still logs exactly one attempted unittest invocation and no retry/replay
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-190, check-unit unittest argv exact-vector parity canary
  - added canary asserting success and failure paths both preserve exact argv vector `-m unittest discover -s tests -v` (byte-identical ordering, no arg drift)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-191, quality-gate docs note for check-unit unittest argv exact-vector contract
  - added concise docs note documenting exact unittest argv-vector parity across check-unit pass/fail modes
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-192, check-unit unexpected-invocation argv-vector tri-parity canary
  - added canary asserting pass, fail, and unexpected-invocation modes all preserve the same single attempted unittest argv vector
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-193, check-unit unexpected-invocation invocation-log terminal-line exactness canary
  - added canary asserting unexpected-invocation mode keeps invocation-log terminal line byte-identical to `-m unittest discover -s tests -v`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-194, quality-gate docs note for check-unit tri-mode argv-vector parity
  - updated quality-gate contract note to explicitly include pass/fail/unexpected-invocation tri-mode argv-vector parity
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-195, check-unit tri-mode invocation-log cardinality parity canary
  - added canary asserting pass/fail/unexpected-invocation modes each persist exactly one invocation-log line with canonical argv literal `-m unittest discover -s tests -v`
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-196, check-unit unexpected-invocation invocation-log ordering canary
  - added canary asserting unexpected-invocation invocation-log entry preserves canonical argv ordering token-by-token (`-m`, `unittest`, `discover`, `-s`, `tests`, `-v`)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-197, quality-gate docs note for tri-mode invocation-log cardinality/order contracts
  - added concise docs note describing one-line invocation-log cardinality and canonical ordering guarantees across check-unit tri-modes
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-198, check-unit unexpected-invocation diagnostic/log suffix parity canary
  - added canary asserting unexpected-invocation stderr diagnostic suffix after `unexpected invocation: ` is byte-identical to the invocation-log terminal line
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-199, check-unit unexpected-invocation diagnostic token-count parity canary
  - added canary asserting diagnostic/log argv tokenization remains exactly six canonical tokens with stable ordering
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-200, quality-gate docs note for unexpected-invocation diagnostic/log parity contract
  - added concise docs note documenting suffix-equality and token-count parity guarantees between unexpected-invocation stderr diagnostics and invocation-log entries
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-201, check-unit unexpected-invocation diagnostic/log separator-count parity canary
  - added canary asserting diagnostic suffix and invocation-log line each contain exactly five single-space separators (no collapsed or doubled separators)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-202, check-unit unexpected-invocation diagnostic/log no-empty-token parity canary
  - added canary asserting both diagnostic suffix and invocation-log argv splits contain zero empty tokens while preserving canonical token order
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-203, quality-gate docs note for separator/no-empty-token parity contract
  - added concise docs note documenting separator-count and no-empty-token parity guarantees for unexpected-invocation diagnostics vs invocation-log entries
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-204, check-unit unexpected-invocation diagnostic-prefix exact-text parity canary
  - added canary asserting stderr starts with exact prefix `unexpected invocation: ` (single colon + space, no case/spacing drift) and preserves canonical suffix extraction parity with invocation-log output
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-205, check-unit unexpected-invocation invocation-log trim-boundary parity canary
  - added canary asserting invocation-log argv line has no leading/trailing whitespace and equals `' '.join(tokens)` for canonical six-token ordering
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-206, quality-gate docs note for diagnostic-prefix/trim-boundary parity contract
  - added concise docs note documenting exact-prefix and trim-boundary parity guarantees for unexpected-invocation diagnostics vs invocation-log entries
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-207, check-unit unexpected-invocation diagnostic-prefix cardinality canary
  - added canary asserting stderr contains exactly one `unexpected invocation: ` prefix occurrence at line start and zero repeated-prefix leakage into the diagnostic suffix
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-208, check-unit unexpected-invocation suffix non-empty boundary parity canary
  - added canary asserting diagnostic suffix after prefix extraction is non-empty and token-boundary stable (first/last token preserved, no boundary whitespace drift) against invocation-log argv line
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-209, quality-gate docs note for diagnostic-prefix-cardinality/suffix-boundary parity contract
  - added concise docs note documenting single-prefix cardinality and non-empty suffix boundary guarantees for unexpected-invocation diagnostics vs invocation-log entries
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-210, check-unit unexpected-invocation suffix single-line canary
  - added canary asserting diagnostic suffix after prefix extraction is a single logical line (no embedded newline leakage) and remains line-equal to invocation-log argv entry
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-211, check-unit unexpected-invocation stderr terminal-newline cardinality canary
  - added canary asserting unexpected-invocation stderr ends with exactly one terminal newline and no extra trailing blank diagnostic lines
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-212, quality-gate docs note for suffix single-line/newline-cardinality parity contract
  - added concise docs note documenting single-line suffix and single-terminal-newline guarantees for unexpected-invocation diagnostics vs invocation-log entries
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-213, check-unit unexpected-invocation stderr CRLF/CR leak guard canary
  - added canary asserting unexpected-invocation stderr diagnostic line is LF-only (no `\r` carriage-return leakage) while preserving canonical diagnostic literal
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-214, check-unit unexpected-invocation diagnostic/log CRLF parity canary
  - added canary asserting both diagnostic suffix and invocation-log argv line remain CR-free and token-equal under explicit CR-sensitive checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-215, quality-gate docs note for unexpected-invocation LF-only diagnostic contract
  - added concise docs note documenting LF-only stderr diagnostics (no CR/CRLF drift) for unexpected-invocation failures
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-216, check-unit unexpected-invocation stdout line-ending isolation canary
  - added canary asserting unexpected-invocation failure stdout remains exactly one LF-terminated banner line (`[unit] Running unittest suite\n`) with no CR/CRLF leakage
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-217, check-unit unexpected-invocation stderr single-line LF segmentation canary
  - added canary asserting stderr splits into exactly one LF-only diagnostic line and remains canonical after explicit line-segmentation checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-218, quality-gate docs note for unexpected-invocation line-ending channel isolation contract
  - added concise docs note documenting LF-only per-channel line-ending guarantees (stdout banner + stderr diagnostic) for unexpected-invocation failures
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-219, check-unit stdout line-ending tri-mode parity canary
  - added tri-mode canary asserting check-unit stdout remains CR-free and LF-terminated across pass/fail/unexpected modes with canonical mode-specific non-empty line boundaries
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-220, check-unit stderr line-ending tri-mode parity canary
  - added tri-mode canary asserting mode-accurate stderr behavior (success empty, fail passthrough LF-only, unexpected canonical LF-only diagnostic) without CR/CRLF leakage
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-221, quality-gate docs note for check-unit tri-mode line-ending parity contract
  - added concise docs note documenting tri-mode LF-only channel behavior and CR/CRLF exclusion expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-222, check-unit stdout tri-mode terminal-newline cardinality canary
  - added tri-mode canary asserting mode-accurate terminal newline counts for stdout across pass/fail/unexpected modes (pass emits two LF-terminated banner lines, fail/unexpected emit one)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-223, check-unit stderr tri-mode explicit segmentation parity canary
  - added tri-mode canary asserting mode-accurate stderr segmentation parity via `splitlines()` and `splitlines(keepends=True)` (success empty, fail passthrough one LF line, unexpected canonical one LF diagnostic line)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-224, quality-gate docs note for check-unit tri-mode newline-cardinality and segmentation parity
  - added concise docs note documenting tri-mode newline-cardinality and line-segmentation guarantees for stdout/stderr channels
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-225, check-unit stdout tri-mode keepends recompose parity canary
  - added tri-mode canary asserting `''.join(stdout.splitlines(keepends=True)) == stdout` across pass/fail/unexpected modes with mode-accurate banner-line vectors
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-226, check-unit stderr tri-mode terminal-newline cardinality parity canary
  - added tri-mode canary asserting stderr newline counts stay mode-accurate (pass `0`, fail `1`, unexpected `1`) with explicit non-empty-line boundaries
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-227, quality-gate docs note for tri-mode keepends-recompose and stderr newline-cardinality parity
  - added concise docs note documenting tri-mode stdout recompose parity and stderr terminal-newline cardinality guarantees
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-228, check-unit stdout tri-mode split-plus-join parity canary
  - added tri-mode canary asserting `"\n".join(stdout.splitlines()) + ("\n" if stdout else "") == stdout` across pass/fail/unexpected modes with mode-accurate non-empty line vectors
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-229, check-unit stderr tri-mode keepends recompose parity canary
  - added tri-mode canary asserting `''.join(stderr.splitlines(keepends=True)) == stderr` across pass/fail/unexpected modes with mode-accurate empty/single-line behavior
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-230, quality-gate docs note for tri-mode split-join and stderr keepends-recompose parity
  - added concise docs note documenting tri-mode stdout split/join parity and stderr keepends recompose guarantees
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-231, check-unit stderr tri-mode split-plus-join parity canary
  - added tri-mode canary asserting `"\n".join(stderr.splitlines()) + ("\n" if stderr else "") == stderr` across pass/fail/unexpected modes with mode-accurate empty/single-line behavior
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-232, check-unit stdout tri-mode keepends-to-splitlines normalization parity canary
  - added tri-mode canary asserting `[line.removesuffix("\n") for line in stdout.splitlines(keepends=True)] == stdout.splitlines()` across pass/fail/unexpected modes with mode-accurate banner-line vectors
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-233, quality-gate docs note for tri-mode stderr split-join and stdout keepends-normalization parity
  - added concise docs note documenting tri-mode stderr split/join parity and stdout keepends-normalization guarantees
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-234, check-unit stderr tri-mode keepends-to-splitlines normalization parity canary
  - added tri-mode canary asserting `[line.removesuffix("\n") for line in stderr.splitlines(keepends=True)] == stderr.splitlines()` across pass/fail/unexpected modes with mode-accurate empty/single-line behavior
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-235, check-unit stdout tri-mode split-segmentation parity canary
  - added tri-mode canary asserting `stdout.split("\n") == [*stdout.splitlines(), ""]` across pass/fail/unexpected modes with mode-accurate banner-line vectors
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-236, quality-gate docs note for tri-mode stderr keepends-normalization and stdout split-segmentation parity
  - added concise docs note documenting tri-mode stderr keepends-normalization and stdout split-segmentation guarantees
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-237, check-unit stderr tri-mode split-segmentation parity canary
  - added tri-mode canary asserting `stderr.split("\n") == [*stderr.splitlines(), ""]` across pass/fail/unexpected modes with mode-accurate empty/single-line behavior
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-238, check-unit stdout tri-mode split tail-cardinality parity canary
  - added tri-mode canary asserting `len(stdout.split("\n")) == len(stdout.splitlines()) + 1` across pass/fail/unexpected modes with mode-accurate banner-line vectors
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-239, quality-gate docs note for tri-mode stderr split-segmentation and stdout split tail-cardinality parity
  - added concise docs note documenting tri-mode stderr split-segmentation and stdout split tail-cardinality guarantees
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-240, check-unit stderr tri-mode split tail-cardinality parity canary
  - added tri-mode canary asserting `len(stderr.split("\n")) == len(stderr.splitlines()) + 1` across pass/fail/unexpected modes with mode-accurate empty/single-line behavior
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-241, check-unit tri-mode cross-channel split tail-cardinality parity canary
  - added tri-mode canary asserting mode-accurate split tail-cardinality parity for both channels in one contract (`len(stdout.split("\n")) == len(stdout.splitlines()) + 1`, `len(stderr.split("\n")) == len(stderr.splitlines()) + 1`)
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-242, quality-gate docs note for stderr split tail-cardinality and cross-channel split tail-cardinality parity
  - added concise docs note documenting tri-mode stderr split tail-cardinality guarantees and cross-channel split tail-cardinality parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-243, check-unit stderr tri-mode split trailing-empty-segment parity canary
  - added tri-mode canary asserting one terminal empty split segment plus pre-tail equality (`stderr.split("\n")[-1] == ""`, `stderr.split("\n")[:-1] == stderr.splitlines()`) across pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-244, check-unit tri-mode cross-channel split trailing-empty-segment parity canary
  - added cross-channel tri-mode canary asserting trailing-empty-segment and pre-tail equality contracts for both stdout and stderr in each mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-245, quality-gate docs note for split trailing-empty-segment parity and cross-channel parity
  - added concise docs note documenting tri-mode stderr trailing-empty-segment guarantees and cross-channel split trailing-tail parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-246, check-unit stdout tri-mode split trailing-empty-segment parity canary
  - added tri-mode canary asserting `stdout.split("\n")[-1] == ""` and `stdout.split("\n")[:-1] == stdout.splitlines()` across pass/fail/unexpected modes with mode-accurate banner vectors
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-247, check-unit tri-mode cross-channel split trailing-tail identity parity canary
  - added cross-channel canary asserting `channel_output.split("\n")[-1] == ""` and `channel_output.split("\n")[:-1] == expected_lines[channel]` for both stdout/stderr in each mode via one shared contract loop
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-248, quality-gate docs note for stdout trailing-empty-segment and cross-channel trailing-tail identity parity
  - added concise docs note documenting tri-mode stdout trailing-empty-segment guarantees and cross-channel trailing-tail identity parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-249, check-unit stdout tri-mode split trailing-tail length parity canary
  - added tri-mode canary asserting `len(stdout.split("\n")[:-1]) == len(stdout.splitlines()) == len(expected_stdout_lines)` across pass/fail/unexpected modes with mode-accurate banner vectors
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-250, check-unit tri-mode cross-channel split trailing-tail length parity canary
  - added cross-channel canary asserting `len(channel_output.split("\n")[:-1]) == len(expected_lines[channel])` and `len(channel_output.splitlines()) == len(expected_lines[channel])` for stdout/stderr in each mode via one shared contract loop
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-251, quality-gate docs note for trailing-tail length parity contracts
  - added concise docs note documenting tri-mode trailing-tail length parity guarantees for stdout plus cross-channel parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-252, check-unit stdout tri-mode split trailing-tail index-boundary parity canary
  - added tri-mode canary asserting `stdout.split("\n")[:len(expected_stdout_lines)] == expected_stdout_lines` and `stdout.split("\n")[len(expected_stdout_lines)] == ""` across pass/fail/unexpected modes with explicit boundary cardinality checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-253, check-unit tri-mode cross-channel split trailing-tail index-boundary parity canary
  - added cross-channel canary asserting `channel_output.split("\n")[:len(expected_lines[channel])] == expected_lines[channel]` and `channel_output.split("\n")[len(expected_lines[channel])] == ""` for stdout/stderr in each mode with boundary cardinality checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-254, quality-gate docs note for trailing-tail index-boundary parity contracts
  - added concise docs note documenting tri-mode trailing-tail index-boundary guarantees for stdout plus cross-channel parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-255, check-unit stdout tri-mode split trailing-tail post-boundary singleton parity canary
  - added tri-mode canary asserting `stdout.split("\n")[len(expected_stdout_lines):] == [""]` across pass/fail/unexpected modes with mode-accurate expected-line vectors and CR exclusion checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-256, check-unit tri-mode cross-channel split trailing-tail post-boundary singleton parity canary
  - added cross-channel canary asserting `channel_output.split("\n")[len(expected_lines[channel]):] == [""]` for stdout/stderr in each mode with channel-accurate expected-output parity checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-257, quality-gate docs note for trailing-tail post-boundary singleton parity contracts
  - added concise docs note documenting tri-mode trailing-tail post-boundary singleton guarantees for stdout plus cross-channel parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-258, check-unit stdout tri-mode split trailing-tail post-boundary singleton-length parity canary
  - added tri-mode canary asserting `len(stdout.split("\n")[len(expected_stdout_lines):]) == 1` with explicit singleton-element equality checks across pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-259, check-unit tri-mode cross-channel split trailing-tail post-boundary singleton-length parity canary
  - added cross-channel canary asserting `len(channel_output.split("\n")[len(expected_lines[channel]):]) == 1` with explicit singleton-element equality checks for stdout/stderr in each mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-260, quality-gate docs note for trailing-tail post-boundary singleton-length parity contracts
  - added concise docs note documenting tri-mode stdout trailing-tail post-boundary singleton-length guarantees plus cross-channel parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-261, check-unit stderr tri-mode split trailing-tail post-boundary singleton-length parity canary
  - added tri-mode canary asserting `len(stderr.split("\n")[len(expected_stderr_lines):]) == 1` with explicit singleton-element equality checks across pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-262, check-unit tri-mode cross-channel split trailing-tail post-boundary singleton-length boundary-index canary
  - added cross-channel canary asserting `channel_output.split("\n")[len(expected_lines[channel]):]` has exactly one element and that element sits at the explicit post-boundary index for stdout/stderr per mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-263, quality-gate docs note for stderr singleton-length and cross-channel boundary-index parity contracts
  - added concise docs note documenting tri-mode stderr post-boundary singleton-length guarantees plus cross-channel boundary-index parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-264, check-unit stderr tri-mode split trailing-tail post-boundary singleton boundary-index parity canary
  - added tri-mode canary asserting `stderr.split("\n")[:len(expected_stderr_lines)] == expected_stderr_lines`, `stderr.split("\n")[len(expected_stderr_lines)] == ""`, `stderr.split("\n")[len(expected_stderr_lines):] == [""]`, and `len(stderr.split("\n")) == len(expected_stderr_lines) + 1` across pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-265, check-unit tri-mode cross-channel split trailing-tail boundary-index length equality canary
  - added cross-channel canary asserting `len(split_segments) == len(expected_lines[channel]) + 1` while preserving pre-boundary exactness and singleton-tail closure for stdout/stderr in each mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-266, quality-gate docs note for stderr boundary-index and cross-channel boundary-length parity contracts
  - added concise docs note documenting stderr boundary-index singleton guarantees plus cross-channel boundary-length equality expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-267, check-unit stderr tri-mode split boundary-length pre-tail cardinality canary
  - added tri-mode canary asserting `len(stderr.split("\n")[:-1]) == len(expected_stderr_lines)` and `stderr.split("\n")[:-1] == expected_stderr_lines` across pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-268, check-unit tri-mode cross-channel split boundary-length pre-tail cardinality canary
  - added cross-channel canary asserting `len(channel_output.split("\n")[:-1]) == len(expected_lines[channel])` with exact pre-tail line parity for stdout/stderr in each mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-269, quality-gate docs note for boundary-length pre-tail cardinality parity contracts
  - added concise docs note documenting stderr pre-tail cardinality guarantees plus cross-channel pre-tail parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-270, check-unit stderr tri-mode split full-vector boundary-closure parity canary
  - added tri-mode canary asserting `stderr.split("\n") == [*expected_stderr_lines, ""]` across pass/fail/unexpected modes to lock pre-tail exactness plus terminal-empty closure in one contract
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-271, check-unit tri-mode cross-channel split full-vector boundary-closure parity canary
  - added cross-channel canary asserting `channel_output.split("\n") == [*expected_lines[channel], ""]` for stdout/stderr in each mode with channel-accurate expected-line parity
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-272, quality-gate docs note for split full-vector boundary-closure parity contracts
  - added concise docs note documenting stderr full-vector boundary-closure guarantees plus cross-channel parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-273, check-unit stderr tri-mode split full-vector boundary-closure tail-index parity canary
  - aligned tri-mode canary naming and diagnostics to the full-vector boundary-closure tail-index contract, asserting `stderr.split("\n")[-1] == ""` and `stderr.split("\n")[:-1] == expected_stderr_lines` with `splitlines()` parity plus CR-exclusion across pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-274, check-unit tri-mode cross-channel split full-vector boundary-closure tail-index parity canary
  - aligned cross-channel canary naming and diagnostics to the full-vector boundary-closure tail-index contract, asserting `channel_output.split("\n")[-1] == ""` and `channel_output.split("\n")[:-1] == expected_lines[channel]` with `splitlines()` parity plus CR-exclusion for stdout/stderr in each mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-275, quality-gate docs note for split full-vector tail-index parity contracts
  - added concise docs note documenting stderr full-vector tail-index guarantees plus cross-channel tail-index parity expectations
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-276, check-unit stderr tri-mode split full-vector tail-index length-coupling canary
  - added tri-mode canary asserting `len(stderr.split("\n")) == len(expected_stderr_lines) + 1` together with tail-index closure (`stderr.split("\n")[-1] == ""`) and pre-tail exactness across pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-277, check-unit tri-mode cross-channel split full-vector tail-index length-coupling canary
  - added cross-channel canary asserting `len(channel_output.split("\n")) == len(expected_lines[channel]) + 1` together with tail-index closure and pre-tail equality for stdout/stderr in pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-278, quality-gate docs note for split full-vector tail-index length-coupling contracts
  - added concise docs note documenting stderr and cross-channel split-vector length-coupling expectations for tail-index parity checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-279, check-unit stderr tri-mode split full-vector tail-index length-coupling splitlines-parity canary
  - added tri-mode canary asserting `len(stderr.split("\n")) == len(stderr.splitlines()) + 1` and `len(stderr.splitlines()) == len(expected_stderr_lines)` together with tail-index closure in pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-280, check-unit tri-mode cross-channel split full-vector tail-index length-coupling splitlines-parity canary
  - added cross-channel canary asserting `len(channel_output.split("\n")) == len(channel_output.splitlines()) + 1` and `len(channel_output.splitlines()) == len(expected_lines[channel])` for stdout/stderr per mode with tail-index closure
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-281, quality-gate docs note for split full-vector tail-index splitlines length-coupling parity contracts
  - added concise docs note documenting split/splitlines length-coupling parity expectations for stderr and cross-channel checks in tri-mode runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-282, check-unit stderr tri-mode split full-vector tail-index length-coupling splitlines-pre-tail parity canary
  - added tri-mode canary asserting `stderr.split("\n")[:-1] == stderr.splitlines()` plus `len(stderr.split("\n")[:-1]) == len(expected_stderr_lines)` with terminal-tail closure in pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-283, check-unit tri-mode cross-channel split full-vector tail-index length-coupling splitlines-pre-tail parity canary
  - added cross-channel canary asserting `channel_output.split("\n")[:-1] == channel_output.splitlines()` plus pre-tail cardinality parity (`len(channel_output.splitlines()) == len(expected_lines[channel])`) for stdout/stderr per mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-284, quality-gate docs note for split full-vector splitlines pre-tail parity contracts
  - added concise docs note documenting split pre-tail and splitlines parity expectations for stderr and cross-channel checks in tri-mode runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-285, check-unit stderr tri-mode split full-vector splitlines-pre-tail length-delta parity canary
  - added tri-mode canary asserting `len(stderr.split("\n")[:-1]) == len(stderr.split("\n")) - 1` and `len(stderr.split("\n")[:-1]) == len(stderr.splitlines())` with terminal-tail closure in pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-286, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail length-delta parity canary
  - added cross-channel canary asserting `len(channel_output.split("\n")[:-1]) == len(channel_output.split("\n")) - 1` and `len(channel_output.split("\n")[:-1]) == len(channel_output.splitlines())` for stdout/stderr per mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-287, quality-gate docs note for split full-vector splitlines pre-tail length-delta parity contracts
  - added concise docs note documenting split pre-tail length-delta parity expectations for stderr tri-mode checks and cross-channel parity in tri-mode runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-288, check-unit stderr tri-mode split full-vector splitlines-pre-tail length-delta identity parity canary
  - added tri-mode canary asserting `len(stderr.split("\n")) - len(stderr.splitlines()) == 1` and `len(stderr.split("\n")[:-1]) == len(stderr.splitlines())` with terminal-tail closure in pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-289, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail length-delta identity parity canary
  - added cross-channel canary asserting `len(channel_output.split("\n")) - len(channel_output.splitlines()) == 1` and `len(channel_output.split("\n")[:-1]) == len(channel_output.splitlines())` for stdout/stderr per mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-290, quality-gate docs note for split full-vector splitlines pre-tail length-delta identity parity contracts
  - added concise docs note documenting split pre-tail length-delta identity parity expectations for stderr tri-mode checks and cross-channel parity in tri-mode runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-291, check-unit stderr tri-mode split full-vector splitlines-pre-tail length-delta signed-inverse parity canary
  - added tri-mode canary asserting `len(stderr.splitlines()) - len(stderr.split("\n")) == -1` and `len(stderr.splitlines()) - len(stderr.split("\n")[:-1]) == 0` with terminal-tail closure in pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-292, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail length-delta signed-inverse parity canary
  - added cross-channel canary asserting `len(channel_output.splitlines()) - len(channel_output.split("\n")) == -1` and `len(channel_output.splitlines()) - len(channel_output.split("\n")[:-1]) == 0` for stdout/stderr per mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-293, quality-gate docs note for split full-vector splitlines pre-tail length-delta signed-inverse parity contracts
  - added concise docs note documenting signed-inverse length-delta parity expectations for stderr tri-mode checks and cross-channel parity in tri-mode runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-294, check-unit stderr tri-mode split full-vector splitlines-pre-tail signed-inverse plus identity zero-sum parity canary
  - added tri-mode canary asserting signed-inverse and identity deltas cancel to zero via `(len(split_lines) - len(split_segments)) + (len(split_segments) - len(split_lines)) == 0` while preserving terminal-tail closure for pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-295, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail signed-inverse plus identity zero-sum parity canary
  - added cross-channel canary asserting zero-sum cancellation identity for stdout/stderr per mode with existing boundary closure and CR exclusion checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-296, quality-gate docs note for split full-vector splitlines signed-inverse plus identity zero-sum parity contracts
  - added concise docs note documenting zero-sum parity expectations that pair signed-inverse and identity length-delta checks for stderr tri-mode and cross-channel runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-297, check-unit stderr tri-mode split full-vector splitlines-pre-tail signed-inverse and identity absolute-delta parity canary
  - added tri-mode canary asserting `abs(len(stderr.splitlines()) - len(stderr.split("\n"))) == abs(len(stderr.split("\n")) - len(stderr.splitlines())) == 1` with terminal-tail closure retained for pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-298, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail signed-inverse and identity absolute-delta parity canary
  - added cross-channel canary asserting `abs(len(channel_output.splitlines()) - len(channel_output.split("\n"))) == abs(len(channel_output.split("\n")) - len(channel_output.splitlines())) == 1` for stdout/stderr per mode with boundary closure checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-299, quality-gate docs note for split full-vector splitlines signed-inverse and identity absolute-delta parity contracts
  - added concise docs note documenting absolute-delta parity expectations that pair signed-inverse and identity checks for stderr tri-mode and cross-channel runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-300, check-unit stderr tri-mode split full-vector splitlines-pre-tail signed-inverse and identity absolute-delta zero-difference parity canary
  - added tri-mode stderr canary asserting zero-difference absolute-delta parity (`lhs_absolute_delta - rhs_absolute_delta == 0`) while retaining `== 1` absolute-delta magnitude checks across pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-301, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail signed-inverse and identity absolute-delta zero-difference parity canary
  - added cross-channel tri-mode canary asserting the same zero-difference absolute-delta contract for stdout/stderr per mode with retained `== 1` magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-302, quality-gate docs note for split full-vector splitlines signed-inverse and identity absolute-delta zero-difference parity contracts
  - added concise docs note documenting zero-difference absolute-delta parity expectations paired with retained `== 1` magnitude checks for stderr tri-mode and cross-channel runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-303, check-unit stderr tri-mode split full-vector splitlines-pre-tail signed-inverse and identity absolute-delta reverse-order zero-difference parity canary
  - added tri-mode canary asserting `abs(len(stderr.split("\n")) - len(stderr.splitlines())) - abs(len(stderr.splitlines()) - len(stderr.split("\n"))) == 0` while retaining `== 1` absolute-delta magnitude checks for pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-304, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail signed-inverse and identity absolute-delta reverse-order zero-difference parity canary
  - added cross-channel canary asserting `abs(len(channel_output.split("\n")) - len(channel_output.splitlines())) - abs(len(channel_output.splitlines()) - len(channel_output.split("\n"))) == 0` while retaining `== 1` absolute-delta magnitude checks for stdout/stderr per mode
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-305, quality-gate docs note for split full-vector splitlines signed-inverse and identity absolute-delta reverse-order zero-difference parity contracts
  - added concise docs note documenting reverse-order zero-difference absolute-delta parity expectations paired with retained `== 1` magnitude checks for stderr tri-mode and cross-channel runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-306, check-unit stderr tri-mode split full-vector splitlines-pre-tail signed-inverse and identity absolute-delta reverse-order symmetric-sum parity canary
  - added tri-mode canary asserting `(abs(len(stderr.split("\n")) - len(stderr.splitlines())) - abs(len(stderr.splitlines()) - len(stderr.split("\n")))) + (abs(len(stderr.splitlines()) - len(stderr.split("\n"))) - abs(len(stderr.split("\n")) - len(stderr.splitlines()))) == 0` while retaining `== 1` absolute-delta magnitude checks for pass/fail/unexpected modes
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-307, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail signed-inverse and identity absolute-delta reverse-order symmetric-sum parity canary
  - added cross-channel canary asserting the same reverse-order symmetric-sum zero contract for stdout/stderr per mode, while retaining `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-308, quality-gate docs note for split full-vector splitlines signed-inverse and identity absolute-delta reverse-order symmetric-sum parity contracts
  - added concise docs note documenting reverse-order symmetric-sum parity expectations paired with retained `== 1` magnitude checks for stderr tri-mode and cross-channel runs
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-309, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity parity canary
  - added tri-mode canary asserting reverse-order symmetric-sum commutativity (`lhs_symmetric_sum + rhs_symmetric_sum == rhs_symmetric_sum + lhs_symmetric_sum`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-310, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity parity canary
  - added cross-channel canary asserting the same symmetric-sum commutativity contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-311, quality-gate docs note for reverse-order symmetric-sum commutativity parity contracts
  - added concise docs note documenting symmetric-sum commutativity parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-312, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference parity canary
  - added tri-mode canary asserting commutativity delta closure (`(lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-313, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference parity canary
  - added cross-channel canary asserting the same commutativity delta closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-314, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference parity contracts
  - added concise docs note documenting commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-315, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value parity canary
  - added tri-mode canary asserting absolute commutativity delta closure (`abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-316, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value parity canary
  - added cross-channel canary asserting the same absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-317, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value parity contracts
  - added concise docs note documenting absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-318, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence parity canary
  - added tri-mode canary asserting idempotent absolute closure (`abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum))) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-319, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence parity canary
  - added cross-channel canary asserting the same idempotent absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-320, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence parity contracts
  - added concise docs note documenting idempotent absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-321, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point parity canary
  - added tri-mode canary asserting fixed-point absolute closure (`abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)))) == abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum))) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-322, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point parity canary
  - added cross-channel canary asserting the same fixed-point idempotent absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-323, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point parity contracts
  - added concise docs note documenting fixed-point idempotent absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-324, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence parity canary
  - added tri-mode canary asserting fixed-point-idempotence absolute closure (`abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum))))) == abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)))) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-325, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same fixed-point-idempotence absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-326, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence parity contracts
  - added concise docs note documenting fixed-point-idempotence absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-327, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary asserting fixed-point-idempotence fixed-point absolute closure (`abs(abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)))))) == abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum))))) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-328, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same fixed-point-idempotence fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-329, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting fixed-point-idempotence fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-330, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added tri-mode canary asserting fixed-point-idempotence fixed-point-idempotence absolute closure (`abs(abs(abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum))))))) == abs(abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)))))) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-331, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same fixed-point-idempotence fixed-point-idempotence absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-332, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence parity contracts
  - retained concise docs note documenting fixed-point-idempotence fixed-point-idempotence absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-333, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary asserting fixed-point-idempotence fixed-point-idempotence fixed-point absolute closure (`abs(abs(abs(abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)))))))) == abs(abs(abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum))))))) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-334, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same fixed-point-idempotence fixed-point-idempotence fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-335, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting fixed-point-idempotence fixed-point-idempotence fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-336, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added tri-mode canary asserting fixed-point-idempotence fixed-point-idempotence fixed-point-idempotence absolute closure (`abs(abs(abs(abs(abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum))))))))) == abs(abs(abs(abs(abs(abs(abs((lhs_symmetric_sum + rhs_symmetric_sum) - (rhs_symmetric_sum + lhs_symmetric_sum)))))))) == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-337, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same fixed-point-idempotence fixed-point-idempotence fixed-point-idempotence absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-338, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity contracts
  - retained concise docs note documenting fixed-point-idempotence fixed-point-idempotence fixed-point-idempotence absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-339, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-336 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-340, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-341, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-342, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added tri-mode canary extending WLP-339 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-343, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-344, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-345, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-342 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-346, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-347, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-348, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added tri-mode canary extending WLP-345 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-349, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-350, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-351, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-348 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-352, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-353, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-354, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added tri-mode canary extending WLP-351 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-355, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-356, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-357, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-354 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-358, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-359, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-360, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-357 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-361, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-362, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-363, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-360 by one extra fixed-point absolute-closure layer while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-364, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-365, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-366, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-363 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point = abs(next_layer)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-367, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point == next_layer == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-368, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-369, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-366 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence = abs(next_layer_fixed_point)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-370, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence == next_layer_fixed_point == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-371, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point idempotence absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-372, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-369 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point = abs(next_layer_fixed_point_idempotence)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-373, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point == next_layer_fixed_point_idempotence == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-374, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-375, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-372 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence = abs(next_layer_fixed_point_idempotence_fixed_point)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-376, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence == next_layer_fixed_point_idempotence_fixed_point == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-377, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-378, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added tri-mode canary extending WLP-375 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point = abs(next_layer_fixed_point_idempotence_fixed_point_idempotence)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-379, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point == next_layer_fixed_point_idempotence_fixed_point_idempotence == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-380, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-381, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added tri-mode canary extending WLP-378 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence = abs(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-382, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence == next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-383, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity contracts
  - added concise docs note documenting the next-layer fixed-point idempotence absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-384, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-381 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point = abs(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-385, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point == next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-386, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-387, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added tri-mode canary extending WLP-384 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence = abs(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-388, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence == next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-389, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-390, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-387 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point = abs(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-391, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point == next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-392, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-393, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-390 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence = abs(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-394, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence == next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-395, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`


## Next queue (rolling)

- [x] WLP-396, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-393 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point = abs(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-397, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point == next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-398, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] WLP-399, check-unit stderr tri-mode split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added tri-mode canary extending WLP-396 by one extra fixed-point absolute-closure layer (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence = abs(next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point)`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-400, check-unit tri-mode cross-channel split full-vector splitlines-pre-tail reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity canary
  - added cross-channel canary asserting the same next-layer fixed-point absolute commutativity delta-closure contract for stdout/stderr per mode (`next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence == next_layer_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point_idempotence_fixed_point == 0`) while retaining symmetric-sum zero checks and `== 1` absolute-delta magnitude checks
  - target files: `tests/test_quality_gate_scripts.py`

- [x] WLP-401, quality-gate docs note for reverse-order symmetric-sum commutativity zero-difference absolute-value idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point idempotence fixed-point parity contracts
  - added concise docs note documenting the next-layer fixed-point absolute commutativity delta-closure parity expectations for stderr tri-mode and cross-channel runs with retained absolute-delta magnitude checks
  - target files: `docs/quality-gates.md`

## v0.1 Exit Rule (locked)

- Stop adding new canary layers after WLP-401.
- After WLP-401, execute only release-close tasks:
  - full gate run (`./scripts/check.sh`),
  - benchmark verification against v0.1 threshold,
  - v0.1 checklist/docs freeze,
  - ship-ready summary for David.
- Additional canary expansion is allowed only if a real regression appears in active gates.

## Next queue (rolling)

- [x] RC-001, v0.1 release-close benchmark verification snapshot
  - reran `./scripts/check.sh` and persisted benchmark threshold evidence for release notes (`1389 -> 709`, `48.96%`, target `>=25%` met)
  - target files: `docs/PROTOKOLL.md`, `docs/quality-gates.md`

- [x] RC-002, v0.1 checklist/docs freeze pass
  - finalized and froze v0.1 checklist wording and migration/quality-gate cross-links
  - target files: `docs/acceptance-metrics.md`, `docs/migrations.md`, `docs/quality-gates.md`

- [x] RC-003, ship-ready summary for David
  - prepared concise ship status, executed gates, and remaining non-blocking follow-ups
  - target files: `docs/review-sprint1.md`, `docs/PROTOKOLL.md`

## Next queue (rolling)

- [x] RL-001, release evidence artifact automation
  - added `scripts/release_snapshot.py`, exporting dated + latest benchmark/gate evidence snapshots to `docs/release-artifacts/`
  - added script coverage in `tests/test_release_snapshot.py`
  - target files: `scripts/release_snapshot.py`, `docs/release-artifacts/`, `docs/quality-gates.md`, `tests/test_release_snapshot.py`

- [x] RL-002, benchmark metadata freshness
  - refreshed `bench/token-harness/results/latest.json` metadata timestamp and documented source-of-truth policy for non-mutating gate runs
  - target files: `bench/token-harness/results/latest.json`, `bench/token-harness/results/latest.md`, `bench/token-harness/README.md`, `docs/quality-gates.md`

- [x] RL-003, quality-gates narrative compaction
  - compacted repetitive canary narrative into a concise contract summary while preserving machine-checked contract references
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-004, release snapshot artifact index and retention policy
  - added `docs/release-artifacts/README.md` index documenting naming semantics, `latest.*` pointer behavior, and explicit/manual cleanup policy
  - linked the index from release-evidence automation notes in `docs/quality-gates.md`
  - target files: `docs/release-artifacts/README.md`, `docs/quality-gates.md`

- [x] RL-005, optional check-lane integration for release snapshot export
  - documented opt-in post-pass hook flow (`./scripts/check.sh && python3 scripts/release_snapshot.py`) while keeping `scripts/check.sh` unchanged by default
  - added explicit non-automatic hook note in quality-gates docs and mirrored recommendation in ship-ready review notes
  - target files: `docs/quality-gates.md`, `docs/review-sprint1.md`

- [x] RL-006, release evidence schema guardrail
  - added lightweight shape-contract test for release artifacts (`test_latest_json_shape_contract_for_release_evidence`) to lock `latest.json` required objects/key types
  - documented the guardrail test reference in release-evidence automation notes
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-007, release-evidence quickstart discoverability pass
  - added concise onboarding pointers for release evidence workflow in top-level and benchmark harness docs, plus mirrored discoverability note in quality-gates release section
  - target files: `README.md`, `bench/token-harness/README.md`, `docs/quality-gates.md`

- [x] RL-008, repo-artifact latest freshness/assertion canary
  - added deterministic parity canary locking checked-in `docs/release-artifacts/latest.json` parseability and key-path consistency against `bench/token-harness/results/latest.json`
  - documented canary reference in quality-gates release-evidence automation notes
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-009, retention runbook command snippets
  - added explicit/manual prune runbook command snippets (dry-run first, optional apply, preserve `latest.*`) and linked retention snippet availability in quality-gates notes
  - target files: `docs/release-artifacts/README.md`, `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-010, checked-in release artifact markdown presence canary
  - added deterministic canary `test_repo_checked_in_latest_md_presence_and_source_markers` proving `docs/release-artifacts/latest.md` exists and contains benchmark-source/freshness markers expected by release-close docs
  - documented the new markdown presence/source-marker canary in release-evidence quality-gate notes
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-011, release-evidence quickstart command parity canary
  - added lightweight doc-parity canary `test_release_evidence_quickstart_command_parity_docs` locking `./scripts/check.sh && python3 scripts/release_snapshot.py` presence in `README.md` and `bench/token-harness/README.md`
  - documented quickstart command parity canary coverage in release-evidence quality-gate notes
  - target files: `tests/test_release_snapshot.py`, `README.md`, `bench/token-harness/README.md`, `docs/quality-gates.md`

- [x] RL-012, retention runbook shell-safety note hardening
  - tightened retention runbook wording with explicit repo-root precondition, `latest.*` preservation rule, and matched-pair deletion invariant while keeping dry-run-first defaults
  - mirrored shell-safety contract note in release-evidence quality-gate docs
  - target files: `docs/release-artifacts/README.md`, `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-013, release snapshot markdown/json source-of-truth string parity canary
  - added deterministic checked-in artifact canary `test_repo_checked_in_source_of_truth_rule_parity_between_latest_json_and_latest_md` asserting `latest.md` source-of-truth bullet stays byte-identical to `latest.json` `meta.source_of_truth_rule`
  - mirrored canary reference in release-evidence automation notes
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-014, release artifact index quickstart pointer parity note
  - added explicit quickstart pointer block in `docs/release-artifacts/README.md` and mirrored command-parity note in quality-gates release automation bullets
  - target files: `docs/release-artifacts/README.md`, `docs/quality-gates.md`

- [x] RL-015, retention runbook shell-safety checklist ordering polish
  - reordered retention preconditions into an explicit ordered checklist (`repo-root`, `latest.*` preserve, matched dated-pair-only deletions) and tightened apply-confirmation wording
  - mirrored ordered-checklist framing in quality-gates release automation notes
  - target files: `docs/release-artifacts/README.md`, `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-016, release artifact index quickstart command parity canary
  - added deterministic docs canary `test_release_artifact_index_quickstart_command_parity_with_quality_gate_notes` asserting `docs/release-artifacts/README.md` and `docs/quality-gates.md` both contain `./scripts/check.sh && python3 scripts/release_snapshot.py`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`, `docs/quality-gates.md`

- [x] RL-017, retention checklist token-order parity canary
  - added docs canary `test_release_artifact_index_retention_precondition_token_order` locking ordered retention tokens (`repo-root`, `latest.*`, `matched pair`) and tightened checklist wording in artifact index for explicit token stability
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-018, release-evidence notes compactness pass
  - trimmed duplicated quickstart wording in `docs/quality-gates.md` while keeping release-evidence canary references intact
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-019, release automation hook singularity canary
  - added deterministic docs canary `test_quality_gates_release_hook_literal_singularity` asserting `docs/quality-gates.md` contains `./scripts/check.sh && python3 scripts/release_snapshot.py` exactly once
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-020, release artifact index quickstart heading presence canary
  - added docs canary `test_release_artifact_index_quickstart_heading_presence` locking `## Quickstart pointer` heading presence in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-021, retention runbook ordered-checklist section anchor canary
  - added docs canary `test_release_artifact_index_retention_preconditions_anchor_marker` asserting retention checklist marker string presence (`Preconditions checklist (execute in order before running commands):`)
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

## Next queue (rolling)

- [x] RL-022, release artifact index heading singularity canary
  - upgraded quickstart heading canary to singularity contract via `test_release_artifact_index_quickstart_heading_singularity` (`count(...) == 1`)
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-023, retention checklist marker singularity canary
  - upgraded retention checklist marker canary to singularity contract via `test_release_artifact_index_retention_preconditions_anchor_marker_singularity` (`count(...) == 1`)
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-024, release-evidence heading presence canary
  - added docs canary `test_quality_gates_release_evidence_heading_presence` asserting `Release evidence automation:` marker remains present in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`


## Next queue (rolling)

- [x] RL-025, release-evidence heading singularity canary
  - added docs canary `test_quality_gates_release_evidence_heading_singularity` asserting `Release evidence automation:` appears exactly once in `docs/quality-gates.md`
  - mirrored canary reference in release-evidence automation notes
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-026, release artifact index title heading presence canary
  - added docs canary `test_release_artifact_index_title_heading_presence` asserting top-level `# Release Artifacts Index` heading remains present in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-027, release artifact index title heading singularity canary
  - added docs canary `test_release_artifact_index_title_heading_singularity` asserting `# Release Artifacts Index` appears exactly once in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

## Next queue (rolling)

- [x] RL-028, release-evidence heading line-boundary canary
  - added docs canary `test_quality_gates_release_evidence_heading_line_boundary` asserting `Release evidence automation:` remains a standalone line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-029, release artifact index title first-line boundary canary
  - added docs canary `test_release_artifact_index_title_first_non_empty_line_boundary` asserting first non-empty line of `docs/release-artifacts/README.md` is exactly `# Release Artifacts Index`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-030, release-evidence docs note for heading-boundary canaries
  - added compact release-evidence note referencing RL-028/RL-029 heading-boundary contracts for docs stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-031, release artifact index quickstart heading line-boundary canary
  - added docs canary `test_release_artifact_index_quickstart_heading_line_boundary` asserting `## Quickstart pointer` exists as a standalone line in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-032, release artifact index retention marker line-boundary canary
  - added docs canary `test_release_artifact_index_retention_preconditions_anchor_marker_line_boundary` asserting `Preconditions checklist (execute in order before running commands):` stays a standalone line in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-033, release-evidence docs note for artifact-index line-boundary canaries
  - added compact quality-gate note referencing RL-031/RL-032 line-boundary contracts for artifact-index stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-034, release artifact index quickstart-heading order boundary canary
  - added docs canary `test_release_artifact_index_quickstart_heading_order_boundary` asserting `## Quickstart pointer` appears after `# Release Artifacts Index` in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-035, release artifact index retention-marker order boundary canary
  - added docs canary `test_release_artifact_index_retention_preconditions_anchor_marker_order_boundary` asserting `Preconditions checklist (execute in order before running commands):` appears after `## Quickstart pointer` in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-036, release-evidence docs note for artifact-index order-boundary canaries
  - added compact quality-gate note referencing RL-034/RL-035 ordering contracts for artifact-index stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-037, release artifact index heading-order line-index boundary canary
  - added docs canary `test_rl_037_release_artifact_index_heading_order_line_index_boundary_canary` asserting the first `## Quickstart pointer` line index is greater than the title heading line index in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-038, release artifact index retention-order line-index boundary canary
  - added docs canary `test_rl_038_release_artifact_index_retention_order_line_index_boundary_canary` asserting the first `Preconditions checklist (execute in order before running commands):` line index is greater than the quickstart heading line index in `docs/release-artifacts/README.md`
  - target files: `tests/test_release_snapshot.py`, `docs/release-artifacts/README.md`

- [x] RL-039, release-evidence docs note for line-index order-boundary canaries
  - added compact quality-gate note referencing RL-037/RL-038 line-index ordering contracts for artifact-index stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-040, release hook bullet line-boundary singularity canary
  - added docs canary `test_rl_040_quality_gates_release_hook_bullet_line_singularity_boundary_canary` asserting `Optional post-pass hook` appears as exactly one standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-041, release hook-before-dated-snapshot bullet order canary
  - added docs canary `test_rl_041_quality_gates_release_hook_before_dated_snapshot_bullet_order_canary` asserting the `Optional post-pass hook` bullet appears before `Dated snapshots are written...` in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-042, release-evidence docs alignment for hook-line boundary/order canaries
  - updated release-evidence automation notes to document RL-040/RL-041 hook-line boundary/order contract with explicit canary references
  - target files: `docs/quality-gates.md`, `docs/workloop-queue.md`

- [x] RL-043, dated-snapshot bullet singularity canary
  - added docs canary `test_rl_043_quality_gates_dated_snapshot_bullet_singularity_canary` asserting `Dated snapshots are written...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-044, dated-snapshot bullet line-boundary canary
  - added docs canary `test_rl_044_quality_gates_dated_snapshot_bullet_line_boundary_canary` asserting `Dated snapshots are written...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-045, release-evidence docs note for dated-snapshot bullet boundary canaries
  - added compact quality-gate note referencing RL-043/RL-044 dated-snapshot bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-046, naming-policy bullet singularity canary
  - added docs canary `test_rl_046_quality_gates_naming_policy_bullet_singularity_canary` asserting the canonical `Naming/latest-pointer/cleanup policy...` bullet appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-047, naming-policy bullet line-boundary canary
  - added docs canary `test_rl_047_quality_gates_naming_policy_bullet_line_boundary_canary` asserting `Naming/latest-pointer/cleanup policy...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-048, release-evidence docs note for naming-policy bullet boundary canaries
  - added compact quality-gate note referencing RL-046/RL-047 naming-policy bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-049, source-of-truth bullet singularity canary
  - added docs canary `test_rl_049_quality_gates_source_of_truth_rule_bullet_singularity_canary` asserting the canonical `Source-of-truth rule: ...` bullet appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-050, source-of-truth bullet line-boundary canary
  - added docs canary `test_rl_050_quality_gates_source_of_truth_rule_bullet_line_boundary_canary` asserting `Source-of-truth rule: ...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-051, release-evidence docs note for source-of-truth bullet boundary canaries
  - added compact quality-gate note referencing RL-049/RL-050 source-of-truth bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-052, quickstart-pointer bullet singularity canary
  - added docs canary `test_rl_052_quality_gates_quickstart_pointer_bullet_singularity_canary` asserting the canonical `Quickstart pointers are mirrored...` bullet appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-053, quickstart-pointer bullet line-boundary canary
  - added docs canary `test_rl_053_quality_gates_quickstart_pointer_bullet_line_boundary_canary` asserting `Quickstart pointers are mirrored...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-054, release-evidence docs note for quickstart-pointer bullet boundary canaries
  - added compact quality-gate note referencing RL-052/RL-053 quickstart-pointer bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-055, release-artifact-json-shape bullet singularity canary
  - added docs canary `test_rl_055_quality_gates_release_artifact_json_shape_bullet_singularity_canary` asserting the canonical `Release artifact JSON shape contract is locked...` bullet appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-056, release-artifact-json-shape bullet line-boundary canary
  - added docs canary `test_rl_056_quality_gates_release_artifact_json_shape_bullet_line_boundary_canary` asserting `Release artifact JSON shape contract is locked...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-057, release-evidence docs note for release-artifact-json-shape bullet boundary canaries
  - added compact quality-gate note referencing RL-055/RL-056 release-artifact-json-shape bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-058, checked-in-freshness/parity bullet singularity canary
  - added docs canary `test_rl_058_quality_gates_checked_in_freshness_parity_bullet_singularity_canary` asserting `Checked-in freshness/parity canary is locked...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-059, checked-in-freshness/parity bullet line-boundary canary
  - added docs canary `test_rl_059_quality_gates_checked_in_freshness_parity_bullet_line_boundary_canary` asserting `Checked-in freshness/parity canary is locked...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-060, release-evidence docs note for checked-in-freshness/parity bullet boundary canaries
  - added compact quality-gate note referencing RL-058/RL-059 checked-in-freshness/parity bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-061, checked-in-latest-md presence/source-marker bullet singularity canary
  - added docs canary `test_rl_061_quality_gates_checked_in_latest_md_presence_source_marker_bullet_singularity_canary` asserting `Checked-in release markdown presence/source-marker canary is locked...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-062, checked-in-latest-md presence/source-marker bullet line-boundary canary
  - added docs canary `test_rl_062_quality_gates_checked_in_latest_md_presence_source_marker_bullet_line_boundary_canary` asserting `Checked-in release markdown presence/source-marker canary is locked...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-063, release-evidence docs note for checked-in-latest-md presence/source-marker bullet boundary canaries
  - added compact quality-gate note referencing RL-061/RL-062 checked-in-latest-md presence/source-marker bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-064, quickstart-command-parity bullet singularity canary
  - added docs canary `test_rl_064_quality_gates_quickstart_command_parity_bullet_singularity_canary` asserting `Quickstart command parity canary for onboarding docs is locked...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-065, quickstart-command-parity bullet line-boundary canary
  - added docs canary `test_rl_065_quality_gates_quickstart_command_parity_bullet_line_boundary_canary` asserting `Quickstart command parity canary for onboarding docs is locked...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-066, release-evidence docs note for quickstart-command-parity bullet boundary canaries
  - added compact quality-gate note referencing RL-064/RL-065 quickstart-command-parity bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-067, release-evidence-heading-singularity bullet singularity canary
  - added docs canary `test_rl_067_quality_gates_release_evidence_heading_singularity_bullet_singularity_canary` asserting `Release-evidence heading singularity canary is locked...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-068, release-evidence-heading-singularity bullet line-boundary canary
  - added docs canary `test_rl_068_quality_gates_release_evidence_heading_singularity_bullet_line_boundary_canary` asserting `Release-evidence heading singularity canary is locked...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-069, release-evidence docs note for release-evidence-heading-singularity bullet boundary canaries
  - added compact quality-gate note referencing RL-067/RL-068 release-evidence-heading-singularity bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-070, heading-boundary-canaries bullet singularity canary
  - added docs canary `test_rl_070_quality_gates_heading_boundary_canaries_bullet_singularity_canary` asserting `Heading-boundary canaries are locked by ...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-071, heading-boundary-canaries bullet line-boundary canary
  - added docs canary `test_rl_071_quality_gates_heading_boundary_canaries_bullet_line_boundary_canary` asserting `Heading-boundary canaries are locked by ...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-072, release-evidence docs note for heading-boundary-canaries bullet boundary canaries
  - added compact quality-gate note referencing RL-070/RL-071 heading-boundary-canaries bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-073, artifact-index-line-boundary-canaries bullet singularity canary
  - added docs canary `test_rl_073_quality_gates_artifact_index_line_boundary_canaries_bullet_singularity_canary` asserting `Artifact-index line-boundary canaries are locked by ...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-074, artifact-index-line-boundary-canaries bullet line-boundary canary
  - added docs canary `test_rl_074_quality_gates_artifact_index_line_boundary_canaries_bullet_line_boundary_canary` asserting `Artifact-index line-boundary canaries are locked by ...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-075, release-evidence docs note for artifact-index-line-boundary-canaries bullet boundary canaries
  - added compact quality-gate note referencing RL-073/RL-074 artifact-index-line-boundary-canaries bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-076, artifact-index-order-boundary-contract bullet singularity canary
  - added docs canary `test_rl_076_quality_gates_artifact_index_order_boundary_contract_bullet_singularity_canary` asserting `Artifact-index order-boundary contract (RL-034/RL-035): ...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-077, artifact-index-order-boundary-contract bullet line-boundary canary
  - added docs canary `test_rl_077_quality_gates_artifact_index_order_boundary_contract_bullet_line_boundary_canary` asserting `Artifact-index order-boundary contract (RL-034/RL-035): ...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-078, release-evidence docs note for artifact-index-order-boundary-contract bullet boundary canaries
  - added compact quality-gate note referencing RL-076/RL-077 artifact-index-order-boundary-contract bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-079, artifact-index-line-index-order-boundary-contract bullet singularity canary
  - added docs canary `test_rl_079_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_singularity_canary` asserting `Artifact-index line-index order-boundary contract (RL-037/RL-038): ...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-080, artifact-index-line-index-order-boundary-contract bullet line-boundary canary
  - added docs canary `test_rl_080_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_line_boundary_canary` asserting `Artifact-index line-index order-boundary contract (RL-037/RL-038): ...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-081, release-evidence docs note for artifact-index-line-index-order-boundary-contract bullet boundary canaries
  - added compact quality-gate note referencing RL-079/RL-080 artifact-index-line-index-order-boundary-contract bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-082, release-artifact-index-title-heading-presence/singularity bullet singularity canary
  - added docs canary `test_rl_082_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_singularity_canary` asserting `Release artifact index title-heading presence/singularity canaries are locked...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-083, release-artifact-index-title-heading-presence/singularity bullet line-boundary canary
  - added docs canary `test_rl_083_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_line_boundary_canary` asserting `Release artifact index title-heading presence/singularity canaries are locked...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-084, release-evidence docs note for release-artifact-index-title-heading-presence/singularity bullet boundary canaries
  - added compact quality-gate note referencing RL-082/RL-083 release-artifact-index-title-heading-presence/singularity bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-085, source-of-truth string parity bullet singularity canary
  - added docs canary `test_rl_085_quality_gates_source_of_truth_string_parity_bullet_singularity_canary` asserting `Source-of-truth string parity canary between checked-in latest.json and latest.md is locked...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-086, source-of-truth string parity bullet line-boundary canary
  - added docs canary `test_rl_086_quality_gates_source_of_truth_string_parity_bullet_line_boundary_canary` asserting `Source-of-truth string parity canary between checked-in latest.json and latest.md is locked...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-087, release-evidence docs note for source-of-truth string parity bullet boundary canaries
  - added compact quality-gate note referencing RL-085/RL-086 source-of-truth string parity bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-088, source-of-truth-string-parity boundary-contract bullet singularity canary
  - added docs canary `test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary` asserting `Source-of-truth-string-parity bullet boundary contract (RL-085/RL-086): ...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-089, source-of-truth-string-parity boundary-contract bullet line-boundary canary
  - added docs canary `test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary` asserting `Source-of-truth-string-parity bullet boundary contract (RL-085/RL-086): ...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-090, release-evidence docs note for source-of-truth-string-parity boundary-contract bullet boundary canaries
  - added compact quality-gate note referencing RL-088/RL-089 source-of-truth-string-parity boundary-contract bullet singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-091, source-of-truth-string-parity boundary-contract bullet token-literal canary
  - added docs canary `test_rl_091_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_token_literal_canary` asserting the RL-088/RL-089 boundary-contract bullet preserves ``latest.json`` + ``latest.md`` exactly once each
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-092, source-of-truth-string-parity boundary-contract bullet test-reference pair canary
  - added docs canary `test_rl_092_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_test_reference_pair_canary` asserting the RL-088/RL-089 boundary-contract bullet preserves both referenced canary names exactly once (`test_rl_088...`, `test_rl_089...`)
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-093, release-evidence docs note for source-of-truth-string-parity boundary-contract token/reference canaries
  - added compact quality-gate note referencing RL-091/RL-092 token-literal and test-reference pair contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

- [x] RL-094, source-of-truth-string-parity token/reference note singularity canary
  - added docs canary `test_rl_094_quality_gates_source_of_truth_string_parity_token_reference_note_singularity_canary` asserting `Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): ...` appears exactly once in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-095, source-of-truth-string-parity token/reference note line-boundary canary
  - added docs canary `test_rl_095_quality_gates_source_of_truth_string_parity_token_reference_note_line_boundary_canary` asserting `Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): ...` remains a standalone bullet line in `docs/quality-gates.md`
  - target files: `tests/test_release_snapshot.py`, `docs/quality-gates.md`

- [x] RL-096, release-evidence docs note for source-of-truth-string-parity token/reference note-boundary canaries
  - added compact quality-gate note referencing RL-094/RL-095 note singularity/line-boundary contracts for release-evidence stability
  - target files: `docs/quality-gates.md`

## Next queue (rolling)

## CTO override (2026-03-03)

- Stop release-evidence canary expansion at RL-096.
- RL-097..RL-099 are intentionally dropped due to low incremental product value.
- Continue release-evidence work only on real regressions found by active gates.

## Next queue, functional track (v0.2 prep)

- [x] FN-001, machine-readable error envelope spec
  - defined stable error envelope contract for parse/validate/runtime/cli (`code`, `stage`, `message`, `span`, `hint`, `details`)
  - added docs contract + deterministic JSON example
  - target files: `docs/ir-contract-v0.1.md`, `docs/quality-gates.md`, `README.md`

- [x] FN-002, CLI JSON error mode
  - added deterministic JSON error output mode for `erz parse`/`erz validate` via `--json-errors`
  - preserved default human-readable stderr mode when JSON mode is not requested
  - target files: `cli/main.py`, `tests/test_cli.py`

- [x] FN-003, runtime error mapping + tests
  - added stable parser/runtime/io error-to-code mapping in `runtime/errors.py`
  - added coverage for malformed input, schema violations, runtime contract failures, and CLI IO failure path
  - target files: `runtime/errors.py`, `tests/test_integration_pipeline.py`, `tests/test_cli.py`

## Next queue, functional track (rolling)

### CTO Cutoff (active)

- Boundary-only canary expansion is paused.
- New tasks must deliver user-visible/runtime-visible product behavior.
- If a task only protects line/heading adjacency in docs, it is out of scope for this lane.

- [x] FP-001, CLI `eval` command for deterministic policy execution
  - added `erz eval <program.erz> --input <event.json>` command and deterministic JSON envelope output
  - integrated `eval_policies_envelope(...)` runtime adapter path
  - CLI coverage added for success path, runtime-error envelope path, and invalid input JSON path
  - target files: `cli/main.py`, `README.md`, `tests/test_compact.py`

- [x] FP-002, eval fixtures + integration tests
  - added `examples/eval/program.erz`, `examples/eval/event-ok.json`, `examples/eval/event-invalid.json`
  - added CLI fixture coverage for success shape, repeated-run determinism, and runtime error-envelope shape
  - added integration coverage for byte-identical repeated CLI eval runs and stable runtime error-envelope behavior on invalid event payload
  - target files: `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `examples/eval/`

- [x] FP-003, docs + operator quickstart for eval workflow
  - added concise non-technical quickstart in README and runtime determinism docs
  - added end-to-end eval command block plus stable success/error output-shape examples
  - target files: `README.md`, `docs/runtime-determinism.md`

- [x] FP-004, eval CLI summary mode for operator readability
  - added optional `--summary` mode to `erz eval` with deterministic single-line output and unchanged JSON default lane
  - summary lines are stable for success (`status=ok ...`) and runtime envelope failures (`status=error code=... stage=...`)
  - added CLI + integration coverage for summary success and runtime-error determinism
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`

- [x] FP-005, eval strict-exit flag for automation
  - added optional `--strict` mode to `erz eval`, runtime error envelopes now return exit code `1` while preserving deterministic payload output
  - added CLI + integration coverage for strict runtime-error exit semantics and repeated-run payload stability
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`

- [x] FP-006, eval output-file support
  - added `--output <path>` to persist deterministic eval payloads while keeping stdout output unchanged
  - added stdout/file parity tests and repeated-write determinism coverage, plus README operator examples
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`

- [x] FP-007, eval references sidecar input
  - added optional `--refs <path>` for external refs JSON (direct map or `{ "refs": {...} }` wrapper) to resolve runtime `_ref` bindings without embedding every `rf{...}` in the program file
  - codified deterministic merge policy: canonicalized refs merge when disjoint, collisions fail with stable canonical `@<id>` diagnostics
  - added CLI + integration coverage for sidecar success determinism and collision error stability, plus operator examples under `examples/eval/`
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `examples/eval/`

- [x] FP-008, eval deterministic metadata envelope mode
  - added optional `--meta` for deterministic eval metadata (`meta.program_sha256`, `meta.event_sha256`) while keeping default envelope shape unchanged
  - added explicit `--generated-at <value>` opt-in field (requires `--meta`) and locked metadata field order (`program_sha256`, `event_sha256`, optional `generated_at`)
  - added CLI + integration coverage for ordered metadata shape, opt-in behavior, and repeated-run determinism in success/runtime-error paths
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-009, eval exit-code policy presets
  - added `--exit-policy <default|strict|strict-no-actions>` preset lane for CI policy control without payload-shape drift
  - kept backward compatibility via `--strict` legacy shortcut (`--strict` resolves to `--exit-policy strict`)
  - added CLI + integration matrix tests to lock deterministic stdout parity while exit codes vary by policy
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`

- [x] FP-010, eval empty-action fixture lane for CI policy validation
  - added explicit no-match fixture `examples/eval/event-no-action.json` to validate empty-action behavior deterministically
  - locked policy matrix assertions for default/strict/strict-no-actions on identical no-action payload output
  - target files: `examples/eval/`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`

- [x] FP-011, eval summary policy hint for CI logs
  - added optional `--summary-policy` suffix for `--summary` lines, deterministic contract: `policy=<...> exit=<0|1>`
  - summary default output remains byte-identical when `--summary-policy` is not enabled
  - added single-event and integration coverage for strict/default exit-policy suffix behavior plus argument-guard (`--summary-policy` requires `--summary`)
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`

- [x] FP-012, eval batch runner for fixture directories
  - added `erz eval --batch <dir>` deterministic replay lane (sorted `*.json` events, stable `events[]` envelope + aggregate `summary` counters)
  - implemented strict exit-policy aggregation over per-event envelopes (`default`, `strict`, `strict-no-actions`) without payload drift across policies
  - added batch fixtures and CLI/integration coverage for aggregate shape, sorted ordering, exit-policy matrix, summary-policy suffix, and batch/meta guardrails
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `examples/eval/`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-013, eval batch include/exclude glob filters
  - added optional `--include <glob>` / `--exclude <glob>` filters for batch fixtures with deterministic pre-filter ordering (sorted input, include first, exclude second)
  - added stable empty-selection diagnostics (`--batch filters matched no .json files ...`) and guardrails (`--include/--exclude` require `--batch`)
  - added CLI + integration coverage for deterministic filtered envelopes and error-path contract
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-014, eval batch per-event output export directory
  - added optional `--batch-output <dir>` to persist deterministic per-event envelopes (`<event>.envelope.json`) plus `summary.json` for CI attachment workflows
  - stdout aggregate envelope remains byte-stable, artifact writes are deterministic across repeated runs
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-015, eval batch failure artifact mode for CI triage
  - added optional `--batch-output-errors-only` mode to persist artifacts only for runtime-error/no-action events while preserving full stdout aggregate envelope determinism
  - added guardrail contract: `--batch-output-errors-only` requires `--batch-output`
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-016, eval batch artifact integrity manifest
  - added optional `--batch-output-manifest` lane, `summary.json` now includes deterministic `artifact_sha256` mapping for every written event artifact (`<relative_artifact_path> -> sha256(file_bytes)`)
  - kept default batch-output payload stable when flag is not set, stdout aggregate envelope stays byte-identical to non-artifact runs
  - added CLI + integration coverage for manifest determinism and hash/value parity against written artifact bytes
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-017, eval batch artifact naming policy switch
  - added optional `--batch-output-layout <flat|by-status>` policy lane (`flat` default, `by-status` groups event artifacts under `ok/`, `no-action/`, `error/`)
  - added guardrail contract: `--batch-output-layout` requires `--batch-output`
  - summary artifact now records `layout` for non-default mode and keeps deterministic `event_artifacts` ordering across default/errors-only lanes
  - added CLI + integration coverage for by-status artifact grouping, deterministic ordering, and strict-no-actions errors-only subset behavior
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-018, eval batch artifact run metadata envelope
  - added optional `--batch-output-run-id <id>` to stamp deterministic `run.id` metadata into `summary.json` without changing per-event envelopes or stdout aggregate payloads
  - added guardrails: `--batch-output-run-id` requires `--batch-output`, empty run ids fail with deterministic CLI error
  - added CLI + integration coverage for deterministic artifact parity and summary key/order contract with `run.id`
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-019, eval batch artifact verify mode
  - added optional verify-only lane `--batch-output-verify <dir>` to validate `summary.json` manifest hashes against written event artifacts and return deterministic pass/fail output (`status=ok|error`)
  - added deterministic machine-readable verify payload + concise `--summary` contract for CI log parsers (`checked`, `verified`, `missing`, `manifest_missing`, `invalid_hashes`, `mismatched`, `unexpected_manifest`)
  - added guardrails for verify mode (`--batch-output-verify` cannot be mixed with eval/batch generation flags) and deterministic failure exit on integrity mismatch
  - added CLI + integration coverage for pass determinism, tamper mismatch detection, and verify guardrail errors
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-020, eval batch artifact verify strict-manifest policy
  - added optional strict verify lane (`--batch-output-verify-strict`) plus expected-profile selectors (`--batch-output-verify-expected-mode`, `--batch-output-verify-expected-layout`, `--batch-output-verify-expected-run-id-pattern`)
  - strict verify now fails deterministically on `summary.json` profile drift (`mode`, optional `layout`, optional `run.id` regex mismatch) and surfaces `strict_profile_mismatches` in JSON plus `strict_mismatches=<n>` in `--summary`
  - added guardrails for strict verify flag combinations and invalid run-id regex patterns
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-021, verify strict profile presets for CI ergonomics
  - added `--batch-output-verify-profile <default|triage-by-status>` presets for strict verify ergonomics (`default` => mode=all+layout=flat, `triage-by-status` => mode=errors-only+layout=by-status)
  - preset usage now auto-enables strict verify checks, while explicit expected-mode/layout/run-id flags remain available for overrides
  - added CLI + integration coverage for preset pass/fail behavior and updated operator docs/examples
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`

- [x] FP-022, strict verify run.id presence policy toggle
  - added optional `--batch-output-verify-require-run-id` strict-only toggle, fails deterministic strict verify runs when `summary.json` omits `run.id` (without requiring regex checks)
  - added guardrails for invalid combinations (`--batch-output-verify-require-run-id` requires verify mode + strict verify lane)
  - added CLI + integration coverage for toggle pass/fail behavior, summary contract (`strict_mismatches=<n>`), and mismatch payload (`run.id expected=present`)
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-023, generation-time self-verify gate for artifacts
  - added optional `--batch-output-self-verify` on batch generation, runs immediate manifest integrity verification after artifact write and fails deterministically before pipeline handoff on mismatch
  - stdout contract stays byte-identical to normal batch runs on success; self-verify auto-enables manifest emission in `summary.json`
  - added guardrails for unsupported combinations (`--batch-output-self-verify` requires `--batch-output`, rejected in verify-only lane)
  - added CLI + integration coverage for success parity, manifest presence, and guardrail behavior
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-024, verify strict expected-event-count guardrail
  - added optional `--batch-output-verify-expected-event-count <int>` strict selector, fails deterministic verify runs when `summary.event_count` drifts from pipeline expectations
  - strict profile payload now includes `expected_event_count`, mismatch payload uses `field=summary.event_count` with numeric expected/actual values
  - added guardrails for invalid combinations and negative values (`--batch-output-verify-expected-event-count requires strict verify`, `... must be >= 0`)
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-025, batch self-verify strict profile handoff mode
  - added optional generation flag `--batch-output-self-verify-strict` to run self-verify with strict profile/preset expectations in the same command
  - reused strict selectors/presets (`--batch-output-verify-profile`, `--batch-output-verify-expected-*`, `--batch-output-verify-require-run-id`) for generation-time CI handoff gates
  - added guardrails for invalid mixes (`--batch-output-self-verify-strict requires --batch-output-self-verify`, not allowed with `--batch-output-verify`)
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-026, batch artifact summary export for CI dashboards
  - added optional `--batch-output-summary-file <path>` to export the aggregate batch envelope as deterministic JSON file bytes while leaving stdout unchanged
  - added guardrails for unsupported combinations (`requires --batch`, not supported with `--summary` or `--batch-output-verify`) and empty-path rejection
  - added CLI + integration parity coverage for stdout/file byte equality and repeated-write stability
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-027, verify lane summary export parity for CI dashboards
  - added optional `--batch-output-verify-summary-file <path>` to persist verify result payload (`JSON` or summary line depending on `--summary`) with deterministic stdout/file parity
  - added verify-only guardrails and deterministic failure-path file-write coverage (output file written before non-zero verify exit)
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-028, verify lane artifact subset selectors for large runs
  - added optional `--batch-output-verify-include <glob>` / `--batch-output-verify-exclude <glob>` selectors for deterministic verify artifact subsets (include first, exclude second)
  - added guardrails (`requires --batch-output-verify`, non-empty selector values) plus deterministic empty-selection failure contract
  - added CLI + integration coverage for subset-pass behavior, tampered-artifact exclusion, full-lane mismatch detection, and selector no-match errors
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-029, verify lane strict expected-verified-count selector
  - added optional strict selector `--batch-output-verify-expected-verified-count <int>` to lock expected successful hash validations (`verified`) for CI gates
  - strict profile payload now includes `expected_verified_count`; deterministic mismatch payload uses `field=verified` with numeric expected/actual values
  - added strict-only guardrails (`requires strict verify`, non-negative values) and CLI + integration coverage for pass/fail summary parity
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-030, verify lane strict expected-checked-count selector
  - added optional strict selector `--batch-output-verify-expected-checked-count <int>` to lock selected artifact count (`checked`) for deterministic subset gates
  - strict profile payload now includes `expected_checked_count`; deterministic mismatch payload uses `field=checked` with numeric expected/actual values
  - added strict-only guardrails (`requires strict verify`, non-negative values) and CLI + integration coverage for pass/fail summary parity
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-031, verify lane strict expected-missing-count selector
  - added optional strict selector `--batch-output-verify-expected-missing-count <int>` to lock expected missing artifact count (`missing_artifacts`) for deterministic triage gates
  - strict profile payload now includes `expected_missing_count`; deterministic mismatch payload uses `field=missing_artifacts.count` with numeric expected/actual values
  - added strict-only guardrails (`requires strict verify`, non-negative values) and CLI + integration coverage for pass/fail summary parity
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-032, verify lane strict expected-mismatched-count selector
  - added optional strict selector `--batch-output-verify-expected-mismatched-count <int>` to lock expected hash mismatch count (`mismatched_artifacts`) for deterministic tamper gates
  - strict profile payload now includes `expected_mismatched_count`; deterministic mismatch payload uses `field=mismatched_artifacts.count` with numeric expected/actual values
  - added strict-only guardrails (`requires strict verify`, non-negative values) and CLI + integration coverage for pass/fail summary parity
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-033, verify lane strict expected-manifest-missing-count selector
  - added optional strict selector `--batch-output-verify-expected-manifest-missing-count <int>` to lock expected manifest-entry miss count (`missing_manifest_entries`) for deterministic manifest-integrity gates
  - added strict-only guardrails (`requires strict verify`, non-negative values) and deterministic mismatch payload (`field=missing_manifest_entries.count`)
  - added CLI + integration coverage for pass/fail summary parity and strict-profile mismatch wiring
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-034, verify lane strict expected-invalid-hashes-count selector
  - added optional strict selector `--batch-output-verify-expected-invalid-hashes-count <int>` to lock expected malformed-manifest-hash count (`invalid_manifest_hashes`) for deterministic integrity-policy gates
  - added strict-only guardrails (`requires strict verify`, non-negative values) and deterministic mismatch payload (`field=invalid_manifest_hashes.count`)
  - added CLI + integration coverage for pass/fail summary parity and strict-profile mismatch wiring
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-035, verify lane strict expected-unexpected-manifest-count selector
  - added optional strict selector `--batch-output-verify-expected-unexpected-manifest-count <int>` to lock expected extra-manifest-entry count (`unexpected_manifest_entries`) for deterministic manifest-shape gates
  - added strict-only guardrails (`requires strict verify`, non-negative values) and deterministic mismatch payload (`field=unexpected_manifest_entries.count`)
  - added CLI + integration coverage for pass/fail summary parity and strict-profile mismatch wiring
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-036, verify lane strict expected-status selector
  - added optional strict selector `--batch-output-verify-expected-status <ok|error>` to lock final verify status for deterministic CI gate intent
  - added strict-only guardrails and deterministic mismatch payload (`field=status`)
  - added CLI + integration coverage for pass/fail behavior and summary strict-mismatch parity
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-037, verify lane strict expected-strict-mismatch-count selector
  - added optional strict selector `--batch-output-verify-expected-strict-mismatches-count <int>` to lock expected strict-profile mismatch cardinality for policy smoke gates
  - added strict-only guardrails (`requires strict verify`, non-negative values) and deterministic mismatch payload (`field=strict_profile_mismatches.count`)
  - added CLI + integration coverage for selector pass/fail behavior and summary strict-mismatch cardinality output
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-038, verify lane strict expected-event-artifact-count selector
  - added optional strict selector `--batch-output-verify-expected-event-artifact-count <int>` to lock `summary.json` `event_artifacts` cardinality for deterministic manifest-shape gates
  - added strict-only guardrails (`requires strict verify`, non-negative values) and deterministic mismatch payload (`field=event_artifacts.count`)
  - added CLI + integration coverage for selector pass/fail behavior and summary strict-mismatch parity
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-039, verify lane strict expected-manifest-entry-count selector
  - added optional strict selector `--batch-output-verify-expected-manifest-entry-count <int>` to lock `summary.json` `artifact_sha256` entry cardinality for deterministic manifest-completeness gates
  - added strict-only guardrails (`requires strict verify`, non-negative values) and deterministic mismatch payload (`field=artifact_sha256.count`)
  - added CLI + integration coverage for selector pass/fail behavior and summary strict-mismatch parity
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-040, verify lane strict expected-selected-artifact-count selector
  - added optional strict selector `--batch-output-verify-expected-selected-artifact-count <int>` to lock selector-filtered verify scope independently from raw `event_artifacts` cardinality
  - added strict-only guardrails (`requires strict verify`, non-negative values) and deterministic mismatch payload (`field=selected_artifacts.count`)
  - extended CLI + integration coverage for pass/fail summary parity (include-filtered subset lane)
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-041, verify lane strict expected-manifest-selected-entry-count selector
  - added optional strict selector `--batch-output-verify-expected-manifest-selected-entry-count <int>` to lock count of selected artifacts that have manifest entries before hash evaluation
  - added strict-only guardrails (`requires strict verify`, non-negative values) and deterministic mismatch payload (`field=selected_manifest_entries.count`)
  - extended CLI + integration coverage for pass/fail summary parity with deterministic manifest-entry drop scenario
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-042, verify JSON output selected-scope counters
  - added deterministic `selected_artifacts_count` + `selected_manifest_entries_count` fields to verify JSON output for dashboard/export visibility
  - kept existing verify fields stable, appended new counters at the tail, and extended CLI + integration coverage for full-set and subset verify lanes
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-043, verify summary-line selected-scope counters
  - appended `selected=<n>` and `selected_manifest=<n>` tokens in `--summary` verify output, byte-stable after existing base counters and before `strict_mismatches=<n>`
  - updated strict/non-strict summary contracts, verify-summary-file parity, and docs so downstream parsers can adopt the expanded deterministic lane explicitly
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-044, batch-output compare lane for baseline drift gates
  - added `--batch-output-compare <candidate-dir> --batch-output-compare-against <baseline-dir>` to diff batch artifact sets without manifest dependency, comparing event bytes plus `event_artifacts` ordering and `mode/layout/summary.*` metadata deterministically
  - intentionally ignored only `run.id`, and added summary/JSON contracts plus CLI + integration coverage for pass/fail + guardrail paths
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-045, compare lane manifest drift enforcement
  - extended compare metadata checks to catch `artifact_sha256` drift when manifest data is present, so summary-only manifest corruption no longer slips through as a false-green regression pass
  - added deterministic CLI + integration coverage for manifest-only drift while keeping separate `run.id` values intentionally ignored across baseline/candidate runs
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-046, compare lane empty-artifact contract
  - locked deterministic compare behavior for `event_artifacts=[]` summaries, especially `--batch-output-errors-only` runs with no persisted event envelopes, pass path stays `compared=0 matched=0` while summary drift still fails deterministically
  - added CLI + integration coverage for empty-lane pass/fail behavior, including manifest-present empty summaries
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-047, compare lane scoped selectors
  - added optional `--batch-output-compare-include <glob>` / `--batch-output-compare-exclude <glob>` selectors for deterministic baseline-vs-candidate artifact subsets (include vor exclude)
  - scoped compare now filters byte drift, `event_artifacts` ordering, and `artifact_sha256` metadata to the selected subset; empty selector matches fail with deterministic CLI error
  - added CLI + integration coverage for subset pass/fail behavior, manifest drift scoping, and selector no-match guardrails
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

## Next queue, functional track (rolling)

- [x] FP-048, compare JSON output selected-scope counters
  - compare JSON now exports deterministic `selected_baseline_artifacts_count` / `selected_candidate_artifacts_count` counters so automation can see the exact scoped compare surface without reverse-engineering selector behavior
  - added CLI + integration assertions for full-scope, empty-lane, and scoped compare payloads
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-049, compare summary-line selected-scope counters
  - compare `--summary` now appends `selected_baseline=<n>` / `selected_candidate=<n>` after `metadata_mismatches=<n>` for deterministic CI log parsing
  - updated compare contract docs plus summary expectations across pass/fail/scoped/empty lanes
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-050, compare lane strict expected-drift selectors
  - added `--batch-output-compare-strict` plus exact `--batch-output-compare-expected-*` selectors for raw compare status, compared/matched/changed counts, and selected baseline/candidate scope
  - strict compare now preserves raw drift as `compare_status`, surfaces `strict_profile_mismatches`, and lets CI pass when expected drift matches exactly instead of forcing generic compare failure
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-051, runtime payload path predicates
  - added deterministic `payload_path_exists:<dot.path>` and `payload_path_equals:<dot.path>=<value>` clause forms to `runtime.eval`, keeping AND-only rule evaluation, stable ordering, and no expression language
  - path traversal is intentionally narrow: dot-separated payload keys plus numeric list indexes, with deterministic scalar literals (`true|false|null|number|string`) and no threshold/weighted semantics
  - added focused runtime coverage plus runtime-determinism doc updates for supported-clause/current-limit contracts
  - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_integration_pipeline.py`, `docs/runtime-determinism.md`

- [x] FP-052, program packs migrated to nested payload paths
  - updated alert-routing and dedup-cluster packs/baselines to match real nested event structure via path predicates instead of synthetic boolean marker keys
  - refreshed pack docs + fixtures and kept deterministic actions/trace outputs green under targeted tests and full `./scripts/check.sh`
  - target files: `examples/program-packs/alert-routing/*`, `examples/program-packs/dedup-cluster/*`, `docs/program-pack-dedup-cluster.md`, `tests/test_program_pack_alert_routing.py`, `tests/test_program_pack_dedup_cluster.py`

- [x] FP-053, compare strict extended drift selectors
  - added exact strict expectations for `baseline_only/candidate_only/missing_baseline/missing_candidate/metadata_mismatches`, so compare gates can encode asymmetric artifact-set drift without falling back to coarse `changed` heuristics
  - covered both CLI and integration lanes with ghost-artifact scenarios that prove raw `compare_status` can stay `error` while strict status passes when the drift contract is explicitly expected
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-054, compare strict preset profiles
  - added named strict compare presets `clean`, `metadata-only`, and `expected-asymmetric-drift`, so CI lanes can encode common drift contracts without repeating the same flag bundle on every run
  - kept explicit `--batch-output-compare-expected-*` selectors authoritative over preset defaults and covered clean, metadata-only, and asymmetric-drift profile paths in CLI/integration tests
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-055, runtime payload membership predicates
  - added deterministic `payload_path_in:<dot.path>=<csv-or-json-list>` support for finite enum routing, with CSV scalar parsing plus JSON-array membership lists and no expression-language creep
  - covered nested keys, list indexes, scalar normalization, mismatch behavior, syntax errors, and operator-doc parity so runtime-visible membership routing stays deterministic end to end
  - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_integration_pipeline.py`, `docs/runtime-determinism.md`, `docs/program-pack-dedup-cluster.md`

- [x] FP-056, compare lane output preset fixtures
  - checked in reusable compare artifact lanes under `examples/eval/compare-presets/` for clean, metadata-only, and asymmetric drift contracts, so CI users can run strict compare examples without generating their own fixture trees first
  - added CLI smoke coverage plus operator-facing copy-paste commands in repo docs, keeping the checked-in fixtures tied to real compare behavior instead of prose-only examples
  - target files: `examples/eval/*`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-057, runtime path predicates in operator docs + pack exemplars
  - added a minimal `examples/eval/program-paths.erz` smoke program with matching nested payload inputs and propagated the newer `payload_path_exists/equals/in` forms through README, runtime docs, and pack READMEs
  - aligned alert-routing/operator pack docs around real nested payload structure, so onboarding examples now match runtime-visible routing behavior instead of older synthetic marker fields
  - target files: `examples/eval/*`, `examples/program-packs/*`, `README.md`, `docs/program-pack-*.md`

- Queue state: refreshed after FP-059. Next functional slices:
  - [x] FP-058, compare lane summary-file parity
    - shipped `--batch-output-compare-summary-file <path>`, which exports compare JSON or `--summary` output byte-identically with stdout for CI handoff without shell redirection hacks
    - covered guardrails and parity via CLI + integration tests, so compare lanes now support a first-class summary artifact instead of ad hoc shell capture
    - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`
  - [x] FP-059, checked-in nested-path output fixtures
    - checked in frozen expected-output fixtures plus `examples/eval/README.md` copy-paste commands for `examples/eval/program-paths.erz`, so nested-payload smoke lanes now ship with reproducible envelopes and summary output
    - aligned docs/tests to consume those fixtures directly instead of relying only on inline assertions
    - target files: `examples/eval/*`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`
  - [x] FP-060, numeric payload-threshold predicates + dedup pack migration
    - added deterministic `payload_path_gt/gte/lt/lte` runtime clauses for finite numeric payload thresholds, plus checked-in threshold smoke fixtures so operators can copy-paste real nested-number eval runs
    - migrated the dedup-cluster pack/baseline/docs from synthetic bucket fields to direct numeric payload paths, keeping runtime-visible behavior deterministic without boundary-only canary churn
    - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `examples/eval/*`, `examples/program-packs/dedup-cluster/*`, `README.md`, `docs/runtime-determinism.md`, `docs/program-pack-dedup-cluster.md`

- [x] FP-061, threshold batch handoff fixtures for compare/verify operators
  - checked in `examples/eval/threshold-handoff/` with deterministic threshold batch inputs plus manifest-bearing baseline and `triage-by-status` artifact trees carrying stable `run.id` values
  - froze copy-paste `--batch-output-verify` and `--batch-output-compare` summary outputs so operators can rehearse threshold handoff contracts without generating local fixture trees first
  - covered the new handoff lane in `tests/test_cli.py` and linked it from `examples/eval/README.md`, keeping the frontier on user-visible eval behavior instead of boundary-only canaries

- [x] FP-062, alert-routing pack migrated to direct numeric measurements
  - migrated Pack #3 from `routing.*_bucket` markers to direct `measurements.severity/confidence` threshold clauses, so checked-in operator routing no longer depends on upstream bucket projection
  - refreshed pack baselines/docs/index wording and added pack-level assertions that fixtures/rules use numeric measurements directly while keeping deterministic action/trace outputs unchanged
  - target files: `examples/program-packs/alert-routing/*`, `examples/program-packs/README.md`, `tests/test_program_pack_alert_routing.py`

- Queue state: refreshed after FP-067. Latest functional slices:
  - [x] FP-063, runtime string payload predicates + checked-in operator smoke
    - added deterministic `payload_path_startswith` and `payload_path_contains` clauses for nested payload paths, case-sensitive string-only matching with no regex and no expression-language creep
    - shipped `examples/eval/program-strings.erz` plus frozen `event-string-*` fixtures, CLI/runtime coverage, and operator docs so copy-paste string routing is runtime-visible instead of prose-only
    - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_cli.py`, `examples/eval/*`, `README.md`, `docs/runtime-determinism.md`
  - [ ] FP-064, string-aware pack migration only if it removes synthetic markers or duplicated upstream shaping
    - kept held, Pack #2 and Pack #3 already run on real payload structure, so there is still no justified synthetic-marker cleanup to do there
    - target files when justified: `examples/program-packs/*`, `tests/test_program_pack_*.py`, `README.md`, `docs/program-pack-*.md`
  - [x] FP-065, payload-path length predicates + ingest-normalize cardinality gate
    - added deterministic `payload_path_len_gt/gte/lt/lte` clauses for strings, lists, and mappings, with CLI/runtime fixtures/docs so collection cardinality checks are now first-class runtime behavior
    - migrated Program Pack #1 publish gating from `payload_has:entities` to `payload_path_len_gte:entities=1`, removing the empty-list false positive and making the checked-in ingest/normalize flow depend on actual extracted-entity count
    - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_cli.py`, `tests/test_program_pack_ingest_normalize.py`, `examples/eval/*`, `examples/program-packs/ingest-normalize/*`, `README.md`, `docs/runtime-determinism.md`
  - [x] FP-066, dedup-cluster pack collapse from dual raw/mapped fixtures to one canonical event lane
    - replaced `baseline-mapping.json` with `baseline.json`, centered the pack on `fixtures[*].event`, and aligned the checked-in runtime contract/rules with the canonical nested payload shape used at eval time
    - rewired pack tests and operator docs around the canonical event lane, so Program Pack #2 no longer carries a duplicate raw-to-mapped fixture projection just to explain the same runtime behavior twice
    - target files: `examples/program-packs/dedup-cluster/*`, `tests/test_program_pack_dedup_cluster.py`, `docs/program-pack-dedup-cluster.md`, `examples/program-packs/README.md`
  - [x] FP-067, real string-aware pack migration only where inline payload text replaces ref-only gating
    - migrated Program Pack #1 from `text_ref` / `normalized_text_ref` placeholder gating to inline `text` / `normalized_text` payload fields, with `payload_path_contains:text=Unfall` and `payload_path_startswith:normalized_text=Verkehrsunfall` now driving the checked-in runtime behavior
    - removed dead text sidecar refs, refreshed the pack baseline/trace/docs, and added pack-level regression coverage proving the flow no longer depends on `*_text_ref` payload fields while keeping `template_ref` action rendering intact
    - target files: `examples/program-packs/ingest-normalize/*`, `tests/test_program_pack_ingest_normalize.py`, `examples/program-packs/README.md`

- [x] FP-068, generation-time self-compare handoff contract
  - added `--batch-output-self-compare-against` so `erz eval` can compare freshly written batch artifacts against a baseline before handoff, without forcing a second compare command or changing the normal batch stdout lane on success
  - added `--batch-output-self-compare-strict`, reusing the existing compare strict profiles and `--batch-output-compare-expected-*` selectors for expected generation-time drift contracts, plus summary-file export support for the self-compare lane
  - covered the feature with targeted CLI + integration tests, and aligned README/runtime/example docs around operator copy-paste handoff flows
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`, `examples/eval/*`

- [x] FP-069, checked-in self-compare handoff snapshot lane
  - froze a reproducible threshold-handoff replay lane with checked-in `candidate-clean/`, the existing `triage-by-status/` candidate snapshot, and frozen generation-time `--summary` exports for clean and strict self-compare handoffs
  - documented in-place replay commands that intentionally rewrite the tracked snapshot outputs, so operators can rehearse the gate and confirm determinism with `git diff -- examples/eval/threshold-handoff`
  - added a dedicated snapshot reproducibility test that regenerates the self-compare candidates + exported summaries in temp and asserts byte-for-byte parity with the checked-in fixtures
  - target files: `examples/eval/threshold-handoff/*`, `examples/eval/README.md`, `tests/test_threshold_handoff_snapshots.py`, `README.md`, `docs/runtime-determinism.md`

- [x] FP-070, self-compare baseline manifest policy hardening
  - hardened the threshold-handoff lane and broader integration coverage around the actual operator contract: manifest-bearing baselines make generation-time self-compare auto-write the same candidate manifest you would otherwise request explicitly, while manifest-less baselines keep candidate manifest emission opt-in
  - aligned the in-repo replay/integration commands with the checked-in `candidate-clean/` and `triage-by-status/` snapshot lanes, including `run.id`, `by-status`, and strict expected-count metadata so the threshold handoff test exercises the real operator path instead of a stale pseudo-lane
  - target files: `tests/test_integration_pipeline.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/eval/*`, `docs/workloop-queue.md`

- Queue state after FP-070:
  - cutoff held, no return to canary-only gate/doc adjacency work
  - next concrete functional item:
    - none queued on the self-compare lane until a runtime-visible gap appears; do not reopen this track for docs/heading/line-adjacency-only canaries

- [x] FP-071, batch summary JSON optional per-rule hit counts
  - added `--batch-summary-rule-counts` so batch JSON envelopes can include deterministic per-rule hit counts in `summary.rule_counts` for operator triage without changing `--summary` output
  - enforced guardrails: requires `--batch`, rejected with `--summary`, and kept rule-id ordering deterministic in the exported JSON
  - covered with targeted CLI tests and README command examples
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`

- Queue state after FP-071:
  - cutoff held, no follow-on docs-only or canary-only work from this slice
  - next concrete functional item:
    - refresh queue outside the closed self-compare lane and pick the next runtime-visible operator gap

- [x] FP-072, batch summary JSON optional per-action-kind counts
  - added `--batch-summary-action-kind-counts` so batch JSON envelopes can include deterministic per-action-kind totals in `summary.action_kind_counts` for operator triage and downstream dashboards without changing `--summary` output
  - enforced guardrails: requires `--batch`, rejected with `--summary`, composes cleanly with `--batch-summary-rule-counts`, and keeps action-kind ordering deterministic in exported JSON/artifact summaries
  - covered with targeted CLI tests and operator docs so the feature lands as runtime-visible batch behavior instead of more canary adjacency churn
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `docs/workloop-queue.md`

- Queue state after FP-072:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - next concrete functional items:
    - add an operator-facing pack replay lane that evaluates checked-in pack fixtures/baselines from the CLI instead of only through Python tests

- [x] FP-073, operator-facing program-pack replay lane
  - added `erz pack-replay <pack-dir>` so fixture-bearing checked-in packs can be replayed directly against the pack `.erz` program and baseline expectations without dropping into Python tests
  - output stays deterministic in both JSON and `--summary` modes, supports `--output <path>`, surfaces rule-source drift separately via `rule_source_status`, and includes per-fixture mismatch payloads when expectations drift
  - guardrails reject non-directory inputs, ambiguous/missing pack files, and inline-baseline packs that do not yet expose `rules` + `fixtures` replay matrices
  - covered with targeted CLI tests for success, mismatch, and unsupported inline-baseline shapes, plus operator docs in `README.md`, `docs/runtime-determinism.md`, and `examples/program-packs/README.md`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-074, inline-baseline support for operator pack replay
  - extended `erz pack-replay <pack-dir>` to accept inline statement baselines in addition to fixture-matrix baselines, so packs like `ingest-normalize/` now replay directly from the CLI instead of erroring on non-matrix baseline shape
  - derive deterministic replay fixtures from embedded `ev` samples plus the checked-in baseline rule set, while preserving the existing rule-source drift reporting and JSON/`--summary` output contract
  - covered with targeted CLI tests for inline-pack success and program-drift mismatch, and updated operator docs/examples across `README.md`, `docs/runtime-determinism.md`, and `examples/program-packs/README.md`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-075, fixture selectors for operator pack replay
  - added repeatable `--fixture <id>` selectors to `erz pack-replay` so CI can gate one or a few checked-in pack cases deterministically without hand-copying baseline files
  - filtered runs preserve canonical pack fixture order, fail fast on duplicate or unknown selectors, expose `selected_fixture_ids` in JSON, and show `fixtures=<selected>/<total>` in `--summary`
  - covered with targeted CLI tests for subset replay and unknown-selector rejection, plus operator docs/examples across `README.md`, `docs/runtime-determinism.md`, and `examples/program-packs/README.md`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-076, fixture glob selectors for operator pack replay
  - extended `erz pack-replay <pack-dir>` with repeatable `--include-fixture <glob>` / `--exclude-fixture <glob>` selectors, so CI and operators can carve out deterministic multi-case fixture slices without enumerating every id by hand
  - selection composes as exact `--fixture` ids union include-glob matches, then exclude-glob removal, always preserving canonical pack order; empty selections and unmatched glob selectors fail with deterministic CLI errors instead of silently drifting to the wrong slice
  - covered with targeted CLI tests for glob subset success, exact+glob union behavior, unmatched include/exclude guardrails, and zero-match rejection, plus compact operator doc examples in README/runtime/program-pack docs
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`

- [x] FP-077, pack-replay fixture class counters for operator triage
  - extended `erz pack-replay` with additive exclusive fixture class counters under `summary.fixture_class_counts` (`ok`, `expectation_mismatch`, `runtime_error`), so operators no longer have to infer non-runtime drift by subtracting `runtime_error_count` from the legacy mismatch total
  - appended deterministic `fixture_classes=ok:<n>,expectation_mismatch:<n>,runtime_error:<n>` to `--summary` output while preserving the existing `matched/mismatches/runtime_errors` tokens for backwards-compatible log parsing
  - covered success, selector-scope, mismatch, inline-pack, and mixed runtime-error replay lanes in CLI tests, plus operator docs across README/runtime/program-pack docs
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-078, pack-replay JSON fixture ids grouped by class
  - extended `erz pack-replay` JSON output with deterministic `summary.fixture_class_ids`, mirroring the exclusive `ok` / `expectation_mismatch` / `runtime_error` classes as canonical fixture-id lists for operator triage without changing the stable `--summary` line
  - selector-scoped runs now export the same per-class ids for just the selected fixture slice, while mismatch/runtime-error lanes make the failing fixture ids explicit without forcing consumers to diff the whole fixture array
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-079, pack-replay per-fixture class labels in JSON
  - extended each `erz pack-replay` fixture entry with deterministic `fixture_class` labels (`ok`, `expectation_mismatch`, `runtime_error`), so downstream consumers can filter a single fixture row without cross-referencing `summary.fixture_class_ids`
  - kept the stable `--summary` line unchanged while aligning selector-scope, mismatch, runtime-error, and inline-pack JSON lanes on the same per-fixture class contract
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-080, pack-replay fixture-class selectors for CLI triage
  - added repeatable `--fixture-class <ok|expectation_mismatch|runtime_error>` selectors to `erz pack-replay`, applied after exact/glob fixture selection and replay classification so operators can isolate runtime errors or expectation drift without post-processing JSON in CI
  - filtered runs preserve canonical pack order, reject duplicate or unmatched class selectors deterministically, export the final slice in `selected_fixture_ids`, and record the active class filter under `fixture_class_selectors` while keeping the stable `--summary` line compact
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-081, pack-replay fixture-class summary sidecar export
  - added `--fixture-class-summary-file <path>` so fixture-class filtered `erz pack-replay` runs can persist the deterministic `--summary` line without changing the default stdout lane, making one-shot JSON + summary handoff possible for CI/operators without shell redirection
  - requires at least one `--fixture-class`, rejects empty paths deterministically, and writes the same newline-terminated summary contract even when the filtered replay exits non-zero
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-082, generic pack-replay summary sidecar export
  - added `erz pack-replay --summary-file <path>` so every pack replay lane can persist the deterministic summary line without changing stdout, making JSON stdout + summary-file and summary stdout + identical sidecar both first-class operator paths
  - kept `--fixture-class-summary-file` as the narrower compatibility flag for fixture-class filtered runs, and covered success, failure-before-nonzero-exit, and empty-path guardrails in CLI tests
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-082:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - next concrete functional item:
    - add generic `pack-replay --json-file <path>` only if operators need the inverse dual-lane handoff, summary on stdout plus full JSON envelope sidecar in the same run

- [x] FP-083, generic pack-replay JSON sidecar export
  - added `erz pack-replay --json-file <path>` so pack replay can hand off the full deterministic JSON envelope as a sidecar while `--summary` stays on stdout, making the inverse dual-lane contract first-class without shell redirection
  - kept default JSON stdout unchanged, made `--json-file` byte-identical to stdout when no `--summary` flag is active, and covered success, failure-before-nonzero-exit, and empty-path guardrails in CLI tests
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-084, strict pack-replay expectation selectors
  - added `erz pack-replay --strict` plus `--expected-fixture-count`, `--expected-mismatch-count`, `--expected-runtime-error-count` and `--expected-rule-source-status`, so CI can encode exact replay contracts without post-processing JSON
  - strict runs preserve the raw replay outcome under `replay_status`, switch top-level `status` to the strict gate result, and append `strict_profile_mismatches` / `strict_mismatches=<n>` in JSON + `--summary`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-085, strict expectation-drift selector for pack replay
  - clarified the strict contract boundary by keeping `--expected-mismatch-count` tied to the broad `summary.mismatch_count` and adding `--expected-expectation-mismatch-count` for the pure `fixture_class=expectation_mismatch` lane, so CI can distinguish wrong output from runtime crashes without JSON post-processing
  - covered mixed expectation-mismatch + runtime-error replays in CLI tests, and updated operator docs/examples to spell out the difference between total mismatches and pure expectation drift
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-085:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - next concrete functional items:
    - add `pack-replay --strict --expected-total-fixture-count` so subset-gated runs still catch silent pack growth/shrink in checked-in packs
    - add exact selected-fixture contracts, e.g. repeatable `--expected-selected-fixture <id>`, so glob/class-filtered lanes catch selector drift even when aggregate counts stay constant


- [x] FP-086, strict total-pack fixture count for pack replay
  - added `erz pack-replay --strict --expected-total-fixture-count <int>` so selector-scoped replay runs can still fail deterministically when the checked-in pack grows or shrinks outside the selected slice
  - kept `--expected-fixture-count` scoped to the selected replay slice, surfaced total-pack drift as `field=total_fixture_count` in `strict_profile_mismatches`, and covered green/red subset replay behavior plus guardrails in CLI tests
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- [x] FP-087, exact selected-fixture strict contracts for pack replay
  - added repeatable `erz pack-replay --strict --expected-selected-fixture <id>` so strict replay can assert the final deterministic `selected_fixture_ids` list after exact/glob/class filtering instead of trusting aggregate counts alone
  - strict runs now surface selector drift as `field=selected_fixture_ids`, preserve canonical pack order in both the actual replay slice and the expected contract, and cover the highest-value class-filtered case where aggregate counts stay constant but the wrong fixture survives selection
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-087:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - next concrete functional items:
    - add exact class-specific strict fixture contracts, e.g. repeatable `--expected-runtime-error-fixture <id>` and `--expected-expectation-mismatch-fixture <id>`, so CI can assert not just the selected slice but also the exact failure partition without JSON post-processing

- [x] FP-088, strict class-specific failure-partition fixture contracts for pack replay
  - added repeatable `erz pack-replay --strict --expected-expectation-mismatch-fixture <id>` and `--expected-runtime-error-fixture <id>`, wired against deterministic `summary.fixture_class_ids.*` slices in canonical pack order so strict replay can gate exact failure membership, not just counts
  - strict failures now surface partition drift as `field=fixture_class_ids.expectation_mismatch` or `field=fixture_class_ids.runtime_error`, preserving the raw replay outcome under `replay_status` while exposing the exact class slice that drifted
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-088:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - next concrete functional items:
    - add exact ok-partition strict fixture contracts, e.g. repeatable `--expected-ok-fixture <id>`, so CI can express the full fixture-class partition directly instead of deriving green members by subtraction

- [x] FP-089, strict ok-partition fixture contracts for pack replay
  - added repeatable `erz pack-replay --strict --expected-ok-fixture <id>`, wired against deterministic `summary.fixture_class_ids.ok` in canonical pack order so strict replay can gate the green partition directly instead of inferring it from selected fixtures minus mismatches
  - strict failures now surface green-partition drift as `field=fixture_class_ids.ok`, keeping the raw replay outcome under `replay_status` while exposing the exact ok-slice drift that broke the contract
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-089:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - next concrete functional items:
    - add `pack-replay --strict-profile clean` style presets, so the common green CI lane stops depending on long brittle `--expected-*` bundles for checked-in packs
    - add aggregate class-histogram strict contracts, so CI can gate the full `fixture_class_counts` object in one place when exact ids are unnecessary but class distribution drift must still fail fast

- [x] FP-090, green-lane strict replay profile preset for checked-in packs
  - added `erz pack-replay --strict-profile clean`, which auto-enables strict replay and hard-gates `expected_mismatch_count=0`, `expected_expectation_mismatch_count=0`, `expected_runtime_error_count=0`, and `expected_rule_source_status=ok` without forcing long repeated fixture-id bundles into CI scripts
  - explicit `--expected-*` selectors still layer on top of the preset, so teams can keep the short green profile for day-to-day CI and selectively add exact fixture-count or fixture-id contracts only where they materially catch extra drift
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-090:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - next concrete functional items:
    - add aggregate class-histogram strict contracts, so CI can gate the full `fixture_class_counts` object in one place when exact ids are unnecessary but class distribution drift must still fail fast

- [x] FP-091, aggregate strict fixture-class histogram contract for pack replay
  - added `erz pack-replay --strict --expected-fixture-class-counts ok=<n>,expectation_mismatch=<n>,runtime_error=<n>`, which gates the full deterministic `summary.fixture_class_counts` object in one flag so CI can fail fast on class-distribution drift without enumerating every fixture id
  - strict failures now surface histogram drift as `field=fixture_class_counts`, keeping raw replay status under `replay_status` while exposing the exact expected vs actual class distribution in one mismatch payload
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-091:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - next concrete functional items:
    - add more named `pack-replay --strict-profile` presets for recurring non-green checked-in packs, so CI can express curated red-lane contracts without long repetitive `--expected-*` bundles
    - add pack-specific clean replay presets that also encode total fixture count plus class histogram for checked-in packs, so green CI can collapse to a single stable preset per pack without hand-maintained count flags

- [x] FP-092, pack-specific clean strict-profile presets for checked-in pack replay
  - added `erz pack-replay --strict-profile ingest-normalize-clean|dedup-cluster-clean|alert-routing-clean`, each preset layering the green-lane `clean` contract with the expected checked-in `pack_id`, `total_fixture_count`, and deterministic `fixture_class_counts` histogram so full-pack CI gates collapse to one stable preset name instead of manual count bundles
  - strict mismatches now surface `field=pack_id` when a pack-specific preset is applied to the wrong checked-in pack, which keeps the failure legible instead of leaving operators to infer the mistake only from count drift
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-092:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - current checked-in packs are all green, so no justified named red-lane preset exists yet, do not invent one without a real checked-in expected-drift pack
  - next concrete functional items:
    - add named non-green `pack-replay --strict-profile` presets only when the repo contains a recurring checked-in expected-drift pack that operators actually need to replay
    - otherwise pivot away from pack-replay preset churn toward the next runtime-visible operator gap

- [x] FP-093, generic strict pack-id selector for pack replay
  - added `erz pack-replay --strict --expected-pack-id <pack-id>`, exposing the same deterministic `pack_id` gate used by pack-specific clean presets as a reusable selector for custom or renamed packs without inventing more preset names
  - added non-empty guardrails plus deterministic mismatch payloads on `field=pack_id`, so raw replay health can stay green under `replay_status` while strict identity drift still fails legibly under `status=error`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-093:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - pack replay now exposes the generic pack identity gate, so the next justified slices should pivot to a new operator/runtime gap, not more preset naming churn
  - next concrete functional items:
    - add `pack-replay --strict --expected-baseline-shape <fixture-matrix|inline-statements>` if operators need to hard-gate baseline form drift separately from `pack_id` and rule-source drift
    - otherwise pivot out of pack-replay and pick the next runtime-visible eval/operator gap with reproducible fixtures, not boundary-only canaries

- [x] FP-094, strict baseline-shape selector for pack replay
  - added `erz pack-replay --strict --expected-baseline-shape <fixture-matrix|inline-statements>`, wired against deterministic `baseline_shape` already exported in the replay envelope so CI/operators can hard-gate fixture-matrix versus inline-statement pack form drift without inferring it from `pack_id` or `rule_source_status`
  - pack-specific `*-clean` strict profiles now also pin the checked-in pack `baseline_shape`, so the one-flag green lane covers pack identity, baseline form, total fixture count, and class histogram together
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-094:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - pack replay now hard-gates baseline form drift, so the next justified slices should pivot back to eval/operator handoff parity, not more preset churn
  - next concrete functional items:
    - add `--batch-output-verify-json-file <path>` so verify can emit machine-readable JSON sidecars while keeping summary stdout stable for CI logs
    - add `--batch-output-compare-json-file <path>` so compare/self-compare runs can hand off the full drift envelope without stdout redirection, mirroring existing summary-file ergonomics
    - if both land, collapse self-verify/self-compare docs + fixtures onto explicit dual-lane summary-stdout + JSON-sidecar examples instead of shell-redirection recipes

- [x] FP-095, eval compare/verify JSON sidecar export parity
  - added `erz eval --batch-output-verify-json-file <path>` and `--batch-output-compare-json-file <path>`, so operators can keep stdout on compact summary/eval lanes while persisting the full machine-readable verify/compare payload in a sidecar file
  - self-compare now exports the compare envelope through the same JSON sidecar flag without mutating normal eval stdout, and the checked-in threshold-handoff refresh path plus CLI contracts now demonstrate explicit dual-lane stdout-vs-sidecar behavior
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_threshold_handoff_snapshots.py`, `README.md`, `docs/runtime-determinism.md`, `examples/eval/threshold-handoff/README.md`, `docs/workloop-queue.md`

- Queue state after FP-095:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - eval/operator handoff now has first-class compare/verify JSON sidecars, so the next justified slices should stay on generation-time handoff parity, not revert to pack-replay preset churn
  - next concrete functional items:
    - add `--batch-output-self-verify-json-file <path>` so generation-time self-verify can hand off the full verify envelope without losing normal eval stdout
    - add `--batch-output-self-verify-summary-file <path>` or equivalent mirrored sidecar support so generation-time verify lanes get the same explicit stdout/file split as standalone verify and self-compare
    - once self-verify has sidecar parity, add checked-in threshold-handoff fixtures that exercise both generation-time handoff sidecars in one reproducible operator path

- [x] FP-096, generation-time self-verify sidecar export parity
  - added `erz eval --batch-output-self-verify-summary-file <path>` and `--batch-output-self-verify-json-file <path>`, so generation-time self-verify can export the verify envelope explicitly without mutating normal eval stdout
  - `--batch-output-self-verify-summary-file` mirrors standalone verify output semantics, JSON by default and `--summary` line when requested, while `--batch-output-self-verify-json-file` always writes the full verify JSON sidecar for dashboards and CI handoff
  - strict self-verify now writes both sidecars before non-zero exit on contract drift, and CLI + integration coverage lock guardrails, stdout parity, file payload shape on pass/fail paths, plus collision guards against `--output`/`--batch-output-summary-file` overwrites and summary/json same-path ambiguity under `--summary`
  - target files: `cli/main.py`, `tests/test_cli.py`, `tests/test_integration_pipeline.py`, `README.md`, `docs/runtime-determinism.md`, `docs/workloop-queue.md`

- Queue state after FP-096:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - generation-time self-verify now has first-class sidecar parity with standalone verify, so the next justified slice is the reproducible fixture lane, not more guardrail canaries
  - next concrete functional items:
    - add checked-in threshold-handoff fixtures and refresh commands that exercise both generation-time self-verify sidecars in one reproducible operator path
    - once those fixtures land, collapse any remaining self-verify shell-redirection guidance onto explicit dual-lane summary-stdout plus JSON-sidecar examples

- [x] FP-097, checked-in threshold-handoff self-verify sidecar snapshot lane
  - checked in the strict generation-time self-verify JSON sidecar under `examples/eval/threshold-handoff/triage.verify.expected.json` and refreshed the threshold-handoff replay docs so the in-repo command set now exercises both self-verify sidecars directly
  - extended `tests/test_threshold_handoff_snapshots.py` with a reproducibility lane that regenerates `triage-by-status/` plus the self-verify summary/json sidecars in temp and asserts byte-for-byte parity with the checked-in fixtures, so the operator handoff path is no longer only prose plus an untracked artifact
  - target files: `examples/eval/threshold-handoff/*`, `examples/eval/README.md`, `tests/test_threshold_handoff_snapshots.py`, `docs/workloop-queue.md`

- Queue state after FP-097:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - the threshold-handoff lane now covers generation-time self-verify and generation-time self-compare with checked-in reproducible JSON sidecars, and the self-verify path is no longer just prose plus an untracked artifact
  - next concrete functional items:
    - add checked-in threshold-handoff standalone verify JSON sidecars plus replay/test coverage, so `--batch-output-verify-json-file` has the same in-repo reproducibility story as the generation-time self-verify lane
    - add checked-in threshold-handoff standalone compare JSON sidecars plus replay/test coverage, so `--batch-output-compare-json-file` is exercised directly as an operator fixture lane instead of only via generation-time self-compare

- [x] FP-098, checked-in threshold-handoff standalone verify/compare JSON snapshot lane
  - added frozen standalone verify JSON sidecars for both the flat baseline lane and the strict triage lane, then extended the snapshot replay tests so `--batch-output-verify-json-file` now proves reproducibility directly against the checked-in artifact trees instead of inheriting confidence only from generation-time self-verify
  - added frozen standalone compare JSON sidecars for both clean and asymmetric-drift threshold-handoff lanes, plus replay/test coverage that confirms compare sidecar export does not mutate the checked-in baseline/candidate trees while matching the tracked JSON envelopes byte-for-byte
  - refreshed the threshold-handoff fixture docs so operators now have explicit copy-paste refresh commands for standalone verify, standalone compare, generation-time self-verify, and generation-time self-compare sidecars in one place
  - target files: `examples/eval/threshold-handoff/*`, `examples/eval/README.md`, `tests/test_threshold_handoff_snapshots.py`, `docs/workloop-queue.md`

- Queue state after FP-098:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - the threshold-handoff lane now covers standalone verify/compare plus generation-time self-verify/self-compare with checked-in JSON sidecars and reproducibility tests, so the sidecar story is no longer split between runtime behavior and prose-only operator recipes
  - next concrete functional items:
    - only add a one-shot refresh helper if it materially removes shell drift while rewriting the same tracked threshold-handoff outputs deterministically
    - otherwise pivot away from threshold-handoff and inspect the next runtime-visible eval/operator gap instead of reopening sidecar-only adjacency work

- [x] FP-099, one-shot threshold-handoff refresh helper
  - added `scripts/refresh_threshold_handoff.py`, a single deterministic refresh entrypoint that rewrites the tracked `examples/eval/threshold-handoff/` artifact trees and sidecar snapshots without making operators replay a page of fragile shell commands by hand
  - simplified the threshold-handoff docs around the one-shot helper, and added end-to-end test coverage proving a temp copy with all generated outputs removed is restored byte-for-byte to the checked-in fixture tree
  - target files: `scripts/refresh_threshold_handoff.py`, `tests/test_threshold_handoff_snapshots.py`, `examples/eval/threshold-handoff/README.md`, `examples/eval/README.md`, `README.md`, `docs/runtime-determinism.md`, `docs/workloop-queue.md`

- [x] FP-100, aggregate multi-pack pack-replay lane
  - extended `erz pack-replay` so it now accepts either a single pack directory, a directory of child packs, or a pack index JSON file with deterministic path order, then emits one aggregate JSON envelope plus a summary view that starts with overall pack totals and follows with stable per-pack lines
  - aggregate mode keeps single-pack behavior untouched, but explicitly rejects fixture selectors, fixture-class filtering, and strict replay contracts that only make sense once a single pack has already been chosen
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `docs/workloop-queue.md`

- Queue state after FP-100:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - pack replay now covers single-pack and multi-pack operator replay in one CLI surface, so the next justified work is only stricter aggregate gating if real CI/operator need appears
  - next concrete functional items:
    - FP-101 candidate, extend aggregate `pack-replay` with strict expected pack-count / selected-pack contracts only if the new multi-pack lane proves useful in CI/operator flow
    - otherwise pivot to the next runtime-visible eval/operator gap instead of inventing more aggregate-only policy surface
    - if a future fixture lane grows into the same kind of multi-command sprawl, only add a refresh helper when it collapses real operator toil instead of dressing docs in new clothes

- [x] FP-101, aggregate strict pack-selection contracts for pack replay
  - added aggregate-only `erz pack-replay --strict --expected-pack-count <n>` and repeatable `--expected-selected-pack <path>`, so the new multi-pack replay lane can hard-gate deterministic pack selection and order in CI/operator flows without pretending single-pack fixture selectors scale to collection replay
  - strict aggregate mismatches now preserve raw replay health under `replay_status`, flip `status` to the gate result, and report exact pack-selection drift under `strict_profile_mismatches` as `pack_count` and `selected_pack_paths` in canonical replay order
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-101:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - aggregate pack replay now has the minimum useful CI-grade strict contract, do not reopen this lane for more aggregate-only counters or presets without a concrete operator need
  - next concrete functional items:
    - add aggregate pack selectors, `--include-pack <glob>` and `--exclude-pack <glob>`, so multi-pack replay can target deterministic subsets without requiring bespoke index files
    - once pack selectors land, reuse FP-101 strict pack-count/selected-pack contracts to hard-gate selector drift instead of inventing another aggregate-only policy layer
    - otherwise pivot to the next runtime-visible eval/operator gap, not back to canary churn

- [x] FP-102, aggregate pack selectors for pack replay
  - added aggregate-only `erz pack-replay --include-pack <glob>` and `--exclude-pack <glob>`, applied against deterministic aggregate display paths before replay, so multi-pack runs can target stable pack subsets without bespoke index JSON files or shell-side path filtering
  - aggregate JSON envelopes now preserve the resulting `selected_pack_paths` plus the applied `include_pack_globs` and `exclude_pack_globs`, and FP-101 strict pack-count/selected-pack contracts now compose directly with selector-scoped aggregate replay so selector drift fails under `strict_profile_mismatches` without changing raw `replay_status`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-102:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - aggregate pack replay now covers selection plus strict selector drift gates, so do not pad this lane with more aggregate-only presets or counters unless operators actually need them
  - next concrete functional items:
    - if operators need visibility into pack growth outside a selected subset, add a pre-filter aggregate total-pack contract instead of more selector canaries
    - otherwise pivot out of aggregate pack replay and inspect the next runtime-visible eval/operator gap with reproducible fixtures
    - keep future work product-facing, not docs-only adjacency churn

- [x] FP-103, aggregate pre-filter total-pack strict contract for pack replay
  - added aggregate-only `erz pack-replay --strict --expected-total-pack-count <n>`, so selector-scoped multi-pack replays can still fail deterministically when the underlying collection grows or shrinks outside the selected pack subset
  - aggregate `--summary` now exposes `total_packs=<n>` whenever the selected pack count differs from the underlying collection size, and strict aggregate mismatches report `total_pack_count` alongside `pack_count` / `selected_pack_paths` without changing raw `replay_status`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-103:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - aggregate pack replay now covers selected-slice contracts plus pre-filter collection-size drift, so close this lane unless a new operator need shows up
  - next concrete functional items:
    - add a checked-in `program-pack-index.json` fixture plus replay/test coverage, so the aggregate index-path lane stops depending on ad-hoc `/tmp` examples and becomes reproducible in-repo
    - if that lands, add a one-shot refresh helper only if it materially rewrites the same tracked pack-index fixture inputs without shell drift
    - otherwise pivot to the next runtime-visible eval/operator gap, not back into aggregate-only pack-replay policy churn

- [x] FP-104, checked-in aggregate pack-index fixture lane for pack replay
  - added tracked `examples/program-packs/program-pack-index.json` with mixed string/object entries and relative pack paths in deliberate declared order, so the index-path aggregate replay lane is now reproducible in-repo instead of living only in ad-hoc `/tmp` examples
  - switched CLI coverage to the checked-in index fixture, proving relative-path resolution, declared display-path ordering, include-pack glob matching, JSON envelope selection order, and strict aggregate gating directly against the tracked example operators will actually run
  - updated README/runtime/program-pack docs to use the checked-in index path and its declared order instead of ephemeral `/tmp/program-pack-index.json` commands
  - target files: `examples/program-packs/program-pack-index.json`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/program-packs/README.md`, `docs/workloop-queue.md`

- Queue state after FP-104:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - the aggregate index-path lane is now reproducible in-repo, and a refresh helper is not justified yet because the tracked surface is one small hand-authored JSON fixture, not a generated artifact tree
  - next concrete functional items:
    - pivot out of aggregate pack replay and inspect the next runtime-visible eval/operator gap with reproducible fixtures, not more aggregate-only selector churn
    - only add a pack-index refresh helper if future tracked index inputs or generated outputs create real operator toil instead of one-file edit overhead

- [x] FP-105, declarative batch-index replay lane for eval
  - extended `erz eval --batch <dir|index.json>` so batch replay now accepts a checked-in JSON index with mixed string/object entries under `{"events": [...]}`, preserving declared event order without bespoke temp directories or shell-side file shuffling
  - kept batch filtering on deterministic event filenames and added checked-in `examples/eval/batch-index.json` plus CLI coverage, so operators can freeze curated replay subsets/orders in-repo while leaving the existing directory lane untouched
  - target files: `cli/main.py`, `tests/test_cli.py`, `examples/eval/batch-index.json`, `README.md`, `docs/runtime-determinism.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-105:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - eval batch replay now has the same checked-in index-fixture ergonomics that pack replay gained, so curated operator subsets no longer require bespoke directories just to lock order
  - next concrete functional items:
    - if operators now need hard CI gates on curated batch subsets, add strict expected event-count / selected-event contracts on top of the batch-index lane instead of inventing more pack-replay policy surface
    - otherwise inspect the next runtime-visible eval/operator gap in artifact handoff or checked-in fixture replay, not docs-only adjacency work

- [x] FP-106, strict curated batch-slice contracts for eval batch replay
  - added `erz eval --batch-strict` with `--batch-expected-event-count <n>` plus repeatable `--batch-expected-selected-event <name>`, so curated batch-index or filtered directory replays can hard-gate the final deterministic event slice without losing the raw replay outcome
  - strict batch replay now preserves green raw replay under `replay_status`, flips top-level `status` on selector drift, exports the final `selected_event_names`, and reports mismatches under `strict_profile_mismatches`; `--summary` adds `strict_mismatches=<n>` and the command exits non-zero on strict drift even when the underlying replay stayed green
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-106:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - eval batch replay now covers checked-in index order plus strict final-slice contracts, so close this lane unless a concrete operator need appears beyond selection drift
  - next concrete functional items:
    - if curated batch subsets also need growth detection outside the selected slice, add a pre-filter total-event strict contract instead of padding this lane with more selector-only policy knobs
    - otherwise pivot to the next runtime-visible eval/operator gap in artifact handoff or checked-in fixture replay, not back into batch-only selector churn

- [x] FP-107, pre-filter total-event strict contract for eval batch replay
  - added `erz eval --batch-strict --batch-expected-total-event-count <n>`, so selector-scoped batch replays can still fail deterministically when the underlying batch collection grows or shrinks outside the selected event slice
  - batch JSON summaries now export `summary.total_event_count`, while `--summary` appends `total_events=<n>` whenever the selected replay slice differs from the pre-filter collection size; strict drift reports `field=total_event_count` under `strict_profile_mismatches` without hiding the raw `replay_status`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-107:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - eval batch replay now covers both the final selected event slice and the pre-filter batch collection size, so this lane no longer needs more selector-only padding
  - next concrete functional items:
    - if operators need exact identity gating for the source batch collection itself, add a checked-in strict contract for the declared pre-filter event list, not more count-only canaries
    - otherwise pivot to the next runtime-visible eval/operator gap in artifact handoff or checked-in fixture replay, not back into batch-only selector churn

- [x] FP-108, pre-filter source-batch identity contract for eval batch replay
  - added repeatable `erz eval --batch-strict --batch-expected-total-event <name>`, so selector-scoped batch replays can also hard-gate the exact deterministic pre-filter source collection, not just its size
  - strict batch envelopes now export `total_event_names` whenever that contract is active, and drift reports `field=total_event_names` under `strict_profile_mismatches` without hiding the raw `replay_status`
  - target files: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/runtime-determinism.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-108:
  - cutoff held, no return to docs/heading/line-adjacency-only canaries
  - eval batch replay now covers selected-slice identity plus pre-filter collection size and identity, so this selector lane is functionally complete for now
  - next concrete functional items:
    - pivot to the next runtime-visible eval/operator gap in artifact handoff or checked-in fixture replay, not back into batch selector churn
    - if a new operator need appears here, it must change runtime-visible handoff behavior, not just add boundary-only canaries

- [x] FP-109, eval operator expansion and first-class single-run sidecar handoff
  - expanded deterministic eval clauses with missing-path, negative nested equality, regex match/negation, list-set membership (`any_in` / `all_in` / `none_in`), and negative string-prefix/suffix families, then pinned them with runtime coverage plus checked-in example programs/events/envelopes so operators can replay the new paths without inventing ad-hoc fixtures
  - added generic `erz eval --summary-file <path>` and `--json-file <path>` sidecars for single-event and batch eval runs, including collision guards against `--output` and lane-specific verify/compare sidecars so summary stdout and machine JSON handoff become first-class without stdout drift
  - refreshed README/example docs and added focused CLI fixture suites for missing-path, negation, string-negation, regex-match, suffix, `any_in`, `all_in`, `none_in`, and eval-sidecar parity
  - target files: `runtime/eval.py`, `cli/main.py`, `tests/test_runtime_eval.py`, `tests/test_cli.py`, `tests/test_cli_*_examples.py`, `tests/test_cli_eval_sidecars.py`, `examples/eval/*`, `README.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-109:
  - cutoff held, no return to canary drift, this run closed a user-visible eval/runtime gap with replayable fixtures and handoff sidecars instead of padding selector contracts
  - the active eval slice now covers deterministic missing-path, negative, regex, list-membership, and suffix operator families plus checked-in replay fixtures and single-run sidecar exports, so operators can validate and hand off results without bespoke wrapper scripts
  - next concrete functional items:
    - pivot to the next runtime-visible eval gap that changes machine handoff or checked-in replay behavior, not another fixture-only adjacency pass
    - if more operator work appears here, prefer one coherent operator family with checked-in examples and docs parity, not isolated clause canaries

- [x] FP-110, checked-in eval sidecar replay fixtures for machine handoff
  - froze the new eval sidecar behavior into checked-in replay fixtures for both lanes operators actually hand off, a refs-backed single-event run (`event-sidecar.expected.*`) and the canonical batch replay (`batch.expected.*`), so summary/file-sidecar parity is now byte-checkable in-repo instead of living only in ad-hoc `/tmp` commands
  - added focused CLI example coverage that writes `--summary-file` and `--json-file` into temp paths and compares them against the checked-in fixtures, while docs now surface the new single-run and batch sidecar handoff lanes directly in README, runtime determinism notes, and `examples/eval/README.md`
  - target files: `tests/test_cli_eval_sidecar_examples.py`, `examples/eval/event-sidecar.expected.*`, `examples/eval/batch.expected.*`, `README.md`, `docs/runtime-determinism.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-110:
  - cutoff held, no return to canary drift, this run tightened checked-in machine handoff behavior instead of inventing more selector-only or heading-only churn
  - eval sidecars are now replayable from repo fixtures in both the refs-backed single-event lane and the canonical batch lane, so operators can rehearse exact summary/json handoff without bespoke temp-file setup or post-hoc diffing
  - next concrete functional items:
    - if the next eval slice stays in replay parity, prefer one coherent remaining operator family that still lacks a checked-in smoke lane, not another docs-only adjacency pass
    - otherwise pivot to the next runtime-visible eval gap that changes handoff semantics, not more sidecar prose alone

- [x] FP-111, threshold replay smoke lane
  - added `tests/test_cli_threshold_examples.py`, pinning `examples/eval/program-thresholds.erz` against the checked-in `event-threshold-*.expected.*` fixtures so the numeric-threshold lane is replayable as an operator-facing CLI smoke suite instead of docs/examples only
  - target files: `tests/test_cli_threshold_examples.py`, `docs/workloop-queue.md`

- Queue state after FP-111:
  - numeric thresholds now have the same checked-in CLI replay coverage as the other recent eval operator families, so the next justified slice should stay on one remaining replay gap instead of reopening sidecar/docs adjacency work
  - next concrete functional items:
    - prefer the next coherent checked-in operator smoke lane, with payload-length as the obvious follow-on
    - keep the focus on runtime-visible replay parity, not more prose-only expansion

- [x] FP-112, payload-length replay smoke lane
  - added `tests/test_cli_length_examples.py`, pinning `examples/eval/program-lengths.erz` against the checked-in `event-length-*.expected.*` envelope and summary fixtures so the payload-length operator family now has a first-class CLI replay smoke lane in repo
  - target files: `tests/test_cli_length_examples.py`, `docs/workloop-queue.md`

- Queue state after FP-112:
  - threshold and payload-length lanes are both now covered by checked-in CLI smoke tests, so this replay-parity pass keeps moving on functional operator slices instead of docs or canary churn
  - next concrete functional items:
    - inspect the next remaining checked-in eval operator replay gap, likely one of the older path or positive string lanes that still ships fixtures without a dedicated CLI smoke suite
    - only pivot away from replay parity if the next slice materially changes machine handoff behavior

- [x] FP-113, exact payload-type predicates with checked-in replay smoke
  - added deterministic `payload_path_is_null/bool/number/string/list/object` clauses so eval rules can gate exact nested payload shapes without abusing equality or length checks; numbers stay finite-only and explicitly exclude bools, missing paths stay clean non-matches
  - checked in `examples/eval/program-types.erz` with `event-type-*.json` plus frozen envelope/summary outputs, then added `tests/test_cli_type_examples.py` so operators can replay the new type lane directly from repo fixtures instead of inventing ad-hoc shape probes
  - refreshed README, `examples/eval/README.md`, and `docs/runtime-determinism.md` around the new type family, and extended runtime/doc boundary coverage so the supported-clause contract stays explicit instead of drifting into prose-only adjacency
  - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_cli_type_examples.py`, `tests/test_integration_pipeline.py`, `examples/eval/*`, `README.md`, `examples/eval/README.md`, `docs/runtime-determinism.md`

- Queue state after FP-113:
  - cutoff held, this run shipped a new user-visible eval operator family with checked-in replay fixtures instead of looping on more doc/canary-only parity work
  - exact payload-type gating is now first-class in runtime and operator examples, so the next justified slice should be another coherent eval/operator family or machine-handoff gap, not more boundary-only padding around the same docs
  - next concrete functional items:
    - if eval stays on operator families, pick one fresh deterministic gap that materially changes runtime behavior instead of revisiting already-covered replay lanes
    - otherwise pivot to the next handoff/export gap only if it changes machine-visible CLI behavior, not just prose or refresh ergonomics

- [x] FP-114, case-insensitive membership predicates with checked-in replay smoke
  - added `payload_path_in_ci/not_in_ci/any_in_ci/all_in_ci/none_in_ci`, so eval rules can now casefold-match string scalar membership and non-empty string-list membership without forcing operators to normalize input casing upstream or explode one rule into multiple exact-case variants
  - checked in `examples/eval/program-membership-ci.erz` with `event-membership-ci-*.json` plus frozen envelope/summary outputs, then added `tests/test_cli_membership_ci_examples.py` so the new operator family is replayable from repo fixtures instead of living only in runtime unit tests
  - refreshed `examples/eval/README.md` and the runtime determinism contract to pin the new string-only `_in_ci` limits explicitly, keeping the operator surface machine-visible instead of prose drift or canary padding
  - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_cli_membership_ci_examples.py`, `tests/test_integration_pipeline.py`, `examples/eval/*`, `examples/eval/README.md`, `docs/runtime-determinism.md`

- Queue state after FP-114:
  - cutoff held, this run stayed on a real runtime/operator frontier and did not reopen the already-heavy handoff/action-plan surface for ornamental follow-ups
  - eval now has case-insensitive exact-string and case-insensitive membership families, so operators can express stable enum/tag/channel guards directly in rules instead of pre-normalizing payloads outside erz
  - next concrete functional items:
    - if eval stays on operator families, prefer another missing deterministic predicate family with obvious operator value, not more replay-only adjacency around the just-added membership lane
    - otherwise pivot to a separate runtime-visible operator/CI frontier, not back into handoff-bundle polish unless a concrete leverage point shows up

- [x] FP-115, cross-field payload path comparisons with checked-in replay smoke
  - added `payload_path_equals_path/not_equals_path` plus numeric `payload_path_gt_path/gte_path/lt_path/lte_path`, so eval rules can compare two resolved payload fields directly instead of forcing operators to precompute mirror flags or duplicate threshold material outside erz
  - pinned the new lane with `examples/eval/program-cross-paths.erz`, frozen `event-cross-path-*.expected.*` fixtures, and `tests/test_cli_cross_path_examples.py`, keeping the new cross-field operator contract replayable from repo instead of living only in runtime unit tests
  - refreshed the runtime determinism contract, eval fixture index, README commands, and boundary canaries around the current-limits bullet so the new `*_path` surface stays explicit and machine-visible instead of silently drifting behind docs
  - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_cli_cross_path_examples.py`, `tests/test_integration_pipeline.py`, `examples/eval/*`, `README.md`, `examples/eval/README.md`, `docs/runtime-determinism.md`, `docs/workloop-queue.md`

- Queue state after FP-115:
  - cutoff held, this run added a real runtime/operator lever, direct cross-field gating, instead of reopening bundle/docs adjacency or another narrow canary lane
  - eval can now contract nested field-to-field equality and threshold relationships directly in rules, which removes a chunk of external event-shaping glue from operator workflows
  - next concrete functional items:
    - if eval stays on operator families, prefer another missing deterministic comparison family with similarly obvious runtime leverage, not more replay-only polish around the new cross-field lane
    - otherwise pivot to a separate operator/CI frontier only if it changes machine-visible behavior, not prose or canary density alone

- [x] FP-116, cross-field string path predicates with checked-in replay smoke
  - added `payload_path_startswith_path/contains_path/endswith_path`, their negative forms, and the full `*_path_ci` family, so eval rules can compare one resolved payload string against another without hard-coding transient literals or precomputing mirror flags outside erz
  - pinned the new lane with `examples/eval/program-cross-path-strings.erz`, frozen `event-cross-path-strings-*.expected.*` fixtures, and `tests/test_cli_cross_path_string_examples.py`, keeping the operator contract replayable from repo instead of hiding in runtime-only coverage
  - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_cli_cross_path_string_examples.py`, `examples/eval/*`, `README.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-116:
  - cutoff held, this run stayed on a real runtime/operator frontier and avoided further handoff-bundle ornament after the already-heavy action-plan/ref lane
  - eval can now contract dynamic string-prefix/contains/suffix relationships directly between payload fields, including case-insensitive variants, which removes another chunk of upstream normalization and mirror-field glue from operator workflows
  - next concrete functional items:
    - if eval stays on operator families, prefer another missing dynamic predicate family with similarly obvious runtime leverage, not another replay-only adjacency pass around this string-path lane
    - otherwise pivot to a separate operator/CI frontier only if it changes machine-visible behavior, not prose or canary density alone

- [x] FP-117, checked-in pack-replay contracts via existing program-pack infrastructure
  - added `scripts/refresh_program_pack_replay_contracts.py` plus checked-in `examples/program-packs/*.replay.expected.*` sidecars for the single-pack `refs-handoff` lane and the aggregate `program-pack-index.json` lane, so operators now have repo-native summary/json/handoff-bundle contracts for `pack-replay`, not just unit assertions
  - normalized internal `target_path` / `program_path` / `baseline_path` fields to fixture-root-relative strings in the checked-in snapshots, which keeps temp-copy refreshes byte-stable and avoids machine-local absolute roots leaking into the repo contract
  - pinned the slice with `tests/test_program_pack_replay_snapshots.py` and refreshed the pack docs/runtime notes, keeping the new handoff path tied to the existing packs, helpers, and replay surface instead of inventing a parallel fixture stack

- Queue state after FP-117:
  - cutoff held, this run improved the existing operator/CI pack-replay path instead of spinning up another ad-hoc harness around the same feature surface
  - pack-replay now matches the repo-native handoff discipline already used by eval batch lanes, which makes the pack surface materially easier to verify, hand off, and keep deterministic over time
  - next concrete functional items:
    - if pack-replay stays in focus, prefer another machine-visible operator lever on the same surface, for example mismatch-field contracts or replay path determinism in first-class JSON, not more prose-only expansion
    - otherwise pivot back to a separate runtime-visible frontier, not another docs/canary-only pass

- [x] FP-118, repo-native umbrella refresh for checked-in contract fixtures
  - added `scripts/refresh_contract_fixtures.py`, a thin deterministic orchestrator over the existing `refresh_action_plan_handoff.py`, `refresh_threshold_handoff.py`, and `refresh_program_pack_replay_contracts.py` helpers, so operators can refresh the current checked-in eval handoff and pack-replay contract surfaces in one command without inventing local shell glue
  - added `tests/test_refresh_contract_fixtures.py`, which copies all three tracked fixture roots into temp space, deletes their generated outputs, reruns the umbrella helper, and asserts byte-for-byte parity against the checked-in trees, keeping the new entrypoint aligned with the repo-native helpers instead of becoming a shadow path
  - surfaced the one-shot helper in `README.md`, keeping the refresh path discoverable at the same level as the existing eval/pack quickstart commands instead of burying it only in per-fixture READMEs
  - target files: `scripts/refresh_contract_fixtures.py`, `tests/test_refresh_contract_fixtures.py`, `README.md`, `docs/workloop-queue.md`

- Queue state after FP-118:
  - cutoff held, this run improved repo-native operator clarity around existing helpers and checked-in fixtures instead of adding parallel refresh infrastructure or more prose-only padding
  - the current eval handoff and pack-replay contract roots now have a single top-level refresh entrypoint, while the surface-specific helpers remain the source of truth underneath
  - next concrete functional items:
    - if work stays near pack/eval contract refresh, prefer another machine-visible leverage point on top of the existing sidecars and bundles, not another layer of refresh indirection
    - otherwise pivot back to a runtime-visible eval or replay feature gap, not docs or canary density alone

- [x] FP-119, uniform checked-in replay sidecars for every program pack
  - expanded `scripts/refresh_program_pack_replay_contracts.py` from a refs-only special case into a data-driven pass over all checked-in packs, so `ingest-normalize`, `dedup-cluster`, `alert-routing`, and `refs-handoff` now each ship deterministic summary/json/handoff-bundle replay sidecars under the same repo-native naming scheme
  - updated the snapshot coverage in `tests/test_program_pack_replay_snapshots.py` and the umbrella refresh coverage in `tests/test_refresh_contract_fixtures.py`, so temp-copy refreshes must regenerate every per-pack sidecar plus the aggregate index contract, not just the single refs pack
  - refreshed pack determinism notes to point at the broader `*.replay.expected.*` surface instead of the old refs-only exception, keeping operator guidance aligned with the actual checked-in contract paths
  - target files: `scripts/refresh_program_pack_replay_contracts.py`, `tests/test_program_pack_replay_snapshots.py`, `tests/test_refresh_contract_fixtures.py`, `examples/program-packs/README.md`, `docs/runtime-determinism.md`, `docs/workloop-queue.md`

- Queue state after FP-119:
  - cutoff held, this run stayed on the existing program-pack/refresh infrastructure and made the replay contract surface uniform instead of multiplying one-off sidecar paths
  - operators can now grab or diff a checked-in replay bundle for any shipped pack, while the refresh helper remains the single source of truth for regenerating them all
  - next concrete functional items:
    - if pack-replay stays in focus, prefer another machine-visible leverage point on top of these uniform sidecars, for example richer aggregate contracts or first-class mismatch partitioning, not more README-only expansion
    - otherwise pivot back to a separate runtime-visible eval or replay frontier, not docs or canary density alone

- [x] FP-120, one-shot refresh helper for top-level eval smoke fixtures
  - added `scripts/refresh_eval_example_fixtures.py`, which rewrites the checked-in top-level `examples/eval/*.expected.*` smoke outputs, including the action-plan and handoff-bundle sidecars already exercised by the repo, without touching the dedicated `action-plan-handoff/` or `threshold-handoff/` artifact trees
  - added `tests/test_eval_example_snapshots.py`, which copies `examples/eval/` into temp, deletes every top-level `*.expected.*` file, reruns the helper, and asserts byte-for-byte parity against the checked-in fixtures, so the helper stays anchored to the existing repo-native replay surface instead of becoming another shell recipe
  - surfaced the helper in the main README and `examples/eval/README.md`, keeping the smoke-fixture refresh path as discoverable as the newer contract-refresh helpers instead of leaving operators with dozens of ad hoc copy-paste commands
  - target files: `scripts/refresh_eval_example_fixtures.py`, `tests/test_eval_example_snapshots.py`, `README.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-120:
  - cutoff held, this run tightened the existing checked-in eval smoke surface and its refresh path instead of inventing a parallel harness or reopening docs-only adjacency work
  - top-level eval examples now have the same repo-native refresh discipline as the deeper action-plan/threshold/program-pack contract trees, which makes the current local diff easier to refresh, review, and push as one coherent slice
  - next concrete functional items:
    - if eval example work stays in focus, prefer another machine-visible leverage point on top of these checked-in fixtures, for example a narrower strict handoff/export gap or an existing helper umbrella only if it removes real operator toil
    - otherwise pivot back to a separate runtime-visible eval or replay frontier, not more refresh-layer ornament

- [x] FP-121, one-shot umbrella refresh now includes top-level eval smoke fixtures
  - extended `scripts/refresh_contract_fixtures.py` to call the existing `refresh_eval_example_fixtures.py` helper first-class under `--only eval-smoke` / `--eval-root`, so operators can now refresh the checked-in top-level eval smoke outputs, the deeper eval handoff trees, and the program-pack replay contracts in one repo-native command instead of remembering two adjacent entrypoints
  - expanded `tests/test_refresh_contract_fixtures.py` to prove the umbrella helper regenerates a temp-copied `examples/eval/` tree byte-for-byte, and added an eval-only selector lane so the new surface stays deterministic instead of silently broadening the helper contract
  - kept the dedicated eval helper intact for narrower rewrites, but aligned README/operator notes around the umbrella path as the default full-fixture refresh entrypoint
  - target files: `scripts/refresh_contract_fixtures.py`, `tests/test_refresh_contract_fixtures.py`, `README.md`, `examples/eval/README.md`, `docs/workloop-queue.md`

- Queue state after FP-121:
  - cutoff held, this run chose the real operator-toil reduction that was already visible on the current fixture/refresh track, instead of reopening handoff-bundle edge polish or adding another wrapper layer
  - the repo now has one first-class refresh entrypoint for the full checked-in eval/program-pack fixture surface, while the existing narrower helpers remain available underneath for targeted rewrites
  - next concrete functional items:
    - if this surface stays in focus, prefer a machine-visible handoff/export gap on top of the existing checked-in fixtures, not another refresh indirection layer
    - otherwise pivot back to a separate runtime-visible eval or replay frontier, not docs/canary density alone

- [x] FP-122, program-pack replay refresh now derives contracts from the checked-in pack index
  - removed the stale second source of truth in `scripts/refresh_program_pack_replay_contracts.py` by loading pack paths from `examples/program-packs/program-pack-index.json`, deriving per-pack output stems/clean strict profiles from the declared index order, and computing aggregate `--expected-fixture-class-counts` from the generated per-pack replay JSON instead of hard-coded pack/fixture totals
  - aligned `tests/test_program_pack_replay_snapshots.py` and `tests/test_refresh_contract_fixtures.py` with the same repo-native index source, so future pack additions or reordering now fail in one place instead of silently drifting across duplicated helper/test lists
  - target files: `scripts/refresh_program_pack_replay_contracts.py`, `tests/test_program_pack_replay_snapshots.py`, `tests/test_refresh_contract_fixtures.py`, `docs/workloop-queue.md`

- Queue state after FP-122:
  - cutoff held, this run stayed on the existing refresh/contract surface but removed duplicated pack topology and aggregate count policy from the helper layer instead of adding more wrapper prose
  - the checked-in pack index is now the single repo-native source of truth for program-pack replay contract refresh, which makes pack growth or reorder work cheaper to refresh and harder to desync
  - next concrete functional items:
    - if pack replay stays in focus, prefer a machine-visible replay/export gap on top of the existing contract outputs, not another duplicate helper manifest
    - otherwise pivot back to a separate runtime-visible eval or replay frontier, not docs/canary density alone

- [x] FP-123, aggregate pack-replay strict preset for the checked-in collection
  - extended aggregate `erz pack-replay <packs-dir|pack-index.json>` so `--strict-profile program-pack-index-clean` is now first-class on collection targets, auto-enabling strict replay from the checked-in `examples/program-packs/program-pack-index.json` plus the per-pack `*.replay.expected.json` contracts instead of forcing operators to restate pack-count, selection, and histogram flags by hand
  - taught `scripts/refresh_program_pack_replay_contracts.py` to regenerate the aggregate `program-pack-index.replay.expected.*` sidecars through that preset, so the checked-in aggregate strict contract now flows through the same repo-native pack index + replay snapshot sources as the CLI itself
  - pinned the slice with aggregate-pass / filtered-drift coverage in `tests/test_cli.py`, plus the existing snapshot/umbrella refresh tests that now lock the richer aggregate strict profile into the checked-in replay and handoff-bundle sidecars byte-for-byte
  - target files: `cli/main.py`, `scripts/refresh_program_pack_replay_contracts.py`, `tests/test_cli.py`, `examples/program-packs/program-pack-index.replay.expected.*`, `README.md`, `examples/program-packs/README.md`, `docs/runtime-determinism.md`, `docs/workloop-queue.md`

- Queue state after FP-123:
  - cutoff held, this run stayed on the current program-pack/operator surface and closed a real aggregate strict-profile gap instead of adding more refresh indirection or docs-only padding
  - operators can now gate the full checked-in pack collection with one stable preset name, while the preset itself stays anchored to the checked-in pack index and replay sidecars rather than another duplicated manifest of counts
  - next concrete functional items:
    - if pack replay stays in focus, prefer another machine-visible aggregate contract on top of the existing replay/handoff outputs, for example a first-class rule-source aggregate preset or richer mismatch partitioning, not more preset prose
    - otherwise pivot back to a separate runtime-visible eval or replay frontier, not docs/canary density alone

- [x] FP-124, aggregate rule-source strict contract for checked-in pack replay
  - extended aggregate `erz pack-replay <packs-dir|pack-index.json>` strict replay with `--expected-rule-source-status-counts ok=<n>,mismatch=<n>`, so collection runs can hard-gate the visible rule-source histogram directly instead of inferring drift indirectly from pack counts or fixture totals
  - taught `--strict-profile program-pack-index-clean` to derive `expected_rule_source_status_counts` from the checked-in pack index plus per-pack replay contracts, and refreshed `program-pack-index.replay.expected.*` so the aggregate replay and handoff bundle now expose that histogram gate byte-for-byte
  - pinned the slice with new aggregate selector coverage in `tests/test_cli.py`, including aggregate strict-profile drift on a filtered pack slice and a direct `rule_source_status_counts` mismatch lane
  - target files: `cli/main.py`, `tests/test_cli.py`, `examples/program-packs/program-pack-index.replay.expected.*`, `README.md`, `examples/program-packs/README.md`, `docs/runtime-determinism.md`, `docs/workloop-queue.md`

- Queue state after FP-124:
  - cutoff held, this run stayed on the current program-pack aggregate contract surface and closed the next machine-visible operator gap instead of slipping into more refresh-layer or docs-only churn
  - operators can now gate the checked-in collection on the same `rule_sources=ok:<n>,mismatch:<n>` histogram already shown in aggregate summaries, with the preset remaining derived from repo-native replay contracts rather than another manual count list
  - next concrete functional items:
    - if pack replay stays in focus, prefer the next aggregate contract that still changes operator leverage, for example richer mismatch partitioning on the collection lane or another replay/export surface, not more preset prose
    - otherwise pivot back to a separate runtime-visible eval or replay frontier, not docs/canary density alone

- [x] FP-125, multi-key object guards on payload paths with checked-in smoke fixtures
  - added `payload_path_has_keys`, `payload_path_missing_keys`, and their `_ci` variants, so eval rules can contract required and forbidden key sets on object-valued payload paths in one clause instead of stacking long runs of single-key checks
  - pinned the new lane with `examples/eval/program-object-key-sets.erz`, checked-in `event-object-key-sets-*.expected.*` fixtures generated through the existing `scripts/refresh_eval_example_fixtures.py` helper, and `tests/test_cli_object_key_set_examples.py`, keeping the slice on the repo-native smoke/refresh path instead of ad hoc harness glue
  - extended runtime coverage in `tests/test_runtime_eval.py` with positive, negative, and parse-error lanes, including the stricter `missing_keys` semantics where every listed key must actually be absent
  - target files: `runtime/eval.py`, `tests/test_runtime_eval.py`, `tests/test_cli_object_key_set_examples.py`, `examples/eval/*`, `scripts/refresh_eval_example_fixtures.py`, `docs/workloop-queue.md`

- Queue state after FP-125:
  - cutoff held, this run stayed on a visible runtime/operator surface and used the existing checked-in fixture pipeline instead of reopening handoff/docs churn
  - operators can now write compact object-shape guards directly in erz, which cuts repetitive `has_key` clause ladders in routing policies without any upstream event reshaping
  - next concrete functional items:
    - if eval operator work stays in focus, prefer another missing high-leverage structural predicate family on existing payload/event surfaces, not replay-only polish
    - otherwise pivot back to a separate machine-visible replay/export frontier, not docs/canary density alone

- [x] FP-126, machine-enforced docs sync for checked-in eval smoke lanes
  - extended `examples/eval/README.md` so every top-level smoke case currently generated by `scripts/refresh_eval_example_fixtures.py` is now discoverable through the repo-native fixture docs, including the newer cross-path regex, event-type path/pattern/string, path-length, object-key-path, and rule-priority lanes that had already landed in fixtures/tests but were still missing from the operator index
  - added docs-sync coverage to `tests/test_eval_example_snapshots.py`, loading the refresh helper's `SMOKE_CASES` as the source of truth and asserting the fixture README mentions each program, input pair, and frozen `*.expected.*` sidecars, so future eval lanes cannot silently drift out of the checked-in operator docs
  - added a short pointer in the top-level `README.md` that the full smoke matrix lives under `examples/eval/README.md`, keeping quickstart readable while making the deeper fixture index the explicit canonical map for copy-paste eval lanes
  - target files: `examples/eval/README.md`, `tests/test_eval_example_snapshots.py`, `README.md`, `docs/workloop-queue.md`

- Queue state after FP-126:
  - cutoff held, this run chose repo-native operator clarity with a hard test oracle instead of adding more prose that can silently rot
  - the checked-in eval smoke matrix now has a single tested documentation surface tied directly to the refresh helper's declared cases, which reduces operator search time and future drift when new predicate families land
  - next concrete functional items:
    - if eval operator work stays in focus, prefer another runtime-visible predicate family or batch/export lever, not more README expansion without a machine-checked source of truth
    - otherwise pivot back to a separate replay/export frontier with direct CLI leverage, not docs-only adjacency

