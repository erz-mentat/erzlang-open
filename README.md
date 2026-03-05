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

# Token benchmark harness ausführen (knappe Zusammenfassung + PASS/FAIL)
erz bench

# Optional: eigenes Ziel für Token-Einsparung setzen
erz bench --target-pct 40
```

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
- Snapshot-Index + Retention-Runbook: `docs/release-artifacts/README.md`
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
