# Threshold batch handoff fixtures

Checked-in batch inputs and artifact trees for the numeric-threshold eval lane.

Run the replay commands below from the repo root. They intentionally rewrite the tracked snapshot outputs in place, so a deterministic replay leaves `git diff -- examples/eval/threshold-handoff` empty.

## Fixture layout

- `batch/` — three threshold events for batch replay: `ok`, `no-action`, `invalid`
- `baseline/` — flat `mode=all` artifact set with manifest + `run.id=threshold-ci-baseline-001`
- `candidate-clean/` — manifest-bearing clean candidate snapshot + `run.id=threshold-ci-candidate-clean-001`
- `triage-by-status/` — `errors-only` + `by-status` artifact set with manifest + `run.id=threshold-ci-triage-001`, also used as the strict self-compare candidate snapshot
- `*.expected.summary.txt` — frozen `--summary` outputs for verify/compare/self-compare handoff checks
- `self-compare-vs-baseline.expected.json` — frozen clean generation-time self-compare export against the manifest-bearing baseline
- `self-compare-triage-vs-baseline.expected.json` — frozen strict asymmetric generation-time self-compare export against the same baseline

## Self-compare manifest policy

If the baseline `summary.json` carries `artifact_sha256`, generation-time self-compare compares that mapping as part of the handoff contract and auto-writes the same manifest into the freshly generated candidate `summary.json`. That keeps the clean handoff contract identical whether the candidate run passed `--batch-output-manifest` explicitly or relied on the baseline-triggered self-compare path. If the baseline has no manifest, candidate manifest emission stays opt-in.

## Copy-paste commands

```bash
erz eval --batch-output-verify examples/eval/threshold-handoff/baseline --summary --batch-output-verify-profile default --batch-output-verify-require-run-id --batch-output-verify-expected-run-id-pattern '^threshold-ci-.*$' --batch-output-verify-expected-event-count 3

erz eval --batch-output-verify examples/eval/threshold-handoff/triage-by-status --summary --batch-output-verify-profile triage-by-status --batch-output-verify-require-run-id --batch-output-verify-expected-run-id-pattern '^threshold-ci-.*$' --batch-output-verify-expected-event-count 3

erz eval --batch-output-compare examples/eval/threshold-handoff/triage-by-status --batch-output-compare-against examples/eval/threshold-handoff/baseline --summary --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 3 --batch-output-compare-expected-candidate-only-count 2 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2 --batch-output-compare-expected-metadata-mismatches-count 4

python3 -m cli.main eval examples/eval/program-thresholds.erz --batch examples/eval/threshold-handoff/batch --batch-output examples/eval/threshold-handoff/candidate-clean --batch-output-run-id threshold-ci-candidate-clean-001 --batch-output-manifest --summary --batch-output-self-compare-against examples/eval/threshold-handoff/baseline --batch-output-compare-summary-file examples/eval/threshold-handoff/candidate-clean-vs-baseline.self-compare.expected.summary.txt

python3 -m cli.main eval examples/eval/program-thresholds.erz --batch examples/eval/threshold-handoff/batch --batch-output examples/eval/threshold-handoff/triage-by-status --batch-output-errors-only --batch-output-layout by-status --batch-output-run-id threshold-ci-triage-001 --batch-output-manifest --summary --batch-output-self-compare-against examples/eval/threshold-handoff/baseline --batch-output-self-compare-strict --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 3 --batch-output-compare-expected-candidate-only-count 2 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2 --batch-output-compare-expected-metadata-mismatches-count 4 --batch-output-compare-summary-file examples/eval/threshold-handoff/triage-by-status-vs-baseline.self-compare.expected.summary.txt

git diff -- examples/eval/threshold-handoff
```

## Optional JSON export refresh

```bash
python3 -m cli.main eval examples/eval/program-thresholds.erz --batch examples/eval/threshold-handoff/batch --batch-output examples/eval/threshold-handoff/candidate-clean --batch-output-run-id threshold-ci-candidate-clean-001 --batch-output-manifest --batch-output-self-compare-against examples/eval/threshold-handoff/baseline --batch-output-compare-summary-file examples/eval/threshold-handoff/self-compare-vs-baseline.expected.json

python3 -m cli.main eval examples/eval/program-thresholds.erz --batch examples/eval/threshold-handoff/batch --batch-output examples/eval/threshold-handoff/triage-by-status --batch-output-errors-only --batch-output-layout by-status --batch-output-run-id threshold-ci-triage-001 --batch-output-manifest --batch-output-self-compare-against examples/eval/threshold-handoff/baseline --batch-output-self-compare-strict --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 3 --batch-output-compare-expected-candidate-only-count 2 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2 --batch-output-compare-expected-metadata-mismatches-count 4 --batch-output-compare-summary-file examples/eval/threshold-handoff/self-compare-triage-vs-baseline.expected.json
```

## Regeneration

```bash
python3 -m cli.main eval examples/eval/program-thresholds.erz --batch examples/eval/threshold-handoff/batch --batch-output examples/eval/threshold-handoff/baseline --batch-output-run-id threshold-ci-baseline-001 --batch-output-manifest

python3 -m cli.main eval examples/eval/program-thresholds.erz --batch examples/eval/threshold-handoff/batch --batch-output examples/eval/threshold-handoff/candidate-clean --batch-output-run-id threshold-ci-candidate-clean-001 --batch-output-manifest

python3 -m cli.main eval examples/eval/program-thresholds.erz --batch examples/eval/threshold-handoff/batch --batch-output examples/eval/threshold-handoff/triage-by-status --batch-output-errors-only --batch-output-layout by-status --batch-output-run-id threshold-ci-triage-001 --batch-output-self-verify --batch-output-self-verify-strict --batch-output-verify-profile triage-by-status --batch-output-verify-require-run-id --batch-output-verify-expected-run-id-pattern '^threshold-ci-.*$' --batch-output-verify-expected-event-count 3
```
