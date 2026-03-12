from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Callable, Tuple

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
OUT_JSON = ROOT / "results" / "latest.json"
OUT_MD = ROOT / "results" / "latest.md"
TOKEN_TARGET_PCT = 25.0


@dataclass
class PairResult:
    name: str
    baseline_bytes: int
    erz_bytes: int
    bytes_saved: int
    bytes_saving_pct: float
    baseline_tokens: int
    erz_tokens: int
    tokens_saved: int
    token_saving_pct: float


def _resolve_token_counter() -> Tuple[Callable[[str], int], str]:
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return (lambda text: len(enc.encode(text))), "tiktoken:cl100k_base"
    except Exception:
        return (
            lambda text: max(1, math.ceil(len(text.encode("utf-8")) / 4)),
            "approx:utf8_bytes_div_4",
        )


TOKEN_COUNT, TOKEN_COUNTER_NAME = _resolve_token_counter()


def _saving(old: int, new: int) -> float:
    if old <= 0:
        return 0.0
    return round((old - new) / old * 100, 2)


def _fixture_class(name: str) -> str:
    parts = name.split("_")
    if parts and parts[0] == "calibration":
        if len(parts) >= 2 and parts[1]:
            return f"calibration:{parts[1]}"
        return "calibration:general"
    return "core"


def _summarize_rows(rows: list[PairResult]) -> dict:
    baseline_tokens = sum(r.baseline_tokens for r in rows)
    erz_tokens = sum(r.erz_tokens for r in rows)
    baseline_bytes = sum(r.baseline_bytes for r in rows)
    erz_bytes = sum(r.erz_bytes for r in rows)

    return {
        "pair_count": len(rows),
        "baseline_tokens": baseline_tokens,
        "erz_tokens": erz_tokens,
        "tokens_saved": baseline_tokens - erz_tokens,
        "token_saving_pct": _saving(baseline_tokens, erz_tokens),
        "baseline_bytes": baseline_bytes,
        "erz_bytes": erz_bytes,
        "bytes_saved": baseline_bytes - erz_bytes,
        "bytes_saving_pct": _saving(baseline_bytes, erz_bytes),
    }


def _read_pair_text(name: str) -> tuple[str, str]:
    baseline_path = FIXTURES / f"{name}.baseline.json"
    erz_path = FIXTURES / f"{name}.erz"

    if not erz_path.exists():
        raise FileNotFoundError(f"Missing fixture pair file: {erz_path}")

    baseline = baseline_path.read_text(encoding="utf-8").strip()
    erz = erz_path.read_text(encoding="utf-8").strip()
    return baseline, erz


def measure_pair(name: str) -> PairResult:
    baseline, erz = _read_pair_text(name)

    baseline_bytes = len(baseline.encode("utf-8"))
    erz_bytes = len(erz.encode("utf-8"))
    baseline_tokens = TOKEN_COUNT(baseline)
    erz_tokens = TOKEN_COUNT(erz)

    return PairResult(
        name=name,
        baseline_bytes=baseline_bytes,
        erz_bytes=erz_bytes,
        bytes_saved=baseline_bytes - erz_bytes,
        bytes_saving_pct=_saving(baseline_bytes, erz_bytes),
        baseline_tokens=baseline_tokens,
        erz_tokens=erz_tokens,
        tokens_saved=baseline_tokens - erz_tokens,
        token_saving_pct=_saving(baseline_tokens, erz_tokens),
    )


def _render_markdown(results: list[PairResult], summary: dict) -> str:
    lines = [
        "# Token Benchmark Results",
        "",
        "| Fixture | Tokens (base→erz) | Token Δ | Token Saving | Bytes (base→erz) | Byte Δ | Byte Saving |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for row in results:
        lines.append(
            f"| `{row.name}` | {row.baseline_tokens}→{row.erz_tokens} | {row.tokens_saved} | {row.token_saving_pct:.2f}% | "
            f"{row.baseline_bytes}→{row.erz_bytes} | {row.bytes_saved} | {row.bytes_saving_pct:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Summary",
            f"- Fixture pairs: **{summary['pair_count']}**",
            f"- Total tokens: **{summary['totals']['baseline_tokens']}→{summary['totals']['erz_tokens']}** "
            f"(saved **{summary['totals']['tokens_saved']}**, {summary['totals']['token_saving_pct']:.2f}%)",
            f"- Total bytes: **{summary['totals']['baseline_bytes']}→{summary['totals']['erz_bytes']}** "
            f"(saved **{summary['totals']['bytes_saved']}**, {summary['totals']['bytes_saving_pct']:.2f}%)",
            f"- Average token saving per fixture: **{summary['averages']['token_saving_pct']:.2f}%**",
            f"- Median token saving per fixture: **{summary['medians']['token_saving_pct']:.2f}%**",
            f"- Target (≥ {TOKEN_TARGET_PCT:.1f}% token saving): **{('met' if summary['target']['met'] else 'not met')}**",
            "",
            f"_Token counter: `{TOKEN_COUNTER_NAME}`_",
        ]
    )

    calibration_classes = summary.get("calibration_classes", {})
    if calibration_classes:
        lines.extend(
            [
                "",
                "## Calibration Fixture Class Breakdown",
                "",
                "| Class | Fixtures | Tokens (base→erz) | Token Saving | Bytes (base→erz) | Byte Saving |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )

        for class_name, class_summary in sorted(calibration_classes.items()):
            lines.append(
                f"| `{class_name}` | {class_summary['pair_count']} | "
                f"{class_summary['baseline_tokens']}→{class_summary['erz_tokens']} | "
                f"{class_summary['token_saving_pct']:.2f}% | "
                f"{class_summary['baseline_bytes']}→{class_summary['erz_bytes']} | "
                f"{class_summary['bytes_saving_pct']:.2f}% |"
            )

    return "\n".join(lines)


def main() -> None:
    names = sorted({p.name.split(".")[0] for p in FIXTURES.glob("*.baseline.json")})
    results = [measure_pair(name) for name in names]

    total_baseline_tokens = sum(r.baseline_tokens for r in results)
    total_erz_tokens = sum(r.erz_tokens for r in results)
    total_baseline_bytes = sum(r.baseline_bytes for r in results)
    total_erz_bytes = sum(r.erz_bytes for r in results)

    fixture_classes: dict[str, list[PairResult]] = {}
    for row in results:
        fixture_classes.setdefault(_fixture_class(row.name), []).append(row)

    fixture_class_summary = {
        class_name: _summarize_rows(rows)
        for class_name, rows in sorted(fixture_classes.items())
    }
    calibration_class_summary = {
        class_name.split(":", 1)[1]: class_totals
        for class_name, class_totals in fixture_class_summary.items()
        if class_name.startswith("calibration:")
    }

    summary = {
        "pair_count": len(results),
        "totals": {
            "baseline_tokens": total_baseline_tokens,
            "erz_tokens": total_erz_tokens,
            "tokens_saved": total_baseline_tokens - total_erz_tokens,
            "token_saving_pct": _saving(total_baseline_tokens, total_erz_tokens),
            "baseline_bytes": total_baseline_bytes,
            "erz_bytes": total_erz_bytes,
            "bytes_saved": total_baseline_bytes - total_erz_bytes,
            "bytes_saving_pct": _saving(total_baseline_bytes, total_erz_bytes),
        },
        "averages": {
            "token_saving_pct": round(
                sum(r.token_saving_pct for r in results) / max(1, len(results)), 2
            ),
            "bytes_saving_pct": round(
                sum(r.bytes_saving_pct for r in results) / max(1, len(results)), 2
            ),
        },
        "medians": {
            "token_saving_pct": round(
                median([r.token_saving_pct for r in results]) if results else 0.0, 2
            ),
            "bytes_saving_pct": round(
                median([r.bytes_saving_pct for r in results]) if results else 0.0, 2
            ),
        },
        "fixture_classes": fixture_class_summary,
        "calibration_classes": calibration_class_summary,
        "target": {
            "token_saving_pct": TOKEN_TARGET_PCT,
            "met": _saving(total_baseline_tokens, total_erz_tokens) >= TOKEN_TARGET_PCT,
        },
    }

    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "token_counter": TOKEN_COUNTER_NAME,
        },
        "pairs": [asdict(r) for r in results],
        "summary": summary,
        "notes": {
            "method": "Compares compact JSON fixtures against erz compact fixtures with equivalent intent.",
            "limitation": "Token counts vary by tokenizer; fallback approximation is less precise than tiktoken.",
            "fixture_classing": "Fixture classes are inferred from filename prefixes (e.g. calibration_<class>_*).",
        },
    }

    markdown = _render_markdown(results, summary)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(markdown + "\n", encoding="utf-8")

    print(markdown)
    print("\nJSON results:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
