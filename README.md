# erzlang

Agentenfreundliche DSL mit deterministischer Runtime, Policy-Kern und maschinenlesbarem Trace.

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

# Optionale Operator-Kurzfassung (eine deterministische Zeile)
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --summary

# Optional: Summary-Zeile mit Exit-Policy-Suffix für CI-Logparser
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --summary --summary-policy

# Automation: Exit-Policy-Presets für CI/Orchestrierung
erz eval examples/eval/program.erz --input examples/eval/event-invalid.json --exit-policy strict
erz eval examples/eval/program.erz --input examples/eval/event-no-action.json --exit-policy strict-no-actions

# Batch-Replay: mehrere Event-Fixtures deterministisch gegen ein Programm ausführen
erz eval examples/eval/program.erz --batch examples/eval/batch

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
13. Optional für Automation-Traceability im Single-Event-Lane: nutze `--meta` (plus `--generated-at <ts>` wenn du den Timestamp explizit steuern willst).

```bash
erz eval examples/eval/program.erz --input examples/eval/event-ok.json
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --summary --summary-policy
erz eval examples/eval/program.erz --batch examples/eval/batch
erz eval examples/eval/program.erz --batch examples/eval/batch --include "*ok*.json"
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-errors-only
erz eval examples/eval/program.erz --batch examples/eval/batch --batch-output /tmp/eval-batch-artifacts --batch-output-manifest --batch-output-layout by-status
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

Wenn du `--batch-output <dir>` setzt, entstehen deterministische CI-Artefakte im Zielordner: pro Event `<name>.envelope.json` plus `summary.json`. Mit `--batch-output-errors-only` werden nur Fehler-/No-Action-Events geschrieben, die stdout-Aggregat-Envelope bleibt dabei unverändert. Mit `--batch-output-manifest` ergänzt `summary.json` ein deterministisches `artifact_sha256`-Mapping für alle geschriebenen Event-Artefakte. Mit `--batch-output-layout by-status` werden Event-Artefakte unter `ok/`, `no-action/` und `error/` gruppiert, Dateinamen und Reihenfolge bleiben deterministisch.

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
