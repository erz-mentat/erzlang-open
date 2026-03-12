# Eval fixtures

Minimal `erz eval` inputs and frozen outputs for copy-paste checks.

## Nested payload path smoke lane

Program and inputs:

- `program-paths.erz`
- `event-path-ok.json`
- `event-path-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-path-ok.expected.envelope.json`
- `event-path-no-action.expected.envelope.json`
- `event-path-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-ok.json
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-no-action.json
erz eval examples/eval/program-paths.erz --input examples/eval/event-path-no-action.json --summary
```

## String payload smoke lane

Program and inputs:

- `program-strings.erz`
- `event-string-ok.json`
- `event-string-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-string-ok.expected.envelope.json`
- `event-string-no-action.expected.envelope.json`
- `event-string-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-strings.erz --input examples/eval/event-string-ok.json
erz eval examples/eval/program-strings.erz --input examples/eval/event-string-no-action.json
erz eval examples/eval/program-strings.erz --input examples/eval/event-string-no-action.json --summary
```

## Payload-length smoke lane

Program and inputs:

- `program-lengths.erz`
- `event-length-ok.json`
- `event-length-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-length-ok.expected.envelope.json`
- `event-length-no-action.expected.envelope.json`
- `event-length-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-ok.json
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-no-action.json
erz eval examples/eval/program-lengths.erz --input examples/eval/event-length-no-action.json --summary
```

## Numeric threshold smoke lane

Program and inputs:

- `program-thresholds.erz`
- `event-threshold-ok.json`
- `event-threshold-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-threshold-ok.expected.envelope.json`
- `event-threshold-no-action.expected.envelope.json`
- `event-threshold-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-ok.json
erz eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-no-action.json
erz eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-no-action.json --summary
```

## Numeric threshold batch handoff lane

Checked-in compare/verify handoff fixtures for the same threshold program live under `threshold-handoff/`.

Contents:

- `threshold-handoff/batch/` — deterministic batch inputs (`ok`, `no-action`, `invalid`)
- `threshold-handoff/baseline/` — flat manifest-bearing artifact set with `run.id`
- `threshold-handoff/candidate-clean/` — checked-in clean self-compare candidate snapshot with manifest + `run.id`
- `threshold-handoff/triage-by-status/` — `errors-only` + `by-status` artifact set with `run.id`, also reused as the strict self-compare candidate snapshot
- `threshold-handoff/*.expected.summary.txt` — frozen verify/compare/self-compare summary exports
- `threshold-handoff/self-compare-vs-baseline.expected.json` — frozen clean generation-time self-compare export
- `threshold-handoff/self-compare-triage-vs-baseline.expected.json` — frozen strict asymmetric self-compare export

Because `threshold-handoff/baseline/summary.json` carries `artifact_sha256`, the generation-time self-compare lane auto-emits the same candidate manifest that an explicit `--batch-output-manifest` run would write. The checked-in replay commands still pass the flag so the standalone candidate snapshot and the self-compare handoff stay byte-identical.

See `threshold-handoff/README.md` for in-place snapshot replay commands. The self-compare lane is designed so you can rerun the checked-in commands and expect `git diff -- examples/eval/threshold-handoff` to stay empty when the handoff contract still holds.
