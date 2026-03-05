# erzlang

Agentenfreundliche DSL fuer deterministische Policy-Ausfuehrung, trace-first Explainability und kompakte, maschinenlesbare Outputs.

## Was es ist

`erzlang` ist bewusst **keine** General-Purpose-Sprache.
Der Kern ist schmal gehalten: Regeln, Aktionen, Trace, stabile Fehlervertraege.

## Scope v0.1

- Deterministische Ausfuehrung
- Canonical IR als Kernformat
- Trace als Standard-Output
- JSON-Error-Envelopes fuer Tooling
- Compact-Form mit Referenzen (`rf`) und Payload-Container (`pl`)

## Nicht-Ziele v0.1

- Funktionen
- Schleifen
- Module
- Typinferenz

## Schnellstart

```bash
# 1) Parse + Validate
python3 -m cli.main parse examples/sample.erz
python3 -m cli.main validate examples/sample.erz

# 2) Canonical Formatting
python3 -m cli.main fmt examples/sample.erz

# 3) JSON -> compact+refs
python3 -m cli.main pack examples/program-packs/ingest-normalize/baseline.json

# 4) compact+refs -> canonical JSON
python3 -m cli.main unpack examples/program-packs/ingest-normalize/program.erz
```

## Error Envelope (kurz)

Mit `--json-errors` liefern `parse`, `validate`, `pack`, `unpack` ein stabiles JSON-Envelope mit:

- `code`
- `stage`
- `message`
- `span`
- `hint`
- `details`

Ohne Flag bleibt stderr bewusst human-readable.

## Repo-Struktur

- `cli/` CLI entrypoints
- `runtime/` deterministische Runtime + Fehlerabbildung
- `ir/` Referenz-/IR-Modelle
- `schema/` JSON-Schema (`ir.v0.1`)
- `examples/` lauffaehige DSL- und Program-Pack-Beispiele
- `scripts/` Check-/Gate-Helfer
- `docs/` Vertrags- und Designdokumente

## Wichtige Dokus

- Scope: `docs/scope-v0.md`
- Runtime-Vertrag: `docs/runtime-determinism.md`
- IR-Vertrag: `docs/ir-contract-v0.1.md`
- Migrationshinweise: `docs/migrations.md`
- Release-Artefakte: `docs/release-artifacts/README.md`

## Status

Der Fokus liegt auf Stabilitaet und klaren Vertraegen fuer Agent-Workflows, nicht auf Sprachflaeche.
Wenn ein Verhalten nicht deterministisch abgesichert ist, gilt es als nicht fertig.
