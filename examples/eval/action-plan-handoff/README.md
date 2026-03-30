# Action-plan batch handoff fixtures

Checked-in batch inputs and artifact trees for the refs-backed `erz eval --action-plan` handoff lane.

This fixture set freezes the operator-visible batch-output surfaces that matter after action-plan materialization landed: standalone verify, self-verify, standalone compare, and generation-time self-compare all carry the same deterministic `action_plan_count=1` and `resolved_ref_count=1` contract, even across the asymmetric `errors-only` + `by-status` triage snapshot.

## Fixture layout

- `batch/` — three canonical eval events: `ok`, `no-action`, `invalid`
- `baseline/` — flat `mode=all` artifact set with manifest + `run.id=action-plan-ci-baseline-001`
- `candidate-clean/` — manifest-bearing clean candidate snapshot + `run.id=action-plan-ci-candidate-clean-001`
- `triage-by-status/` — `errors-only` + `by-status` artifact set with manifest + `run.id=action-plan-ci-triage-001`
- `baseline.verify.expected.summary.txt` / `baseline.verify.expected.json` — frozen standalone verify outputs
- `triage.handoff-bundle.expected.json` — frozen strict generation-time self-verify handoff bundle for the asymmetric triage snapshot
- `candidate-clean-vs-baseline.compare.expected.summary.txt` / `.json` — frozen strict standalone compare outputs
- `triage-vs-baseline.compare.expected.summary.txt` / `.json` — frozen strict asymmetric compare outputs
- `candidate-clean-vs-baseline.handoff-bundle.expected.json` — frozen clean generation-time self-compare handoff bundle
- `triage-by-status-vs-baseline.handoff-bundle.expected.json` — frozen strict asymmetric generation-time self-compare handoff bundle

## One-shot refresh

```bash
python3 scripts/refresh_action_plan_handoff.py
git diff -- examples/eval/action-plan-handoff
```

The helper regenerates all tracked outputs in one deterministic pass, including the asymmetric `errors-only` + `by-status` triage tree plus the generation-time handoff bundles. A no-op refresh should leave the fixture tree byte-identical.

For temp-copy replays or harnesses, point it at another fixture tree:

```bash
python3 scripts/refresh_action_plan_handoff.py --fixture-root /tmp/action-plan-handoff
```

## Program under test

The fixture tree intentionally reuses `examples/eval/program.erz`, the smallest checked-in refs-backed rule set. The `ok` event materializes one `notify` step and resolves `@sev_label` to `high`, while the `no-action` and `invalid` events keep the error/no-op envelope shape honest. The asymmetric triage snapshot proves that operators can drop success artifacts for CI triage without losing the summary-level action-plan and resolved-ref counters that signal whether the materialization lane still fired.
