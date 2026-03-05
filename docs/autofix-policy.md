# Autofix Policy (Sprint-3)

This policy defines what `erz fmt` is allowed to auto-correct and what must fail fast.

## Principle

- `erz fmt` runs only after successful parse/validation.
- Autofixes are **syntax-normalization only**.
- No runtime behavior changes, no inferred defaults, no coercions.

## Allowed autofixes (deterministic)

`erz fmt` may rewrite:

1. **Whitespace/layout**
   - removes optional spaces/newlines
   - emits one statement per line
   - appends trailing newline

2. **Statement field order**
   - reorders fields to schema order:
     - `erz`: `v`
     - `event` / `ev`: `type`, `payload`
     - `rule` / `rl`: `id`, `when`, `then`
     - `action` / `ac`: `kind`, `params`
     - `tr`: `rule_id`, `matched_clauses`, `score`, `calibrated_probability`, `timestamp`, `seed`
     - `rf`: `id`, `v`
     - `pl`: `rt`

3. **Object key order**
   - sorts object keys lexicographically, recursively

4. **Key rendering style**
   - object keys that are valid identifiers may be emitted unquoted
   - other keys remain JSON-quoted

## Non-fixable errors (must fail)

The formatter must not hide or repair invalid input. These remain hard errors:

- unknown statement tags
- unknown fields
- missing required fields
- duplicate statement fields
- duplicate object keys
- invalid field types (for example `rule.when` not list of strings)
- non-finite numeric literals (`NaN`, `Infinity`, `-Infinity`) in numeric trace fields

## Operator guidance

Use this sequence in CI/local checks:

1. `erz validate <file>`
2. `erz fmt <file>` or `erz fmt --in-place <file>`
3. re-parse formatted output when determinism checks are needed

Few-shot examples and expected pass/fail outcomes are tracked in:
- `examples/fewshot/cases.json`
- `scripts/validate_fewshot.py`
