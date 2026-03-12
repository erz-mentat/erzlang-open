# Runtime Determinism Contract (Rule Engine v0)

`runtime.eval.eval_policies` is the deterministic, pure-evaluation Rule Engine for the current v0 runtime subset.

## Operator quickstart (eval lane)

Fast path for operators:

1. Program file wählen, z. B. `examples/eval/program.erz`.
2. Event-JSON wählen, z. B. `examples/eval/event-ok.json`.
3. `erz eval <program> --input <event>` ausführen.
4. `actions` für Output lesen, `trace` für Nachvollziehbarkeit prüfen.
5. Optional für CI-Logs: `--summary --summary-policy` nutzen, dann ist `policy=<...> exit=<0|1>` immer dabei.
6. Optional für Replay-Lanes: `--batch <dir>` nutzen, dann werden alle `*.json` deterministisch nach Dateiname aggregiert.
7. Optional für Batch-Filter: `--include <glob>` und/oder `--exclude <glob>` nutzen (include vor exclude, Match über Dateiname).
8. Optional für Batch-Triage direkt im JSON-Envelope: `--batch-summary-rule-counts` und/oder `--batch-summary-action-kind-counts` ergänzen, dann enthält `summary` deterministische per-Rule- bzw. per-Action-Kind-Zähler, ohne den `--summary`-Textmodus zu verändern.
9. Optional für CI-Artefakte im Batch-Lane: `--batch-output <dir>` nutzen, dann entstehen pro Event Envelope-Dateien plus `summary.json`.
10. Optional für schmale Triage-Artefakte: `--batch-output-errors-only` ergänzen, dann werden nur Fehler-/No-Action-Events persistiert.
11. Optional für Integritätsprüfungen ohne Nachrechnen: `--batch-output-manifest` ergänzen, dann enthält `summary.json` ein deterministisches `artifact_sha256`-Mapping für geschriebene Event-Artefakte.
12. Optional für große Runs: `--batch-output-layout by-status` ergänzen, dann landen Event-Artefakte unter `ok/`, `no-action/` oder `error/`.
13. Optional für CI-Run-Traceability: `--batch-output-run-id <id>` ergänzen, dann enthält `summary.json` zusätzlich `run.id`.
14. Optional für Dashboard-Exports ohne stdout-Drift: `--batch-output-summary-file <path>` ergänzen, dann wird das Batch-Aggregat byte-identisch zu stdout in eine Datei geschrieben.
15. Optional für generation-time Integrity-Gates: `--batch-output-self-verify` setzen, dann verifiziert `erz eval` frisch geschriebene Batch-Artefakte sofort vor Handoff und schreibt das Manifest automatisch.
16. Optional für generation-time Strict-Handoff: `--batch-output-self-verify-strict` ergänzen, dann nutzt der Self-Verify-Lauf dieselben Strict-Profile/Selectoren (`--batch-output-verify-profile`, `--batch-output-verify-expected-*`, `--batch-output-verify-require-run-id`) direkt beim Generieren.
17. Optional für nachgelagerte Integrity-Gates: `--batch-output-verify <dir>` nutzen, dann prüft `erz eval` Manifest-Hashes deterministisch, JSON enthält dabei zusätzlich `selected_artifacts_count` und `selected_manifest_entries_count`, `--summary` ergänzt `selected=<n>` und `selected_manifest=<n>`.
18. Optional für Candidate-vs-Baseline-Regressionsgates: `--batch-output-compare <candidate-dir> --batch-output-compare-against <baseline-dir>` nutzen, dann vergleicht `erz eval` zwei Batch-Artifact-Sets direkt auf Byte- und Metadaten-Drift, ohne Manifestpflicht; identische Empty-Lanes mit `event_artifacts=[]` bleiben dabei gültig und liefern deterministisch `compared=0 matched=0`; mit `--batch-output-compare-include <glob>` und `--batch-output-compare-exclude <glob>` lässt sich die Compare-Lane auf ein deterministisches Artifact-Subset beschränken, wenn `artifact_sha256` vorhanden ist, wird die Mapping-Drift für dasselbe Subset ebenfalls geprüft, bewusst ignoriert bleibt nur `run.id`, damit getrennte CI-Runs mit verschiedenen IDs sauber vergleichbar bleiben; JSON ergänzt dafür `selected_baseline_artifacts_count` und `selected_candidate_artifacts_count`, `--summary` ergänzt `selected_baseline=<n>` und `selected_candidate=<n>`. Mit `--batch-output-compare-strict` plus `--batch-output-compare-expected-status|compared|matched|changed|baseline-only|candidate-only|missing-baseline|missing-candidate|metadata-mismatches|selected-*` kann dieselbe Lane erwartete Drift exakt als Gate ausdrücken. Für wiederkehrende CI-Verträge gibt es zusätzlich `--batch-output-compare-profile <clean|metadata-only|expected-asymmetric-drift>`, explizite `--batch-output-compare-expected-*` Werte überschreiben dabei Preset-Defaults. `compare_status` hält den rohen Driftstatus fest, `status` zeigt den Strict-Gate-Ausgang, `strict_profile_mismatches` erklären Abweichungen, und `--summary` ergänzt `strict_mismatches=<n>`.
19. Optional für generation-time Baseline-Gates ohne zweiten Compare-Command: `--batch-output <candidate-dir> --batch-output-self-compare-against <baseline-dir>` nutzen, dann vergleicht `erz eval` die frisch geschriebenen Artefakte direkt vor dem Handoff gegen eine Baseline, ohne den normalen Batch-stdout zu verändern; bei Drift stoppt der Lauf mit einem deterministischen Fehler noch vor dem Handoff. Trägt die Baseline `artifact_sha256`, wird dieses Mapping mitverglichen und Self-Compare schreibt für denselben Candidate-Lauf automatisch ebenfalls ein Manifest.
20. Optional für erwartete generation-time Drift: `--batch-output-self-compare-strict` ergänzen, dann nutzt dieselbe Handoff-Lane die vorhandenen Compare-Strict-Verträge (`--batch-output-compare-profile`, `--batch-output-compare-expected-*`) direkt beim Generieren; `compare_status` bleibt der rohe Driftstatus, `status` der Strict-Gate-Ausgang, inklusive Metadaten-Drift gegen manifesttragende Baselines. Praktisch heißt das: mit oder ohne explizites `--batch-output-manifest` landet derselbe Self-Compare-Handoff bei manifesttragenden Baselines auf demselben Candidate-Manifest, ohne Baseline bleibt Manifest-Schreiben opt-in.
21. Optional für policy-gebundene CI-Gates nachgelagert: `--batch-output-verify-strict` aktivieren, optional mit erwarteten Profilwerten (`--batch-output-verify-expected-mode`, `--batch-output-verify-expected-layout`, `--batch-output-verify-expected-run-id-pattern`, `--batch-output-verify-expected-event-count`, `--batch-output-verify-expected-verified-count`, `--batch-output-verify-expected-checked-count`, `--batch-output-verify-expected-missing-count`, `--batch-output-verify-expected-mismatched-count`, `--batch-output-verify-expected-manifest-missing-count`, `--batch-output-verify-expected-invalid-hashes-count`, `--batch-output-verify-expected-unexpected-manifest-count`, `--batch-output-verify-expected-status`, `--batch-output-verify-expected-strict-mismatches-count`, `--batch-output-verify-expected-event-artifact-count`, `--batch-output-verify-expected-manifest-entry-count`, `--batch-output-verify-expected-selected-artifact-count`, `--batch-output-verify-expected-manifest-selected-entry-count`, `--batch-output-verify-require-run-id`).
22. Optional für Verify-Lane-Dashboard-Exports ohne stdout-Drift: `--batch-output-verify-summary-file <path>` nutzen, dann wird der Verify-Output (JSON oder `--summary`, inklusive Selected-Scope-Zählern) byte-identisch zu stdout in eine Datei geschrieben.
23. Optional für Compare-Lane-Dashboard-Exports ohne stdout-Drift: `--batch-output-compare-summary-file <path>` nutzen, dann wird der Compare-Output, JSON oder `--summary`, byte-identisch zu stdout in eine Datei geschrieben, und im Self-Compare-Lane landet derselbe Compare-Output in der Datei, während stdout beim normalen Eval-Output bleibt.
24. Optional für große Verify-Lanes: `--batch-output-verify-include <glob>` und/oder `--batch-output-verify-exclude <glob>` nutzen (include vor exclude, Match über relative Artifact-Pfade aus `summary.json`).
25. Optional für Automation-Traceability im Single-Event-Lane: `--meta` aktivieren, optional `--generated-at <timestamp>` setzen.
26. Optional für checked-in Program Packs: `erz pack-replay <pack-dir>` nutzen, dann werden Fixture-Matrix-Baselines und Inline-Statement-Baselines deterministisch gegen das Pack-Programm geprüft, `--fixture <id>` bleibt repeatable für exakte Fälle, `--include-fixture <glob>` und `--exclude-fixture <glob>` bauen deterministische Multi-Case-Slices, immer in Pack-Reihenfolge, include/exakt zuerst, exclude danach; `--fixture-class <ok|expectation_mismatch|runtime_error>` filtert den replayten Slice danach deterministisch auf Replay-Klassen; `--summary` liefert dafür bei Selektion kompakt `fixtures=<selected>/<total>` plus `fixture_classes=ok:<n>,expectation_mismatch:<n>,runtime_error:<n>`, und das JSON-Envelope exportiert dieselbe exklusive Klassensicht pro Eintrag unter `fixtures[].fixture_class`, aggregiert unter `summary.fixture_class_counts`, plus die zugehörigen deterministischen Fixture-IDs unter `summary.fixture_class_ids`; `--summary-file <path>` schreibt dieselbe kompakte Summary-Zeile für jeden Pack-Run zusätzlich in eine Datei, `--json-file <path>` schreibt invers dazu immer das volle JSON-Envelope in eine Sidecar-Datei, sodass Summary-stdout plus JSON-Handoff in einem Lauf first-class werden, `--fixture-class-summary-file <path>` bleibt als engere Kompatibilitätsvariante für fixture-class-gefilterte Läufe erhalten, während `--output <path>` weiterhin denselben Replay-Output wie stdout spiegelt. Für den üblichen Green-CI-Lauf reicht `--strict-profile clean`, das Strict-Replay automatisch aktiviert und `rule_source_status=ok` plus null `mismatch_count`, `expectation_mismatch_count` und `runtime_error_count` absichert, ohne dass jede checked-in Pack-ID als `--expected-*`-Bundle ausgeschrieben werden muss. Für die drei checked-in Packs gibt es zusätzlich `--strict-profile ingest-normalize-clean`, `dedup-cluster-clean` und `alert-routing-clean`; diese Presets pinnen neben der grünen Basis auch `pack_id`, `baseline_shape`, `total_fixture_count` und das volle `fixture_class_counts`-Histogramm, damit ein kompletter Pack-Green-Gate auf einen stabilen einzelnen Preset-Namen schrumpft. Für exakte CI-Verträge ergänzt `--strict` beziehungsweise `--strict-profile <preset>` denselben Replay-Lauf weiterhin um `--expected-pack-id <pack-id>`, `--expected-baseline-shape <fixture-matrix|inline-statements>`, `--expected-fixture-count`, `--expected-total-fixture-count`, repeatable `--expected-selected-fixture <id>`, repeatable `--expected-ok-fixture <id>`, repeatable `--expected-expectation-mismatch-fixture <id>`, repeatable `--expected-runtime-error-fixture <id>`, `--expected-fixture-class-counts ok=<n>,expectation_mismatch=<n>,runtime_error=<n>`, `--expected-mismatch-count`, `--expected-expectation-mismatch-count`, `--expected-runtime-error-count` und `--expected-rule-source-status`; `--expected-fixture-count` bleibt bewusst der selektierte Replay-Slice, `--expected-total-fixture-count` hält die ungeschnittene Pack-Größe vor Selector-Filtering fest, `--expected-selected-fixture` prüft die finale deterministische `selected_fixture_ids`-Liste nach exact/glob/class-Filtern in kanonischer Pack-Reihenfolge, und die class-spezifischen Fixture-Selektoren prüfen zusätzlich die exakten `summary.fixture_class_ids.ok`, `summary.fixture_class_ids.expectation_mismatch` und `summary.fixture_class_ids.runtime_error`-Listen in derselben Reihenfolge. So wird sowohl Green-Partition-Drift als auch Failure-Partition-Drift auch bei stabilen Aggregaten sichtbar, ohne JSON nachträglich auseinanderzunehmen. `--expected-pack-id` zieht dieselbe Pack-Identitätsprüfung aus den spezialisierten `*-clean`-Presets in einen generischen Strict-Selector, damit auch eigene oder umbenannte Packs ohne Preset-Churn hart gatebar bleiben. `--expected-baseline-shape` ergänzt dieselbe harte Formprüfung für Fixture-Matrix- versus Inline-Statement-Baselines, damit Baseline-Form-Drift separat von Pack-ID oder Rule-Source-Drift sichtbar wird. Wenn exakte IDs unnötig spröde wären, kann `--expected-fixture-class-counts` stattdessen die gesamte deterministische Histogramm-Sicht unter `summary.fixture_class_counts` hart gatebar machen. `--expected-mismatch-count` prüft dabei bewusst die breite `summary.mismatch_count` inklusive `runtime_error`-Fixtures, während `--expected-expectation-mismatch-count` nur die reine Driftklasse `fixture_class=expectation_mismatch` absichert. `status` zeigt dann den Strict-Gate-Ausgang, `replay_status` hält den rohen Replay-Befund fest, und `--summary` ergänzt `strict_mismatches=<n>`. Inline-Packs leiten ihre Replay-Fixtures dabei direkt aus den eingebetteten `ev`-Samples plus dem Baseline-Regelsatz ab.

```bash
erz eval examples/eval/program.erz --input examples/eval/event-ok.json
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --summary --summary-policy
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-ok.json
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-no-action.json
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-no-action.json --summary
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-ok.json
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-no-action.json
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-no-action.json --summary
erz eval examples/eval/program.erz --batch examples/eval/batch
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-summary-action-kind-counts
erz eval examples/eval/program.erz --batch examples/eval/batch --include "*ok*.json"
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-errors-only
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-manifest --batch-output-layout by-status
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-run-id ci-run-2026-03-06T20-30-00Z
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output-summary-file /tmp/eval-batch-aggregate.json
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-candidate --batch-output-manifest --batch-output-self-compare-against /tmp/eval-batch-baseline --batch-output-compare-summary-file /tmp/eval-batch-self-compare.json
# If /tmp/eval-batch-baseline/summary.json carries artifact_sha256, self-compare auto-emits the same candidate manifest you would otherwise request with --batch-output-manifest.
# Frozen in-repo replay lane: examples/eval/threshold-handoff/README.md
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-candidate --batch-output-manifest --batch-output-errors-only --batch-output-self-compare-against /tmp/eval-batch-baseline --batch-output-self-compare-strict --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 1 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-self-verify
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-errors-only --batch-output-layout by-status --batch-output-run-id ci-run-2026-03-07T11-15-00Z --batch-output-self-verify --batch-output-self-verify-strict --batch-output-verify-profile triage-by-status --batch-output-verify-expected-run-id-pattern '^ci-run-.*$' --batch-output-verify-expected-event-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts
erz eval --batch-output-verify /tmp/eval-batch-artifacts --summary
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-summary-file /tmp/eval-batch-verify.json
erz eval --batch-output-verify /tmp/eval-batch-artifacts --summary --batch-output-verify-summary-file /tmp/eval-batch-verify-summary.txt
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-include "*ok*"
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-include "*.envelope.json" --batch-output-verify-exclude "*invalid*"
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --summary --batch-output-compare-summary-file /tmp/eval-batch-compare-summary.txt
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-summary-file /tmp/eval-batch-compare.json
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-include "01-ok.envelope.json"
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-include "*.envelope.json" --batch-output-compare-exclude "*invalid*"
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-strict --batch-output-compare-expected-status error --batch-output-compare-expected-changed-count 1 --batch-output-compare-expected-metadata-mismatches-count 1
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-profile clean
erz pack-replay examples/program-packs/ingest-normalize --summary
erz pack-replay examples/program-packs/dedup-cluster --summary
erz pack-replay examples/program-packs/dedup-cluster --fixture new_ops_time_miss --summary
erz pack-replay examples/program-packs/dedup-cluster --include-fixture "new_*" --exclude-fixture "*security*" --summary
erz pack-replay examples/program-packs/dedup-cluster --fixture-class runtime_error --summary
erz pack-replay examples/program-packs/dedup-cluster --summary-file /tmp/dedup.summary.txt
erz pack-replay examples/program-packs/dedup-cluster --summary --json-file /tmp/dedup.summary.json
erz pack-replay examples/program-packs/dedup-cluster --fixture-class runtime_error --fixture-class-summary-file /tmp/dedup-runtime-error.summary.txt
erz pack-replay examples/program-packs/dedup-cluster --summary --strict-profile clean --expected-fixture-class-counts ok=4,expectation_mismatch=0,runtime_error=0
erz pack-replay examples/program-packs/dedup-cluster --summary --strict --expected-pack-id sprint-7-program-pack-2-dedup-cluster --expected-baseline-shape fixture-matrix --expected-mismatch-count 0 --expected-expectation-mismatch-count 0 --expected-runtime-error-count 0 --expected-rule-source-status ok
erz pack-replay examples/program-packs/dedup-cluster --summary --strict-profile dedup-cluster-clean
erz pack-replay examples/program-packs/ingest-normalize --summary --strict-profile ingest-normalize-clean
erz pack-replay examples/program-packs/alert-routing --summary --strict-profile alert-routing-clean
erz pack-replay examples/program-packs/alert-routing
erz pack-replay examples/program-packs/alert-routing --output /tmp/alert-routing-pack-replay.json
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-profile metadata-only --batch-output-compare-expected-metadata-mismatches-count 1

# Checked-in Preset-Fixtures für sofort lauffähige Compare-Demos
erz eval --batch-output-compare examples/eval/compare-presets/candidate-clean --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile clean
erz eval --batch-output-compare examples/eval/compare-presets/candidate-metadata-only --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile metadata-only --batch-output-compare-expected-metadata-mismatches-count 1
erz eval --batch-output-compare examples/eval/compare-presets/candidate-asymmetric --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 3 --batch-output-compare-expected-candidate-only-count 2 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2 --batch-output-compare-expected-metadata-mismatches-count 4
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-require-run-id
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-event-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-verified-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-checked-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-missing-count 0
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-mismatched-count 0
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-manifest-missing-count 0
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-invalid-hashes-count 0
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-unexpected-manifest-count 0
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-status ok
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-strict-mismatches-count 0
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-event-artifact-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-manifest-entry-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-selected-artifact-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-manifest-selected-entry-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict --batch-output-verify-expected-layout by-status --batch-output-verify-expected-run-id-pattern '^ci-run-.*$'
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --meta
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --meta --generated-at 2026-03-06T18:30:00Z
```

For the nested-path smoke lane, the repo also carries frozen stdout fixtures next to the inputs: `examples/eval/event-path-ok.expected.envelope.json`, `examples/eval/event-path-no-action.expected.envelope.json`, and `examples/eval/event-path-no-action.expected.summary.txt`.

For the payload-length smoke lane, the matching checked-in fixtures live next to `examples/eval/program-lengths.erz`: `examples/eval/event-length-ok.expected.envelope.json`, `examples/eval/event-length-no-action.expected.envelope.json`, and `examples/eval/event-length-no-action.expected.summary.txt`.

For the numeric-threshold smoke lane, the matching checked-in fixtures live next to `examples/eval/program-thresholds.erz`: `examples/eval/event-threshold-ok.expected.envelope.json`, `examples/eval/event-threshold-no-action.expected.envelope.json`, and `examples/eval/event-threshold-no-action.expected.summary.txt`.

Expected JSON shape:

```json
{
  "actions": ["..."],
  "trace": ["..."]
}
```

Runtime contract failure shape (stable):

```json
{
  "actions": [],
  "trace": [],
  "error": {
    "code": "ERZ_RUNTIME_CONTRACT",
    "stage": "runtime",
    "details": {
      "error_type": "TypeError",
      "command": "eval"
    }
  }
}
```

## Guarantees

1. **Pure evaluation / no side effects**
   - No I/O, no randomness, no wall-clock reads.
   - No action execution hooks or callbacks are invoked.
   - Inputs are not mutated.

2. **Deterministic ordering**
   - Rules are normalized and evaluated in stable order by `(rule_id, declaration_index)`.
   - Returned `actions` and `trace` follow that same stable order.
   - Within each trace step, `matched_clauses` preserves rule clause declaration order.

3. **Deterministic payload/action normalization**
   - Mapping keys are canonicalized recursively (sorted) for stable output shape.
   - Action params and payload data must be declarative JSON-like data only:
     `str | int | float | bool | null | list | object`.

4. **Explicit trace contract (per fired rule)**
   - Every fired rule emits exactly one trace step.
   - Required fields:
     - `rule_id: non-empty str`
     - `matched_clauses: non-empty list[str]`
   - Optional fields:
     - `score: finite number` (present when `include_score=True`; runtime emits float)
     - `calibrated_probability: finite number in [0.0, 1.0]`
       (present when `calibration=<piecewise_linear_config>` is provided; runtime emits float)
     - `timestamp: string|number` (present when `now` or `event.payload.timestamp` is provided)
     - `seed: string|int` (present when `seed` or `event.payload.seed` is provided)
   - Unknown trace keys are rejected by runtime validation.
   - Stable trace key order:
     `rule_id`, `matched_clauses`, `score`, `calibrated_probability`, `timestamp`, `seed`.
   - Runtime helper APIs: `validate_trace_step` and `validate_trace`.

5. **Deterministic timestamp/seed handling**
   - The evaluator never generates time or seed values.
   - If provided via arguments (`now`, `seed`) or payload fallback, those values are copied into trace unchanged.

6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**
   - Success payload contains exactly `actions`, `trace` and omits `error`.
   - Runtime contract/value failures return deterministic empty payload lanes:
     `actions == []`, `trace == []`, plus stable `error` envelope.
   - Stable code mapping for captured runtime failures:
     - `TypeError -> ERZ_RUNTIME_CONTRACT`
     - `ValueError -> ERZ_RUNTIME_VALUE`
   - Stable runtime parity contract for adapter + direct-builder lanes: adapter failures and direct `build_error_envelope(...)` outputs keep `stage="runtime"` and `details.command="eval"`.
   - Ordered details contract is deterministic: `error.details` serializes `error_type` first, then `command`.
   - Non-contract internal failures are re-raised unchanged (no envelope swallowing).
   - Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer.

## Rule Engine v0 semantics

### Rule form

`rule.when` is interpreted as a **simple AND-clause list**:

- All clauses in `when` must match for the rule to fire.
- If any clause fails, the rule does not fire.
- No expression language is supported (no `&&`, `||`, `and`, `or`, `not`, parentheses).

If `when` is omitted (or empty), v0 uses default clause `event_type_present` for backward compatibility.

### Supported clause grammar

Only these clause forms are valid:

- `event_type_present`
- `event_type_equals:<value>`
- `payload_has:<top_level_key>`
- `payload_path_exists:<dot.path>`
- `payload_path_equals:<dot.path>=<value>`
- `payload_path_in:<dot.path>=<csv-or-json-list>`
- `payload_path_startswith:<dot.path>=<string>`
- `payload_path_contains:<dot.path>=<string>`
- `payload_path_len_gt:<dot.path>=<integer>`
- `payload_path_len_gte:<dot.path>=<integer>`
- `payload_path_len_lt:<dot.path>=<integer>`
- `payload_path_len_lte:<dot.path>=<integer>`
- `payload_path_gt:<dot.path>=<number>`
- `payload_path_gte:<dot.path>=<number>`
- `payload_path_lt:<dot.path>=<number>`
- `payload_path_lte:<dot.path>=<number>`

Unsupported clauses raise a `TypeError` (rule evaluation aborts for that policy set).

### Action emission semantics

- `then` actions are emitted as declarative output records only.
- Runtime does **not** execute action kinds.
- Missing `then` defaults to: `{"kind": "act", "params": {"rule_id": <rule.id>}}`.

### Score semantics

- `score` is structural match coverage for fired rules:
  `len(matched_clauses) / len(rule.when)`.
- Because only fully matched AND-rules fire in v0, fired rules currently emit `score = 1.0`.
- If `include_score=False`, `score` is omitted.

### Calibration integration semantics (Sprint-5)

- `eval_policies(..., calibration=<config>)` applies deterministic piecewise-linear mapping
  (`runtime.calibration.map_raw_score_to_probability`) to the structural raw score.
- The mapped value is emitted as `trace[].calibrated_probability`.
- Calibration is optional; when omitted, trace shape remains backward compatible.
- Calibration input affects trace output only; it does not change rule matching or action emission.
- No wall-clock reads or randomness are introduced by calibration flow.

### Separation guard (severity/confidence)

- Runtime does **not** infer probabilistic semantics from payload fields like
  `severity` or `confidence`.
- Both `score` and `calibrated_probability` are derived from structural clause match
  coverage only in v0.

## Current limits

- Clause matching is intentionally narrow and deterministic.
- `payload_has` checks top-level payload keys only.
- `payload_path_*` traverses dot-separated payload keys and numeric list indexes only, `payload_path_in` accepts finite scalar member sets only (CSV or JSON array), `payload_path_startswith/contains` are case-sensitive string-only checks, `payload_path_len_*` compares only string/list lengths plus mapping key counts against non-negative integer clause literals, and `payload_path_gt/gte/lt/lte` compare only finite numeric payload values against finite numeric clause literals.
- No probabilistic or weighted rule scoring.
- No runtime action dispatch/execution in v0.
- Trace shape and fired-rule alignment are validated in-process (no external validator dependency required).
