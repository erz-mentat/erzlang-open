from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from compact import CompactError, parse_and_dump_json, parse_and_format_compact, parse_compact
from runtime.errors import build_error_envelope, render_error_envelope_json
from transform import TransformError, pack_json_text, unpack_to_json_text

ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = ROOT / "bench" / "token-harness"
BENCH_SCRIPT = BENCH_ROOT / "measure.py"
BENCH_RESULTS_JSON = BENCH_ROOT / "results" / "latest.json"


class BenchError(Exception):
    """Raised when benchmark execution or reporting fails."""


def main() -> None:
    parser = argparse.ArgumentParser(prog="erz")
    subparsers = parser.add_subparsers(dest="command")

    parse_parser = subparsers.add_parser("parse", help="parse compact DSL and emit canonical JSON")
    parse_parser.add_argument("path", nargs="?", default="-", help="input file path or '-' for stdin")
    parse_parser.add_argument(
        "--json-errors",
        action="store_true",
        help="emit machine-readable JSON error envelope to stderr",
    )

    validate_parser = subparsers.add_parser(
        "validate", help="validate compact DSL (exit code 0 when valid)"
    )
    validate_parser.add_argument("path", nargs="?", default="-", help="input file path or '-' for stdin")
    validate_parser.add_argument(
        "--json-errors",
        action="store_true",
        help="emit machine-readable JSON error envelope to stderr",
    )

    fmt_parser = subparsers.add_parser("fmt", help="format compact DSL deterministically")
    fmt_parser.add_argument("path", nargs="?", default="-", help="input file path or '-' for stdin")
    fmt_parser.add_argument(
        "-i",
        "--in-place",
        action="store_true",
        help="rewrite the input file with canonical compact formatting",
    )

    pack_parser = subparsers.add_parser(
        "pack", help="pack supported JSON fixture subset into compact+refs"
    )
    pack_parser.add_argument("path", nargs="?", default="-", help="input JSON file path or '-' for stdin")
    pack_parser.add_argument(
        "--json-errors",
        action="store_true",
        help="emit machine-readable JSON error envelope to stderr",
    )

    unpack_parser = subparsers.add_parser(
        "unpack", help="unpack compact+refs subset into canonical JSON"
    )
    unpack_parser.add_argument("path", nargs="?", default="-", help="input compact+refs file path or '-' for stdin")
    unpack_parser.add_argument(
        "--json-errors",
        action="store_true",
        help="emit machine-readable JSON error envelope to stderr",
    )

    bench_parser = subparsers.add_parser(
        "bench", help="run token harness and print concise token savings summary"
    )
    bench_parser.add_argument(
        "--target-pct",
        type=float,
        default=None,
        help="override token-saving target percentage for pass/fail",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    try:
        if args.command == "parse":
            source = _read_source(args.path)
            print(parse_and_dump_json(source))
            return

        if args.command == "validate":
            source = _read_source(args.path)
            parse_compact(source)
            print("valid")
            return

        if args.command == "fmt":
            source = _read_source(args.path)
            formatted = parse_and_format_compact(source)
            if args.in_place:
                if args.path == "-":
                    raise CompactError("--in-place requires a file path")
                Path(args.path).write_text(formatted, encoding="utf-8")
                return
            print(formatted, end="")
            return

        if args.command == "pack":
            source = _read_source(args.path)
            print(pack_json_text(source), end="")
            return

        if args.command == "unpack":
            source = _read_source(args.path)
            print(unpack_to_json_text(source))
            return

        if args.command == "bench":
            _run_bench(args.target_pct)
            return

        parser.error(f"Unknown command: {args.command}")
    except (CompactError, TransformError, BenchError) as exc:
        _emit_cli_error(args, exc)
        raise SystemExit(1) from exc
    except OSError as exc:
        _emit_cli_error(args, exc)
        raise SystemExit(1) from exc


def _emit_cli_error(args: argparse.Namespace, exc: Exception) -> None:
    if _json_error_mode_enabled(args):
        stage = _derive_error_stage(command=getattr(args, "command", None), exc=exc)
        envelope = build_error_envelope(exc, stage=stage, command=getattr(args, "command", None))
        print(render_error_envelope_json(envelope), file=sys.stderr)
        return

    print(f"error: {exc}", file=sys.stderr)


def _json_error_mode_enabled(args: argparse.Namespace) -> bool:
    command = getattr(args, "command", None)
    return command in {"parse", "validate", "pack", "unpack"} and bool(
        getattr(args, "json_errors", False)
    )


def _derive_error_stage(*, command: str | None, exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "cli"
    if command in {"parse", "validate"}:
        return command
    if command in {"pack", "unpack"}:
        return "transform"
    if command == "bench":
        return "bench"
    return "cli"


def _run_bench(target_pct: float | None) -> None:
    if target_pct is not None and target_pct < 0:
        raise BenchError("--target-pct must be >= 0")

    if not BENCH_SCRIPT.exists():
        raise BenchError(f"benchmark script not found: {BENCH_SCRIPT}")

    result = subprocess.run(
        [sys.executable, str(BENCH_SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "unknown benchmark error"
        raise BenchError(f"benchmark harness failed: {details}")

    try:
        payload = json.loads(BENCH_RESULTS_JSON.read_text(encoding="utf-8"))
        meta = payload["meta"]
        summary = payload["summary"]
        totals = summary["totals"]
        fixture_classes = summary["fixture_classes"]
        default_target = float(summary["target"]["token_saving_pct"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise BenchError("benchmark output is missing required summary fields") from exc

    effective_target = default_target if target_pct is None else target_pct
    met = float(totals["token_saving_pct"]) >= effective_target

    print(
        f"token benchmark: {summary['pair_count']} fixture pairs "
        f"(tokenizer={meta['token_counter']})"
    )
    print(
        "overall tokens: "
        f"{totals['baseline_tokens']} -> {totals['erz_tokens']} "
        f"(saved {totals['tokens_saved']}, {totals['token_saving_pct']:.2f}%)"
    )
    print(
        "overall bytes: "
        f"{totals['baseline_bytes']} -> {totals['erz_bytes']} "
        f"(saved {totals['bytes_saved']}, {totals['bytes_saving_pct']:.2f}%)"
    )
    print("per-class savings:")
    for class_name, class_totals in sorted(fixture_classes.items()):
        print(
            f"- {class_name}: "
            f"tokens {class_totals['baseline_tokens']} -> {class_totals['erz_tokens']} "
            f"({class_totals['token_saving_pct']:.2f}%), "
            f"bytes {class_totals['baseline_bytes']} -> {class_totals['erz_bytes']} "
            f"({class_totals['bytes_saving_pct']:.2f}%)"
        )

    print(f"target: >= {effective_target:.2f}% token saving -> {'PASS' if met else 'FAIL'}")
    if not met:
        raise SystemExit(1)


def _read_source(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


if __name__ == "__main__":
    main()
