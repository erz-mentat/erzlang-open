# Token Benchmark Results

| Fixture | Tokens (base→erz) | Token Δ | Token Saving | Bytes (base→erz) | Byte Δ | Byte Saving |
|---|---:|---:|---:|---:|---:|---:|
| `act_event` | 167→80 | 87 | 52.10% | 665→319 | 346 | 52.03% |
| `act_event_nested_payload` | 161→106 | 55 | 34.16% | 642→421 | 221 | 34.42% |
| `alert_event` | 66→27 | 39 | 59.09% | 263→106 | 157 | 59.70% |
| `calibration_overconfident_alert` | 204→70 | 134 | 65.69% | 816→280 | 536 | 65.69% |
| `calibration_underconfident_alert` | 204→70 | 134 | 65.69% | 815→278 | 537 | 65.89% |
| `ingest_event` | 78→52 | 26 | 33.33% | 312→207 | 105 | 33.65% |
| `ingest_event_nested_payload` | 81→62 | 19 | 23.46% | 321→245 | 76 | 23.68% |
| `ingest_event_rich_payload` | 130→71 | 59 | 45.38% | 517→283 | 234 | 45.26% |
| `normalize_event` | 152→81 | 71 | 46.71% | 606→323 | 283 | 46.70% |
| `normalize_event_nested_payload` | 146→90 | 56 | 38.36% | 584→359 | 225 | 38.53% |

## Summary
- Fixture pairs: **10**
- Total tokens: **1389→709** (saved **680**, 48.96%)
- Total bytes: **5541→2821** (saved **2720**, 49.09%)
- Average token saving per fixture: **46.40%**
- Median token saving per fixture: **46.05%**
- Target (≥ 25.0% token saving): **met**

_Token counter: `approx:utf8_bytes_div_4`_

## Calibration Fixture Class Breakdown

| Class | Fixtures | Tokens (base→erz) | Token Saving | Bytes (base→erz) | Byte Saving |
|---|---:|---:|---:|---:|---:|
| `overconfident` | 1 | 204→70 | 65.69% | 816→280 | 65.69% |
| `underconfident` | 1 | 204→70 | 65.69% | 815→278 | 65.89% |
