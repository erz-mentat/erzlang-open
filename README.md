# erzlang

Agentenfreundliche DSL mit deterministischer Runtime, Policy-Kern und maschinenlesbarem Trace.

Public slice: aktuelle Runtime-, CLI-, Docs- und Example-Fortschritte sind enthalten, private Protokoll-/Queue-Historien und die schwere interne Test-Lane bleiben draußen.

## v0.1 Fokus (24 Wochen)

- DSL statt General-Purpose-Sprache
- Canonical IR als Kernformat
- Deterministische Ausführung
- Trace/Explainability als Standard-Output
- Token-Effizienz über References + Packing

## Nicht-Ziele v0.1

- Funktionen
- Schleifen
- Module
- Typinferenz

## Unterstützter Compact-Subset (Sprint-3)

Unterstützte Statements (strict, unknown keys fail hard):

- `erz{v:<int>}`
- `event{type:<string>,payload:<object>?}` (legacy long-form)
- `rule{id:<string>,when:<string[]>,then:<action[]>}` (legacy long-form)
- `action{kind:<string>,params:<object>?}` (legacy long-form)
- `ev{type:<string>,payload:<object>?}`
- `rl{id:<string>,when:<string[]>,then:<action[]>}`
- `ac{kind:<string>,params:<object>?}`
- `tr{rule_id:<string>,matched_clauses:<string[]>,score:<number>?,calibrated_probability:<number[0..1]>?,timestamp:<string|number>?,seed:<string|int>?}`
- `rf{id:<string>,v:<string>}`
- `pl{rt:<object>?}`

Hinweis für `tr`-Felder: `score`/`calibrated_probability` akzeptieren finite Zahlen (bool ausgeschlossen), `calibrated_probability` liegt in `[0.0, 1.0]`, `timestamp` ist `string|number`, `seed` ist `string|int`.

### CLI

```bash
# Parse + canonical JSON ausgeben
erz parse examples/sample.erz

# Nur validieren (exit 0/1)
erz validate examples/sample.erz

# Parse-/Validate-Fehler als deterministisches JSON-Envelope (stderr)
erz parse broken.erz --json-errors
erz validate broken.erz --json-errors

# Deterministisch formatieren nach stdout
erz fmt examples/sample.erz

# Datei in-place kanonisch formatieren
erz fmt examples/sample.erz --in-place

# lokal ohne Installation
python3 -m cli.main fmt examples/sample.erz

# Sprint-3: JSON fixture subset -> compact+refs
python3 -m cli.main pack bench/token-harness/fixtures/ingest_event.baseline.json

# Sprint-3: compact+refs -> canonical JSON
python3 -m cli.main unpack bench/token-harness/fixtures/ingest_event.erz

# Deterministische Policy-Evaluation als JSON-Envelope (actions/trace/error)
erz eval examples/eval/program.erz --input examples/eval/event-ok.json

# Nested payload path predicates als copy-pastebarer Eval-Start (exists/equals/in)
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-ok.json
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-no-action.json
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-no-action.json --summary
# Frozen expected outputs dazu liegen direkt daneben:
# - examples/eval/event-path-ok.expected.envelope.json
# - examples/eval/event-path-no-action.expected.envelope.json
# - examples/eval/event-path-no-action.expected.summary.txt

# String payload predicates als copy-pastebarer Eval-Start (startswith/contains)
erz eval examples/eval/program-strings.erz --input examples/eval/event-string-ok.json
erz eval examples/eval/program-strings.erz --input examples/eval/event-string-no-action.json
erz eval examples/eval/program-strings.erz --input examples/eval/event-string-no-action.json --summary
# Frozen expected outputs dazu liegen direkt daneben:
# - examples/eval/event-string-ok.expected.envelope.json
# - examples/eval/event-string-no-action.expected.envelope.json
# - examples/eval/event-string-no-action.expected.summary.txt

# Payload-length predicates als copy-pastebarer Eval-Start (len_gt/gte/lt/lte)
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-ok.json
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-no-action.json
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-no-action.json --summary
# Frozen expected outputs dazu liegen direkt daneben:
# - examples/eval/event-length-ok.expected.envelope.json
# - examples/eval/event-length-no-action.expected.envelope.json
# - examples/eval/event-length-no-action.expected.summary.txt

# Numeric threshold predicates als copy-pastebarer Eval-Start (gt/gte/lt/lte)
erz eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-ok.json
erz eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-no-action.json
erz eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-no-action.json --summary
# Frozen expected outputs dazu liegen direkt daneben:
# - examples/eval/event-threshold-ok.expected.envelope.json
# - examples/eval/event-threshold-no-action.expected.envelope.json
# - examples/eval/event-threshold-no-action.expected.summary.txt

# Optionale Operator-Kurzfassung (eine deterministische Zeile)
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --summary

# Optional: Summary-Zeile mit Exit-Policy-Suffix für CI-Logparser
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --summary --summary-policy

# Automation: Exit-Policy-Presets für CI/Orchestrierung
erz eval examples/eval/program.erz --input examples/eval/event-invalid.json --exit-policy strict
erz eval examples/eval/program.erz --input examples/eval/event-no-action.json --exit-policy strict-no-actions

# Batch-Replay: mehrere Event-Fixtures deterministisch gegen ein Programm ausführen
erz eval examples/eval/program.erz --batch examples/eval/batch

# Optional: per-Rule Hit-Counts in die JSON-Summary aufnehmen
# (nur im JSON-Envelope, nicht mit --summary kombinierbar)
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-summary-rule-counts

# Optional: per-Action-Kind Counts für Operator-Triage in die JSON-Summary aufnehmen
# (nur im JSON-Envelope, nicht mit --summary kombinierbar)
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-summary-action-kind-counts

# Optional: Batch-Dateien mit Glob-Filtern einschränken (include zuerst, dann exclude)
erz eval examples/eval/program.erz --batch examples/eval/batch --include "*ok*.json"
erz eval examples/eval/program.erz --batch examples/eval/batch --include "*.json" --exclude "*invalid*.json"

# Optional: Batch-Artefakte für CI persistieren (pro Event + summary.json)
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-errors-only

# Optional: SHA256-Manifest für geschriebene Event-Artefakte in summary.json
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-manifest

# Optional: Artefakte nach Status gruppieren (ok/no-action/error)
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-layout by-status

# Optional: Run-Metadaten für CI-Traceability in summary.json (run.id)
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-run-id ci-run-2026-03-06T20-30-00Z

# Optional: Aggregate Batch-Envelope zusätzlich als Datei exportieren (stdout bleibt identisch)
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output-summary-file /tmp/eval-batch-aggregate.json

# Optional: Generation-Lane mit sofortigem Self-Verify-Gate (schreibt Manifest automatisch)
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-self-verify

# Optional: generation-time Strict-Handoff in einem Lauf (Self-Verify + Profil/Expectations)
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-errors-only --batch-output-layout by-status --batch-output-run-id ci-run-2026-03-07T11-15-00Z --batch-output-self-verify --batch-output-self-verify-strict --batch-output-verify-profile triage-by-status --batch-output-verify-expected-run-id-pattern '^ci-run-.*$' --batch-output-verify-expected-event-count 3

# Optional: vorhandene Batch-Artefakte per Manifest verifizieren (CI integrity gate)
erz eval --batch-output-verify /tmp/eval-batch-artifacts
erz eval --batch-output-verify /tmp/eval-batch-artifacts --summary
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-summary-file /tmp/eval-batch-verify.json
erz eval --batch-output-verify /tmp/eval-batch-artifacts --summary --batch-output-verify-summary-file /tmp/eval-batch-verify-summary.txt
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-include "*ok*"
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-include "*.envelope.json" --batch-output-verify-exclude "*invalid*"

# Optional: Candidate-vs-Baseline Drift ohne Manifestpflicht vergleichen (run.id wird bewusst ignoriert)
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --summary
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --output /tmp/eval-batch-compare.json
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-summary-file /tmp/eval-batch-compare.json
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --summary --batch-output-compare-summary-file /tmp/eval-batch-compare-summary.txt
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-include "01-ok.envelope.json"
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-include "*.envelope.json" --batch-output-compare-exclude "*invalid*"

# Optional: erwartete Drift exakt als Gate ausdrücken
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-strict --batch-output-compare-expected-status error --batch-output-compare-expected-changed-count 1 --batch-output-compare-expected-metadata-mismatches-count 1

# Optional: Compare-Preset für häufige CI-Verträge nutzen, dann nur die variablen Zähler ergänzen
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-profile clean
erz eval --batch-output-compare /tmp/eval-batch-candidate --batch-output-compare-against /tmp/eval-batch-baseline --batch-output-compare-profile metadata-only --batch-output-compare-expected-metadata-mismatches-count 1

# Checked-in Preset-Fixtures, damit Compare-Lanes ohne eigenes Vorbereiten sofort laufen
erz eval --batch-output-compare examples/eval/compare-presets/candidate-clean --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile clean
erz eval --batch-output-compare examples/eval/compare-presets/candidate-metadata-only --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile metadata-only --batch-output-compare-expected-metadata-mismatches-count 1
erz eval --batch-output-compare examples/eval/compare-presets/candidate-asymmetric --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 3 --batch-output-compare-expected-candidate-only-count 2 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2 --batch-output-compare-expected-metadata-mismatches-count 4

# Optional: striktes Verify-Profil (Mode + optional Layout/Run-ID/Event-Count/Verified-Count/Checked-Count/Missing-Count/Mismatched-Count/Manifest-Missing-Count/Invalid-Hashes-Count/Unexpected-Manifest-Count/Status/Strict-Mismatches-Count/Event-Artifact-Count/Manifest-Entry-Count/Selected-Artifact-Count/Manifest-Selected-Entry-Count)
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-strict
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
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-profile triage-by-status
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-profile triage-by-status --batch-output-verify-expected-run-id-pattern '^ci-run-.*$'

# Legacy shortcut bleibt erhalten (entspricht --exit-policy strict)
erz eval examples/eval/program.erz --input examples/eval/event-invalid.json --strict

# Eval-Output zusätzlich in Datei persistieren (stdout bleibt identisch)
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --output /tmp/eval-envelope.json

# Optionales Meta-Envelope für Automation-Traceability (opt-in, Single-Event-Lane)
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --meta
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --meta --generated-at 2026-03-06T18:30:00Z

# Externe Ref-Bindings als Sidecar laden (Merge mit programminternen rf-Bindings)
erz eval examples/eval/program-sidecar.erz --input examples/eval/event-ok.json --refs examples/eval/refs-sidecar.json

# Token benchmark harness ausführen (knappe Zusammenfassung + PASS/FAIL)
erz bench

# Optional: eigenes Ziel für Token-Einsparung setzen
erz bench --target-pct 40

# Checked-in Program Packs gegen ihre Fixture-Baselines replayen
erz pack-replay examples/program-packs/ingest-normalize --summary
erz pack-replay examples/program-packs/dedup-cluster
erz pack-replay examples/program-packs/dedup-cluster --summary
erz pack-replay examples/program-packs/dedup-cluster --fixture new_ops_time_miss --summary
erz pack-replay examples/program-packs/dedup-cluster --include-fixture "new_*" --exclude-fixture "*security*" --summary
erz pack-replay examples/program-packs/dedup-cluster --fixture-class runtime_error --summary
erz pack-replay examples/program-packs/dedup-cluster --summary-file /tmp/dedup.summary.txt
erz pack-replay examples/program-packs/dedup-cluster --summary --json-file /tmp/dedup.summary.json
erz pack-replay examples/program-packs/dedup-cluster --fixture-class runtime_error --fixture-class-summary-file /tmp/dedup-runtime-error.summary.txt
erz pack-replay examples/program-packs/dedup-cluster --summary --strict-profile clean
erz pack-replay examples/program-packs/dedup-cluster --summary --strict-profile dedup-cluster-clean
erz pack-replay examples/program-packs/ingest-normalize --summary --strict-profile ingest-normalize-clean
erz pack-replay examples/program-packs/alert-routing --summary --strict-profile alert-routing-clean
erz pack-replay examples/program-packs/dedup-cluster --summary --strict-profile clean --expected-fixture-class-counts ok=4,expectation_mismatch=0,runtime_error=0
erz pack-replay examples/program-packs/dedup-cluster --summary --strict --expected-pack-id sprint-7-program-pack-2-dedup-cluster --expected-baseline-shape fixture-matrix --expected-mismatch-count 0 --expected-expectation-mismatch-count 0 --expected-runtime-error-count 0 --expected-rule-source-status ok
erz pack-replay examples/program-packs/alert-routing --output /tmp/alert-routing-pack-replay.json
```

### Eval Quickstart (Operator)

Kurz, ohne DSL-Details:

1. Nimm ein Programm (`.erz`) und ein Event (`.json`).
2. Starte `erz eval`.
3. Lies `actions` als Ergebnis, `trace` als Begründung.
4. Optional: nutze `--refs <refs.json>`, wenn Ref-Bindings als Sidecar vorliegen.
5. Optional für Automation-Exitcodes: nutze `--exit-policy strict` (Runtime-Fehler) oder `--exit-policy strict-no-actions` (Runtime-Fehler + leere `actions`).
6. Optional für CI-Logs: nutze `--summary --summary-policy`, dann endet die Zeile deterministisch mit `policy=<...> exit=<0|1>`.
7. Optional für Batch-Replays: nutze `--batch <dir>` für mehrere Event-JSONs (sortiert nach Dateiname, ein aggregiertes Envelope).
8. Optional für Batch-Filter: nutze `--include <glob>` und/oder `--exclude <glob>` (include läuft vor exclude, Match-Basis ist der Dateiname).
9. Optional für CI-Artefakte im Batch-Lane: nutze `--batch-output <dir>`, dann schreibt `erz eval` pro Event ein Envelope-JSON plus `summary.json`.
10. Optional für schlanke CI-Triage-Artefakte: ergänze `--batch-output-errors-only`, dann werden nur Fehler-/No-Action-Events persistiert.
11. Optional für Integritätsprüfungen ohne Nachrechnen: ergänze `--batch-output-manifest`, dann enthält `summary.json` ein deterministisches `artifact_sha256`-Mapping für alle geschriebenen Event-Artefakte.
12. Optional für große Runs: ergänze `--batch-output-layout by-status`, dann landen Event-Artefakte unter `ok/`, `no-action/` oder `error/`.
13. Optional für CI-Run-Traceability: ergänze `--batch-output-run-id <id>`, dann enthält `summary.json` zusätzlich `run.id` bei unverändertem stdout-Aggregat.
14. Optional für Dashboard-Exports ohne stdout-Drift: ergänze `--batch-output-summary-file <path>`, dann schreibt `erz eval` das Batch-Aggregat byte-identisch zu stdout in eine Datei.
15. Optional für generation-time Integrity-Gate: ergänze `--batch-output-self-verify`, dann verifiziert `erz eval` die frisch geschriebenen Artefakte sofort vor Pipeline-Handoff (Manifest wird dabei automatisch in `summary.json` geschrieben).
16. Optional für generation-time Strict-Handoff: ergänze `--batch-output-self-verify-strict`, dann nutzt der Self-Verify-Lauf dieselben Strict-Profile/Selectoren (`--batch-output-verify-profile`, `--batch-output-verify-expected-*`, `--batch-output-verify-require-run-id`) direkt im Generierungs-Command.
17. Optional für Integritäts-Gate nach dem Lauf: nutze `--batch-output-verify <dir>` (plus `--summary` für eine kompakte CI-Pass/Fail-Zeile).
18. Optional für policy-gebundene CI-Gates nachgelagert: nutze `--batch-output-verify-profile <default|triage-by-status>` als Preset (aktiviert strict verify automatisch), optional ergänzt mit `--batch-output-verify-expected-mode`, `--batch-output-verify-expected-layout`, `--batch-output-verify-expected-run-id-pattern`, `--batch-output-verify-expected-event-count`, `--batch-output-verify-expected-verified-count`, `--batch-output-verify-expected-checked-count`, `--batch-output-verify-expected-missing-count`, `--batch-output-verify-expected-mismatched-count`, `--batch-output-verify-expected-manifest-missing-count`, `--batch-output-verify-expected-invalid-hashes-count`, `--batch-output-verify-expected-unexpected-manifest-count`, `--batch-output-verify-expected-status`, `--batch-output-verify-expected-strict-mismatches-count`, `--batch-output-verify-expected-event-artifact-count`, `--batch-output-verify-expected-manifest-entry-count`, `--batch-output-verify-expected-selected-artifact-count`, `--batch-output-verify-expected-manifest-selected-entry-count` und `--batch-output-verify-require-run-id`.
19. Optional für Verify-Lane-Dashboard-Exports ohne stdout-Drift: nutze `--batch-output-verify-summary-file <path>`, dann schreibt `erz eval` den Verify-Output (JSON oder `--summary`-Zeile) byte-identisch in eine Datei.
20. Optional für generation-time Baseline-Gates ohne zweiten Compare-Command: nutze `--batch-output-self-compare-against <baseline-dir>`, dann vergleicht `erz eval` die frisch geschriebenen Artefakte direkt vor dem Handoff gegen eine Baseline; bei Erfolg bleibt stdout identisch zum normalen Batch-Lauf, bei Drift stoppt der Lauf vor dem Handoff. Trägt die Baseline ein `artifact_sha256`-Manifest, wird dieses Mapping mitverglichen und Self-Compare schreibt für denselben Candidate-Lauf automatisch ebenfalls ein Manifest.
21. Optional für erwartete generation-time Drift: ergänze `--batch-output-self-compare-strict` plus `--batch-output-compare-profile` oder konkrete `--batch-output-compare-expected-*` Werte, dann kann derselbe Handoff-Lauf bewusst asymmetrische oder metadata-only Drift als Vertrag ausdrücken, inklusive Metadaten-Drift gegen manifesttragende Baselines. Praktisch heißt das: mit oder ohne explizites `--batch-output-manifest` landet derselbe Self-Compare-Handoff bei manifesttragenden Baselines auf demselben Candidate-Manifest, ohne Baseline bleibt Manifest-Schreiben opt-in.
22. Optional für Compare-Lane-Dashboard-Exports ohne stdout-Drift: nutze `--batch-output-compare-summary-file <path>`, dann schreibt `erz eval` den Compare-Output, JSON oder `--summary`, byte-identisch in eine Datei, sowohl für `--batch-output-compare` als auch für `--batch-output-self-compare-against`.
23. Optional für große Verify-Lanes: nutze `--batch-output-verify-include <glob>` und/oder `--batch-output-verify-exclude <glob>` für deterministische Artefakt-Subset-Prüfung (include vor exclude, Match-Basis ist der relative Artifact-Pfad aus `summary.json`).
24. Optional für Automation-Traceability im Single-Event-Lane: nutze `--meta` (plus `--generated-at <ts>` wenn du den Timestamp explizit steuern willst).
25. Optional für checked-in Program Packs: nutze `erz pack-replay <pack-dir>`, dann werden die Pack-Fixtures deterministisch gegen das `.erz`-Programm und die Baseline-Erwartungen geprüft, egal ob die Baseline als Fixture-Matrix oder als Inline-Statement-Satz mit eingebetteten `ev`-Samples vorliegt; `--fixture <id>` bleibt repeatable für exakte Fälle, `--include-fixture <glob>` und `--exclude-fixture <glob>` bauen deterministische Multi-Case-Slices, immer in Pack-Reihenfolge, include/exakt zuerst, exclude danach; `--fixture-class <ok|expectation_mismatch|runtime_error>` filtert den replayten Slice danach deterministisch auf Replay-Klassen; `--summary` liefert dann `fixtures=<selected>/<total>` plus `fixture_classes=ok:<n>,expectation_mismatch:<n>,runtime_error:<n>` für schnelle Operator-Triage, und das JSON-Envelope ergänzt dieselbe exklusive Klassensicht pro Eintrag unter `fixtures[].fixture_class`, aggregiert unter `summary.fixture_class_counts`, plus die zugehörigen deterministischen Fixture-IDs unter `summary.fixture_class_ids`; `--summary-file <path>` schreibt dieselbe kompakte Summary-Zeile für jeden Pack-Run zusätzlich in eine Datei, `--json-file <path>` schreibt invers dazu immer das volle JSON-Envelope in eine Sidecar-Datei, sodass Summary-stdout plus JSON-Handoff in einem Lauf first-class werden, `--fixture-class-summary-file <path>` bleibt als engere Kompatibilitätsvariante für fixture-class-gefilterte Läufe erhalten, und `--output <path>` spiegelt weiterhin den eigentlichen stdout-Output zusätzlich in eine Datei. Für den üblichen Green-CI-Lauf reicht `--strict-profile clean`, das automatisch Strict-Replay aktiviert und `rule_source_status=ok` plus null `mismatch_count`, `expectation_mismatch_count` und `runtime_error_count` hart gatebar macht, ohne lange brittle `--expected-*`-Listen auszuschreiben. Für die drei checked-in Packs gibt es zusätzlich `--strict-profile ingest-normalize-clean`, `dedup-cluster-clean` und `alert-routing-clean`; diese Presets pinnen neben der grünen Basis auch `pack_id`, `baseline_shape`, `total_fixture_count` und das volle `fixture_class_counts`-Histogramm, damit ein kompletter Pack-Green-Gate auf einen stabilen einzelnen Preset-Namen schrumpft. Für exakte CI-Verträge ergänzt `--strict` beziehungsweise `--strict-profile <preset>` denselben Replay-Lauf weiterhin um `--expected-pack-id <pack-id>`, `--expected-baseline-shape <fixture-matrix|inline-statements>`, `--expected-fixture-count`, `--expected-total-fixture-count`, repeatable `--expected-selected-fixture <id>`, repeatable `--expected-ok-fixture <id>`, repeatable `--expected-expectation-mismatch-fixture <id>`, repeatable `--expected-runtime-error-fixture <id>`, `--expected-fixture-class-counts ok=<n>,expectation_mismatch=<n>,runtime_error=<n>`, `--expected-mismatch-count`, `--expected-expectation-mismatch-count`, `--expected-runtime-error-count` und `--expected-rule-source-status`; `--expected-selected-fixture` prüft dabei die finale deterministische `selected_fixture_ids`-Liste nach allen exact/glob/class-Filtern in kanonischer Pack-Reihenfolge, sodass Selector-Drift auch dann sichtbar wird, wenn die Aggregate gleich bleiben. Die class-spezifischen Fixture-Selektoren prüfen zusätzlich die exakten `summary.fixture_class_ids.ok`, `summary.fixture_class_ids.expectation_mismatch` und `summary.fixture_class_ids.runtime_error`-Listen in derselben kanonischen Pack-Reihenfolge, damit sowohl Green-Partition-Drift als auch Failure-Partition-Drift ohne JSON-Postprocessing hart gatebar werden. `--expected-pack-id` zieht dieselbe Identitätsprüfung auch für eigene oder umbenannte Packs aus den hartkodierten `*-clean`-Presets heraus und macht sie als generischen Strict-Selector verfügbar, `--expected-baseline-shape` zieht dasselbe für Fixture-Matrix- versus Inline-Statement-Baselines nach, sodass Baseline-Form-Drift separat von Pack-ID oder Regeldrift sichtbar wird. Wenn exakte IDs zu spröde wären, kann `--expected-fixture-class-counts` alternativ die komplette deterministische Klassenverteilung unter `summary.fixture_class_counts` in einem Schritt absichern. `--expected-mismatch-count` prüft weiterhin die breite `summary.mismatch_count` inklusive `runtime_error`-Fixtures, während `--expected-expectation-mismatch-count` die reine Driftklasse `fixture_class=expectation_mismatch` absichert. `status` zeigt dann den Strict-Gate-Ausgang, `replay_status` hält den rohen Replay-Befund fest, und `--summary` ergänzt `strict_mismatches=<n>`.

```bash
erz eval examples/eval/program.erz --input examples/eval/event-ok.json
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --summary --summary-policy
erz eval examples/eval/program.erz --batch examples/eval/batch
erz eval examples/eval/program.erz --batch examples/eval/batch --include "*ok*.json"
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-errors-only
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-manifest --batch-output-layout by-status
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-run-id ci-run-2026-03-06T20-30-00Z
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output-summary-file /tmp/eval-batch-aggregate.json
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-candidate --batch-output-manifest --batch-output-self-compare-against /tmp/eval-batch-baseline --batch-output-compare-summary-file /tmp/eval-batch-self-compare.json
# Frozen in-repo replay lane: examples/eval/threshold-handoff/README.md
erz pack-replay examples/program-packs/ingest-normalize --summary
erz pack-replay examples/program-packs/dedup-cluster --summary
erz pack-replay examples/program-packs/dedup-cluster --fixture new_ops_time_miss --summary
erz pack-replay examples/program-packs/dedup-cluster --include-fixture "new_*" --exclude-fixture "*security*" --summary
erz pack-replay examples/program-packs/dedup-cluster --fixture-class runtime_error --summary
erz pack-replay examples/program-packs/dedup-cluster --summary-file /tmp/dedup.summary.txt
erz pack-replay examples/program-packs/dedup-cluster --summary --json-file /tmp/dedup.summary.json
erz pack-replay examples/program-packs/dedup-cluster --fixture-class runtime_error --fixture-class-summary-file /tmp/dedup-runtime-error.summary.txt
erz pack-replay examples/program-packs/alert-routing
erz pack-replay examples/program-packs/alert-routing --output /tmp/alert-routing-pack-replay.json
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-candidate --batch-output-manifest --batch-output-errors-only --batch-output-self-compare-against /tmp/eval-batch-baseline --batch-output-self-compare-strict --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 1 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-self-verify
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-errors-only --batch-output-layout by-status --batch-output-run-id ci-run-2026-03-07T11-15-00Z --batch-output-self-verify --batch-output-self-verify-strict --batch-output-verify-profile triage-by-status --batch-output-verify-expected-run-id-pattern '^ci-run-.*$' --batch-output-verify-expected-event-count 3
erz eval --batch-output-verify /tmp/eval-batch-artifacts
erz eval --batch-output-verify /tmp/eval-batch-artifacts --summary
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-summary-file /tmp/eval-batch-verify.json
erz eval --batch-output-verify /tmp/eval-batch-artifacts --summary --batch-output-verify-summary-file /tmp/eval-batch-verify-summary.txt
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-include "*ok*"
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-include "*.envelope.json" --batch-output-verify-exclude "*invalid*"
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
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-profile triage-by-status
erz eval --batch-output-verify /tmp/eval-batch-artifacts --batch-output-verify-profile triage-by-status --batch-output-verify-expected-run-id-pattern '^ci-run-.*$'
erz eval examples/eval/program-sidecar.erz --input examples/eval/event-ok.json --refs examples/eval/refs-sidecar.json
```

Erwartete Output-Form (gekürzt):

```json
{
  "actions": [{"kind": "notify", "params": {"channel": "ops", "severity_ref": "@sev_label"}}],
  "trace": [{"rule_id": "route_ops", "matched_clauses": ["event_type_present", "payload_has:severity"], "score": 1.0}]
}
```

Mit `--meta` kommt zusätzlich ein deterministischer `meta`-Block dazu (`program_sha256`, `event_sha256`, optional `generated_at`).

Wenn der Input den Runtime-Vertrag verletzt, bleibt die Form stabil:

```json
{
  "actions": [],
  "trace": [],
  "error": {"code": "ERZ_RUNTIME_CONTRACT", "stage": "runtime", "message": "...", "span": null, "hint": null, "details": {"error_type": "TypeError", "command": "eval"}}
}
```

Batch-Lane (`--batch`) liefert ein stabiles Aggregat. Mit `--include/--exclude` kannst du deterministisch nach Dateinamen filtern, bei leerer Auswahl kommt ein stabiler Fehler (`--batch filters matched no .json files ...`).

Wenn du `--batch-output <dir>` setzt, entstehen deterministische CI-Artefakte im Zielordner, pro Event `<name>.envelope.json` plus `summary.json`. Mit `--batch-output-errors-only` werden nur Fehler-/No-Action-Events geschrieben, die stdout-Aggregat-Envelope bleibt dabei unverändert. Mit `--batch-output-manifest` ergänzt `summary.json` ein deterministisches `artifact_sha256`-Mapping für alle geschriebenen Event-Artefakte. Mit `--batch-output-layout by-status` werden Event-Artefakte unter `ok/`, `no-action/` und `error/` gruppiert, Dateinamen und Reihenfolge bleiben deterministisch. Mit `--batch-output-run-id <id>` ergänzt `summary.json` zusätzlich ein `run`-Objekt mit stabiler Form (`{"id":"<id>"}`), ohne Per-Event-Envelope oder stdout zu verändern. Mit `--batch-output-summary-file <path>` exportierst du dasselbe Batch-Aggregat zusätzlich in eine Datei, byte-identisch zum JSON-stdout (nicht mit `--summary` kombinierbar). Mit `--batch-output-self-verify` läuft direkt nach dem Schreiben ein deterministischer Integrity-Check, bei Erfolg bleibt stdout identisch zum normalen Batch-Output, bei Fehler stoppt der Lauf vor Handoff; das Manifest wird dabei automatisch geschrieben. Mit `--batch-output-self-verify-strict` nutzt derselbe generation-time Check zusätzlich Strict-Profil-Expectations (inklusive Presets und erwarteter `mode/layout/run.id/event_count/verified/checked/missing_artifacts.count/mismatched_artifacts.count/missing_manifest_entries.count/invalid_manifest_hashes.count/unexpected_manifest_entries.count/status/strict_profile_mismatches.count/event_artifacts.count/artifact_sha256.count/selected_artifacts.count/selected_manifest_entries.count`), damit CI-Handoff-Gates ohne zweiten Verify-Command greifen. Mit `--batch-output-self-compare-against <baseline-dir>` läuft derselbe generation-time Handoff direkt gegen eine Baseline, ohne zweiten Compare-Command und ohne stdout-Drift im normalen Batch-Output. Trägt die Baseline dabei `artifact_sha256`, schreibt Self-Compare für denselben Candidate-Lauf automatisch ebenfalls ein Manifest, damit der Handoff-Vertrag zwischen explizitem Manifest-Lauf und baseline-getriggertem Manifest-Lauf zusammenfällt. Mit `--batch-output-self-compare-strict` wird daraus ein bewusst vertraglicher Handoff-Gate, der dieselben Compare-Presets und `--batch-output-compare-expected-*` Selektoren wie die nachgelagerte Compare-Lane nutzt. Mit `--batch-output-verify <dir>` kannst du ein vorhandenes Artifact-Set deterministisch gegen das Manifest prüfen, JSON-Output liefert `status=ok|error` plus Detailfelder (`missing_artifacts`, `mismatched_artifacts`, `selected_artifacts_count`, `selected_manifest_entries_count`, usw.), und `--summary` gibt eine kompakte CI-Zeile mit denselben Basiszählern plus `selected=<n>` und `selected_manifest=<n>` aus. Mit `--batch-output-verify-summary-file <path>` exportierst du den Verify-Output zusätzlich in eine Datei, byte-identisch zu stdout (JSON-Lane oder `--summary`-Lane). Mit `--batch-output-verify-include <glob>` und `--batch-output-verify-exclude <glob>` kannst du die Verify-Lane auf ein deterministisches Artifact-Subset einschränken (include vor exclude, Match gegen relative Artifact-Pfade aus `summary.json`). Mit `--batch-output-compare <candidate-dir> --batch-output-compare-against <baseline-dir>` vergleichst du zwei Batch-Artifact-Sets direkt auf Drift, auch ohne Manifest, inklusive Event-Artefakt-Bytes, `event_artifacts`-Reihenfolge sowie `mode/layout/summary.*`-Metadaten. Leere Artifact-Sets aus `--batch-output-errors-only` bleiben dabei ein gültiger Contract, identische Empty-Lanes liefern deterministisch `compared=0 matched=0`. Mit `--batch-output-compare-include <glob>` und `--batch-output-compare-exclude <glob>` kannst du die Compare-Lane auf ein deterministisches Artifact-Subset einschränken, Match erfolgt gegen relative Artifact-Pfade aus `summary.json`, include vor exclude. Wenn beide Seiten ein Manifest tragen, wird auch `artifact_sha256` für dasselbe selektierte Subset auf deterministische Summary-Drift geprüft, bewusst ignoriert bleibt nur `run.id`, damit getrennte CI-Runs mit unterschiedlichen IDs sauber vergleichbar bleiben, solange der eigentliche Output identisch bleibt. JSON-Output liefert `baseline_only_artifacts`, `candidate_only_artifacts`, `missing_baseline_artifacts`, `missing_candidate_artifacts`, `changed_artifacts`, `metadata_mismatches`, `selected_baseline_artifacts_count` und `selected_candidate_artifacts_count`, `--summary` reduziert das deterministisch auf `compared/matched/changed/baseline_only/candidate_only/missing_baseline/missing_candidate/metadata_mismatches/selected_baseline/selected_candidate`. Mit `--batch-output-compare-summary-file <path>` exportierst du denselben Compare-Output zusätzlich in eine Datei, byte-identisch zu stdout, sowohl für JSON als auch für `--summary`, und im Self-Compare-Lane landet derselbe Compare-Output in der Datei, während stdout beim normalen Eval-Output bleibt. Mit `--batch-output-compare-strict` plus `--batch-output-compare-expected-*` lässt sich dieselbe Lane als exaktes Drift-Gate verwenden, inklusive separater Expectations für `baseline_only/candidate_only/missing_baseline/missing_candidate/metadata_mismatches`. Für häufige Verträge gibt es zusätzlich `--batch-output-compare-profile <clean|metadata-only|expected-asymmetric-drift>`, explizite `--batch-output-compare-expected-*` Werte überschreiben dabei die Preset-Defaults. Für copy-pastebare Startpunkte liegen unter `examples/eval/compare-presets/` drei echte Artifact-Sets im Repo, clean, metadata-only und asymmetric drift. `compare_status` bleibt der rohe Driftstatus, `status` zeigt den Strict-Gate-Ausgang, `strict_profile_mismatches` erklärt Abweichungen, und `--summary` ergänzt `strict_mismatches=<n>`. Mit `--batch-output-verify-profile <default|triage-by-status>` aktivierst du ein striktes Preset-Gate auf `summary.json`-Metadaten (`default` = `mode=all` + `layout=flat`, `triage-by-status` = `mode=errors-only` + `layout=by-status`), optional ergänzt um `--batch-output-verify-expected-run-id-pattern`, `--batch-output-verify-expected-event-count`, `--batch-output-verify-expected-verified-count`, `--batch-output-verify-expected-checked-count`, `--batch-output-verify-expected-missing-count`, `--batch-output-verify-expected-mismatched-count`, `--batch-output-verify-expected-manifest-missing-count`, `--batch-output-verify-expected-invalid-hashes-count`, `--batch-output-verify-expected-unexpected-manifest-count`, `--batch-output-verify-expected-status`, `--batch-output-verify-expected-strict-mismatches-count`, `--batch-output-verify-expected-event-artifact-count`, `--batch-output-verify-expected-manifest-entry-count`, `--batch-output-verify-expected-selected-artifact-count`, `--batch-output-verify-expected-manifest-selected-entry-count` und `--batch-output-verify-require-run-id`; Summary-Output ergänzt dann `strict_mismatches=<n>` nach den Selected-Scope-Tokens. `--batch-output-verify-strict` bleibt als expliziter Schalter weiter verfügbar.

```json
{
  "events": [
    {"event": "01-ok.json", "actions": [...], "trace": [...]},
    {"event": "02-no-action.json", "actions": [], "trace": []},
    {"event": "03-invalid.json", "actions": [], "trace": [], "error": {...}}
  ],
  "summary": {"event_count": 3, "error_count": 1, "no_action_count": 1, "action_count": 1, "trace_count": 1}
}
```

`--summary --summary-policy` ergänzt die Kurzzeile deterministisch um `policy=<...> exit=<0|1>`.

Fehler-Envelope in `--json-errors` Modus (v0.2 prep):
- Gilt für `erz parse`, `erz validate`, `erz pack`, `erz unpack`; ohne Flag bleibt stderr human-readable (`error: ...`)
- Felder: `code`, `stage`, `message`, `span`, `hint`, `details`
- `span` ist `null` oder z. B. `{ "position": 17 }` bei Parserfehlern
- Stabiler JSON-Output, gedacht für Tooling/Automation
- Ordered-details-Vertrag ist fix: `details` serialisiert immer zuerst `error_type`, dann `command` (CLI + direkte Envelope-Builder-Pfade)
- Transform-Error-Snapshots enthalten span-bearing Unpack-Fehler mit stabilen Position-Signaturen (`transform_unpack_unexpected_char.stderr`, `transform_unpack_unexpected_char_secondary.stderr`)
- Runtime-Adapter: `runtime.eval.eval_policies_envelope(...)`
  - Erfolg: `{ "actions": [...], "trace": [...] }` (ohne `error` Feld)
  - Laufzeitvertrag-/Wertfehler: `{ "actions": [], "trace": [], "error": { ...Envelope... } }`
  - Failure-Shape ist deterministisch, wiederholte Läufe liefern dieselbe Payload-Struktur
  - Code-Mapping ist stabil: `TypeError -> ERZ_RUNTIME_CONTRACT`, `ValueError -> ERZ_RUNTIME_VALUE`
  - Runtime-Parität ist fix: Runtime-Fehler führen immer `stage="runtime"` und `details.command="eval"`; Adapter-Fehler werden gegen direkte `build_error_envelope(...)`-Outputs verglichen
  - Consumer-Guidance: Fehler über das Vorhandensein von `error` erkennen (nicht über leere `actions`/`trace`)
  - Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller

### Check-Lanes (Quality Gates)

```bash
# Fast Lane (inner loop): nur Unit-Tests
./scripts/check-unit.sh

# Full Lane (pre-merge/release): alle aktiven Gates
./scripts/check.sh

# Gleichwertiger Wrapper (identischer Full-Lane-Run)
./scripts/check-full.sh
```

`check-full.sh` ist ein dünner Wrapper um `check.sh`; beide führen denselben Full-Lane-Gatesatz aus.
Gate-interne Contract-/Anchor-Prüfungen laufen dabei über Helper unter `scripts/gates/`.

### Release-Evidence Quickstart

```bash
# Full Lane + Snapshot-Export (explizit/manual)
./scripts/check.sh && python3 scripts/release_snapshot.py
```

- Frische Evidence: `docs/release-artifacts/latest.{json,md}`
- Snapshot-Index + Retention-Runbook: siehe Dokumentation im Ordner `docs/release-artifacts/`.
- Source-of-truth-Regel: `bench/token-harness/results/latest.json` bleibt gate-gepinnt,
  `docs/release-artifacts/latest.json` bildet die Freshness-Pointer-Evidence.

Weitere Beispiele:

- `examples/sprint3_mixed.erz`
- `examples/sprint3_policy.erz`

Sprint-7 Program Packs (siehe auch `examples/program-packs/README.md`):
- `examples/program-packs/ingest-normalize/` (Pack #1)
- `examples/program-packs/dedup-cluster/` (Pack #2)
- `examples/program-packs/alert-routing/` (Pack #3)

### Calibration (Sprint-5 kickoff)

- Minimal piecewise-linear calibration scaffold: `runtime/calibration.py`
- API: `map_raw_score_to_probability(raw_score, calibration)`
- Details + guard semantics: `docs/calibration-v0.md`

### Canonical Formatting

- deterministische Feldreihenfolge pro Statement
- sortierte Objekt-Keys
- keine optionalen Leerzeichen
- stabiler Output für denselben unterstützten Input
