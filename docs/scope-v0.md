# erzlang Scope v0

## Zielbild
In 6 Monaten liefern wir keine neue General-Purpose-Sprache, sondern eine DSL für Agenten-Workflows:

`ingest -> normalize -> evaluate -> act`

Die DSL beschreibt Pipelines, Policies und Entscheidungen mit deterministischer Ausführung und Trace.

## Harte Abgrenzung
- Keine beliebige Algorithmik
- Keine imperative Kontrollflusskonstrukte
- Keine Runtime-Side-Effects innerhalb der Evaluation

## Kernschnittstellen
- Input: streng schema-validierbare Events
- Verarbeitung: Rule Engine mit klarer Semantik
- Output: Actions + maschinenlesbarer Trace

## Qualitätskriterien
- Deterministisch replaybar
- Stable Parser/Printer-Roundtrip
- Messbare Token-Effizienz

## Kill-Kriterium (bestätigt)
Wenn `erzlang compact` gegen `kompaktes JSON + References` nicht mindestens 25% Token-Ersparnis oder bessere Agent-Robustheit zeigt, wird der Syntax-Scope reduziert und Fokus auf IR/Runtime/Tooling gelegt.
