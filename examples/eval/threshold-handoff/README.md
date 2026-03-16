# Threshold batch handoff fixtures

Checked-in batch inputs and artifact trees for the numeric-threshold eval lane.

Run the refresh helper from the repo root. It rewrites the tracked snapshot outputs in place, so a deterministic replay leaves `git diff -- examples/eval/threshold-handoff` empty.

## Fixture layout

- `batch/` — three threshold events for batch replay: `ok`, `no-action`, `invalid`
- `baseline/` — flat `mode=all` artifact set with manifest + `run.id=threshold-ci-baseline-001`
- `candidate-clean/` — manifest-bearing clean candidate snapshot + `run.id=threshold-ci-candidate-clean-001`
- `triage-by-status/` — `errors-only` + `by-status` artifact set with manifest + `run.id=threshold-ci-triage-001`, also reused as the strict self-compare candidate snapshot
- `*.expected.summary.txt` — frozen `--summary` outputs for verify/compare/self-compare handoff checks
- `*.expected.json` — frozen standalone verify/compare plus generation-time self-verify/self-compare JSON sidecars

## One-shot refresh

```bash
python3 scripts/refresh_threshold_handoff.py
git diff -- examples/eval/threshold-handoff
```

The helper regenerates all tracked outputs in one deterministic pass:

- `baseline/`
- `candidate-clean/`
- `triage-by-status/`
- `baseline.verify.expected.summary.txt`
- `baseline.verify.expected.json`
- `triage.verify.expected.summary.txt`
- `triage.verify.expected.json`
- `candidate-clean-vs-baseline.compare.expected.json`
- `triage-vs-baseline.compare.expected.summary.txt`
- `triage-vs-baseline.compare.expected.json`
- `candidate-clean-vs-baseline.self-compare.expected.summary.txt`
- `triage-by-status-vs-baseline.self-compare.expected.summary.txt`
- `self-compare-vs-baseline.expected.json`
- `self-compare-triage-vs-baseline.expected.json`

For temp-copy replays or test harnesses, point it at another fixture tree:

```bash
python3 scripts/refresh_threshold_handoff.py --fixture-root /tmp/threshold-handoff
```

## Self-compare manifest policy

If the baseline `summary.json` carries `artifact_sha256`, generation-time self-compare compares that mapping as part of the handoff contract and auto-writes the same manifest into the freshly generated candidate `summary.json`. That keeps the clean handoff contract identical whether the candidate run passed `--batch-output-manifest` explicitly or relied on the baseline-triggered self-compare path. If the baseline has no manifest, candidate manifest emission stays opt-in.

## Raw commands

The helper is the source of truth for the refresh sequence. If you need the exact underlying commands, inspect `scripts/refresh_threshold_handoff.py`.
