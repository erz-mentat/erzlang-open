# Token Benchmark Harness

Vergleicht:
- Baseline: compact JSON + references
- Candidate: erzlang compact + references

## Fixtures (aktuell)
- `ingest_event`
- `ingest_event_nested_payload`
- `ingest_event_rich_payload`
- `normalize_event`
- `normalize_event_nested_payload`
- `alert_event`
- `act_event`
- `act_event_nested_payload`
- `calibration_underconfident_alert`
- `calibration_overconfident_alert`

## Messgrößen
- Token count
- Byte size
- Einsparung in %
- Aggregierte Totals/Averages/Medians

## Ausführung
```bash
# Ergonomische CLI-Zusammenfassung mit PASS/FAIL
erz bench

# Roh-Report (Markdown + JSON payload auf stdout)
python3 bench/token-harness/measure.py
```

Outputs:
- `bench/token-harness/results/latest.json`
- `bench/token-harness/results/latest.md`

## Release-Evidence Quickstart

```bash
# Gate-Lauf + expliziter Snapshot-Export
./scripts/check.sh && python3 scripts/release_snapshot.py
```

Danach:
- aktuelle Release-Evidence unter `docs/release-artifacts/latest.{json,md}`
- Snapshot-Index + Retention-Runbook unter `docs/release-artifacts/README.md`

## Mindestziel
>= 25% Token-Einsparung oder bessere Robustheit bei gleicher Größe.

## Benchmark-Limits & Reproduzierbarkeit
- **Tokenizer-Effekt:** Ergebnisse hängen vom verwendeten Tokenizer ab (`tiktoken` vs. Fallback `utf8_bytes/4`).
- **Fixture-Bias:** Das Set ist klein und repräsentiert nur v0-Scope-Beispiele, nicht die komplette Produktionsvarianz.
- **Format-only Vergleich:** Gemessen wird nur Repräsentation (Bytes/Tokens), nicht Modellqualität oder Fehlertoleranz.

Für reproduzierbare Läufe:
1. Gleiche Fixture-Dateien und gleiche `measure.py` Version verwenden.
2. Gleiches Python-Setup nutzen (insb. ob `tiktoken` installiert ist).
3. `results/latest.json` als repo-gepinnten Gate-Stand halten (nicht pro Check-Lauf mutieren).
4. Frische Release-Evidence per `python3 scripts/release_snapshot.py` nach `docs/release-artifacts/` exportieren.
5. Für `calibration_*`-Fixtures die Point-Reihenfolge und Klassen-Namen stabil halten (der Klassen-Breakdown wird aus dem Dateinamenpräfix `calibration_<klasse>_*` abgeleitet).
