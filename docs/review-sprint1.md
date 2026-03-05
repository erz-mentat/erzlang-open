# Sprint-1 Architecture/Risk Review (erzlang)

Scope reviewed against current repo (`README.md`, `docs/*`, `spec/grammar-card.md`, `ir/models.py`, `runtime/eval.py`, `cli/main.py`, `bench/token-harness/*`, `tests/test_smoke.py`).

## v0.1 ship-ready summary (2026-03-02)

Status: **ship-ready for v0.1 scope**.

What was revalidated in release-close pass:
- `./scripts/check.sh` passed end-to-end (`[1/7]` through `[7/7]`).
- Benchmark gate reconfirmed: `1389 -> 709` tokens, `48.96%` saving, target `>= 25.0%` met.
- Fixture floors reconfirmed: `10/10` total pairs and `2/2` calibration-prefixed pairs.
- Runtime/schema trace contract gate passed.
- Migration/profile anchor gate passed.

Non-blocking follow-ups (post-ship, not release blockers):
1. ✅ Replaced stale benchmark metadata timestamp flow with repo-pinned benchmark payload + release-artifact freshness source-of-truth.
2. ✅ Added one-command release evidence exporter: `python3 scripts/release_snapshot.py`.
3. ✅ Compacted repetitive canary narrative in `docs/quality-gates.md` without changing gate contracts.
4. Recommended post-pass release flow remains opt-in: `./scripts/check.sh && python3 scripts/release_snapshot.py` (explicit export wrapper, no default hook inside `scripts/check.sh`).

---

## What is solid

1. **Clear product boundary and kill criterion are documented early.**
   - DSL-only scope, deterministic runtime target, trace-first output, and 25% token kill gate are explicit (`README.md`, `docs/scope-v0.md`, `docs/acceptance-metrics.md`).

2. **Token benchmark harness exists and is runnable now.**
   - `bench/token-harness/measure.py` runs and produces `results/latest.json`.
   - Current fixtures show average token saving **46.21%** (2 pairs), above the 25% gate (`bench/token-harness/results/latest.json`).

3. **Core domain vocabulary is started in IR models.**
   - `Ref`, `Event`, `Rule`, `Action`, `TraceStep` dataclasses exist (`ir/models.py`), giving a base for canonical IR.

4. **Deterministic intent is reflected in runtime stub.**
   - Evaluator has no side effects and returns actions + trace (`runtime/eval.py`).

---

## Top 5 risks (current)

1. **Parser/printer are not implemented yet.**
   - CLI commands are placeholders (`cli/main.py`), grammar is still draft (`spec/grammar-card.md`), but roundtrip stability is a primary metric (`docs/acceptance-metrics.md`).

2. **Canonical IR contract is incomplete.**
   - Models exist, but no Program-level schema, versioned IR format, or migration policy is implemented (`ir/models.py` vs migration gate in `docs/acceptance-metrics.md`).

3. **Runtime semantics are too placeholder for policy guarantees.**
   - `eval_policies` currently fires any rule when event type exists; no clause semantics, tie-breaking, or policy safety behavior (`runtime/eval.py`).

4. **Trace contract is not enforced end-to-end.**
   - Trace is emitted as raw dicts, not validated against `TraceStep`; required fields in metrics doc are only partially guaranteed (`runtime/eval.py`, `ir/models.py`, `docs/acceptance-metrics.md`).

5. **Quality gates are not yet real gates.**
   - Test suite is only `assert True` (`tests/test_smoke.py`) and `pytest` is not declared in `pyproject.toml`; regression risk is high.

---

## Concrete mitigations for next 2 sprints

### Sprint-2 (must land)
- **Freeze minimal v0 grammar + parser** for `header`, `ev`, `rf`, `pl` blocks from existing fixtures.
- **Add canonical IR envelope** (`ir_version`, `program`, `events`, `rules`, `refs`) with strict field ordering + unknown-key failure.
- **Define deterministic eval rules** (clause evaluation order, stable rule order, deterministic score behavior).
- **Enforce typed trace output** (always `rule_id`, `matched_clauses`, optional score/prob fields with explicit optional-field policy, no implicit null coercion).
- **Replace smoke test with boundary tests**: parser success/failure fixtures, runtime determinism replay, trace shape validation.

### Sprint-3 (hardening)
- **Implement printer + roundtrip tests** (parse -> IR -> print -> parse).
- **Expand benchmark set** beyond 2 fixtures (at least 10 diverse event/policy packs).
- **Make benchmark reproducible** by pinning tokenizer path (prefer `tiktoken`, fail loudly or dual-report when fallback is used).
- **Add IR migration notes + fixture versioning** for every IR change.
- **Wire review gate script** that fails CI on: determinism mismatch, roundtrip failures, missing trace fields, token target drift.

---

## Definition-of-Done checks

### Sprint-2 DoD
- [ ] `erz parse` works for current compact fixture syntax and rejects unknown keys.
- [ ] Canonical IR schema is documented and validated in tests.
- [ ] `eval_policies` deterministic replay test passes (same input/version => byte-identical actions+trace).
- [ ] Trace tests verify required fields per fired rule.
- [ ] Test suite includes meaningful parser/runtime tests (not only smoke).

### Sprint-3 DoD
- [ ] `erz fmt`/printer exists and roundtrip fixtures pass 100%.
- [ ] Benchmark corpus >= 10 pairs with reproducible token counting path.
- [ ] Kill criterion report is generated in CI artifact (`>=25%` token saving or explicit exception decision).
- [ ] IR migration notes are present for any schema change.
- [ ] Sprint gate script blocks merge on determinism/roundtrip/trace regressions.

---

## Key decision recommendation

For the next 2 sprints, **prioritize parser+IR+deterministic semantics over syntax expansion**. The project already has promising token signal; the main schedule risk is missing enforceable contracts (IR, trace, tests), not missing language surface area.
