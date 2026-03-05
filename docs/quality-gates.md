# Quality Gates (Sprint-2 to Sprint-6)

This document defines practical pass/fail gates for deterministic integration hardening.

## How to run

From repo root:

```bash
# fast lane (inner loop): unit tests only
./scripts/check-unit.sh

# full lane (pre-merge/release): all active gates
./scripts/check.sh

# equivalent full-lane wrapper (identical gate set)
./scripts/check-full.sh
```

The scripts are dependency-light (Python stdlib + existing project code).
Use `check-unit.sh` for quick inner-loop feedback. Use `check.sh` (or equivalently `check-full.sh`) before merge/release.
`check-unit.sh` output contract is fixed: emit `[unit] Running unittest suite` at start, emit `[unit] Passed` only on success.
`check-unit.sh` stderr contract is fixed: forward unittest stderr unchanged on failures, remain stderr-silent on successful runs.
`check-unit.sh` banner exact-text contract is locked by canaries: both start and success banners must remain byte-identical single-occurrence literals (no whitespace-padded variants).

Canary contract summary (compacted):

- `check-unit.sh` behavior is locked across **pass**, **generic unittest failure**, and **unexpected invocation** modes.
- Output-channel rules are strict: stdout banners stay canonical, stderr is silent on pass, and failure diagnostics remain byte-identical on stderr only.
- Line-ending and segmentation invariants are locked for both channels (LF-only framing, split/splitlines parity, terminal newline cardinality, no CR/CRLF drift).
- Invocation semantics are locked: exactly one unittest invocation, stable argv (`python3 -m unittest discover -s tests -v`), no retry/replay.
- Unexpected-invocation diagnostics are locked byte-for-byte, including prefix text (`unexpected invocation: `), token boundaries, separator count, and newline behavior.
- Full-lane entrypoints (`check.sh`, `check-full.sh`) share identical helper ordering and short-circuit boundaries.
- Full-lane stdout banners are locked by exact-text canaries (`[1/7]`..`[7/7]` and `All active quality gates passed.`), including failure terminal-step boundaries for benchmark/trace/migration helper exits.
- Stderr passthrough exactness (including trailing newline) is locked for benchmark, trace, and migration helper failure paths.
- Deep parity expansion from WLP-314 through WLP-401 is preserved as the terminal fixed-point closure chain, no additional canary layers beyond WLP-401 per v0.1 exit rule.
- Canonical test coverage lives in `tests/test_quality_gate_scripts.py` (script-level contracts) plus release evidence tests in `tests/test_release_snapshot.py`.

### Direct helper invocation contract

You can run helper gates directly for focused debugging from repo root:

```bash
python3 scripts/gates/benchmark_gate.py
python3 scripts/gates/trace_contract_gate.py
python3 scripts/gates/migration_anchor_gate.py
```

Invocation assumptions:
- Current working directory is repo root, helper paths are repo-relative.
- Input files must exist at canonical locations (`bench/token-harness/results/latest.json`, `schema/ir.v0.1.schema.json`, `docs/migrations.md`, `docs/quality-gates.md`).
- Running from non-root cwd is expected to fail with canonical missing-input diagnostics (by design, for deterministic path resolution).

Non-root cwd error-path examples (expected):

```bash
# from a nested directory
python3 ../../scripts/gates/benchmark_gate.py
# -> gate failure [benchmark_gate]: Benchmark result file missing: bench/token-harness/results/latest.json

python3 ../../scripts/gates/trace_contract_gate.py
# -> gate failure [trace_contract_gate]: Schema file missing: schema/ir.v0.1.schema.json

python3 ../../scripts/gates/migration_anchor_gate.py
# -> gate failure [migration_anchor_gate]: Schema file missing: schema/ir.v0.1.schema.json
```

Failure semantics:
- Non-zero exit means gate failure.
- Failure diagnostics are normalized with prefix `gate failure [<gate_name>]: ...` for grep-friendly triage.
- Helper gates print fail-fast diagnostics to stderr, and keep informational success/metric lines on stdout.
- `scripts/check.sh` aggregates helper failures without rewriting helper diagnostics.

### Helper diagnostics matrix (compact)

Canonical helper failure line format:
- `gate failure [<gate_name>]: <category/detail>`
- `<category/detail>` starts with a stable category phrase, followed by contextual detail as needed.

| Helper gate | Required inputs (canonical) | Canonical failure categories (representative) | Stream behavior (stdout/stderr) |
| --- | --- | --- | --- |
| `benchmark_gate.py` | `bench/token-harness/results/latest.json`; `summary.totals.{baseline_tokens, erz_tokens, token_saving_pct}`; `summary.target.{token_saving_pct, met}`; `summary.pair_count`; explicit `root.pairs` list key; `pairs[*].name` key (present + string, calibration floor counts only exact lowercase `calibration_` prefix via case-sensitive match) | `Benchmark result file missing`; `Benchmark result file is not valid JSON`; `Malformed benchmark summary` (for example: Malformed benchmark summary: expected object at `root`); `Malformed benchmark payload`; `Benchmark token-saving target not met`; `Benchmark fixture floor not met`; `Calibration fixture floor not met` | Metrics/status lines go to stdout. Parse/contract/threshold failures emit one canonical `gate failure [...]` line on stderr. |
| `trace_contract_gate.py` | `schema/ir.v0.1.schema.json` (`$defs.trace.required`, `$defs.trace.properties`); runtime `TRACE_REQUIRED_FIELDS`; runtime `TRACE_OPTIONAL_FIELDS` | `Schema file missing`; `Schema file is not valid JSON`; `Malformed schema`; `trace contract drift detected` | Success confirmation goes to stdout. All failures are fail-fast on stderr with canonical prefix. |
| `migration_anchor_gate.py` | `schema/ir.v0.1.schema.json`; `docs/migrations.md` anchor lines (`- Gate anchor trace required:`, `- Gate anchor trace optional:`, `- Gate anchor profiles:`) + migration-entry headings (`## <from> -> <to>`, outside fenced code blocks); `docs/quality-gates.md` anchor line (`- Gate anchor profiles:`); runtime `TRACE_REQUIRED_FIELDS`; runtime `TRACE_OPTIONAL_FIELDS`; exact normalized profile-heading matching (full heading or trailing parenthetical token, no substring fallback) | `Schema file missing`; `Schema file is not valid JSON`; `Malformed migration gate input`; `Required doc missing`; `<doc>: missing required anchor line`; `<doc>: anchor line has no backticked tokens`; `<doc>: anchor line has duplicate tokens`; `trace required field anchor drift`; `trace optional field anchor drift`; `active profile anchor drift between docs/migrations.md and docs/quality-gates.md`; `profile anchor missing from migration headings`; `profile anchor maps to multiple migration headings` | Success confirmation goes to stdout. All failures are fail-fast on stderr with canonical prefix. |

---

## Baseline Gates (always active)

A change **passes** only if all baseline gates below pass.

### Gate B1: CLI smoke for compact subset
- **What runs:** `erz validate`, `erz parse`, `erz fmt` on `examples/sample.erz`
- **Checks:**
  - `validate` prints `valid`
  - parsing formatted output yields the same canonical JSON as original input
  - formatting is idempotent (`fmt(fmt(x)) == fmt(x)`)
- **Fail if:** any command exits non-zero or roundtrip/idempotence check differs.

### Gate B2: Unit tests
- **What runs:** `python3 -m unittest discover -s tests -v`
- **Checks:** parser/formatter/CLI/runtime/schema behavior including determinism and compatibility tests.
- **Fail if:** any test fails.

### Gate B3: Few-shot parser corpus sanity
- **What runs:** `python3 scripts/validate_fewshot.py`
- **Checks:** all curated examples still match parser contract.
- **Fail if:** any case drifts from expected result.

### Gate B4: Benchmark harness execution and token/coverage target
- **What runs:** `python3 bench/token-harness/measure.py` + `python3 scripts/gates/benchmark_gate.py` (via `scripts/check.sh`).
- **Checks:**
  - `bench/token-harness/results/latest.json` is produced
  - `summary.target.met == true` (currently: total token saving >= 25%)
  - benchmark fixture pair floor is met (`summary.pair_count >= 10`)
  - benchmark payload provides explicit `pairs` list key
  - `summary.pair_count` is consistent with actual payload rows (`len(pairs)`)
  - every `pairs[*]` row carries `name` as a required string key
  - calibration fixture floor is met (`>= 2` fixture pairs with exact lowercase `calibration_` prefix; case-sensitive, so `Calibration_`/`CALIBRATION_` do not count)
- **Fail if:** benchmark execution fails, token target is not met, summary/payload counts drift, or fixture coverage floors are violated.

### Gate B5: Runtime/Schema trace contract sync (post-Sprint-5)
- **What runs:** `python3 scripts/gates/trace_contract_gate.py` (via `scripts/check.sh`).
- **Checks:** runtime trace required/optional fields are represented in `schema/ir.v0.1.schema.json`.
- **Fail if:** runtime and schema trace contracts drift.

### Gate B6: Migration/compatibility discipline anchors (WLP-020)
- **What runs:** `python3 scripts/gates/migration_anchor_gate.py` (via `scripts/check.sh`).
- **Checks:**
  - `docs/migrations.md` gate-anchor trace required/optional lists match active runtime+schema trace field names.
  - `docs/migrations.md` and `docs/quality-gates.md` gate-anchor profile references are byte-identical.
  - each anchored active profile is present in exactly one migration-entry heading (`## <from> -> <to>`, outside fenced code blocks; no template/example heading matches).
  - profile-heading matching is normalized exact-match only (collapsed whitespace allowed), either full heading or trailing parenthetical token, no substring fallback.
- **Fail if:** migration/profile anchors drift from active contracts or a profile anchor maps to multiple headings.

### Gate B7: Exit code contract
- **What runs:** aggregated via `scripts/check.sh` (including `scripts/gates/*.py` helper invocations).
- **Checks:** script exits `0` only when all gates pass.
- **Fail if:** script exits non-zero.

### Gate B8: Machine-readable error envelope contract (v0.2 prep)
- **What runs:** `python3 -m unittest discover -s tests -v` (especially `tests/test_cli.py`, `tests/test_runtime_eval.py`, and envelope-mapping coverage in `tests/test_integration_pipeline.py`).
- **Checks:**
  - `erz parse`/`erz validate`/`erz pack`/`erz unpack` support optional `--json-errors` mode while preserving default human-readable errors.
  - JSON error envelope shape is stable: `code`, `stage`, `message`, `span`, `hint`, `details`.
  - Snapshot parity lane covers parse/validate/transform/runtime/io mappings with fixture-backed deterministic stderr snapshots.
  - Command/detail matrix canary locks deterministic `details.command` mapping across parse/validate/pack/unpack/io failure lanes.
  - `details` ordered-item contract is explicit and stable (`error_type`, then `command`) across snapshot parity lanes.
  - Transform snapshot lane includes two span-bearing unpack failure fixtures (`transform_unpack_unexpected_char.stderr`, `transform_unpack_unexpected_char_secondary.stderr`) and locks deterministic `span.position` parity for distinct position signatures.
  - Dual transform span-fixture contract is migration-visible and name-stable: `transform_unpack_unexpected_char.stderr` maps to `position 114`, `transform_unpack_unexpected_char_secondary.stderr` maps to `position 139`.
  - Runtime adapter (`eval_policies_envelope`) keeps shape invariants: success omits `error`, failure returns deterministic empty `actions`/`trace` plus stable runtime envelope.
  - Runtime adapter code mapping triad is locked: `TypeError -> ERZ_RUNTIME_CONTRACT`, `ValueError -> ERZ_RUNTIME_VALUE`, and non-contract internal failures are re-raised unchanged.
  - Runtime envelope rendering parity canary keeps `runtime_contract.stderr` and `runtime_value.stderr` byte-stable when produced via `render_error_envelope_json(...)`; these fixture names are canonical for adapter/direct-builder parity checks.
  - Runtime stage/details-command parity is locked across adapter + direct builder lanes by comparing adapter failures against direct `build_error_envelope(...)` outputs (`stage="runtime"`, `details.command="eval"`).
  - Runtime envelope consumers should branch on `error` presence as the failure signal, not on empty `actions`/`trace`.
  - Docs-canary coverage triage index (FN-031..FN-035): cross-doc parity wording (README/runtime), canonical runtime snapshot-name parity, Gate B8 fail-line wording/singularity, and README/runtime token-literal parity.
- **Fail if:** JSON mode drifts, field shape/order changes, `details` ordered-item invariants drift, transform span snapshots drift, adapter-shape invariants regress, non-contract passthrough behavior regresses, runtime stage/details-command parity across adapter/direct-builder lanes regresses, runtime consumer contract guidance drifts, or stable-code mapping/snapshots drift.

## Active compatibility profile references (machine-checked)

- Gate anchor profiles: `Sprint-5 calibration additive profile`, `Sprint-6 compatibility/ref-hardening profile`

---

## v0.1 release-close benchmark snapshot (2026-03-02)

Run reference:
- Command: `./scripts/check.sh`
- Executed: 2026-03-02 21:50-21:52 +0100
- Gate result: pass (`[7/7] Quality gates complete`, `All active quality gates passed.`)

Benchmark threshold evidence (Gate B4):
- Baseline tokens: `1389`
- erz tokens: `709`
- Token saving: `48.96%`
- Target: `>= 25.0%` -> `met`
- Fixture floor: `10/10` pairs -> `met`
- Calibration fixture floor: `2/2` pairs -> `met`

Release-close cross-links:
- Acceptance freeze checklist: `docs/acceptance-metrics.md` ("v0.1 release-close checklist")
- Migration freeze note: `docs/migrations.md` ("v0.1 release-close freeze")
- Ship status summary: `docs/review-sprint1.md` ("v0.1 ship-ready summary")

Release evidence automation:
- Optional post-pass hook (opt-in, `scripts/check.sh` unchanged by default): `./scripts/check.sh && python3 scripts/release_snapshot.py`.
- Hook-line boundary/order contract (RL-040/RL-041): keep exactly one standalone `Optional post-pass hook` bullet and keep it before the `Dated snapshots are written...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_040_quality_gates_release_hook_bullet_line_singularity_boundary_canary`, `test_rl_041_quality_gates_release_hook_before_dated_snapshot_bullet_order_canary`).
- Dated snapshots are written to `docs/release-artifacts/release-snapshot-<UTCSTAMP>.{json,md}` and mirrored to `docs/release-artifacts/latest.{json,md}`.
- Dated-snapshot bullet boundary contract (RL-043/RL-044): keep exactly one standalone `Dated snapshots are written...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_043_quality_gates_dated_snapshot_bullet_singularity_canary`, `test_rl_044_quality_gates_dated_snapshot_bullet_line_boundary_canary`).
- Naming/latest-pointer/cleanup policy plus manual prune command snippets are indexed in `docs/release-artifacts/README.md`.
- Naming-policy bullet boundary contract (RL-046/RL-047): keep exactly one standalone `Naming/latest-pointer/cleanup policy...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_046_quality_gates_naming_policy_bullet_singularity_canary`, `test_rl_047_quality_gates_naming_policy_bullet_line_boundary_canary`).
- Release artifact index quickstart pointer is explicit and command-aligned with this release automation hook.
- Retention runbook shell-safety contract is explicit and ordered as a checklist: `repo-root` precondition, preserve `latest.*`, then prune dated snapshots only as matched `.json` + `.md` pairs.
- Source-of-truth rule: `bench/token-harness/results/latest.json` stays repo-pinned for non-mutating local gate runs, freshness is tracked via `docs/release-artifacts/latest.json`.
- Source-of-truth bullet boundary contract (RL-049/RL-050): keep exactly one standalone `Source-of-truth rule: ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_049_quality_gates_source_of_truth_rule_bullet_singularity_canary`, `test_rl_050_quality_gates_source_of_truth_rule_bullet_line_boundary_canary`).
- Hook execution is explicit/manual, no gate script invokes release snapshot export automatically.
- Quickstart pointers are mirrored in top-level onboarding docs (`README.md`, `bench/token-harness/README.md`) for discoverability.
- Quickstart-pointer bullet boundary contract (RL-052/RL-053): keep exactly one standalone `Quickstart pointers are mirrored in top-level onboarding docs ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_052_quality_gates_quickstart_pointer_bullet_singularity_canary`, `test_rl_053_quality_gates_quickstart_pointer_bullet_line_boundary_canary`).
- Release artifact JSON shape contract is locked by `tests/test_release_snapshot.py` (`test_latest_json_shape_contract_for_release_evidence`).
- Release-artifact-json-shape bullet boundary contract (RL-055/RL-056): keep exactly one standalone `Release artifact JSON shape contract is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_055_quality_gates_release_artifact_json_shape_bullet_singularity_canary`, `test_rl_056_quality_gates_release_artifact_json_shape_bullet_line_boundary_canary`).
- Checked-in freshness/parity canary is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_latest_json_contract_parity`).
- Checked-in-freshness/parity bullet boundary contract (RL-058/RL-059): keep exactly one standalone `Checked-in freshness/parity canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_058_quality_gates_checked_in_freshness_parity_bullet_singularity_canary`, `test_rl_059_quality_gates_checked_in_freshness_parity_bullet_line_boundary_canary`).
- Checked-in release markdown presence/source-marker canary is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_latest_md_presence_and_source_markers`).
- Checked-in-latest-md presence/source-marker bullet boundary contract (RL-061/RL-062): keep exactly one standalone `Checked-in release markdown presence/source-marker canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_061_quality_gates_checked_in_latest_md_presence_source_marker_bullet_singularity_canary`, `test_rl_062_quality_gates_checked_in_latest_md_presence_source_marker_bullet_line_boundary_canary`).
- Quickstart command parity canary for onboarding docs is locked by `tests/test_release_snapshot.py` (`test_release_evidence_quickstart_command_parity_docs`).
- Quickstart-command-parity bullet boundary contract (RL-064/RL-065): keep exactly one standalone `Quickstart command parity canary for onboarding docs is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_064_quality_gates_quickstart_command_parity_bullet_singularity_canary`, `test_rl_065_quality_gates_quickstart_command_parity_bullet_line_boundary_canary`).
- Release-evidence heading singularity canary is locked by `tests/test_release_snapshot.py` (`test_quality_gates_release_evidence_heading_singularity`).
- Release-evidence-heading-singularity bullet boundary contract (RL-067/RL-068): keep exactly one standalone `Release-evidence heading singularity canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_067_quality_gates_release_evidence_heading_singularity_bullet_singularity_canary`, `test_rl_068_quality_gates_release_evidence_heading_singularity_bullet_line_boundary_canary`).
- Heading-boundary canaries are locked by `tests/test_release_snapshot.py`, release-evidence heading must stay standalone (`test_quality_gates_release_evidence_heading_line_boundary`), and the artifact index title must remain the first non-empty line (`test_release_artifact_index_title_first_non_empty_line_boundary`).
- Heading-boundary-canaries bullet boundary contract (RL-070/RL-071): keep exactly one standalone `Heading-boundary canaries are locked by ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_070_quality_gates_heading_boundary_canaries_bullet_singularity_canary`, `test_rl_071_quality_gates_heading_boundary_canaries_bullet_line_boundary_canary`).
- Artifact-index line-boundary canaries are locked by `tests/test_release_snapshot.py`, quickstart heading must stay standalone (`test_release_artifact_index_quickstart_heading_line_boundary`), and the retention checklist marker must stay standalone (`test_release_artifact_index_retention_preconditions_anchor_marker_line_boundary`).
- Artifact-index-line-boundary-canaries bullet boundary contract (RL-073/RL-074): keep exactly one standalone `Artifact-index line-boundary canaries are locked by ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_073_quality_gates_artifact_index_line_boundary_canaries_bullet_singularity_canary`, `test_rl_074_quality_gates_artifact_index_line_boundary_canaries_bullet_line_boundary_canary`).
- Artifact-index order-boundary contract (RL-034/RL-035): keep `## Quickstart pointer` after `# Release Artifacts Index`, and keep `Preconditions checklist (execute in order before running commands):` after `## Quickstart pointer` to preserve stable release-evidence indexing.
- Artifact-index-order-boundary-contract bullet boundary contract (RL-076/RL-077): keep exactly one standalone `Artifact-index order-boundary contract (RL-034/RL-035): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_076_quality_gates_artifact_index_order_boundary_contract_bullet_singularity_canary`, `test_rl_077_quality_gates_artifact_index_order_boundary_contract_bullet_line_boundary_canary`).
- Artifact-index line-index order-boundary contract (RL-037/RL-038): keep the first `## Quickstart pointer` line index after the title heading line index, and keep the first `Preconditions checklist (execute in order before running commands):` line index after the quickstart heading line index to preserve stable release-evidence indexing.
- Artifact-index-line-index-order-boundary-contract bullet boundary contract (RL-079/RL-080): keep exactly one standalone `Artifact-index line-index order-boundary contract (RL-037/RL-038): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_079_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_singularity_canary`, `test_rl_080_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_line_boundary_canary`).
- Release artifact index title-heading presence/singularity canaries are locked by `tests/test_release_snapshot.py` (`test_release_artifact_index_title_heading_presence`, `test_release_artifact_index_title_heading_singularity`).
- Release-artifact-index-title-heading-presence/singularity bullet boundary contract (RL-082/RL-083): keep exactly one standalone `Release artifact index title-heading presence/singularity canaries are locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_082_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_singularity_canary`, `test_rl_083_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_line_boundary_canary`).
- Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_source_of_truth_rule_parity_between_latest_json_and_latest_md`).
- Source-of-truth-string-parity bullet boundary contract (RL-085/RL-086): keep exactly one standalone `Source-of-truth string parity canary between checked-in latest.json and latest.md is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_085_quality_gates_source_of_truth_string_parity_bullet_singularity_canary`, `test_rl_086_quality_gates_source_of_truth_string_parity_bullet_line_boundary_canary`).
- Source-of-truth-string-parity bullet boundary contract (RL-088/RL-089): keep exactly one standalone `Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary`, `test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary`).
- Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): keep the RL-088/RL-089 boundary-contract bullet with exactly one ``latest.json`` + ``latest.md`` token pair and exactly one reference each to `test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary` and `test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary`, locked by `tests/test_release_snapshot.py` (`test_rl_091_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_token_literal_canary`, `test_rl_092_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_test_reference_pair_canary`).
- Source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095): keep exactly one standalone `Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_094_quality_gates_source_of_truth_string_parity_token_reference_note_singularity_canary`, `test_rl_095_quality_gates_source_of_truth_string_parity_token_reference_note_line_boundary_canary`).

---

## Sprint-3 hardening gates (still relevant)

Sprint-3 extends baseline confidence requirements.

### Gate S3-1: Fixture breadth
- Benchmark corpus should stay at **>= 10** representative fixture pairs.
- Fail if fixture count drops below threshold.

### Gate S3-2: Roundtrip determinism at corpus level
- Parse/format/parse determinism for full supported fixture set.
- Fail on any canonical mismatch.

### Gate S3-3: Runtime determinism replay
- Same input + same version must produce byte-identical actions + trace.
- Fail on any replay mismatch.

---

## Sprint-5 integration hardening focus

Current focus after the Sprint-5 calibration additive profile:

1. Keep trace contract and schema in sync (`calibrated_probability` remains optional and bounded to `[0.0, 1.0]`).
2. Preserve backward compatibility when calibration is omitted.
3. Enforce migration discipline for strict consumers (trace/object-shape validators).
4. Keep quality gates dependency-light and deterministic.

## Sprint-6 compatibility/ref-hardening focus

Current focus for the Sprint-6 compatibility/ref-hardening profile:

1. Keep canonical output stable while accepting legacy aliases (`pack` + `unpack`).
2. Enforce ref-id policy consistently (`[A-Za-z_][A-Za-z0-9_-]*`) across parser + transformer.
3. Reject duplicate/colliding refs deterministically (including `id` vs `@id` collisions).
4. Require reference resolution for all used `@id` pointers.

### Gate S6-1: Alias compatibility coverage
- **What runs:** `python3 -m unittest discover -s tests -v` (especially `tests/test_pack_unpack.py`).
- **Checks:** legacy aliases and payload-wrapped keys still map to canonical event/action/decision fields, including ref-pointer/value alias forms and refs-list normalization.
- **Fail if:** alias-based pack/unpack compatibility drifts.

### Gate S6-2: Ref hardening coverage
- **What runs:** `python3 -m unittest discover -s tests -v` (especially `tests/test_pack_unpack.py` + `tests/test_compact.py`).
- **Checks:** invalid ids, duplicate ids, canonical collisions (`id` + `@id`), and unresolved refs fail hard.
- **Fail if:** any ref-policy rejection path regresses.

---

## Notes

- Gates intentionally avoid new dependencies.
- Benchmarks may use `tiktoken` if present, otherwise fallback estimation; gate uses the existing harness summary target.
- `scripts/check.sh` restores benchmark result artifacts after execution so local gate runs stay non-mutating.
- `bench/token-harness/results/latest.json` is intentionally repo-pinned for gate determinism, `docs/release-artifacts/latest.json` is the freshness source-of-truth.
- These gates are designed to block unsafe syntax growth until parser/runtime behavior stays deterministic and measurable.
