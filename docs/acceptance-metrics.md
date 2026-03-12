# Acceptance & Metrics (v0.1)

## Primäre Metriken

1. Token-Effizienz
   - Ziel: >= 25% Einsparung ggü. Baseline (`compact JSON + refs`)
   - Messung über standardisierte Prompt-Packs

2. Determinismus
   - Gleicher Input + gleiche Version + gleiche Seeds/now => identischer Output + Trace

3. Parser/Printer-Stabilität
   - Roundtrip 100% für definierte Fixture-Sets

4. Trace-Vollständigkeit
   - Jede Rule-Fire erzeugt einen TraceStep mit `rule_id`, `matched_clauses`
   - Optionale Trace-Felder bleiben konsistent und deterministisch: `score` (finite float), `calibrated_probability` (finite float in `[0.0, 1.0]`)
   - `calibrated_probability` bleibt optional (nur bei aktiver Calibration-Konfiguration)

## Erste Benchmark-Events
- ingest_event
- alert_event

## Review-Gate pro Sprint
- Reproduzierbare Benchmarks
- Keine Scope-Ausweitung auf GP-Features
- Klare Migrationsnotizen bei IR-Änderungen

## v0.1 release-close checklist (frozen 2026-03-02)

- [x] Quality gates rerun and passed via `./scripts/check.sh`.
- [x] Token benchmark threshold reconfirmed with active corpus (`48.96%` vs target `>= 25%`).
- [x] Compatibility anchor references remain in sync across the public docs surface (`docs/migrations.md`, `CHANGELOG.md`, release notes).
- [x] Active profile set frozen for v0.1 ship scope: `Sprint-5 calibration additive profile`, `Sprint-6 compatibility/ref-hardening profile`.
- [x] Ship-ready status recorded in `docs/review-sprint1.md` (section "v0.1 ship-ready summary").
- [x] Remaining items limited to non-blocking post-ship follow-ups.
