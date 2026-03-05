# Few-shot Cases

`cases.json` contains 12 parser/validator examples used for Sprint-3 learnability checks.

Schema per case:

- `id`: stable case identifier
- `valid`: expected parse result
- `source`: compact DSL snippet
- `reason`: short human-readable rationale
- `expect_error_contains` (invalid cases): required error substring

Run checker:

```bash
python3 scripts/validate_fewshot.py
```
