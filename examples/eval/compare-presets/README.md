# Compare preset fixtures

Checked-in artifact sets for deterministic `erz eval --batch-output-compare` examples.

## Fixture lanes

- `baseline/` — canonical three-event batch artifact set with manifest.
- `candidate-clean/` — identical artifacts, only `run.id` differs, so `--batch-output-compare-profile clean` stays green.
- `candidate-metadata-only/` — identical artifacts, but `summary.json` carries one metadata drift (`layout`), so strict `metadata-only` passes when `--batch-output-compare-expected-metadata-mismatches-count 1` is set.
- `candidate-asymmetric/` — generated with `--batch-output-errors-only --batch-output-layout by-status`, so compare sees asymmetric artifact drift without byte changes on surviving artifacts. Intended for `expected-asymmetric-drift` examples.

## Copy-paste commands

```bash
erz eval --batch-output-compare examples/eval/compare-presets/candidate-clean --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile clean

erz eval --batch-output-compare examples/eval/compare-presets/candidate-metadata-only --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile metadata-only --batch-output-compare-expected-metadata-mismatches-count 1

erz eval --batch-output-compare examples/eval/compare-presets/candidate-asymmetric --batch-output-compare-against examples/eval/compare-presets/baseline --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 3 --batch-output-compare-expected-candidate-only-count 2 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2 --batch-output-compare-expected-metadata-mismatches-count 4
```
