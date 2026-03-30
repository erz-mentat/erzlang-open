# Eval fixtures

Minimal `erz eval` inputs and frozen outputs for copy-paste checks.

Top-level smoke fixtures can be regenerated directly with `python3 scripts/refresh_eval_example_fixtures.py`, or as part of the repo-wide umbrella refresh via `python3 scripts/refresh_contract_fixtures.py`. The dedicated `action-plan-handoff/` and `threshold-handoff/` trees keep their own refresh helpers underneath because they rewrite tracked artifact directories, not just the top-level smoke outputs listed here.

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

## Cross-path payload compare smoke lane

Program and inputs:

- `program-cross-paths.erz`
- `event-cross-path-ok.json`
- `event-cross-path-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-cross-path-ok.expected.envelope.json`
- `event-cross-path-no-action.expected.envelope.json`
- `event-cross-path-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-cross-paths.erz --input examples/eval/event-cross-path-ok.json
erz eval examples/eval/program-cross-paths.erz --input examples/eval/event-cross-path-no-action.json
erz eval examples/eval/program-cross-paths.erz --input examples/eval/event-cross-path-no-action.json --summary
```

## Case-insensitive cross-path payload compare smoke lane

Program and inputs:

- `program-cross-path-ci.erz`
- `event-cross-path-ci-ok.json`
- `event-cross-path-ci-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-cross-path-ci-ok.expected.envelope.json`
- `event-cross-path-ci-no-action.expected.envelope.json`
- `event-cross-path-ci-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-cross-path-ci.erz --input examples/eval/event-cross-path-ci-ok.json
erz eval examples/eval/program-cross-path-ci.erz --input examples/eval/event-cross-path-ci-no-action.json
erz eval examples/eval/program-cross-path-ci.erz --input examples/eval/event-cross-path-ci-no-action.json --summary
```

## Cross-path string compare smoke lane

Program and inputs:

- `program-cross-path-strings.erz`
- `event-cross-path-strings-ok.json`
- `event-cross-path-strings-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-cross-path-strings-ok.expected.envelope.json`
- `event-cross-path-strings-no-action.expected.envelope.json`
- `event-cross-path-strings-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-cross-path-strings.erz --input examples/eval/event-cross-path-strings-ok.json
erz eval examples/eval/program-cross-path-strings.erz --input examples/eval/event-cross-path-strings-no-action.json
erz eval examples/eval/program-cross-path-strings.erz --input examples/eval/event-cross-path-strings-no-action.json --summary
```

## Cross-path list membership smoke lane

Program and inputs:

- `program-cross-path-lists.erz`
- `event-cross-path-lists-ok.json`
- `event-cross-path-lists-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-cross-path-lists-ok.expected.envelope.json`
- `event-cross-path-lists-no-action.expected.envelope.json`
- `event-cross-path-lists-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-cross-path-lists.erz --input examples/eval/event-cross-path-lists-ok.json
erz eval examples/eval/program-cross-path-lists.erz --input examples/eval/event-cross-path-lists-no-action.json
erz eval examples/eval/program-cross-path-lists.erz --input examples/eval/event-cross-path-lists-no-action.json --summary
```

## Cross-path regex smoke lane

Program and inputs:

- `program-cross-path-regex.erz`
- `event-cross-path-regex-ok.json`
- `event-cross-path-regex-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-cross-path-regex-ok.expected.envelope.json`
- `event-cross-path-regex-no-action.expected.envelope.json`
- `event-cross-path-regex-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-cross-path-regex.erz --input examples/eval/event-cross-path-regex-ok.json
erz eval examples/eval/program-cross-path-regex.erz --input examples/eval/event-cross-path-regex-no-action.json
erz eval examples/eval/program-cross-path-regex.erz --input examples/eval/event-cross-path-regex-no-action.json --summary
```

## Payload-type smoke lane

Program and inputs:

- `program-types.erz`
- `event-type-ok.json`
- `event-type-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-type-ok.expected.envelope.json`
- `event-type-no-action.expected.envelope.json`
- `event-type-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-types.erz --input examples/eval/event-type-ok.json
erz eval examples/eval/program-types.erz --input examples/eval/event-type-no-action.json
erz eval examples/eval/program-types.erz --input examples/eval/event-type-no-action.json --summary
```

## Event-type set smoke lane

Program and inputs:

- `program-event-type-set.erz`
- `event-event-type-set-ok.json`
- `event-event-type-set-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-event-type-set-ok.expected.envelope.json`
- `event-event-type-set-no-action.expected.envelope.json`
- `event-event-type-set-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-event-type-set.erz --input examples/eval/event-event-type-set-ok.json
erz eval examples/eval/program-event-type-set.erz --input examples/eval/event-event-type-set-no-action.json
erz eval examples/eval/program-event-type-set.erz --input examples/eval/event-event-type-set-no-action.json --summary
```

## Case-insensitive event-type smoke lane

Program and inputs:

- `program-event-type-ci.erz`
- `event-event-type-ci-ok.json`
- `event-event-type-ci-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-event-type-ci-ok.expected.envelope.json`
- `event-event-type-ci-no-action.expected.envelope.json`
- `event-event-type-ci-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-event-type-ci.erz --input examples/eval/event-event-type-ci-ok.json
erz eval examples/eval/program-event-type-ci.erz --input examples/eval/event-event-type-ci-no-action.json
erz eval examples/eval/program-event-type-ci.erz --input examples/eval/event-event-type-ci-no-action.json --summary
```

## Event-type path compare smoke lane

Program and inputs:

- `program-event-type-paths.erz`
- `event-event-type-paths-ok.json`
- `event-event-type-paths-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-event-type-paths-ok.expected.envelope.json`
- `event-event-type-paths-no-action.expected.envelope.json`
- `event-event-type-paths-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-event-type-paths.erz --input examples/eval/event-event-type-paths-ok.json
erz eval examples/eval/program-event-type-paths.erz --input examples/eval/event-event-type-paths-no-action.json
erz eval examples/eval/program-event-type-paths.erz --input examples/eval/event-event-type-paths-no-action.json --summary
```

## Event-type regex smoke lane

Program and inputs:

- `program-event-type-patterns.erz`
- `event-event-type-patterns-ok.json`
- `event-event-type-patterns-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-event-type-patterns-ok.expected.envelope.json`
- `event-event-type-patterns-no-action.expected.envelope.json`
- `event-event-type-patterns-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-event-type-patterns.erz --input examples/eval/event-event-type-patterns-ok.json
erz eval examples/eval/program-event-type-patterns.erz --input examples/eval/event-event-type-patterns-no-action.json
erz eval examples/eval/program-event-type-patterns.erz --input examples/eval/event-event-type-patterns-no-action.json --summary
```

## Event-type string compare smoke lane

Program and inputs:

- `program-event-type-string.erz`
- `event-event-type-string-ok.json`
- `event-event-type-string-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-event-type-string-ok.expected.envelope.json`
- `event-event-type-string-no-action.expected.envelope.json`
- `event-event-type-string-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-event-type-string.erz --input examples/eval/event-event-type-string-ok.json
erz eval examples/eval/program-event-type-string.erz --input examples/eval/event-event-type-string-no-action.json
erz eval examples/eval/program-event-type-string.erz --input examples/eval/event-event-type-string-no-action.json --summary
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

## Case-insensitive string payload smoke lane

Program and inputs:

- `program-strings-ci.erz`
- `event-string-ci-ok.json`
- `event-string-ci-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-string-ci-ok.expected.envelope.json`
- `event-string-ci-no-action.expected.envelope.json`
- `event-string-ci-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-strings-ci.erz --input examples/eval/event-string-ci-ok.json
erz eval examples/eval/program-strings-ci.erz --input examples/eval/event-string-ci-no-action.json
erz eval examples/eval/program-strings-ci.erz --input examples/eval/event-string-ci-no-action.json --summary
```

## Case-insensitive exact-string smoke lane

Program and inputs:

- `program-equals-ci.erz`
- `event-equals-ci-ok.json`
- `event-equals-ci-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-equals-ci-ok.expected.envelope.json`
- `event-equals-ci-no-action.expected.envelope.json`
- `event-equals-ci-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-equals-ci.erz --input examples/eval/event-equals-ci-ok.json
erz eval examples/eval/program-equals-ci.erz --input examples/eval/event-equals-ci-no-action.json
erz eval examples/eval/program-equals-ci.erz --input examples/eval/event-equals-ci-no-action.json --summary
```

## Case-insensitive membership smoke lane

Program and inputs:

- `program-membership-ci.erz`
- `event-membership-ci-ok.json`
- `event-membership-ci-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-membership-ci-ok.expected.envelope.json`
- `event-membership-ci-no-action.expected.envelope.json`
- `event-membership-ci-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-membership-ci.erz --input examples/eval/event-membership-ci-ok.json
erz eval examples/eval/program-membership-ci.erz --input examples/eval/event-membership-ci-no-action.json
erz eval examples/eval/program-membership-ci.erz --input examples/eval/event-membership-ci-no-action.json --summary
```

## Negative case-insensitive string payload smoke lane

Program and inputs:

- `program-string-negation-ci.erz`
- `event-string-negation-ci-ok.json`
- `event-string-negation-ci-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-string-negation-ci-ok.expected.envelope.json`
- `event-string-negation-ci-no-action.expected.envelope.json`
- `event-string-negation-ci-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-string-negation-ci.erz --input examples/eval/event-string-negation-ci-ok.json
erz eval examples/eval/program-string-negation-ci.erz --input examples/eval/event-string-negation-ci-no-action.json
erz eval examples/eval/program-string-negation-ci.erz --input examples/eval/event-string-negation-ci-no-action.json --summary
```

## Negative string payload smoke lane

Program and inputs:

- `program-string-negation.erz`
- `event-string-negation-ok.json`
- `event-string-negation-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-string-negation-ok.expected.envelope.json`
- `event-string-negation-no-action.expected.envelope.json`
- `event-string-negation-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-string-negation.erz --input examples/eval/event-string-negation-ok.json
erz eval examples/eval/program-string-negation.erz --input examples/eval/event-string-negation-no-action.json
erz eval examples/eval/program-string-negation.erz --input examples/eval/event-string-negation-no-action.json --summary
```

## Regex payload smoke lane

Program and inputs:

- `program-matches.erz`
- `event-matches-ok.json`
- `event-matches-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-matches-ok.expected.envelope.json`
- `event-matches-no-action.expected.envelope.json`
- `event-matches-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-matches.erz --input examples/eval/event-matches-ok.json
erz eval examples/eval/program-matches.erz --input examples/eval/event-matches-no-action.json
erz eval examples/eval/program-matches.erz --input examples/eval/event-matches-no-action.json --summary
```

## Case-insensitive regex payload smoke lane

Program and inputs:

- `program-matches-ci.erz`
- `event-matches-ci-ok.json`
- `event-matches-ci-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-matches-ci-ok.expected.envelope.json`
- `event-matches-ci-no-action.expected.envelope.json`
- `event-matches-ci-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-matches-ci.erz --input examples/eval/event-matches-ci-ok.json
erz eval examples/eval/program-matches-ci.erz --input examples/eval/event-matches-ci-no-action.json
erz eval examples/eval/program-matches-ci.erz --input examples/eval/event-matches-ci-no-action.json --summary
```

## Negative regex payload smoke lane

Program and inputs:

- `program-not-matches.erz`
- `event-not-matches-ok.json`
- `event-not-matches-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-not-matches-ok.expected.envelope.json`
- `event-not-matches-no-action.expected.envelope.json`
- `event-not-matches-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-not-matches.erz --input examples/eval/event-not-matches-ok.json
erz eval examples/eval/program-not-matches.erz --input examples/eval/event-not-matches-no-action.json
erz eval examples/eval/program-not-matches.erz --input examples/eval/event-not-matches-no-action.json --summary
```

## Negative case-insensitive regex payload smoke lane

Program and inputs:

- `program-not-matches-ci.erz`
- `event-not-matches-ci-ok.json`
- `event-not-matches-ci-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-not-matches-ci-ok.expected.envelope.json`
- `event-not-matches-ci-no-action.expected.envelope.json`
- `event-not-matches-ci-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-not-matches-ci.erz --input examples/eval/event-not-matches-ci-ok.json
erz eval examples/eval/program-not-matches-ci.erz --input examples/eval/event-not-matches-ci-no-action.json
erz eval examples/eval/program-not-matches-ci.erz --input examples/eval/event-not-matches-ci-no-action.json --summary
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

## All-membership smoke lane

Program and inputs:

- `program-all-in.erz`
- `event-all-in-ok.json`
- `event-all-in-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-all-in-ok.expected.envelope.json`
- `event-all-in-no-action.expected.envelope.json`
- `event-all-in-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-all-in.erz --input examples/eval/event-all-in-ok.json
erz eval examples/eval/program-all-in.erz --input examples/eval/event-all-in-no-action.json
erz eval examples/eval/program-all-in.erz --input examples/eval/event-all-in-no-action.json --summary
```

## List-disjoint smoke lane

Program and inputs:

- `program-none-in.erz`
- `event-none-in-ok.json`
- `event-none-in-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-none-in-ok.expected.envelope.json`
- `event-none-in-no-action.expected.envelope.json`
- `event-none-in-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-none-in.erz --input examples/eval/event-none-in-ok.json
erz eval examples/eval/program-none-in.erz --input examples/eval/event-none-in-no-action.json
erz eval examples/eval/program-none-in.erz --input examples/eval/event-none-in-no-action.json --summary
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

## Exact payload-length smoke lane

Program and inputs:

- `program-length-exact.erz`
- `event-length-exact-ok.json`
- `event-length-exact-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-length-exact-ok.expected.envelope.json`
- `event-length-exact-no-action.expected.envelope.json`
- `event-length-exact-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-length-exact.erz --input examples/eval/event-length-exact-ok.json
erz eval examples/eval/program-length-exact.erz --input examples/eval/event-length-exact-no-action.json
erz eval examples/eval/program-length-exact.erz --input examples/eval/event-length-exact-no-action.json --summary
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

## Path-length compare smoke lane

Program and inputs:

- `program-length-paths.erz`
- `event-length-paths-ok.json`
- `event-length-paths-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-length-paths-ok.expected.envelope.json`
- `event-length-paths-no-action.expected.envelope.json`
- `event-length-paths-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-length-paths.erz --input examples/eval/event-length-paths-ok.json
erz eval examples/eval/program-length-paths.erz --input examples/eval/event-length-paths-no-action.json
erz eval examples/eval/program-length-paths.erz --input examples/eval/event-length-paths-no-action.json --summary
```

## Emptiness smoke lane

Program and inputs:

- `program-emptiness.erz`
- `event-emptiness-ok.json`
- `event-emptiness-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-emptiness-ok.expected.envelope.json`
- `event-emptiness-no-action.expected.envelope.json`
- `event-emptiness-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-emptiness.erz --input examples/eval/event-emptiness-ok.json
erz eval examples/eval/program-emptiness.erz --input examples/eval/event-emptiness-no-action.json
erz eval examples/eval/program-emptiness.erz --input examples/eval/event-emptiness-no-action.json --summary
```

## Generic negation smoke lane

Program and inputs:

- `program-negation.erz`
- `event-negation-ok.json`
- `event-negation-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-negation-ok.expected.envelope.json`
- `event-negation-no-action.expected.envelope.json`
- `event-negation-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-negation.erz --input examples/eval/event-negation-ok.json
erz eval examples/eval/program-negation.erz --input examples/eval/event-negation-no-action.json
erz eval examples/eval/program-negation.erz --input examples/eval/event-negation-no-action.json --summary
```

## String suffix smoke lane

Program and inputs:

- `program-suffix.erz`
- `event-suffix-ok.json`
- `event-suffix-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-suffix-ok.expected.envelope.json`
- `event-suffix-no-action.expected.envelope.json`
- `event-suffix-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-suffix.erz --input examples/eval/event-suffix-ok.json
erz eval examples/eval/program-suffix.erz --input examples/eval/event-suffix-no-action.json
erz eval examples/eval/program-suffix.erz --input examples/eval/event-suffix-no-action.json --summary
```

## Object-key smoke lane

Program and inputs:

- `program-object-keys.erz`
- `event-object-keys-ok.json`
- `event-object-keys-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-object-keys-ok.expected.envelope.json`
- `event-object-keys-no-action.expected.envelope.json`
- `event-object-keys-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-object-keys.erz --input examples/eval/event-object-keys-ok.json
erz eval examples/eval/program-object-keys.erz --input examples/eval/event-object-keys-no-action.json
erz eval examples/eval/program-object-keys.erz --input examples/eval/event-object-keys-no-action.json --summary
```

## Object-key set smoke lane

Program and inputs:

- `program-object-key-sets.erz`
- `event-object-key-sets-ok.json`
- `event-object-key-sets-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-object-key-sets-ok.expected.envelope.json`
- `event-object-key-sets-no-action.expected.envelope.json`
- `event-object-key-sets-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-object-key-sets.erz --input examples/eval/event-object-key-sets-ok.json
erz eval examples/eval/program-object-key-sets.erz --input examples/eval/event-object-key-sets-no-action.json
erz eval examples/eval/program-object-key-sets.erz --input examples/eval/event-object-key-sets-no-action.json --summary
```

## Object-key set path smoke lane

Program and inputs:

- `program-object-key-set-paths.erz`
- `event-object-key-set-paths-ok.json`
- `event-object-key-set-paths-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-object-key-set-paths-ok.expected.envelope.json`
- `event-object-key-set-paths-no-action.expected.envelope.json`
- `event-object-key-set-paths-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-object-key-set-paths.erz --input examples/eval/event-object-key-set-paths-ok.json
erz eval examples/eval/program-object-key-set-paths.erz --input examples/eval/event-object-key-set-paths-no-action.json
erz eval examples/eval/program-object-key-set-paths.erz --input examples/eval/event-object-key-set-paths-no-action.json --summary
```

## Rule-priority smoke lane

Program and inputs:

- `program-priority.erz`
- `event-priority-ok.json`
- `event-priority-no-action.json`

Frozen expected outputs from the current CLI/runtime:

- `event-priority-ok.expected.envelope.json`
- `event-priority-no-action.expected.envelope.json`
- `event-priority-no-action.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-priority.erz --input examples/eval/event-priority-ok.json
erz eval examples/eval/program-priority.erz --input examples/eval/event-priority-no-action.json
erz eval examples/eval/program-priority.erz --input examples/eval/event-priority-no-action.json --summary
```

## Action-plan single-event lane

Program and input:

- `program.erz`
- `event-ok.json`

Frozen expected outputs from the current CLI/runtime:

- `event-ok.action-plan.expected.envelope.json`
- `event-ok.action-plan.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --action-plan
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --action-plan --summary
```

## Single-run sidecar handoff lane

Program, input, and refs:

- `program-sidecar.erz`
- `event-ok.json`
- `refs-sidecar.json`

Frozen expected outputs from the current CLI/runtime:

- `event-sidecar.expected.envelope.json`
- `event-sidecar.expected.summary.txt`
- `event-sidecar.action-plan.expected.envelope.json`
- `event-sidecar.action-plan.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program-sidecar.erz --input examples/eval/event-ok.json --refs examples/eval/refs-sidecar.json --summary --summary-file /tmp/eval-sidecar.summary.txt --json-file /tmp/eval-sidecar.envelope.json
erz eval examples/eval/program-sidecar.erz --input examples/eval/event-ok.json --refs examples/eval/refs-sidecar.json --action-plan
erz eval examples/eval/program-sidecar.erz --input examples/eval/event-ok.json --refs examples/eval/refs-sidecar.json --action-plan --summary
```

## Batch sidecar handoff lane

Program and inputs:

- `program.erz`
- `batch/`

Frozen expected outputs from the current CLI/runtime:

- `batch.expected.envelope.json`
- `batch.expected.summary.txt`
- `batch.action-plan.expected.envelope.json`
- `batch.action-plan.expected.summary.txt`

Copy-paste commands:

```bash
erz eval examples/eval/program.erz --batch examples/eval/batch --summary-file /tmp/eval-batch.summary.txt --json-file /tmp/eval-batch.envelope.json
erz eval examples/eval/program.erz --batch examples/eval/batch --action-plan
erz eval examples/eval/program.erz --batch examples/eval/batch --action-plan --summary
```

Strict contract example for operator/CI lanes:

```bash
erz eval examples/eval/program.erz --batch examples/eval/batch-index.json --exclude "*invalid*.json" --action-plan --summary --batch-strict --batch-expected-event-count 2 --batch-expected-action-plan-count 1 --batch-expected-resolved-refs-count 1 --batch-expected-selected-event 02-no-action.json --batch-expected-selected-event 01-ok.json
```

## Batch index smoke lane

Checked-in batch index fixture:

- `batch-index.json` — declarative replay order for the base `batch/` events, mixing string and object entries

Copy-paste commands:

```bash
erz eval examples/eval/program.erz --batch examples/eval/batch-index.json
erz eval examples/eval/program.erz --batch examples/eval/batch-index.json --exclude "*invalid*.json" --summary --batch-strict --batch-expected-event-count 2 --batch-expected-total-event-count 3 --batch-expected-total-event 02-no-action.json --batch-expected-total-event 01-ok.json --batch-expected-total-event 03-invalid.json --batch-expected-selected-event 02-no-action.json --batch-expected-selected-event 01-ok.json
```

## Action-plan batch handoff lane

Checked-in compare/verify handoff fixtures for the refs-backed `--action-plan` lane live under `action-plan-handoff/`.

Contents:

- `action-plan-handoff/batch/` — deterministic refs-backed batch inputs (`ok`, `no-action`, `invalid`)
- `action-plan-handoff/baseline/` — flat manifest-bearing artifact set with `run.id`
- `action-plan-handoff/candidate-clean/` — checked-in clean candidate snapshot with manifest + `run.id`
- `action-plan-handoff/triage-by-status/` — `errors-only` + `by-status` artifact set with `run.id`, also reused as the strict asymmetric self-compare candidate snapshot
- `action-plan-handoff/baseline.verify.expected.*` — frozen standalone verify exports with `plan=1` and `resolved_refs=1`
- `action-plan-handoff/triage.handoff-bundle.expected.json` — frozen strict generation-time self-verify handoff bundle, still carrying `plan=1` and `resolved_refs=1` through the embedded verify verdict
- `action-plan-handoff/candidate-clean-vs-baseline.compare.expected.*` — frozen strict standalone compare exports
- `action-plan-handoff/triage-vs-baseline.compare.expected.*` — frozen strict asymmetric compare exports with preserved action-plan/ref counters
- `action-plan-handoff/candidate-clean-vs-baseline.handoff-bundle.expected.json` — frozen clean generation-time self-compare handoff bundle
- `action-plan-handoff/triage-by-status-vs-baseline.handoff-bundle.expected.json` — frozen strict asymmetric generation-time self-compare handoff bundle

Because the lane uses `examples/eval/program.erz`, the checked-in artifacts freeze the smallest refs-backed batch-output contract end-to-end: one materialized action-plan step, one resolved ref binding, one no-action envelope, one runtime-contract error envelope, and the asymmetric proof that triage snapshots can drop success artifacts without dropping the summary-level action-plan/ref counts CI cares about.

See `action-plan-handoff/README.md` for the one-shot refresh helper. The checked-in replay now covers standalone verify sidecars plus generation-time self-verify/self-compare handoff bundles, alongside standalone compare sidecars, so `python3 scripts/refresh_action_plan_handoff.py` should leave `git diff -- examples/eval/action-plan-handoff` empty when the handoff contract still holds.

## Numeric threshold batch handoff lane

Checked-in compare/verify handoff fixtures for the same threshold program live under `threshold-handoff/`.

Contents:

- `threshold-handoff/batch/` — deterministic batch inputs (`ok`, `no-action`, `invalid`)
- `threshold-handoff/baseline/` — flat manifest-bearing artifact set with `run.id`
- `threshold-handoff/candidate-clean/` — checked-in clean self-compare candidate snapshot with manifest + `run.id`
- `threshold-handoff/triage-by-status/` — `errors-only` + `by-status` artifact set with `run.id`, also reused as the strict self-compare candidate snapshot
- `threshold-handoff/*.expected.summary.txt` — frozen verify/compare summary exports
- `threshold-handoff/baseline.verify.expected.json` — frozen standalone verify JSON sidecar for the flat baseline lane
- `threshold-handoff/triage.verify.expected.json` — frozen strict verify JSON sidecar, reused by standalone verify and generation-time self-verify
- `threshold-handoff/candidate-clean-vs-baseline.compare.expected.json` — frozen clean standalone compare export
- `threshold-handoff/triage-vs-baseline.compare.expected.json` — frozen strict asymmetric standalone compare export
- `threshold-handoff/candidate-clean-vs-baseline.handoff-bundle.expected.json` — frozen clean generation-time self-compare handoff bundle
- `threshold-handoff/triage-by-status-vs-baseline.handoff-bundle.expected.json` — frozen strict asymmetric self-compare handoff bundle

Because `threshold-handoff/baseline/summary.json` carries `artifact_sha256`, the generation-time self-compare lane auto-emits the same candidate manifest that an explicit `--batch-output-manifest` run would write. The checked-in replay commands still pass the flag so the standalone candidate snapshot and the self-compare handoff stay byte-identical.

See `threshold-handoff/README.md` for the one-shot refresh helper. The checked-in replay now covers standalone verify/compare JSON sidecars, generation-time self-verify sidecars, and generation-time self-compare handoff bundles, so `python3 scripts/refresh_threshold_handoff.py` should leave `git diff -- examples/eval/threshold-handoff` empty when the handoff contract still holds.
