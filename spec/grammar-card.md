# Grammar Card (Implemented Compact Subset)

This card documents the **currently implemented** parser/validator behavior (`compact.py`).
It is intentionally strict and deterministic.

## 1) Program shape

```ebnf
program      = ws* statement* ws* ;
statement    = tag "{" fields? "}" ;
fields       = field ("," field)* ;
field        = key ":" value ;

tag          = identifier ;
key          = identifier ;

value        = string
             | number
             | boolean
             | null
             | array
             | object ;

array        = "[" (value ("," value)*)? "]" ;
object       = "{" (object_field ("," object_field)*)? "}" ;
object_field = (identifier | string) ":" value ;
```

## 2) Lexical constraints

- `identifier`: `[A-Za-z_][A-Za-z0-9_-]*`
- `string`: JSON string syntax (double-quoted)
- `number`: optional leading `-`, digits with optional decimal/exponent part (`1`, `-3`, `0.92`, `1e-3`)
- `boolean`: `true` or `false` (lowercase)
- `null`: `null` (lowercase)
- Whitespace is ignored between tokens.

## 3) Supported statements (exact)

Unknown tags or unknown fields are hard errors.

| Statement | Required fields | Optional fields | Field constraints |
|---|---|---|---|
| `erz` | `v` | — | `v` must be a positive integer |
| `event`, `ev` | `type` | `payload` | `type` string; `payload` may be any compact `value` |
| `rule`, `rl` | `id`, `when`, `then` | — | `id` string; `when` list of strings; `then` list of action objects |
| `action`, `ac` | `kind` | `params` | `kind` string; `params` object if present |
| `tr` | `rule_id`, `matched_clauses` | `score`, `calibrated_probability`, `timestamp`, `seed` | `rule_id` string; `matched_clauses` list of strings; `score` finite number (bool disallowed); `calibrated_probability` finite number in `[0.0, 1.0]`; `timestamp` string or number; `seed` string or integer |
| `rf` | `id`, `v` | — | `id` string matching ref-id policy (`[A-Za-z_][A-Za-z0-9_-]*`, no `@` prefix); `v` string |
| `pl` | — | `rt` | if present, `rt` must be object |

### Action object inside `rule.then` / `rl.then`

Each `then[i]` object may contain only:
- required: `kind` (string)
- optional: `params` (object)

## 4) Structural validation rules

- Duplicate statement fields are rejected.
- Duplicate object keys are rejected.
- Missing required fields are rejected.
- Unknown fields are rejected.

## 5) Canonical formatting contract (`erz fmt`)

Formatting does not change runtime semantics; it normalizes syntax deterministically:

- Statement field order is fixed by schema:
  - `erz`: `v`
  - `event` / `ev`: `type`, `payload`
  - `rule` / `rl`: `id`, `when`, `then`
  - `action` / `ac`: `kind`, `params`
  - `tr`: `rule_id`, `matched_clauses`, `score`, `calibrated_probability`, `timestamp`, `seed`
  - `rf`: `id`, `v`
  - `pl`: `rt`
- Object keys are sorted lexicographically (recursively).
- Output has no optional spaces.
- One statement per line; trailing newline at end of file.
