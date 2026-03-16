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

## Missing-path smoke lane

Program and inputs:

- `program-missing-paths.erz`
- `event-missing-path-ok.json`
- `event-missing-path-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-missing-path-ok.expected.envelope.json`
- `event-missing-path-no-action.expected.envelope.json`
- `event-missing-path-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-missing-paths.erz --input examples/eval/event-missing-path-ok.json
erz eval examples/eval/program-missing-paths.erz --input examples/eval/event-missing-path-no-action.json
erz eval examples/eval/program-missing-paths.erz --input examples/eval/event-missing-path-no-action.json --summary
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

## List-membership smoke lane

Program and inputs:

- `program-any-in.erz`
- `event-any-in-ok.json`
- `event-any-in-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-any-in-ok.expected.envelope.json`
- `event-any-in-no-action.expected.envelope.json`
- `event-any-in-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-any-in.erz --input examples/eval/event-any-in-ok.json
erz eval examples/eval/program-any-in.erz --input examples/eval/event-any-in-no-action.json
erz eval examples/eval/program-any-in.erz --input examples/eval/event-any-in-no-action.json --summary
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

## Batch index smoke lane

Checked-in batch index fixture:

- `batch-index.json` — declarative replay order for the base `batch/` events, mixing string and object entries

Copy-paste commands:

```bash
erz eval examples/eval/program.erz --batch examples/eval/batch-index.json
erz eval examples/eval/program.erz --batch examples/eval/batch-index.json --exclude "*invalid*.json" --summary --batch-strict --batch-expected-event-count 2 --batch-expected-total-event-count 3 --batch-expected-total-event 02-no-action.json --batch-expected-total-event 01-ok.json --batch-expected-total-event 03-invalid.json --batch-expected-selected-event 02-no-action.json --batch-expected-selected-event 01-ok.json
```

## Numeric threshold batch handoff lane

Checked-in compare/verify handoff fixtures for the same threshold program live under `threshold-handoff/`.

Contents:

- `threshold-handoff/batch/` — deterministic batch inputs (`ok`, `no-action`, `invalid`)
- `threshold-handoff/baseline/` — flat manifest-bearing artifact set with `run.id`
- `threshold-handoff/candidate-clean/` — checked-in clean self-compare candidate snapshot with manifest + `run.id`
- `threshold-handoff/triage-by-status/` — `errors-only` + `by-status` artifact set with `run.id`, also reused as the strict self-compare candidate snapshot
- `threshold-handoff/*.expected.summary.txt` — frozen verify/compare/self-compare summary exports
- `threshold-handoff/baseline.verify.expected.json` — frozen standalone verify JSON sidecar for the flat baseline lane
- `threshold-handoff/triage.verify.expected.json` — frozen strict verify JSON sidecar, reused by standalone verify and generation-time self-verify
- `threshold-handoff/candidate-clean-vs-baseline.compare.expected.json` — frozen clean standalone compare export
- `threshold-handoff/triage-vs-baseline.compare.expected.json` — frozen strict asymmetric standalone compare export
- `threshold-handoff/self-compare-vs-baseline.expected.json` — frozen clean generation-time self-compare export
- `threshold-handoff/self-compare-triage-vs-baseline.expected.json` — frozen strict asymmetric self-compare export

Because `threshold-handoff/baseline/summary.json` carries `artifact_sha256`, the generation-time self-compare lane auto-emits the same candidate manifest that an explicit `--batch-output-manifest` run would write. The checked-in replay commands still pass the flag so the standalone candidate snapshot and the self-compare handoff stay byte-identical.

See `threshold-handoff/README.md` for the one-shot refresh helper. The checked-in replay now covers standalone verify/compare JSON sidecars plus the generation-time self-verify/self-compare lane, so `python3 scripts/refresh_threshold_handoff.py` should leave `git diff -- examples/eval/threshold-handoff` empty when the handoff contract still holds.
