from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from compact import CompactError, parse_and_dump_json, parse_and_format_compact, parse_compact
from ir.refs import RefPolicyError, canonicalize_ref_bindings
from runtime.errors import build_error_envelope, render_error_envelope_json
from runtime.eval import eval_policies_envelope
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

    eval_parser = subparsers.add_parser(
        "eval",
        help="evaluate rules deterministically and emit actions/trace envelope as JSON",
    )
    eval_parser.add_argument("path", nargs="?", default="-", help="input compact program path or '-' for stdin")
    eval_input_group = eval_parser.add_mutually_exclusive_group(required=True)
    eval_input_group.add_argument(
        "--input",
        help="event JSON path or '-' for stdin",
    )
    eval_input_group.add_argument(
        "--batch",
        help="directory of event JSON fixtures for deterministic batch replay",
    )
    eval_parser.add_argument(
        "--include",
        help="optional glob filter applied to batch event filenames (requires --batch)",
    )
    eval_parser.add_argument(
        "--exclude",
        help="optional glob filter to remove batch event filenames after include filter (requires --batch)",
    )
    eval_parser.add_argument(
        "--batch-output",
        help="optional output directory for deterministic per-event batch envelopes + summary artifact (requires --batch)",
    )
    eval_parser.add_argument(
        "--batch-output-errors-only",
        action="store_true",
        help="write batch artifacts only for runtime-error or no-action events (requires --batch-output)",
    )
    eval_parser.add_argument(
        "--batch-output-manifest",
        action="store_true",
        help="append deterministic SHA256 map for written event artifacts to summary.json (requires --batch-output)",
    )
    eval_parser.add_argument(
        "--batch-output-layout",
        choices=("flat", "by-status"),
        help="artifact layout policy for --batch-output (flat default, or by-status grouping)",
    )
    eval_parser.add_argument(
        "--refs",
        help="optional refs JSON mapping path or '-' for stdin",
    )
    eval_parser.add_argument(
        "--summary",
        action="store_true",
        help="emit deterministic one-line summary instead of JSON envelope",
    )
    eval_parser.add_argument(
        "--summary-policy",
        action="store_true",
        help="append deterministic summary suffix `policy=<...> exit=<0|1>` (requires --summary)",
    )
    eval_parser.add_argument(
        "--strict",
        action="store_true",
        help="legacy shortcut for --exit-policy strict (runtime-error envelopes => exit code 1)",
    )
    eval_parser.add_argument(
        "--exit-policy",
        choices=("default", "strict", "strict-no-actions"),
        default="default",
        help=(
            "exit-code policy preset: default=always 0, strict=runtime-error envelopes => 1, "
            "strict-no-actions=runtime-error envelopes or empty actions => 1"
        ),
    )
    eval_parser.add_argument(
        "--output",
        help="write eval payload to file while preserving deterministic stdout output",
    )
    eval_parser.add_argument(
        "--meta",
        action="store_true",
        help="append deterministic eval metadata (`meta.program_sha256`, `meta.event_sha256`)",
    )
    eval_parser.add_argument(
        "--generated-at",
        help="optional generated-at metadata value, requires --meta",
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

        if args.command == "eval":
            source = _read_source(args.path)
            sidecar_refs = _read_eval_refs_source(args.refs) if args.refs else None

            if args.summary_policy and not args.summary:
                raise ValueError("--summary-policy requires --summary")

            if args.include is not None and not args.batch:
                raise ValueError("--include requires --batch")
            if args.exclude is not None and not args.batch:
                raise ValueError("--exclude requires --batch")
            if args.batch_output is not None and not args.batch:
                raise ValueError("--batch-output requires --batch")
            if args.batch_output_errors_only and not args.batch_output:
                raise ValueError("--batch-output-errors-only requires --batch-output")
            if args.batch_output_manifest and not args.batch_output:
                raise ValueError("--batch-output-manifest requires --batch-output")
            if args.batch_output_layout is not None and not args.batch_output:
                raise ValueError("--batch-output-layout requires --batch-output")
            if args.include == "":
                raise ValueError("--include must be non-empty when provided")
            if args.exclude == "":
                raise ValueError("--exclude must be non-empty when provided")

            if args.batch and args.meta:
                raise ValueError("--meta is not supported with --batch")
            if args.batch and args.generated_at is not None:
                raise ValueError("--generated-at is not supported with --batch")

            if args.batch:
                envelope = _eval_program_batch_envelope(
                    source,
                    batch_dir=args.batch,
                    include_glob=args.include,
                    exclude_glob=args.exclude,
                    sidecar_refs=sidecar_refs,
                )
            else:
                assert args.input is not None
                event_payload = _read_source(args.input)
                event = json.loads(event_payload)
                envelope = _eval_program_envelope(source, event, sidecar_refs=sidecar_refs)
                envelope = _with_eval_metadata(
                    envelope,
                    include_meta=bool(args.meta),
                    generated_at=args.generated_at,
                    source=source,
                    event_payload=event_payload,
                )

            if args.batch_output:
                _write_batch_output_artifacts(
                    output_dir=args.batch_output,
                    envelope=envelope,
                    errors_only=bool(args.batch_output_errors_only),
                    include_manifest=bool(args.batch_output_manifest),
                    layout=str(args.batch_output_layout or "flat"),
                )

            exit_policy = _resolve_eval_exit_policy(
                strict=bool(args.strict),
                exit_policy=str(args.exit_policy),
            )
            should_fail_exit = _should_fail_eval_exit(envelope=envelope, exit_policy=exit_policy)
            exit_code = 1 if should_fail_exit else 0
            rendered_output = _render_eval_output(
                envelope,
                summary=args.summary,
                include_summary_policy=bool(args.summary_policy),
                exit_policy=exit_policy,
                exit_code=exit_code,
            )

            if args.output:
                _write_eval_output(args.output, rendered_output)

            print(rendered_output)

            if should_fail_exit:
                raise SystemExit(1)
            return

        if args.command == "bench":
            _run_bench(args.target_pct)
            return

        parser.error(f"Unknown command: {args.command}")
    except (CompactError, TransformError, BenchError) as exc:
        _emit_cli_error(args, exc)
        raise SystemExit(1) from exc
    except ValueError as exc:
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


def _extract_eval_program_components(source: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    program = parse_compact(source)

    rules: list[dict[str, object]] = []
    refs: dict[str, object] = {}

    for statement in program:
        tag = statement.get("tag")
        fields = statement.get("fields")
        if not isinstance(fields, dict):
            continue

        if tag in {"rule", "rl"}:
            rules.append(
                {
                    "id": fields.get("id"),
                    "when": fields.get("when"),
                    "then": fields.get("then"),
                }
            )
            continue

        if tag == "rf" and "id" in fields and "v" in fields:
            refs[str(fields["id"])] = fields["v"]

    return rules, refs


def _eval_program_envelope(
    source: str,
    event: object,
    *,
    sidecar_refs: dict[str, str] | None = None,
) -> dict[str, object]:
    rules, program_refs = _extract_eval_program_components(source)
    merged_refs = _merge_eval_refs(program_refs=program_refs, sidecar_refs=sidecar_refs)
    return eval_policies_envelope(event, rules, refs=merged_refs)


def _eval_program_batch_envelope(
    source: str,
    *,
    batch_dir: str,
    include_glob: str | None,
    exclude_glob: str | None,
    sidecar_refs: dict[str, str] | None = None,
) -> dict[str, object]:
    batch_root = Path(batch_dir)
    if not batch_root.exists() or not batch_root.is_dir():
        raise ValueError("--batch must point to an existing directory")

    event_paths = sorted(
        path
        for path in batch_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".json"
    )
    if not event_paths:
        raise ValueError("--batch directory must contain at least one .json file")

    event_paths = _filter_batch_event_paths(
        event_paths,
        include_glob=include_glob,
        exclude_glob=exclude_glob,
    )
    if not event_paths:
        include_label = include_glob if include_glob is not None else "<none>"
        exclude_label = exclude_glob if exclude_glob is not None else "<none>"
        raise ValueError(
            "--batch filters matched no .json files "
            f"(include={include_label!r}, exclude={exclude_label!r})"
        )

    rules, program_refs = _extract_eval_program_components(source)
    merged_refs = _merge_eval_refs(program_refs=program_refs, sidecar_refs=sidecar_refs)

    events: list[dict[str, object]] = []
    total_action_count = 0
    total_trace_count = 0
    error_count = 0
    no_action_count = 0

    for event_path in event_paths:
        payload_text = event_path.read_text(encoding="utf-8")
        try:
            event = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--batch event '{event_path.name}' must contain valid JSON: {exc}") from exc

        envelope = eval_policies_envelope(event, rules, refs=merged_refs)

        actions = envelope.get("actions")
        action_count = len(actions) if isinstance(actions, list) else 0
        trace = envelope.get("trace")
        trace_count = len(trace) if isinstance(trace, list) else 0
        has_error = isinstance(envelope.get("error"), dict)

        event_entry: dict[str, object] = {
            "event": event_path.name,
            "actions": actions if isinstance(actions, list) else [],
            "trace": trace if isinstance(trace, list) else [],
        }
        if has_error:
            event_entry["error"] = envelope["error"]

        events.append(event_entry)
        total_action_count += action_count
        total_trace_count += trace_count
        if has_error:
            error_count += 1
        elif action_count == 0:
            no_action_count += 1

    summary = {
        "event_count": len(events),
        "error_count": error_count,
        "no_action_count": no_action_count,
        "action_count": total_action_count,
        "trace_count": total_trace_count,
    }

    return {
        "events": events,
        "summary": summary,
    }


def _filter_batch_event_paths(
    event_paths: list[Path],
    *,
    include_glob: str | None,
    exclude_glob: str | None,
) -> list[Path]:
    filtered_paths = list(event_paths)

    if include_glob is not None:
        filtered_paths = [
            event_path
            for event_path in filtered_paths
            if fnmatch.fnmatchcase(event_path.name, include_glob)
        ]

    if exclude_glob is not None:
        filtered_paths = [
            event_path
            for event_path in filtered_paths
            if not fnmatch.fnmatchcase(event_path.name, exclude_glob)
        ]

    return filtered_paths


def _write_batch_output_artifacts(
    *,
    output_dir: str,
    envelope: dict[str, object],
    errors_only: bool,
    include_manifest: bool,
    layout: str,
) -> None:
    events_payload = envelope.get("events")
    summary_payload = envelope.get("summary")

    if not isinstance(events_payload, list) or not all(isinstance(item, dict) for item in events_payload):
        raise ValueError("--batch-output requires a batch envelope with `events` list")
    if not isinstance(summary_payload, dict):
        raise ValueError("--batch-output requires a batch envelope with `summary` object")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    event_artifacts: list[str] = []
    artifact_sha256: dict[str, str] = {}
    for event_entry in events_payload:
        event_name = event_entry.get("event")
        if not isinstance(event_name, str) or not event_name:
            raise ValueError("--batch output event entry must contain non-empty `event` filename")

        event_status = _batch_event_status(event_entry)
        should_emit = event_status in {"error", "no-action"} if errors_only else True
        if not should_emit:
            continue

        artifact_relative_path = _batch_event_artifact_relative_path(
            event_name=event_name,
            event_status=event_status,
            layout=layout,
        )
        artifact_path = output_root / artifact_relative_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        artifact_payload = json.dumps(event_entry, separators=(",", ":"), ensure_ascii=False)
        artifact_text = f"{artifact_payload}\n"
        artifact_path.write_text(artifact_text, encoding="utf-8")

        event_artifacts.append(artifact_relative_path)
        if include_manifest:
            artifact_sha256[artifact_relative_path] = hashlib.sha256(
                artifact_text.encode("utf-8")
            ).hexdigest()

    summary_artifact: dict[str, object] = {
        "mode": "errors-only" if errors_only else "all",
    }
    if layout != "flat":
        summary_artifact["layout"] = layout
    summary_artifact["event_artifacts"] = event_artifacts
    if include_manifest:
        summary_artifact["artifact_sha256"] = artifact_sha256
    summary_artifact["summary"] = summary_payload

    (output_root / "summary.json").write_text(
        f"{json.dumps(summary_artifact, separators=(',', ':'), ensure_ascii=False)}\n",
        encoding="utf-8",
    )


def _batch_event_status(event_entry: dict[str, object]) -> str:
    if isinstance(event_entry.get("error"), dict):
        return "error"

    actions = event_entry.get("actions")
    action_count = len(actions) if isinstance(actions, list) else 0
    if action_count == 0:
        return "no-action"

    return "ok"


def _batch_event_artifact_relative_path(*, event_name: str, event_status: str, layout: str) -> str:
    artifact_name = _batch_event_artifact_name(event_name)

    if layout == "flat":
        return artifact_name

    if layout == "by-status":
        return f"{event_status}/{artifact_name}"

    raise ValueError("--batch-output-layout must be one of: flat, by-status")


def _batch_event_artifact_name(event_name: str) -> str:
    base_name = Path(event_name).name
    if base_name.lower().endswith(".json"):
        return f"{base_name[:-5]}.envelope.json"
    return f"{base_name}.envelope.json"


def _read_eval_refs_source(path: str) -> dict[str, str]:
    try:
        parsed_payload = json.loads(_read_source(path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"--refs must contain valid JSON: {exc}") from exc

    refs_payload = parsed_payload
    if isinstance(parsed_payload, dict) and set(parsed_payload.keys()) == {"refs"}:
        refs_payload = parsed_payload["refs"]

    if not isinstance(refs_payload, dict):
        raise ValueError("--refs JSON must be an object mapping ref ids to string values")

    try:
        return canonicalize_ref_bindings(
            refs_payload,
            context="--refs",
            allow_literal_keys=True,
        )
    except RefPolicyError as exc:
        raise ValueError(str(exc)) from exc


def _merge_eval_refs(
    *,
    program_refs: dict[str, object],
    sidecar_refs: dict[str, str] | None,
) -> dict[str, str] | None:
    try:
        canonical_program_refs = canonicalize_ref_bindings(
            program_refs,
            context="program refs",
            allow_literal_keys=True,
        )
    except RefPolicyError as exc:
        raise ValueError(str(exc)) from exc

    if sidecar_refs is None:
        return canonical_program_refs or None

    collisions = sorted(set(canonical_program_refs.keys()) & set(sidecar_refs.keys()))
    if collisions:
        collision_literals = ", ".join(f"@{ref_id}" for ref_id in collisions)
        raise ValueError(f"--refs collision with program refs for id(s): {collision_literals}")

    merged: dict[str, str] = dict(canonical_program_refs)
    merged.update(sidecar_refs)
    return {ref_id: merged[ref_id] for ref_id in sorted(merged.keys())} or None


def _render_eval_output(
    envelope: dict[str, object],
    *,
    summary: bool,
    include_summary_policy: bool,
    exit_policy: str,
    exit_code: int,
) -> str:
    if summary:
        rendered_summary = _render_eval_summary(envelope)
        if include_summary_policy:
            return f"{rendered_summary} policy={exit_policy} exit={exit_code}"
        return rendered_summary
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)


def _resolve_eval_exit_policy(*, strict: bool, exit_policy: str) -> str:
    if strict and exit_policy == "strict-no-actions":
        raise ValueError("--strict cannot be combined with --exit-policy strict-no-actions")

    if strict and exit_policy in {"default", "strict"}:
        return "strict"

    return exit_policy


def _iter_eval_envelopes(envelope: dict[str, object]) -> list[dict[str, object]]:
    events = envelope.get("events")
    if isinstance(events, list) and all(isinstance(item, dict) for item in events):
        return [dict(item) for item in events]
    return [envelope]


def _eval_envelope_has_error(envelope: dict[str, object]) -> bool:
    return isinstance(envelope.get("error"), dict)


def _eval_envelope_has_no_actions(envelope: dict[str, object]) -> bool:
    actions = envelope.get("actions")
    return not isinstance(actions, list) or len(actions) == 0


def _should_fail_eval_exit(*, envelope: dict[str, object], exit_policy: str) -> bool:
    eval_entries = _iter_eval_envelopes(envelope)

    if exit_policy == "default":
        return False

    if exit_policy == "strict":
        return any(_eval_envelope_has_error(entry) for entry in eval_entries)

    if exit_policy == "strict-no-actions":
        return any(
            _eval_envelope_has_error(entry) or _eval_envelope_has_no_actions(entry)
            for entry in eval_entries
        )

    raise ValueError(f"unsupported --exit-policy value: {exit_policy}")


def _with_eval_metadata(
    envelope: dict[str, object],
    *,
    include_meta: bool,
    generated_at: str | None,
    source: str,
    event_payload: str,
) -> dict[str, object]:
    if generated_at is not None and not include_meta:
        raise ValueError("--generated-at requires --meta")

    if not include_meta:
        return envelope

    metadata = _build_eval_metadata(
        source=source,
        event_payload=event_payload,
        generated_at=generated_at,
    )

    with_meta: dict[str, object] = {
        "actions": envelope.get("actions", []),
        "trace": envelope.get("trace", []),
    }
    if "error" in envelope:
        with_meta["error"] = envelope["error"]
    with_meta["meta"] = metadata
    return with_meta


def _build_eval_metadata(*, source: str, event_payload: str, generated_at: str | None) -> dict[str, str]:
    metadata: dict[str, str] = {
        "program_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "event_sha256": hashlib.sha256(event_payload.encode("utf-8")).hexdigest(),
    }
    if generated_at is not None:
        if not generated_at:
            raise ValueError("--generated-at must be non-empty when provided")
        metadata["generated_at"] = generated_at
    return metadata


def _write_eval_output(path: str, rendered_output: str) -> None:
    Path(path).write_text(f"{rendered_output}\n", encoding="utf-8")


def _render_eval_summary(envelope: dict[str, object]) -> str:
    events = envelope.get("events")
    if isinstance(events, list):
        summary = envelope.get("summary") if isinstance(envelope.get("summary"), dict) else {}

        event_count = summary.get("event_count") if isinstance(summary.get("event_count"), int) else len(events)
        error_count = summary.get("error_count") if isinstance(summary.get("error_count"), int) else 0
        no_action_count = (
            summary.get("no_action_count") if isinstance(summary.get("no_action_count"), int) else 0
        )
        action_count = summary.get("action_count") if isinstance(summary.get("action_count"), int) else 0
        trace_count = summary.get("trace_count") if isinstance(summary.get("trace_count"), int) else 0

        status = "error" if error_count > 0 else "ok"
        return (
            f"status={status} events={event_count} errors={error_count} "
            f"no_actions={no_action_count} actions={action_count} trace={trace_count}"
        )

    actions = envelope.get("actions")
    trace = envelope.get("trace")

    action_count = len(actions) if isinstance(actions, list) else 0
    trace_count = len(trace) if isinstance(trace, list) else 0

    error = envelope.get("error")
    if isinstance(error, dict):
        code = error.get("code", "ERZ_RUNTIME_ERROR")
        stage = error.get("stage", "runtime")
        return (
            f"status=error code={code} stage={stage} "
            f"actions={action_count} trace={trace_count}"
        )

    return f"status=ok actions={action_count} trace={trace_count}"


def _read_source(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


if __name__ == "__main__":
    main()
