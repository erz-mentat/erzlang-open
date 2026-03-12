from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from compact import (
    CompactError,
    canonicalize_program,
    parse_and_dump_json,
    parse_and_format_compact,
    parse_compact,
)
from ir.refs import RefPolicyError, canonicalize_ref_bindings
from runtime.errors import build_error_envelope, render_error_envelope_json
from runtime.eval import eval_policies_envelope
from transform import TransformError, pack_json_text, unpack_to_json_text

ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = ROOT / "bench" / "token-harness"
BENCH_SCRIPT = BENCH_ROOT / "measure.py"
BENCH_RESULTS_JSON = BENCH_ROOT / "results" / "latest.json"
PROGRAM_PACK_REPLAY_FIXTURE_CLASSES = ("ok", "expectation_mismatch", "runtime_error")
PROGRAM_PACK_REPLAY_STRICT_PROFILES: dict[str, dict[str, object]] = {
    "clean": {
        "expected_mismatch_count": 0,
        "expected_expectation_mismatch_count": 0,
        "expected_runtime_error_count": 0,
        "expected_rule_source_status": "ok",
    },
    "ingest-normalize-clean": {
        "expected_pack_id": "ingest-normalize",
        "expected_baseline_shape": "inline-statements",
        "expected_total_fixture_count": 2,
        "expected_fixture_class_counts": {
            "ok": 2,
            "expectation_mismatch": 0,
            "runtime_error": 0,
        },
        "expected_mismatch_count": 0,
        "expected_expectation_mismatch_count": 0,
        "expected_runtime_error_count": 0,
        "expected_rule_source_status": "ok",
    },
    "dedup-cluster-clean": {
        "expected_pack_id": "sprint-7-program-pack-2-dedup-cluster",
        "expected_baseline_shape": "fixture-matrix",
        "expected_total_fixture_count": 4,
        "expected_fixture_class_counts": {
            "ok": 4,
            "expectation_mismatch": 0,
            "runtime_error": 0,
        },
        "expected_mismatch_count": 0,
        "expected_expectation_mismatch_count": 0,
        "expected_runtime_error_count": 0,
        "expected_rule_source_status": "ok",
    },
    "alert-routing-clean": {
        "expected_pack_id": "sprint-7-pack-03-alert-routing",
        "expected_baseline_shape": "fixture-matrix",
        "expected_total_fixture_count": 3,
        "expected_fixture_class_counts": {
            "ok": 3,
            "expectation_mismatch": 0,
            "runtime_error": 0,
        },
        "expected_mismatch_count": 0,
        "expected_expectation_mismatch_count": 0,
        "expected_runtime_error_count": 0,
        "expected_rule_source_status": "ok",
    },
}


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
    eval_input_group = eval_parser.add_mutually_exclusive_group(required=False)
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
        "--batch-summary-rule-counts",
        action="store_true",
        help=(
            "append deterministic per-rule hit counts to the batch JSON summary "
            "(requires --batch, not supported with --summary)"
        ),
    )
    eval_parser.add_argument(
        "--batch-summary-action-kind-counts",
        action="store_true",
        help=(
            "append deterministic per-action-kind counts to the batch JSON summary "
            "(requires --batch, not supported with --summary)"
        ),
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
        "--batch-output-run-id",
        help="optional run id metadata written to batch summary.json as run.id (requires --batch-output)",
    )
    eval_parser.add_argument(
        "--batch-output-summary-file",
        help=(
            "optional file path to export the deterministic batch aggregate envelope as JSON "
            "(requires --batch, not supported with --summary)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-self-verify",
        action="store_true",
        help=(
            "immediately verify freshly written batch-output artifacts/manifest and fail deterministically "
            "before handoff (requires --batch-output)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-self-verify-strict",
        action="store_true",
        help=(
            "run self-verify with strict summary-profile checks after artifact write "
            "(requires --batch-output-self-verify; supports --batch-output-verify-profile and strict expectation selectors)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-self-compare-against",
        help=(
            "baseline batch-output directory used to compare freshly written artifacts before handoff "
            "(requires --batch-output; manifest-bearing baselines compare artifact_sha256 too, "
            "self-compare auto-writes the candidate manifest when needed)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-self-compare-strict",
        action="store_true",
        help=(
            "run self-compare with strict drift-profile checks after artifact write "
            "(requires --batch-output-self-compare-against; supports --batch-output-compare-profile and strict expectation selectors)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-verify",
        help=(
            "verify existing batch-output summary manifest hashes in <dir> and emit deterministic "
            "pass/fail integrity summary"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-compare",
        help=(
            "compare candidate batch-output artifacts in <dir> against a baseline directory and emit "
            "deterministic drift summary"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-compare-against",
        help="baseline batch-output directory used by --batch-output-compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-include",
        help=(
            "optional glob filter applied to compare artifact paths from summary.json "
            "(requires --batch-output-compare or --batch-output-self-compare-against)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-compare-exclude",
        help=(
            "optional glob filter to remove compare artifact paths after include filter "
            "(requires --batch-output-compare or --batch-output-self-compare-against)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-compare-strict",
        action="store_true",
        help=(
            "enable strict expectation gating for --batch-output-compare "
            "(requires at least one --batch-output-compare-expected-* selector or --batch-output-compare-profile)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-compare-profile",
        choices=("clean", "metadata-only", "expected-asymmetric-drift"),
        help=(
            "strict compare preset for common drift contracts "
            "(clean=no drift, metadata-only=no artifact drift, expected-asymmetric-drift=no changed artifacts), "
            "usable with --batch-output-compare or with --batch-output-self-compare-strict "
            "(which requires --batch-output-self-compare-against) and auto-enables strict compare"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-status",
        choices=("ok", "error"),
        help="optional expected raw compare status for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-compared-count",
        type=int,
        help="optional expected compared artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-matched-count",
        type=int,
        help="optional expected matched artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-changed-count",
        type=int,
        help="optional expected changed artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-baseline-only-count",
        type=int,
        help="optional expected baseline-only artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-candidate-only-count",
        type=int,
        help="optional expected candidate-only artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-missing-baseline-count",
        type=int,
        help="optional expected missing-baseline artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-missing-candidate-count",
        type=int,
        help="optional expected missing-candidate artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-metadata-mismatches-count",
        type=int,
        help="optional expected metadata mismatch count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-selected-baseline-count",
        type=int,
        help="optional expected selected baseline artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-expected-selected-candidate-count",
        type=int,
        help="optional expected selected candidate artifact count for strict compare",
    )
    eval_parser.add_argument(
        "--batch-output-compare-summary-file",
        help=(
            "optional file path to export compare-lane output (JSON or --summary line); "
            "byte-identical to stdout for --batch-output-compare, and for self-compare exports the compare output "
            "while stdout stays the normal eval output "
            "(requires --batch-output-compare or --batch-output-self-compare-against)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-verify-include",
        help=(
            "optional glob filter applied to verify artifact paths from summary.json "
            "(requires --batch-output-verify)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-verify-exclude",
        help=(
            "optional glob filter to remove verify artifact paths after include filter "
            "(requires --batch-output-verify)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-verify-summary-file",
        help=(
            "optional file path to export verify-lane output (JSON or --summary line) "
            "byte-identical to stdout (requires --batch-output-verify)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-verify-strict",
        action="store_true",
        help=(
            "enable strict summary-profile verification for --batch-output-verify "
            "(checks expected mode and optional layout/run.id pattern)"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-verify-profile",
        choices=("default", "triage-by-status"),
        help=(
            "strict verify profile preset for mode/layout expectations "
            "(default=all+flat, triage-by-status=errors-only+by-status), usable with "
            "--batch-output-verify or --batch-output-self-verify-strict"
        ),
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-mode",
        choices=("all", "errors-only"),
        help="expected summary mode for strict verify (default: all)",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-layout",
        choices=("flat", "by-status"),
        help="optional expected summary layout for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-run-id-pattern",
        help="optional regex that run.id must match for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-event-count",
        type=int,
        help="optional expected summary.event_count value for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-verified-count",
        type=int,
        help="optional expected verify_result.verified value for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-checked-count",
        type=int,
        help="optional expected verify_result.checked value for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-missing-count",
        type=int,
        help="optional expected verify_result.missing_artifacts count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-mismatched-count",
        type=int,
        help="optional expected verify_result.mismatched_artifacts count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-manifest-missing-count",
        type=int,
        help="optional expected verify_result.missing_manifest_entries count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-invalid-hashes-count",
        type=int,
        help="optional expected verify_result.invalid_manifest_hashes count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-unexpected-manifest-count",
        type=int,
        help="optional expected verify_result.unexpected_manifest_entries count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-status",
        choices=("ok", "error"),
        help="optional expected verify_result.status value for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-strict-mismatches-count",
        type=int,
        help="optional expected strict_profile_mismatches count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-event-artifact-count",
        type=int,
        help="optional expected summary.event_artifacts count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-manifest-entry-count",
        type=int,
        help="optional expected summary.artifact_sha256 entry count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-selected-artifact-count",
        type=int,
        help="optional expected selector-filtered artifact count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-expected-manifest-selected-entry-count",
        type=int,
        help="optional expected selector-filtered manifest-entry count for strict verify",
    )
    eval_parser.add_argument(
        "--batch-output-verify-require-run-id",
        action="store_true",
        help="strict verify toggle: fail when summary.json omits run.id",
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

    pack_replay_parser = subparsers.add_parser(
        "pack-replay",
        help="replay checked-in program-pack fixtures against the pack program and baseline",
    )
    pack_replay_parser.add_argument(
        "path",
        help="program-pack directory containing one .erz file and one baseline JSON file (fixture matrix or inline statements)",
    )
    pack_replay_parser.add_argument(
        "--fixture",
        action="append",
        help="optional fixture id selector, repeatable, preserves deterministic pack order",
    )
    pack_replay_parser.add_argument(
        "--include-fixture",
        action="append",
        help="optional glob selector for fixture ids, repeatable, evaluated before --exclude-fixture",
    )
    pack_replay_parser.add_argument(
        "--exclude-fixture",
        action="append",
        help="optional glob selector that removes fixture ids after exact/glob inclusion",
    )
    pack_replay_parser.add_argument(
        "--fixture-class",
        action="append",
        choices=PROGRAM_PACK_REPLAY_FIXTURE_CLASSES,
        help="optional post-replay fixture class selector, repeatable, preserves deterministic pack order",
    )
    pack_replay_parser.add_argument(
        "--strict",
        dest="pack_replay_strict",
        action="store_true",
        help=(
            "enable strict replay expectation gating "
            "(requires at least one --expected-* selector or --strict-profile)"
        ),
    )
    pack_replay_parser.add_argument(
        "--strict-profile",
        dest="pack_replay_strict_profile",
        choices=tuple(PROGRAM_PACK_REPLAY_STRICT_PROFILES.keys()),
        help=(
            "strict replay preset for common CI contracts "
            "(clean=generic green lane; *-clean=checked-in pack-specific green lane with pack id, baseline shape, total fixture count, and class histogram); auto-enables strict replay"
        ),
    )
    pack_replay_parser.add_argument(
        "--expected-pack-id",
        dest="pack_replay_expected_pack_id",
        help="optional expected pack_id value for strict replay",
    )
    pack_replay_parser.add_argument(
        "--expected-baseline-shape",
        dest="pack_replay_expected_baseline_shape",
        choices=("fixture-matrix", "inline-statements"),
        help="optional expected baseline_shape value for strict replay",
    )
    pack_replay_parser.add_argument(
        "--expected-fixture-count",
        dest="pack_replay_expected_fixture_count",
        type=int,
        help="optional expected selected fixture count for strict replay",
    )
    pack_replay_parser.add_argument(
        "--expected-selected-fixture",
        dest="pack_replay_expected_selected_fixture_ids",
        action="append",
        help="optional exact selected fixture id contract for strict replay, repeatable, compared in canonical replay order",
    )
    pack_replay_parser.add_argument(
        "--expected-ok-fixture",
        dest="pack_replay_expected_ok_fixture_ids",
        action="append",
        help="optional exact ok fixture id contract for strict replay, repeatable, compared in canonical pack order",
    )
    pack_replay_parser.add_argument(
        "--expected-expectation-mismatch-fixture",
        dest="pack_replay_expected_expectation_mismatch_fixture_ids",
        action="append",
        help="optional exact expectation_mismatch fixture id contract for strict replay, repeatable, compared in canonical pack order",
    )
    pack_replay_parser.add_argument(
        "--expected-runtime-error-fixture",
        dest="pack_replay_expected_runtime_error_fixture_ids",
        action="append",
        help="optional exact runtime_error fixture id contract for strict replay, repeatable, compared in canonical pack order",
    )
    pack_replay_parser.add_argument(
        "--expected-total-fixture-count",
        dest="pack_replay_expected_total_fixture_count",
        type=int,
        help="optional expected total pack fixture count before selector filtering for strict replay",
    )
    pack_replay_parser.add_argument(
        "--expected-fixture-class-counts",
        dest="pack_replay_expected_fixture_class_counts",
        help=(
            "optional exact fixture_class_counts contract for strict replay "
            "(format: ok=<n>,expectation_mismatch=<n>,runtime_error=<n>)"
        ),
    )
    pack_replay_parser.add_argument(
        "--expected-mismatch-count",
        dest="pack_replay_expected_mismatch_count",
        type=int,
        help="optional expected total mismatch count for strict replay (includes runtime_error fixtures)",
    )
    pack_replay_parser.add_argument(
        "--expected-expectation-mismatch-count",
        dest="pack_replay_expected_expectation_mismatch_count",
        type=int,
        help="optional expected pure expectation_mismatch fixture count for strict replay",
    )
    pack_replay_parser.add_argument(
        "--expected-runtime-error-count",
        dest="pack_replay_expected_runtime_error_count",
        type=int,
        help="optional expected runtime_error fixture count for strict replay",
    )
    pack_replay_parser.add_argument(
        "--expected-rule-source-status",
        dest="pack_replay_expected_rule_source_status",
        choices=("ok", "mismatch"),
        help="optional expected rule_source_status value for strict replay",
    )
    pack_replay_parser.add_argument(
        "--summary",
        action="store_true",
        help="emit deterministic one-line replay summary instead of JSON details",
    )
    pack_replay_parser.add_argument(
        "--summary-file",
        help=(
            "write the deterministic replay summary line to file without changing stdout"
        ),
    )
    pack_replay_parser.add_argument(
        "--json-file",
        help=(
            "write the deterministic replay JSON envelope to file without changing stdout"
        ),
    )
    pack_replay_parser.add_argument(
        "--fixture-class-summary-file",
        help=(
            "write the deterministic replay summary line to file for fixture-class filtered runs "
            "without changing stdout"
        ),
    )
    pack_replay_parser.add_argument(
        "--output",
        help="write replay payload to file while preserving deterministic stdout output",
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
            self_verify_strict_enabled = bool(args.batch_output_self_verify_strict)
            self_verify_strict_profile: dict[str, object] | None = None
            self_compare_enabled = args.batch_output_self_compare_against is not None
            self_compare_strict_enabled = bool(args.batch_output_self_compare_strict)
            self_compare_strict_profile: dict[str, object] | None = None

            compare_expected_selectors = [
                ("--batch-output-compare-expected-status", args.batch_output_compare_expected_status),
                (
                    "--batch-output-compare-expected-compared-count",
                    args.batch_output_compare_expected_compared_count,
                ),
                (
                    "--batch-output-compare-expected-matched-count",
                    args.batch_output_compare_expected_matched_count,
                ),
                (
                    "--batch-output-compare-expected-changed-count",
                    args.batch_output_compare_expected_changed_count,
                ),
                (
                    "--batch-output-compare-expected-baseline-only-count",
                    args.batch_output_compare_expected_baseline_only_count,
                ),
                (
                    "--batch-output-compare-expected-candidate-only-count",
                    args.batch_output_compare_expected_candidate_only_count,
                ),
                (
                    "--batch-output-compare-expected-missing-baseline-count",
                    args.batch_output_compare_expected_missing_baseline_count,
                ),
                (
                    "--batch-output-compare-expected-missing-candidate-count",
                    args.batch_output_compare_expected_missing_candidate_count,
                ),
                (
                    "--batch-output-compare-expected-metadata-mismatches-count",
                    args.batch_output_compare_expected_metadata_mismatches_count,
                ),
                (
                    "--batch-output-compare-expected-selected-baseline-count",
                    args.batch_output_compare_expected_selected_baseline_count,
                ),
                (
                    "--batch-output-compare-expected-selected-candidate-count",
                    args.batch_output_compare_expected_selected_candidate_count,
                ),
            ]
            has_compare_strict_contract = (
                args.batch_output_compare_profile is not None
                or any(option_value is not None for _, option_value in compare_expected_selectors)
            )

            if args.batch_output_compare is None:
                if args.batch_output_compare_against is not None:
                    raise ValueError(
                        "--batch-output-compare-against requires --batch-output-compare"
                    )
                if args.batch_output_compare_include is not None and not self_compare_enabled:
                    raise ValueError(
                        "--batch-output-compare-include requires --batch-output-compare or "
                        "--batch-output-self-compare-against"
                    )
                if args.batch_output_compare_exclude is not None and not self_compare_enabled:
                    raise ValueError(
                        "--batch-output-compare-exclude requires --batch-output-compare or "
                        "--batch-output-self-compare-against"
                    )
                if args.batch_output_compare_summary_file is not None and not self_compare_enabled:
                    raise ValueError(
                        "--batch-output-compare-summary-file requires --batch-output-compare or "
                        "--batch-output-self-compare-against"
                    )
                if args.batch_output_compare_strict:
                    raise ValueError("--batch-output-compare-strict requires --batch-output-compare")
                if args.batch_output_compare_profile is not None and not self_compare_enabled:
                    raise ValueError(
                        "--batch-output-compare-profile requires --batch-output-compare or "
                        "--batch-output-self-compare-strict"
                    )
                for option_name, option_value in compare_expected_selectors:
                    if option_value is not None and not self_compare_enabled:
                        raise ValueError(
                            f"{option_name} requires strict compare or --batch-output-self-compare-strict"
                        )
            else:
                if args.batch_output_compare == "":
                    raise ValueError("--batch-output-compare must be non-empty when provided")
                if args.batch_output_compare_against is None:
                    raise ValueError(
                        "--batch-output-compare requires --batch-output-compare-against"
                    )
                if args.batch_output_compare_against == "":
                    raise ValueError(
                        "--batch-output-compare-against must be non-empty when provided"
                    )
                if args.batch_output_compare_include == "":
                    raise ValueError(
                        "--batch-output-compare-include must be non-empty when provided"
                    )
                if args.batch_output_compare_exclude == "":
                    raise ValueError(
                        "--batch-output-compare-exclude must be non-empty when provided"
                    )
                if args.batch_output_compare_summary_file == "":
                    raise ValueError(
                        "--batch-output-compare-summary-file must be non-empty when provided"
                    )
                strict_compare_enabled = bool(
                    args.batch_output_compare_strict or args.batch_output_compare_profile is not None
                )
                if args.batch_output_compare_strict and not has_compare_strict_contract:
                    raise ValueError(
                        "--batch-output-compare-strict requires at least one "
                        "--batch-output-compare-expected-* selector or --batch-output-compare-profile"
                    )
                for option_name, option_value in compare_expected_selectors:
                    if option_value is not None and not strict_compare_enabled:
                        raise ValueError(f"{option_name} requires strict compare")
                for option_name, option_value in compare_expected_selectors:
                    if isinstance(option_value, int) and option_value < 0:
                        raise ValueError(f"{option_name} must be >= 0")
                if args.summary_policy:
                    raise ValueError("--summary-policy is not supported with --batch-output-compare")
                if args.input is not None or args.batch is not None:
                    raise ValueError(
                        "--batch-output-compare cannot be combined with --input or --batch"
                    )
                if args.refs is not None:
                    raise ValueError("--refs is not supported with --batch-output-compare")
                if args.include is not None:
                    raise ValueError("--include is not supported with --batch-output-compare")
                if args.exclude is not None:
                    raise ValueError("--exclude is not supported with --batch-output-compare")
                if args.batch_output is not None:
                    raise ValueError("--batch-output is not supported with --batch-output-compare")
                if args.batch_output_errors_only:
                    raise ValueError(
                        "--batch-output-errors-only is not supported with --batch-output-compare"
                    )
                if args.batch_output_manifest:
                    raise ValueError(
                        "--batch-output-manifest is not supported with --batch-output-compare"
                    )
                if args.batch_output_layout is not None:
                    raise ValueError(
                        "--batch-output-layout is not supported with --batch-output-compare"
                    )
                if args.batch_output_run_id is not None:
                    raise ValueError(
                        "--batch-output-run-id is not supported with --batch-output-compare"
                    )
                if args.batch_output_summary_file is not None:
                    raise ValueError(
                        "--batch-output-summary-file is not supported with --batch-output-compare"
                    )
                if self_compare_enabled:
                    raise ValueError(
                        "--batch-output-self-compare-against is not supported with --batch-output-compare"
                    )
                if args.batch_output_self_compare_strict:
                    raise ValueError(
                        "--batch-output-self-compare-strict is not supported with --batch-output-compare"
                    )
                if args.batch_output_self_verify:
                    raise ValueError(
                        "--batch-output-self-verify is not supported with --batch-output-compare"
                    )
                if args.batch_output_self_verify_strict:
                    raise ValueError(
                        "--batch-output-self-verify-strict is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify is not None:
                    raise ValueError(
                        "--batch-output-verify is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_include is not None:
                    raise ValueError(
                        "--batch-output-verify-include is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_exclude is not None:
                    raise ValueError(
                        "--batch-output-verify-exclude is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_summary_file is not None:
                    raise ValueError(
                        "--batch-output-verify-summary-file is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_strict:
                    raise ValueError(
                        "--batch-output-verify-strict is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_profile is not None:
                    raise ValueError(
                        "--batch-output-verify-profile is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_mode is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-mode is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_layout is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-layout is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_run_id_pattern is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-run-id-pattern is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_event_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-event-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_verified_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-verified-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_checked_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-checked-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_missing_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-missing-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_mismatched_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-mismatched-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_manifest_missing_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-missing-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_invalid_hashes_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-invalid-hashes-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_unexpected_manifest_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-unexpected-manifest-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_status is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-status is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_strict_mismatches_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-strict-mismatches-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_event_artifact_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-event-artifact-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_manifest_entry_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-entry-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_selected_artifact_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-selected-artifact-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_expected_manifest_selected_entry_count is not None:
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-selected-entry-count is not supported with --batch-output-compare"
                    )
                if args.batch_output_verify_require_run_id:
                    raise ValueError(
                        "--batch-output-verify-require-run-id is not supported with --batch-output-compare"
                    )
                if args.meta:
                    raise ValueError("--meta is not supported with --batch-output-compare")
                if args.generated_at is not None:
                    raise ValueError("--generated-at is not supported with --batch-output-compare")
                if args.strict:
                    raise ValueError("--strict is not supported with --batch-output-compare")
                if args.exit_policy != "default":
                    raise ValueError("--exit-policy is not supported with --batch-output-compare")

                strict_compare_profile = _resolve_batch_output_compare_strict_profile(
                    enabled=strict_compare_enabled,
                    profile=args.batch_output_compare_profile,
                    expected_status=args.batch_output_compare_expected_status,
                    expected_compared_count=args.batch_output_compare_expected_compared_count,
                    expected_matched_count=args.batch_output_compare_expected_matched_count,
                    expected_changed_count=args.batch_output_compare_expected_changed_count,
                    expected_baseline_only_count=args.batch_output_compare_expected_baseline_only_count,
                    expected_candidate_only_count=args.batch_output_compare_expected_candidate_only_count,
                    expected_missing_baseline_count=args.batch_output_compare_expected_missing_baseline_count,
                    expected_missing_candidate_count=args.batch_output_compare_expected_missing_candidate_count,
                    expected_metadata_mismatches_count=args.batch_output_compare_expected_metadata_mismatches_count,
                    expected_selected_baseline_count=args.batch_output_compare_expected_selected_baseline_count,
                    expected_selected_candidate_count=args.batch_output_compare_expected_selected_candidate_count,
                )
                compare_summary = _compare_batch_output_artifacts(
                    args.batch_output_compare,
                    against_dir=args.batch_output_compare_against,
                    include_glob=args.batch_output_compare_include,
                    exclude_glob=args.batch_output_compare_exclude,
                    strict_profile=strict_compare_profile,
                    candidate_flag="--batch-output-compare",
                    against_flag="--batch-output-compare-against",
                    selector_flag="--batch-output-compare selectors",
                )
                rendered_output = _render_batch_output_compare_summary(
                    compare_summary,
                    summary=bool(args.summary),
                )

                if args.output:
                    _write_eval_output(args.output, rendered_output)
                if args.batch_output_compare_summary_file:
                    _write_eval_output(args.batch_output_compare_summary_file, rendered_output)

                print(rendered_output)

                if strict_compare_profile is not None:
                    strict_profile_mismatches = compare_summary.get("strict_profile_mismatches")
                    if isinstance(strict_profile_mismatches, list) and strict_profile_mismatches:
                        raise SystemExit(1)
                    return

                if compare_summary["status"] != "ok":
                    raise SystemExit(1)
                return

            if not self_compare_enabled:
                if args.batch_output_self_compare_strict:
                    raise ValueError(
                        "--batch-output-self-compare-strict requires --batch-output-self-compare-against"
                    )
            else:
                if args.batch_output_self_compare_against == "":
                    raise ValueError(
                        "--batch-output-self-compare-against must be non-empty when provided"
                    )
                if args.batch_output_compare_include == "":
                    raise ValueError(
                        "--batch-output-compare-include must be non-empty when provided"
                    )
                if args.batch_output_compare_exclude == "":
                    raise ValueError(
                        "--batch-output-compare-exclude must be non-empty when provided"
                    )
                if args.batch_output_compare_summary_file == "":
                    raise ValueError(
                        "--batch-output-compare-summary-file must be non-empty when provided"
                    )
                if args.batch_output_compare_profile is not None and not self_compare_strict_enabled:
                    raise ValueError(
                        "--batch-output-compare-profile requires --batch-output-self-compare-strict"
                    )
                if self_compare_strict_enabled and not has_compare_strict_contract:
                    raise ValueError(
                        "--batch-output-self-compare-strict requires at least one "
                        "--batch-output-compare-expected-* selector or --batch-output-compare-profile"
                    )
                for option_name, option_value in compare_expected_selectors:
                    if option_value is not None and not self_compare_strict_enabled:
                        raise ValueError(
                            f"{option_name} requires --batch-output-self-compare-strict"
                        )
                    if isinstance(option_value, int) and option_value < 0:
                        raise ValueError(f"{option_name} must be >= 0")
                if self_compare_strict_enabled:
                    self_compare_strict_profile = _resolve_batch_output_compare_strict_profile(
                        enabled=True,
                        profile=args.batch_output_compare_profile,
                        expected_status=args.batch_output_compare_expected_status,
                        expected_compared_count=args.batch_output_compare_expected_compared_count,
                        expected_matched_count=args.batch_output_compare_expected_matched_count,
                        expected_changed_count=args.batch_output_compare_expected_changed_count,
                        expected_baseline_only_count=args.batch_output_compare_expected_baseline_only_count,
                        expected_candidate_only_count=args.batch_output_compare_expected_candidate_only_count,
                        expected_missing_baseline_count=args.batch_output_compare_expected_missing_baseline_count,
                        expected_missing_candidate_count=args.batch_output_compare_expected_missing_candidate_count,
                        expected_metadata_mismatches_count=args.batch_output_compare_expected_metadata_mismatches_count,
                        expected_selected_baseline_count=args.batch_output_compare_expected_selected_baseline_count,
                        expected_selected_candidate_count=args.batch_output_compare_expected_selected_candidate_count,
                    )

            if args.batch_output_verify is None:
                if args.batch_output_verify_include is not None:
                    raise ValueError(
                        "--batch-output-verify-include requires --batch-output-verify"
                    )
                if args.batch_output_verify_exclude is not None:
                    raise ValueError(
                        "--batch-output-verify-exclude requires --batch-output-verify"
                    )
                if args.batch_output_verify_summary_file is not None:
                    raise ValueError(
                        "--batch-output-verify-summary-file requires --batch-output-verify"
                    )
                if args.batch_output_verify_strict:
                    raise ValueError("--batch-output-verify-strict requires --batch-output-verify")
                if args.batch_output_verify_profile is not None and not self_verify_strict_enabled:
                    raise ValueError("--batch-output-verify-profile requires --batch-output-verify")
                if args.batch_output_verify_expected_mode is not None and not self_verify_strict_enabled:
                    raise ValueError(
                        "--batch-output-verify-expected-mode requires strict verify"
                    )
                if args.batch_output_verify_expected_layout is not None and not self_verify_strict_enabled:
                    raise ValueError(
                        "--batch-output-verify-expected-layout requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_run_id_pattern is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-run-id-pattern requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_event_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-event-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_verified_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-verified-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_checked_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-checked-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_missing_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-missing-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_mismatched_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-mismatched-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_manifest_missing_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-missing-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_invalid_hashes_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-invalid-hashes-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_unexpected_manifest_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-unexpected-manifest-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_status is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-status requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_strict_mismatches_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-strict-mismatches-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_event_artifact_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-event-artifact-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_manifest_entry_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-entry-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_selected_artifact_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-selected-artifact-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_manifest_selected_entry_count is not None
                    and not self_verify_strict_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-selected-entry-count requires strict verify"
                    )
                if args.batch_output_verify_require_run_id and not self_verify_strict_enabled:
                    raise ValueError(
                        "--batch-output-verify-require-run-id requires --batch-output-verify"
                    )

                if self_verify_strict_enabled:
                    if args.batch_output_verify_expected_run_id_pattern == "":
                        raise ValueError(
                            "--batch-output-verify-expected-run-id-pattern must be non-empty when provided"
                        )
                    if (
                        args.batch_output_verify_expected_event_count is not None
                        and args.batch_output_verify_expected_event_count < 0
                    ):
                        raise ValueError("--batch-output-verify-expected-event-count must be >= 0")
                    if (
                        args.batch_output_verify_expected_verified_count is not None
                        and args.batch_output_verify_expected_verified_count < 0
                    ):
                        raise ValueError("--batch-output-verify-expected-verified-count must be >= 0")
                    if (
                        args.batch_output_verify_expected_checked_count is not None
                        and args.batch_output_verify_expected_checked_count < 0
                    ):
                        raise ValueError("--batch-output-verify-expected-checked-count must be >= 0")
                    if (
                        args.batch_output_verify_expected_missing_count is not None
                        and args.batch_output_verify_expected_missing_count < 0
                    ):
                        raise ValueError("--batch-output-verify-expected-missing-count must be >= 0")
                    if (
                        args.batch_output_verify_expected_mismatched_count is not None
                        and args.batch_output_verify_expected_mismatched_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-mismatched-count must be >= 0"
                        )
                    if (
                        args.batch_output_verify_expected_manifest_missing_count is not None
                        and args.batch_output_verify_expected_manifest_missing_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-manifest-missing-count must be >= 0"
                        )
                    if (
                        args.batch_output_verify_expected_invalid_hashes_count is not None
                        and args.batch_output_verify_expected_invalid_hashes_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-invalid-hashes-count must be >= 0"
                        )
                    if (
                        args.batch_output_verify_expected_unexpected_manifest_count is not None
                        and args.batch_output_verify_expected_unexpected_manifest_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-unexpected-manifest-count must be >= 0"
                        )
                    if (
                        args.batch_output_verify_expected_strict_mismatches_count is not None
                        and args.batch_output_verify_expected_strict_mismatches_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-strict-mismatches-count must be >= 0"
                        )
                    if (
                        args.batch_output_verify_expected_event_artifact_count is not None
                        and args.batch_output_verify_expected_event_artifact_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-event-artifact-count must be >= 0"
                        )
                    if (
                        args.batch_output_verify_expected_manifest_entry_count is not None
                        and args.batch_output_verify_expected_manifest_entry_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-manifest-entry-count must be >= 0"
                        )
                    if (
                        args.batch_output_verify_expected_selected_artifact_count is not None
                        and args.batch_output_verify_expected_selected_artifact_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-selected-artifact-count must be >= 0"
                        )
                    if (
                        args.batch_output_verify_expected_manifest_selected_entry_count is not None
                        and args.batch_output_verify_expected_manifest_selected_entry_count < 0
                    ):
                        raise ValueError(
                            "--batch-output-verify-expected-manifest-selected-entry-count must be >= 0"
                        )

                    self_verify_strict_profile = _resolve_batch_output_verify_strict_profile(
                        enabled=True,
                        profile=args.batch_output_verify_profile,
                        expected_mode=args.batch_output_verify_expected_mode,
                        expected_layout=args.batch_output_verify_expected_layout,
                        expected_run_id_pattern=args.batch_output_verify_expected_run_id_pattern,
                        expected_event_count=args.batch_output_verify_expected_event_count,
                        expected_verified_count=args.batch_output_verify_expected_verified_count,
                        expected_checked_count=args.batch_output_verify_expected_checked_count,
                        expected_missing_count=args.batch_output_verify_expected_missing_count,
                        expected_mismatched_count=args.batch_output_verify_expected_mismatched_count,
                        expected_manifest_missing_count=args.batch_output_verify_expected_manifest_missing_count,
                        expected_invalid_hashes_count=args.batch_output_verify_expected_invalid_hashes_count,
                        expected_unexpected_manifest_count=args.batch_output_verify_expected_unexpected_manifest_count,
                        expected_status=args.batch_output_verify_expected_status,
                        expected_strict_mismatches_count=args.batch_output_verify_expected_strict_mismatches_count,
                        expected_event_artifact_count=args.batch_output_verify_expected_event_artifact_count,
                        expected_manifest_entry_count=args.batch_output_verify_expected_manifest_entry_count,
                        expected_selected_artifact_count=args.batch_output_verify_expected_selected_artifact_count,
                        expected_manifest_selected_entry_count=args.batch_output_verify_expected_manifest_selected_entry_count,
                        require_run_id=bool(args.batch_output_verify_require_run_id),
                    )
            else:
                if args.batch_output_verify == "":
                    raise ValueError("--batch-output-verify must be non-empty when provided")
                if args.batch_output_verify_include == "":
                    raise ValueError(
                        "--batch-output-verify-include must be non-empty when provided"
                    )
                if args.batch_output_verify_exclude == "":
                    raise ValueError(
                        "--batch-output-verify-exclude must be non-empty when provided"
                    )
                if args.batch_output_verify_summary_file == "":
                    raise ValueError(
                        "--batch-output-verify-summary-file must be non-empty when provided"
                    )
                if args.summary_policy:
                    raise ValueError("--summary-policy is not supported with --batch-output-verify")
                if args.input is not None or args.batch is not None:
                    raise ValueError("--batch-output-verify cannot be combined with --input or --batch")
                if args.refs is not None:
                    raise ValueError("--refs is not supported with --batch-output-verify")
                if args.include is not None:
                    raise ValueError("--include is not supported with --batch-output-verify")
                if args.exclude is not None:
                    raise ValueError("--exclude is not supported with --batch-output-verify")
                if args.batch_output is not None:
                    raise ValueError("--batch-output is not supported with --batch-output-verify")
                if args.batch_output_errors_only:
                    raise ValueError("--batch-output-errors-only is not supported with --batch-output-verify")
                if args.batch_output_manifest:
                    raise ValueError("--batch-output-manifest is not supported with --batch-output-verify")
                if args.batch_output_layout is not None:
                    raise ValueError("--batch-output-layout is not supported with --batch-output-verify")
                if args.batch_output_run_id is not None:
                    raise ValueError("--batch-output-run-id is not supported with --batch-output-verify")
                if args.batch_output_summary_file is not None:
                    raise ValueError(
                        "--batch-output-summary-file is not supported with --batch-output-verify"
                    )
                if args.batch_output_self_verify:
                    raise ValueError("--batch-output-self-verify is not supported with --batch-output-verify")
                if args.batch_output_self_verify_strict:
                    raise ValueError(
                        "--batch-output-self-verify-strict is not supported with --batch-output-verify"
                    )
                if args.meta:
                    raise ValueError("--meta is not supported with --batch-output-verify")
                if args.generated_at is not None:
                    raise ValueError("--generated-at is not supported with --batch-output-verify")
                if args.strict:
                    raise ValueError("--strict is not supported with --batch-output-verify")
                if str(args.exit_policy) != "default":
                    raise ValueError("--exit-policy is not supported with --batch-output-verify")

                strict_verify_enabled = bool(
                    args.batch_output_verify_strict or args.batch_output_verify_profile is not None
                )
                if args.batch_output_verify_expected_mode is not None and not strict_verify_enabled:
                    raise ValueError("--batch-output-verify-expected-mode requires strict verify")
                if args.batch_output_verify_expected_layout is not None and not strict_verify_enabled:
                    raise ValueError("--batch-output-verify-expected-layout requires strict verify")
                if args.batch_output_verify_expected_run_id_pattern is not None and not strict_verify_enabled:
                    raise ValueError(
                        "--batch-output-verify-expected-run-id-pattern requires strict verify"
                    )
                if args.batch_output_verify_expected_event_count is not None and not strict_verify_enabled:
                    raise ValueError("--batch-output-verify-expected-event-count requires strict verify")
                if args.batch_output_verify_expected_verified_count is not None and not strict_verify_enabled:
                    raise ValueError("--batch-output-verify-expected-verified-count requires strict verify")
                if args.batch_output_verify_expected_checked_count is not None and not strict_verify_enabled:
                    raise ValueError("--batch-output-verify-expected-checked-count requires strict verify")
                if args.batch_output_verify_expected_missing_count is not None and not strict_verify_enabled:
                    raise ValueError("--batch-output-verify-expected-missing-count requires strict verify")
                if (
                    args.batch_output_verify_expected_mismatched_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-mismatched-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_manifest_missing_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-missing-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_invalid_hashes_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-invalid-hashes-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_unexpected_manifest_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-unexpected-manifest-count requires strict verify"
                    )
                if args.batch_output_verify_expected_status is not None and not strict_verify_enabled:
                    raise ValueError("--batch-output-verify-expected-status requires strict verify")
                if (
                    args.batch_output_verify_expected_strict_mismatches_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-strict-mismatches-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_event_artifact_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-event-artifact-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_manifest_entry_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-entry-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_selected_artifact_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-selected-artifact-count requires strict verify"
                    )
                if (
                    args.batch_output_verify_expected_manifest_selected_entry_count is not None
                    and not strict_verify_enabled
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-selected-entry-count requires strict verify"
                    )
                if args.batch_output_verify_require_run_id and not strict_verify_enabled:
                    raise ValueError("--batch-output-verify-require-run-id requires strict verify")
                if args.batch_output_verify_expected_run_id_pattern == "":
                    raise ValueError(
                        "--batch-output-verify-expected-run-id-pattern must be non-empty when provided"
                    )
                if (
                    args.batch_output_verify_expected_event_count is not None
                    and args.batch_output_verify_expected_event_count < 0
                ):
                    raise ValueError("--batch-output-verify-expected-event-count must be >= 0")
                if (
                    args.batch_output_verify_expected_verified_count is not None
                    and args.batch_output_verify_expected_verified_count < 0
                ):
                    raise ValueError("--batch-output-verify-expected-verified-count must be >= 0")
                if (
                    args.batch_output_verify_expected_checked_count is not None
                    and args.batch_output_verify_expected_checked_count < 0
                ):
                    raise ValueError("--batch-output-verify-expected-checked-count must be >= 0")
                if (
                    args.batch_output_verify_expected_missing_count is not None
                    and args.batch_output_verify_expected_missing_count < 0
                ):
                    raise ValueError("--batch-output-verify-expected-missing-count must be >= 0")
                if (
                    args.batch_output_verify_expected_mismatched_count is not None
                    and args.batch_output_verify_expected_mismatched_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-mismatched-count must be >= 0"
                    )
                if (
                    args.batch_output_verify_expected_manifest_missing_count is not None
                    and args.batch_output_verify_expected_manifest_missing_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-missing-count must be >= 0"
                    )
                if (
                    args.batch_output_verify_expected_invalid_hashes_count is not None
                    and args.batch_output_verify_expected_invalid_hashes_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-invalid-hashes-count must be >= 0"
                    )
                if (
                    args.batch_output_verify_expected_unexpected_manifest_count is not None
                    and args.batch_output_verify_expected_unexpected_manifest_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-unexpected-manifest-count must be >= 0"
                    )
                if (
                    args.batch_output_verify_expected_strict_mismatches_count is not None
                    and args.batch_output_verify_expected_strict_mismatches_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-strict-mismatches-count must be >= 0"
                    )
                if (
                    args.batch_output_verify_expected_event_artifact_count is not None
                    and args.batch_output_verify_expected_event_artifact_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-event-artifact-count must be >= 0"
                    )
                if (
                    args.batch_output_verify_expected_manifest_entry_count is not None
                    and args.batch_output_verify_expected_manifest_entry_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-entry-count must be >= 0"
                    )
                if (
                    args.batch_output_verify_expected_selected_artifact_count is not None
                    and args.batch_output_verify_expected_selected_artifact_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-selected-artifact-count must be >= 0"
                    )
                if (
                    args.batch_output_verify_expected_manifest_selected_entry_count is not None
                    and args.batch_output_verify_expected_manifest_selected_entry_count < 0
                ):
                    raise ValueError(
                        "--batch-output-verify-expected-manifest-selected-entry-count must be >= 0"
                    )

                strict_profile = _resolve_batch_output_verify_strict_profile(
                    enabled=strict_verify_enabled,
                    profile=args.batch_output_verify_profile,
                    expected_mode=args.batch_output_verify_expected_mode,
                    expected_layout=args.batch_output_verify_expected_layout,
                    expected_run_id_pattern=args.batch_output_verify_expected_run_id_pattern,
                    expected_event_count=args.batch_output_verify_expected_event_count,
                    expected_verified_count=args.batch_output_verify_expected_verified_count,
                    expected_checked_count=args.batch_output_verify_expected_checked_count,
                    expected_missing_count=args.batch_output_verify_expected_missing_count,
                    expected_mismatched_count=args.batch_output_verify_expected_mismatched_count,
                    expected_manifest_missing_count=args.batch_output_verify_expected_manifest_missing_count,
                    expected_invalid_hashes_count=args.batch_output_verify_expected_invalid_hashes_count,
                    expected_unexpected_manifest_count=args.batch_output_verify_expected_unexpected_manifest_count,
                    expected_status=args.batch_output_verify_expected_status,
                    expected_strict_mismatches_count=args.batch_output_verify_expected_strict_mismatches_count,
                    expected_event_artifact_count=args.batch_output_verify_expected_event_artifact_count,
                    expected_manifest_entry_count=args.batch_output_verify_expected_manifest_entry_count,
                    expected_selected_artifact_count=args.batch_output_verify_expected_selected_artifact_count,
                    expected_manifest_selected_entry_count=args.batch_output_verify_expected_manifest_selected_entry_count,
                    require_run_id=bool(args.batch_output_verify_require_run_id),
                )

                verify_summary = _verify_batch_output_artifacts(
                    args.batch_output_verify,
                    strict_profile=strict_profile,
                    include_glob=args.batch_output_verify_include,
                    exclude_glob=args.batch_output_verify_exclude,
                )
                rendered_output = _render_batch_output_verify_summary(
                    verify_summary,
                    summary=bool(args.summary),
                )

                if args.output:
                    _write_eval_output(args.output, rendered_output)
                if args.batch_output_verify_summary_file:
                    _write_eval_output(args.batch_output_verify_summary_file, rendered_output)

                print(rendered_output)

                if verify_summary["status"] != "ok":
                    raise SystemExit(1)
                return

            if args.summary_policy and not args.summary:
                raise ValueError("--summary-policy requires --summary")
            if args.input is None and args.batch is None:
                raise ValueError("one of --input or --batch is required")

            source = _read_source(args.path)
            sidecar_refs = _read_eval_refs_source(args.refs) if args.refs else None

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
            if args.batch_output_run_id is not None and not args.batch_output:
                raise ValueError("--batch-output-run-id requires --batch-output")
            if args.batch_output_summary_file is not None and not args.batch:
                raise ValueError("--batch-output-summary-file requires --batch")
            if args.batch_output_summary_file == "":
                raise ValueError("--batch-output-summary-file must be non-empty when provided")
            if args.batch_output_summary_file is not None and args.summary:
                raise ValueError("--batch-output-summary-file is not supported with --summary")
            if args.batch_output_self_verify and not args.batch_output:
                raise ValueError("--batch-output-self-verify requires --batch-output")
            if args.batch_output_self_verify_strict and not args.batch_output_self_verify:
                raise ValueError(
                    "--batch-output-self-verify-strict requires --batch-output-self-verify"
                )
            if self_compare_enabled and not args.batch_output:
                raise ValueError("--batch-output-self-compare-against requires --batch-output")
            if args.batch_output_self_compare_strict and not self_compare_enabled:
                raise ValueError(
                    "--batch-output-self-compare-strict requires --batch-output-self-compare-against"
                )
            if args.include == "":
                raise ValueError("--include must be non-empty when provided")
            if args.exclude == "":
                raise ValueError("--exclude must be non-empty when provided")
            if args.batch_output_run_id == "":
                raise ValueError("--batch-output-run-id must be non-empty when provided")
            if args.batch_summary_rule_counts and not args.batch:
                raise ValueError("--batch-summary-rule-counts requires --batch")
            if args.batch_summary_rule_counts and args.summary:
                raise ValueError("--batch-summary-rule-counts is not supported with --summary")
            if args.batch_summary_action_kind_counts and not args.batch:
                raise ValueError("--batch-summary-action-kind-counts requires --batch")
            if args.batch_summary_action_kind_counts and args.summary:
                raise ValueError(
                    "--batch-summary-action-kind-counts is not supported with --summary"
                )

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
                    include_rule_counts=bool(args.batch_summary_rule_counts),
                    include_action_kind_counts=bool(args.batch_summary_action_kind_counts),
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

            if args.batch_output_summary_file:
                _write_batch_output_summary_file(args.batch_output_summary_file, envelope)

            if args.batch_output:
                include_manifest = bool(
                    args.batch_output_manifest
                    or args.batch_output_self_verify
                    or (
                        self_compare_enabled
                        and _batch_output_dir_has_manifest(args.batch_output_self_compare_against)
                    )
                )
                _write_batch_output_artifacts(
                    output_dir=args.batch_output,
                    envelope=envelope,
                    errors_only=bool(args.batch_output_errors_only),
                    include_manifest=include_manifest,
                    layout=str(args.batch_output_layout or "flat"),
                    run_id=args.batch_output_run_id,
                )
                if args.batch_output_self_verify:
                    self_verify_summary = _verify_batch_output_artifacts(
                        args.batch_output,
                        strict_profile=self_verify_strict_profile,
                    )
                    if self_verify_summary.get("status") != "ok":
                        rendered_self_verify_summary = _render_batch_output_verify_summary(
                            self_verify_summary,
                            summary=True,
                        )
                        self_verify_flag = (
                            "--batch-output-self-verify-strict"
                            if args.batch_output_self_verify_strict
                            else "--batch-output-self-verify"
                        )
                        raise ValueError(
                            f"{self_verify_flag} failed: {rendered_self_verify_summary}"
                        )
                if self_compare_enabled:
                    self_compare_summary = _compare_batch_output_artifacts(
                        args.batch_output,
                        against_dir=args.batch_output_self_compare_against,
                        include_glob=args.batch_output_compare_include,
                        exclude_glob=args.batch_output_compare_exclude,
                        strict_profile=self_compare_strict_profile,
                        candidate_flag="--batch-output",
                        against_flag="--batch-output-self-compare-against",
                        selector_flag="--batch-output-self-compare selectors",
                    )
                    if args.batch_output_compare_summary_file:
                        rendered_self_compare_output = _render_batch_output_compare_summary(
                            self_compare_summary,
                            summary=bool(args.summary),
                        )
                        _write_eval_output(
                            args.batch_output_compare_summary_file,
                            rendered_self_compare_output,
                        )
                    if self_compare_summary.get("status") != "ok":
                        rendered_self_compare_summary = _render_batch_output_compare_summary(
                            self_compare_summary,
                            summary=True,
                        )
                        self_compare_flag = (
                            "--batch-output-self-compare-strict"
                            if args.batch_output_self_compare_strict
                            else "--batch-output-self-compare-against"
                        )
                        raise ValueError(
                            f"{self_compare_flag} failed: {rendered_self_compare_summary}"
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

        if args.command == "pack-replay":
            if args.fixture_class_summary_file is not None and not args.fixture_class:
                raise ValueError("--fixture-class-summary-file requires --fixture-class")
            if args.summary_file == "":
                raise ValueError("--summary-file must be non-empty when provided")
            if args.json_file == "":
                raise ValueError("--json-file must be non-empty when provided")
            if args.fixture_class_summary_file == "":
                raise ValueError("--fixture-class-summary-file must be non-empty when provided")

            normalized_expected_pack_id = None
            if args.pack_replay_expected_pack_id is not None:
                if not isinstance(args.pack_replay_expected_pack_id, str) or not args.pack_replay_expected_pack_id.strip():
                    raise ValueError("--expected-pack-id must be non-empty")
                normalized_expected_pack_id = args.pack_replay_expected_pack_id.strip()

            normalized_expected_selected_fixture_ids = _normalize_program_pack_fixture_ids(
                args.pack_replay_expected_selected_fixture_ids,
                option_name="--expected-selected-fixture",
            )
            normalized_expected_ok_fixture_ids = _normalize_program_pack_fixture_ids(
                args.pack_replay_expected_ok_fixture_ids,
                option_name="--expected-ok-fixture",
            )
            normalized_expected_expectation_mismatch_fixture_ids = (
                _normalize_program_pack_fixture_ids(
                    args.pack_replay_expected_expectation_mismatch_fixture_ids,
                    option_name="--expected-expectation-mismatch-fixture",
                )
            )
            normalized_expected_runtime_error_fixture_ids = _normalize_program_pack_fixture_ids(
                args.pack_replay_expected_runtime_error_fixture_ids,
                option_name="--expected-runtime-error-fixture",
            )
            normalized_expected_fixture_class_counts = (
                _normalize_program_pack_fixture_class_counts(
                    args.pack_replay_expected_fixture_class_counts
                )
            )

            pack_replay_expected_selectors = [
                ("--expected-pack-id", normalized_expected_pack_id),
                ("--expected-baseline-shape", args.pack_replay_expected_baseline_shape),
                ("--expected-fixture-count", args.pack_replay_expected_fixture_count),
                ("--expected-total-fixture-count", args.pack_replay_expected_total_fixture_count),
                (
                    "--expected-selected-fixture",
                    normalized_expected_selected_fixture_ids,
                ),
                (
                    "--expected-ok-fixture",
                    normalized_expected_ok_fixture_ids,
                ),
                (
                    "--expected-expectation-mismatch-fixture",
                    normalized_expected_expectation_mismatch_fixture_ids,
                ),
                (
                    "--expected-runtime-error-fixture",
                    normalized_expected_runtime_error_fixture_ids,
                ),
                (
                    "--expected-fixture-class-counts",
                    normalized_expected_fixture_class_counts,
                ),
                ("--expected-mismatch-count", args.pack_replay_expected_mismatch_count),
                (
                    "--expected-expectation-mismatch-count",
                    args.pack_replay_expected_expectation_mismatch_count,
                ),
                (
                    "--expected-runtime-error-count",
                    args.pack_replay_expected_runtime_error_count,
                ),
                (
                    "--expected-rule-source-status",
                    args.pack_replay_expected_rule_source_status,
                ),
            ]
            pack_replay_strict_enabled = bool(
                args.pack_replay_strict or args.pack_replay_strict_profile is not None
            )
            has_pack_replay_strict_contract = bool(args.pack_replay_strict_profile is not None) or any(
                option_value is not None for _, option_value in pack_replay_expected_selectors
            )
            if args.pack_replay_strict and not has_pack_replay_strict_contract:
                raise ValueError(
                    "--strict requires at least one --expected-* selector or --strict-profile"
                )
            for option_name, option_value in pack_replay_expected_selectors:
                if option_value is not None and not pack_replay_strict_enabled:
                    raise ValueError(f"{option_name} requires --strict")
            for option_name, option_value in pack_replay_expected_selectors:
                if isinstance(option_value, int) and option_value < 0:
                    raise ValueError(f"{option_name} must be >= 0")

            strict_profile = _resolve_program_pack_replay_strict_profile(
                enabled=pack_replay_strict_enabled,
                profile=args.pack_replay_strict_profile,
                expected_pack_id=normalized_expected_pack_id,
                expected_baseline_shape=args.pack_replay_expected_baseline_shape,
                expected_fixture_count=args.pack_replay_expected_fixture_count,
                expected_total_fixture_count=args.pack_replay_expected_total_fixture_count,
                expected_selected_fixture_ids=normalized_expected_selected_fixture_ids,
                expected_ok_fixture_ids=normalized_expected_ok_fixture_ids,
                expected_expectation_mismatch_fixture_ids=normalized_expected_expectation_mismatch_fixture_ids,
                expected_runtime_error_fixture_ids=normalized_expected_runtime_error_fixture_ids,
                expected_fixture_class_counts=normalized_expected_fixture_class_counts,
                expected_mismatch_count=args.pack_replay_expected_mismatch_count,
                expected_expectation_mismatch_count=args.pack_replay_expected_expectation_mismatch_count,
                expected_runtime_error_count=args.pack_replay_expected_runtime_error_count,
                expected_rule_source_status=args.pack_replay_expected_rule_source_status,
            )
            envelope = _replay_program_pack(
                args.path,
                fixture_ids=args.fixture,
                include_fixture_globs=args.include_fixture,
                exclude_fixture_globs=args.exclude_fixture,
                fixture_classes=args.fixture_class,
                strict_profile=strict_profile,
            )
            rendered_json = _render_program_pack_replay_output(envelope, summary=False)
            rendered_output = rendered_json
            if args.summary:
                rendered_output = _render_program_pack_replay_output(envelope, summary=True)
            rendered_summary = _render_program_pack_replay_output(envelope, summary=True)
            if args.output:
                _write_eval_output(args.output, rendered_output)
            if args.json_file:
                _write_eval_output(args.json_file, rendered_json)
            if args.summary_file:
                _write_eval_output(args.summary_file, rendered_summary)
            if args.fixture_class_summary_file:
                _write_eval_output(
                    args.fixture_class_summary_file,
                    rendered_summary,
                )
            print(rendered_output)
            if envelope.get("status") != "ok":
                raise SystemExit(1)
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


def _build_program_pack_fixture_matrix(
    baseline: object,
    *,
    pack_root: Path,
) -> tuple[str, list[dict[str, object]], list[dict[str, object]], str]:
    if isinstance(baseline, dict):
        baseline_rules = baseline.get("rules")
        if not isinstance(baseline_rules, list):
            raise ValueError("pack baseline must contain `rules` list")

        fixtures = baseline.get("fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            raise ValueError("pack baseline must contain non-empty `fixtures` list")

        pack_id = baseline.get("pack_id") if isinstance(baseline.get("pack_id"), str) else pack_root.name
        return pack_id, baseline_rules, fixtures, "fixture-matrix"

    if not isinstance(baseline, list):
        raise ValueError(
            "pack baseline must contain either an object with `rules` + `fixtures` or an inline statement array"
        )

    baseline_rules: list[dict[str, object]] = []
    inline_events: list[dict[str, object]] = []
    baseline_refs: dict[str, object] = {}

    for index, statement in enumerate(baseline, start=1):
        if not isinstance(statement, dict):
            raise ValueError(f"pack baseline statement #{index} must be an object")

        tag = statement.get("tag")
        fields = statement.get("fields")
        if tag in {"ev", "event", "rl", "rule", "rf"} and not isinstance(fields, dict):
            raise ValueError(
                f"pack baseline statement #{index} with tag `{tag}` must contain object `fields`"
            )

        if tag in {"rl", "rule"}:
            baseline_rules.append(
                {
                    "id": fields.get("id"),
                    "when": fields.get("when"),
                    "then": fields.get("then"),
                }
            )
            continue

        if tag in {"ev", "event"}:
            inline_events.append(fields)
            continue

        if tag == "rf" and "id" in fields and "v" in fields:
            baseline_refs[str(fields["id"])] = fields["v"]

    if not baseline_rules:
        raise ValueError("inline pack baseline must contain at least one `rl` rule statement")
    if not inline_events:
        raise ValueError("inline pack baseline must contain at least one `ev` event statement")

    fixtures: list[dict[str, object]] = []
    for index, event in enumerate(inline_events, start=1):
        event_type = event.get("type") if isinstance(event.get("type"), str) and event.get("type") else "event"
        derived = eval_policies_envelope(event, baseline_rules, refs=baseline_refs)
        expected_actions = (
            derived.get("actions") if isinstance(derived.get("actions"), list) else []
        )
        expected_trace = derived.get("trace") if isinstance(derived.get("trace"), list) else []

        fixtures.append(
            {
                "id": f"event-{index:02d}-{event_type}",
                "event": event,
                "expected_actions": expected_actions,
                "expected_trace": expected_trace,
            }
        )

    return pack_root.name, baseline_rules, fixtures, "inline-statements"


def _normalize_program_pack_fixture_ids(
    fixture_ids: list[str] | None,
    *,
    option_name: str = "--fixture",
) -> list[str] | None:
    if fixture_ids is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for index, fixture_id in enumerate(fixture_ids, start=1):
        if not isinstance(fixture_id, str) or not fixture_id.strip():
            raise ValueError(f"{option_name} entry #{index} must be non-empty")
        normalized_fixture_id = fixture_id.strip()
        if normalized_fixture_id in seen:
            raise ValueError(f"duplicate {option_name} selector: {normalized_fixture_id}")
        seen.add(normalized_fixture_id)
        normalized.append(normalized_fixture_id)
    return normalized


def _normalize_program_pack_fixture_globs(
    option_name: str,
    fixture_globs: list[str] | None,
) -> list[str] | None:
    if fixture_globs is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for index, fixture_glob in enumerate(fixture_globs, start=1):
        if not isinstance(fixture_glob, str) or not fixture_glob.strip():
            raise ValueError(f"{option_name} entry #{index} must be non-empty")
        normalized_fixture_glob = fixture_glob.strip()
        if normalized_fixture_glob in seen:
            raise ValueError(f"duplicate {option_name} selector: {normalized_fixture_glob}")
        seen.add(normalized_fixture_glob)
        normalized.append(normalized_fixture_glob)
    return normalized


def _normalize_program_pack_fixture_classes(
    fixture_classes: list[str] | None,
) -> list[str] | None:
    if fixture_classes is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for index, fixture_class in enumerate(fixture_classes, start=1):
        if not isinstance(fixture_class, str) or not fixture_class.strip():
            raise ValueError(f"--fixture-class entry #{index} must be non-empty")
        normalized_fixture_class = fixture_class.strip()
        if normalized_fixture_class in seen:
            raise ValueError(f"duplicate --fixture-class selector: {normalized_fixture_class}")
        seen.add(normalized_fixture_class)
        normalized.append(normalized_fixture_class)
    return normalized


def _normalize_program_pack_fixture_class_counts(
    fixture_class_counts: str | None,
    *,
    option_name: str = "--expected-fixture-class-counts",
) -> dict[str, int] | None:
    if fixture_class_counts is None:
        return None
    if not isinstance(fixture_class_counts, str) or not fixture_class_counts.strip():
        raise ValueError(f"{option_name} must be non-empty")

    normalized: dict[str, int] = {}
    entries = fixture_class_counts.split(",")
    for index, raw_entry in enumerate(entries, start=1):
        entry = raw_entry.strip()
        if not entry:
            raise ValueError(f"{option_name} entry #{index} must be non-empty")
        fixture_class, separator, count_text = entry.partition("=")
        if not separator:
            raise ValueError(
                f"{option_name} entry #{index} must use <fixture-class>=<count>"
            )
        normalized_fixture_class = fixture_class.strip()
        if normalized_fixture_class not in PROGRAM_PACK_REPLAY_FIXTURE_CLASSES:
            allowed_fixture_classes = ", ".join(PROGRAM_PACK_REPLAY_FIXTURE_CLASSES)
            raise ValueError(
                f"{option_name} entry #{index} has unknown fixture class: {normalized_fixture_class} (expected one of: {allowed_fixture_classes})"
            )
        if normalized_fixture_class in normalized:
            raise ValueError(f"duplicate {option_name} class: {normalized_fixture_class}")
        normalized_count_text = count_text.strip()
        if not normalized_count_text:
            raise ValueError(f"{option_name} entry #{index} must include a count")
        try:
            normalized_count = int(normalized_count_text)
        except ValueError as exc:
            raise ValueError(
                f"{option_name} count for {normalized_fixture_class} must be an integer"
            ) from exc
        if normalized_count < 0:
            raise ValueError(
                f"{option_name} count for {normalized_fixture_class} must be >= 0"
            )
        normalized[normalized_fixture_class] = normalized_count

    missing_fixture_classes = [
        fixture_class
        for fixture_class in PROGRAM_PACK_REPLAY_FIXTURE_CLASSES
        if fixture_class not in normalized
    ]
    if missing_fixture_classes:
        raise ValueError(
            f"{option_name} must include counts for: {', '.join(missing_fixture_classes)}"
        )

    return {
        fixture_class: normalized[fixture_class]
        for fixture_class in PROGRAM_PACK_REPLAY_FIXTURE_CLASSES
    }


def _replay_program_pack(
    path: str,
    *,
    fixture_ids: list[str] | None = None,
    include_fixture_globs: list[str] | None = None,
    exclude_fixture_globs: list[str] | None = None,
    fixture_classes: list[str] | None = None,
    strict_profile: dict[str, object] | None = None,
) -> dict[str, object]:
    pack_root = Path(path)
    if not pack_root.exists() or not pack_root.is_dir():
        raise ValueError("pack-replay path must point to an existing directory")

    program_path = _discover_program_pack_program(pack_root)
    baseline_path = _discover_program_pack_baseline(pack_root)

    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"pack baseline '{baseline_path.name}' must contain valid JSON: {exc}") from exc

    pack_id, baseline_rules, fixtures, baseline_shape = _build_program_pack_fixture_matrix(
        baseline,
        pack_root=pack_root,
    )
    selected_fixture_ids = _normalize_program_pack_fixture_ids(fixture_ids)
    include_fixture_globs = _normalize_program_pack_fixture_globs(
        "--include-fixture",
        include_fixture_globs,
    )
    exclude_fixture_globs = _normalize_program_pack_fixture_globs(
        "--exclude-fixture",
        exclude_fixture_globs,
    )
    selected_fixture_classes = _normalize_program_pack_fixture_classes(fixture_classes)
    total_fixture_count = len(fixtures)
    available_fixture_ids = [
        fixture.get("id")
        for fixture in fixtures
        if isinstance(fixture, dict) and isinstance(fixture.get("id"), str)
    ]
    available_fixture_id_set = set(available_fixture_ids)

    final_selected_fixture_ids: list[str] | None = None
    if selected_fixture_ids is not None:
        missing_fixture_ids = [
            fixture_id for fixture_id in selected_fixture_ids if fixture_id not in available_fixture_id_set
        ]
        if missing_fixture_ids:
            missing_rendered = ", ".join(missing_fixture_ids)
            raise ValueError(f"unknown --fixture selector(s): {missing_rendered}")

    include_selected_fixture_ids: set[str] = set()
    if include_fixture_globs is not None:
        unmatched_include_globs = [
            pattern
            for pattern in include_fixture_globs
            if not any(fnmatch.fnmatchcase(fixture_id, pattern) for fixture_id in available_fixture_ids)
        ]
        if unmatched_include_globs:
            unmatched_rendered = ", ".join(unmatched_include_globs)
            raise ValueError(f"unmatched --include-fixture selector(s): {unmatched_rendered}")
        include_selected_fixture_ids = {
            fixture_id
            for fixture_id in available_fixture_ids
            for pattern in include_fixture_globs
            if fnmatch.fnmatchcase(fixture_id, pattern)
        }

    excluded_fixture_ids: set[str] = set()
    if exclude_fixture_globs is not None:
        unmatched_exclude_globs = [
            pattern
            for pattern in exclude_fixture_globs
            if not any(fnmatch.fnmatchcase(fixture_id, pattern) for fixture_id in available_fixture_ids)
        ]
        if unmatched_exclude_globs:
            unmatched_rendered = ", ".join(unmatched_exclude_globs)
            raise ValueError(f"unmatched --exclude-fixture selector(s): {unmatched_rendered}")
        excluded_fixture_ids = {
            fixture_id
            for fixture_id in available_fixture_ids
            for pattern in exclude_fixture_globs
            if fnmatch.fnmatchcase(fixture_id, pattern)
        }

    if (
        selected_fixture_ids is not None
        or include_fixture_globs is not None
        or exclude_fixture_globs is not None
    ):
        explicitly_selected_fixture_ids = set(selected_fixture_ids or [])
        if selected_fixture_ids is None and include_fixture_globs is None:
            selected_fixture_id_set = available_fixture_id_set.copy()
        else:
            selected_fixture_id_set = explicitly_selected_fixture_ids | include_selected_fixture_ids
        selected_fixture_id_set -= excluded_fixture_ids
        fixtures = [
            fixture
            for fixture in fixtures
            if isinstance(fixture, dict) and fixture.get("id") in selected_fixture_id_set
        ]
        if not fixtures:
            selector_fragments: list[str] = []
            if selected_fixture_ids is not None:
                selector_fragments.append(f"--fixture {', '.join(selected_fixture_ids)}")
            if include_fixture_globs is not None:
                selector_fragments.append(
                    f"--include-fixture {', '.join(include_fixture_globs)}"
                )
            if exclude_fixture_globs is not None:
                selector_fragments.append(
                    f"--exclude-fixture {', '.join(exclude_fixture_globs)}"
                )
            raise ValueError(
                "fixture selectors matched zero fixtures after applying: "
                + "; ".join(selector_fragments)
            )
        final_selected_fixture_ids = [
            fixture["id"]
            for fixture in fixtures
            if isinstance(fixture.get("id"), str)
        ]

    source = program_path.read_text(encoding="utf-8")
    rules, refs = _extract_eval_program_components(source)
    inline_program_statements = None
    inline_baseline_statements = None
    if baseline_shape == "inline-statements" and isinstance(baseline, list):
        inline_program_statements = canonicalize_program(parse_compact(source))
        inline_baseline_statements = baseline

    fixture_reports: list[dict[str, object]] = []

    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, dict):
            raise ValueError(f"pack baseline fixture #{index} must be an object")

        fixture_id = fixture.get("id")
        if not isinstance(fixture_id, str) or not fixture_id:
            raise ValueError(f"pack baseline fixture #{index} must contain non-empty `id`")
        if "event" not in fixture:
            raise ValueError(f"pack baseline fixture '{fixture_id}' must contain `event`")

        expected_actions = fixture.get("expected_actions")
        if not isinstance(expected_actions, list):
            raise ValueError(f"pack baseline fixture '{fixture_id}' must contain `expected_actions` list")

        expected_trace = fixture.get("expected_trace")
        if not isinstance(expected_trace, list):
            raise ValueError(f"pack baseline fixture '{fixture_id}' must contain `expected_trace` list")

        context = fixture.get("context")
        if context is None:
            context = {}
        if not isinstance(context, dict):
            raise ValueError(f"pack baseline fixture '{fixture_id}' must contain object `context`")

        calibration = fixture.get("calibration")
        envelope = eval_policies_envelope(
            fixture["event"],
            rules,
            now=context.get("now"),
            seed=context.get("seed"),
            calibration=calibration,
            refs=refs,
        )
        actions = envelope.get("actions") if isinstance(envelope.get("actions"), list) else []
        trace = envelope.get("trace") if isinstance(envelope.get("trace"), list) else []
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else None

        matches = error is None and actions == expected_actions and trace == expected_trace
        if matches:
            fixture_class = "ok"
        elif error is not None:
            fixture_class = "runtime_error"
        else:
            fixture_class = "expectation_mismatch"

        fixture_report: dict[str, object] = {
            "id": fixture_id,
            "status": "ok" if matches else "mismatch",
            "fixture_class": fixture_class,
            "actions": actions,
            "trace": trace,
        }
        if error is not None:
            fixture_report["error"] = error
        if not matches:
            fixture_report["expected_actions"] = expected_actions
            fixture_report["expected_trace"] = expected_trace

        fixture_reports.append(fixture_report)

    if selected_fixture_classes is not None:
        available_fixture_classes = [
            fixture_report.get("fixture_class")
            for fixture_report in fixture_reports
            if isinstance(fixture_report.get("fixture_class"), str)
        ]
        available_fixture_class_set = set(available_fixture_classes)
        unmatched_fixture_classes = [
            fixture_class
            for fixture_class in selected_fixture_classes
            if fixture_class not in available_fixture_class_set
        ]
        if unmatched_fixture_classes:
            unmatched_rendered = ", ".join(unmatched_fixture_classes)
            raise ValueError(f"unmatched --fixture-class selector(s): {unmatched_rendered}")
        selected_fixture_class_set = set(selected_fixture_classes)
        fixture_reports = [
            fixture_report
            for fixture_report in fixture_reports
            if fixture_report.get("fixture_class") in selected_fixture_class_set
        ]
        final_selected_fixture_ids = [
            fixture_report["id"]
            for fixture_report in fixture_reports
            if isinstance(fixture_report.get("id"), str)
        ]

    matched_count = sum(1 for fixture_report in fixture_reports if fixture_report.get("status") == "ok")
    runtime_error_count = sum(
        1 for fixture_report in fixture_reports if isinstance(fixture_report.get("error"), dict)
    )
    mismatch_count = len(fixture_reports) - matched_count
    fixture_class_ids = {
        "ok": [
            fixture_report["id"]
            for fixture_report in fixture_reports
            if fixture_report.get("fixture_class") == "ok" and isinstance(fixture_report.get("id"), str)
        ],
        "expectation_mismatch": [
            fixture_report["id"]
            for fixture_report in fixture_reports
            if fixture_report.get("fixture_class") == "expectation_mismatch"
            and isinstance(fixture_report.get("id"), str)
        ],
        "runtime_error": [
            fixture_report["id"]
            for fixture_report in fixture_reports
            if fixture_report.get("fixture_class") == "runtime_error"
            and isinstance(fixture_report.get("id"), str)
        ],
    }

    if baseline_shape == "inline-statements":
        rule_source_status = (
            "ok"
            if inline_program_statements == inline_baseline_statements
            else "mismatch"
        )
    else:
        rule_source_status = "ok" if rules == baseline_rules else "mismatch"

    fixture_class_counts = {
        "ok": matched_count,
        "expectation_mismatch": mismatch_count - runtime_error_count,
        "runtime_error": runtime_error_count,
    }
    report: dict[str, object] = {
        "pack_id": pack_id,
        "program": program_path.name,
        "baseline": baseline_path.name,
        "baseline_shape": baseline_shape,
        "rule_source_status": rule_source_status,
        "fixtures": fixture_reports,
        "summary": {
            "fixture_count": len(fixture_reports),
            "matched_count": matched_count,
            "mismatch_count": mismatch_count,
            "runtime_error_count": runtime_error_count,
            "total_fixture_count": total_fixture_count,
            "fixture_class_counts": fixture_class_counts,
            "fixture_class_ids": fixture_class_ids,
        },
    }
    if final_selected_fixture_ids is not None:
        report["selected_fixture_ids"] = final_selected_fixture_ids
    if include_fixture_globs is not None:
        report["include_fixture_globs"] = include_fixture_globs
    if exclude_fixture_globs is not None:
        report["exclude_fixture_globs"] = exclude_fixture_globs
    if selected_fixture_classes is not None:
        report["fixture_class_selectors"] = selected_fixture_classes
    if rule_source_status != "ok":
        report["program_rules"] = rules
        report["baseline_rules"] = baseline_rules
        if baseline_shape == "inline-statements":
            report["program_statements"] = inline_program_statements
            report["baseline_statements"] = inline_baseline_statements

    report["status"] = (
        "ok"
        if rule_source_status == "ok" and mismatch_count == 0 and runtime_error_count == 0
        else "error"
    )
    return _apply_program_pack_replay_strict_profile(report, strict_profile=strict_profile)


def _resolve_program_pack_replay_strict_profile(
    *,
    enabled: bool,
    profile: str | None,
    expected_pack_id: str | None,
    expected_baseline_shape: str | None,
    expected_fixture_count: int | None,
    expected_total_fixture_count: int | None,
    expected_selected_fixture_ids: list[str] | None,
    expected_ok_fixture_ids: list[str] | None,
    expected_expectation_mismatch_fixture_ids: list[str] | None,
    expected_runtime_error_fixture_ids: list[str] | None,
    expected_fixture_class_counts: dict[str, int] | None,
    expected_mismatch_count: int | None,
    expected_expectation_mismatch_count: int | None,
    expected_runtime_error_count: int | None,
    expected_rule_source_status: str | None,
) -> dict[str, object] | None:
    if not enabled:
        return None

    strict_profile: dict[str, object] = {}
    if profile is not None:
        strict_profile.update(PROGRAM_PACK_REPLAY_STRICT_PROFILES[profile])
    if expected_pack_id is not None:
        strict_profile["expected_pack_id"] = expected_pack_id
    if expected_baseline_shape is not None:
        strict_profile["expected_baseline_shape"] = expected_baseline_shape
    if expected_fixture_count is not None:
        strict_profile["expected_fixture_count"] = expected_fixture_count
    if expected_total_fixture_count is not None:
        strict_profile["expected_total_fixture_count"] = expected_total_fixture_count
    if expected_selected_fixture_ids is not None:
        strict_profile["expected_selected_fixture_ids"] = expected_selected_fixture_ids
    if expected_ok_fixture_ids is not None:
        strict_profile["expected_ok_fixture_ids"] = expected_ok_fixture_ids
    if expected_expectation_mismatch_fixture_ids is not None:
        strict_profile["expected_expectation_mismatch_fixture_ids"] = (
            expected_expectation_mismatch_fixture_ids
        )
    if expected_runtime_error_fixture_ids is not None:
        strict_profile["expected_runtime_error_fixture_ids"] = expected_runtime_error_fixture_ids
    if expected_fixture_class_counts is not None:
        strict_profile["expected_fixture_class_counts"] = expected_fixture_class_counts
    if expected_mismatch_count is not None:
        strict_profile["expected_mismatch_count"] = expected_mismatch_count
    if expected_expectation_mismatch_count is not None:
        strict_profile["expected_expectation_mismatch_count"] = expected_expectation_mismatch_count
    if expected_runtime_error_count is not None:
        strict_profile["expected_runtime_error_count"] = expected_runtime_error_count
    if expected_rule_source_status is not None:
        strict_profile["expected_rule_source_status"] = expected_rule_source_status
    return strict_profile


def _program_pack_replay_fixture_class_counts(
    report: dict[str, object],
) -> dict[str, int]:
    summary_payload = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    fixture_class_counts = (
        summary_payload.get("fixture_class_counts")
        if isinstance(summary_payload.get("fixture_class_counts"), dict)
        else {}
    )
    if all(
        isinstance(fixture_class_counts.get(fixture_class), int)
        and not isinstance(fixture_class_counts.get(fixture_class), bool)
        for fixture_class in PROGRAM_PACK_REPLAY_FIXTURE_CLASSES
    ):
        return {
            fixture_class: fixture_class_counts[fixture_class]
            for fixture_class in PROGRAM_PACK_REPLAY_FIXTURE_CLASSES
        }

    fixtures_payload = report.get("fixtures") if isinstance(report.get("fixtures"), list) else []
    normalized_counts = {fixture_class: 0 for fixture_class in PROGRAM_PACK_REPLAY_FIXTURE_CLASSES}
    for fixture_report in fixtures_payload:
        if not isinstance(fixture_report, dict):
            continue
        fixture_class = fixture_report.get("fixture_class")
        if fixture_class in normalized_counts:
            normalized_counts[fixture_class] += 1
    return normalized_counts



def _program_pack_replay_fixture_class_ids(
    report: dict[str, object],
    *,
    fixture_class: str,
) -> list[str]:
    summary_payload = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    fixture_class_ids = (
        summary_payload.get("fixture_class_ids")
        if isinstance(summary_payload.get("fixture_class_ids"), dict)
        else {}
    )
    actual_fixture_ids = fixture_class_ids.get(fixture_class)
    if isinstance(actual_fixture_ids, list) and all(
        isinstance(fixture_id, str) for fixture_id in actual_fixture_ids
    ):
        return actual_fixture_ids

    fixtures_payload = report.get("fixtures") if isinstance(report.get("fixtures"), list) else []
    return [
        fixture_report["id"]
        for fixture_report in fixtures_payload
        if isinstance(fixture_report, dict)
        and fixture_report.get("fixture_class") == fixture_class
        and isinstance(fixture_report.get("id"), str)
    ]



def _apply_program_pack_replay_strict_profile(
    report: dict[str, object],
    *,
    strict_profile: dict[str, object] | None,
) -> dict[str, object]:
    if strict_profile is None:
        return report

    strict_profile_mismatches: list[dict[str, object]] = []
    summary_payload = report.get("summary") if isinstance(report.get("summary"), dict) else {}

    fixture_count = (
        summary_payload.get("fixture_count")
        if isinstance(summary_payload.get("fixture_count"), int)
        else 0
    )
    expected_fixture_count = strict_profile.get("expected_fixture_count")
    if isinstance(expected_fixture_count, int) and not isinstance(expected_fixture_count, bool):
        if fixture_count != expected_fixture_count:
            strict_profile_mismatches.append(
                {
                    "field": "fixture_count",
                    "expected": expected_fixture_count,
                    "actual": fixture_count,
                }
            )

    total_fixture_count = (
        summary_payload.get("total_fixture_count")
        if isinstance(summary_payload.get("total_fixture_count"), int)
        else fixture_count
    )
    expected_total_fixture_count = strict_profile.get("expected_total_fixture_count")
    if isinstance(expected_total_fixture_count, int) and not isinstance(
        expected_total_fixture_count, bool
    ):
        if total_fixture_count != expected_total_fixture_count:
            strict_profile_mismatches.append(
                {
                    "field": "total_fixture_count",
                    "expected": expected_total_fixture_count,
                    "actual": total_fixture_count,
                }
            )

    baseline_shape = (
        report.get("baseline_shape")
        if isinstance(report.get("baseline_shape"), str)
        else "unknown"
    )
    expected_baseline_shape = strict_profile.get("expected_baseline_shape")
    if isinstance(expected_baseline_shape, str):
        if baseline_shape != expected_baseline_shape:
            strict_profile_mismatches.append(
                {
                    "field": "baseline_shape",
                    "expected": expected_baseline_shape,
                    "actual": baseline_shape,
                }
            )

    pack_id = report.get("pack_id") if isinstance(report.get("pack_id"), str) else "unknown"
    expected_pack_id = strict_profile.get("expected_pack_id")
    if isinstance(expected_pack_id, str):
        if pack_id != expected_pack_id:
            strict_profile_mismatches.append(
                {
                    "field": "pack_id",
                    "expected": expected_pack_id,
                    "actual": pack_id,
                }
            )

    actual_selected_fixture_ids = report.get("selected_fixture_ids")
    if not isinstance(actual_selected_fixture_ids, list) or not all(
        isinstance(fixture_id, str) for fixture_id in actual_selected_fixture_ids
    ):
        fixtures_payload = report.get("fixtures") if isinstance(report.get("fixtures"), list) else []
        actual_selected_fixture_ids = [
            fixture_report["id"]
            for fixture_report in fixtures_payload
            if isinstance(fixture_report, dict) and isinstance(fixture_report.get("id"), str)
        ]
    expected_selected_fixture_ids = strict_profile.get("expected_selected_fixture_ids")
    if isinstance(expected_selected_fixture_ids, list) and all(
        isinstance(fixture_id, str) for fixture_id in expected_selected_fixture_ids
    ):
        if actual_selected_fixture_ids != expected_selected_fixture_ids:
            strict_profile_mismatches.append(
                {
                    "field": "selected_fixture_ids",
                    "expected": expected_selected_fixture_ids,
                    "actual": actual_selected_fixture_ids,
                }
            )

    actual_ok_fixture_ids = _program_pack_replay_fixture_class_ids(
        report,
        fixture_class="ok",
    )
    expected_ok_fixture_ids = strict_profile.get("expected_ok_fixture_ids")
    if isinstance(expected_ok_fixture_ids, list) and all(
        isinstance(fixture_id, str) for fixture_id in expected_ok_fixture_ids
    ):
        if actual_ok_fixture_ids != expected_ok_fixture_ids:
            strict_profile_mismatches.append(
                {
                    "field": "fixture_class_ids.ok",
                    "expected": expected_ok_fixture_ids,
                    "actual": actual_ok_fixture_ids,
                }
            )

    actual_expectation_mismatch_fixture_ids = _program_pack_replay_fixture_class_ids(
        report,
        fixture_class="expectation_mismatch",
    )
    expected_expectation_mismatch_fixture_ids = strict_profile.get(
        "expected_expectation_mismatch_fixture_ids"
    )
    if isinstance(expected_expectation_mismatch_fixture_ids, list) and all(
        isinstance(fixture_id, str)
        for fixture_id in expected_expectation_mismatch_fixture_ids
    ):
        if actual_expectation_mismatch_fixture_ids != expected_expectation_mismatch_fixture_ids:
            strict_profile_mismatches.append(
                {
                    "field": "fixture_class_ids.expectation_mismatch",
                    "expected": expected_expectation_mismatch_fixture_ids,
                    "actual": actual_expectation_mismatch_fixture_ids,
                }
            )

    actual_runtime_error_fixture_ids = _program_pack_replay_fixture_class_ids(
        report,
        fixture_class="runtime_error",
    )
    expected_runtime_error_fixture_ids = strict_profile.get(
        "expected_runtime_error_fixture_ids"
    )
    if isinstance(expected_runtime_error_fixture_ids, list) and all(
        isinstance(fixture_id, str) for fixture_id in expected_runtime_error_fixture_ids
    ):
        if actual_runtime_error_fixture_ids != expected_runtime_error_fixture_ids:
            strict_profile_mismatches.append(
                {
                    "field": "fixture_class_ids.runtime_error",
                    "expected": expected_runtime_error_fixture_ids,
                    "actual": actual_runtime_error_fixture_ids,
                }
            )

    mismatch_count = (
        summary_payload.get("mismatch_count")
        if isinstance(summary_payload.get("mismatch_count"), int)
        else 0
    )
    expected_mismatch_count = strict_profile.get("expected_mismatch_count")
    if isinstance(expected_mismatch_count, int) and not isinstance(expected_mismatch_count, bool):
        if mismatch_count != expected_mismatch_count:
            strict_profile_mismatches.append(
                {
                    "field": "mismatch_count",
                    "expected": expected_mismatch_count,
                    "actual": mismatch_count,
                }
            )

    fixture_class_counts = _program_pack_replay_fixture_class_counts(report)
    expected_fixture_class_counts = strict_profile.get("expected_fixture_class_counts")
    if isinstance(expected_fixture_class_counts, dict) and all(
        fixture_class in PROGRAM_PACK_REPLAY_FIXTURE_CLASSES
        and isinstance(expected_fixture_class_counts.get(fixture_class), int)
        and not isinstance(expected_fixture_class_counts.get(fixture_class), bool)
        for fixture_class in expected_fixture_class_counts
    ):
        normalized_expected_fixture_class_counts = {
            fixture_class: expected_fixture_class_counts[fixture_class]
            for fixture_class in PROGRAM_PACK_REPLAY_FIXTURE_CLASSES
            if fixture_class in expected_fixture_class_counts
        }
        if fixture_class_counts != normalized_expected_fixture_class_counts:
            strict_profile_mismatches.append(
                {
                    "field": "fixture_class_counts",
                    "expected": normalized_expected_fixture_class_counts,
                    "actual": fixture_class_counts,
                }
            )
    expectation_mismatch_count = (
        fixture_class_counts.get("expectation_mismatch")
        if isinstance(fixture_class_counts.get("expectation_mismatch"), int)
        else 0
    )
    expected_expectation_mismatch_count = strict_profile.get(
        "expected_expectation_mismatch_count"
    )
    if isinstance(expected_expectation_mismatch_count, int) and not isinstance(
        expected_expectation_mismatch_count, bool
    ):
        if expectation_mismatch_count != expected_expectation_mismatch_count:
            strict_profile_mismatches.append(
                {
                    "field": "expectation_mismatch_count",
                    "expected": expected_expectation_mismatch_count,
                    "actual": expectation_mismatch_count,
                }
            )

    runtime_error_count = (
        summary_payload.get("runtime_error_count")
        if isinstance(summary_payload.get("runtime_error_count"), int)
        else 0
    )
    expected_runtime_error_count = strict_profile.get("expected_runtime_error_count")
    if isinstance(expected_runtime_error_count, int) and not isinstance(
        expected_runtime_error_count, bool
    ):
        if runtime_error_count != expected_runtime_error_count:
            strict_profile_mismatches.append(
                {
                    "field": "runtime_error_count",
                    "expected": expected_runtime_error_count,
                    "actual": runtime_error_count,
                }
            )

    rule_source_status = (
        report.get("rule_source_status")
        if isinstance(report.get("rule_source_status"), str)
        else "unknown"
    )
    expected_rule_source_status = strict_profile.get("expected_rule_source_status")
    if isinstance(expected_rule_source_status, str):
        if rule_source_status != expected_rule_source_status:
            strict_profile_mismatches.append(
                {
                    "field": "rule_source_status",
                    "expected": expected_rule_source_status,
                    "actual": rule_source_status,
                }
            )

    replay_status = report.get("status") if isinstance(report.get("status"), str) else "error"
    strict_report = dict(report)
    if (
        isinstance(expected_selected_fixture_ids, list)
        and "selected_fixture_ids" not in strict_report
    ):
        strict_report["selected_fixture_ids"] = actual_selected_fixture_ids
    strict_report["replay_status"] = replay_status
    strict_report["status"] = "error" if strict_profile_mismatches else "ok"
    strict_report["strict_profile"] = strict_profile
    strict_report["strict_profile_mismatches"] = strict_profile_mismatches
    return strict_report


def _discover_program_pack_program(pack_root: Path) -> Path:
    program_paths = sorted(
        path for path in pack_root.iterdir() if path.is_file() and path.suffix.lower() == ".erz"
    )
    if not program_paths:
        raise ValueError("program pack directory must contain one .erz program file")
    if len(program_paths) > 1:
        raise ValueError("program pack directory must contain exactly one .erz program file")
    return program_paths[0]


def _discover_program_pack_baseline(pack_root: Path) -> Path:
    baseline_paths = sorted(
        path
        for path in pack_root.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".json"
        and (path.name == "baseline.json" or path.name.endswith(".baseline.json"))
    )
    if not baseline_paths:
        raise ValueError(
            "program pack directory must contain one baseline JSON file named baseline.json or *.baseline.json"
        )
    if len(baseline_paths) > 1:
        raise ValueError(
            "program pack directory must contain exactly one baseline JSON file named baseline.json or *.baseline.json"
        )
    return baseline_paths[0]


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
    include_rule_counts: bool = False,
    include_action_kind_counts: bool = False,
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
    rule_counts: dict[str, int] = {}
    action_kind_counts: dict[str, int] = {}

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
        if include_rule_counts and isinstance(trace, list):
            for step in trace:
                if not isinstance(step, dict):
                    continue
                rule_id = step.get("rule_id")
                if isinstance(rule_id, str):
                    rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1
        if include_action_kind_counts and isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                action_kind = action.get("kind")
                if isinstance(action_kind, str):
                    action_kind_counts[action_kind] = action_kind_counts.get(action_kind, 0) + 1
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
    if include_rule_counts:
        summary["rule_counts"] = {
            rule_id: rule_counts[rule_id] for rule_id in sorted(rule_counts)
        }
    if include_action_kind_counts:
        summary["action_kind_counts"] = {
            action_kind: action_kind_counts[action_kind]
            for action_kind in sorted(action_kind_counts)
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


def _filter_batch_artifact_paths(
    artifact_paths: list[str],
    *,
    include_glob: str | None,
    exclude_glob: str | None,
) -> list[str]:
    filtered_paths = list(artifact_paths)

    if include_glob is not None:
        filtered_paths = [
            artifact_path
            for artifact_path in filtered_paths
            if fnmatch.fnmatchcase(artifact_path, include_glob)
        ]

    if exclude_glob is not None:
        filtered_paths = [
            artifact_path
            for artifact_path in filtered_paths
            if not fnmatch.fnmatchcase(artifact_path, exclude_glob)
        ]

    return filtered_paths


def _write_batch_output_artifacts(
    *,
    output_dir: str,
    envelope: dict[str, object],
    errors_only: bool,
    include_manifest: bool,
    layout: str,
    run_id: str | None,
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
    if run_id is not None:
        summary_artifact["run"] = {"id": run_id}
    summary_artifact["event_artifacts"] = event_artifacts
    if include_manifest:
        summary_artifact["artifact_sha256"] = artifact_sha256
    summary_artifact["summary"] = summary_payload

    (output_root / "summary.json").write_text(
        f"{json.dumps(summary_artifact, separators=(',', ':'), ensure_ascii=False)}\n",
        encoding="utf-8",
    )


def _resolve_batch_output_verify_strict_profile(
    *,
    enabled: bool,
    profile: str | None,
    expected_mode: str | None,
    expected_layout: str | None,
    expected_run_id_pattern: str | None,
    expected_event_count: int | None,
    expected_verified_count: int | None,
    expected_checked_count: int | None,
    expected_missing_count: int | None,
    expected_mismatched_count: int | None,
    expected_manifest_missing_count: int | None,
    expected_invalid_hashes_count: int | None,
    expected_unexpected_manifest_count: int | None,
    expected_status: str | None,
    expected_strict_mismatches_count: int | None,
    expected_event_artifact_count: int | None,
    expected_manifest_entry_count: int | None,
    expected_selected_artifact_count: int | None,
    expected_manifest_selected_entry_count: int | None,
    require_run_id: bool,
) -> dict[str, object] | None:
    if not enabled:
        return None

    preset_profiles: dict[str, dict[str, str]] = {
        "default": {
            "expected_mode": "all",
            "expected_layout": "flat",
        },
        "triage-by-status": {
            "expected_mode": "errors-only",
            "expected_layout": "by-status",
        },
    }

    strict_profile: dict[str, object] = {}
    if profile is not None:
        strict_profile.update(preset_profiles[profile])

    strict_profile["expected_mode"] = expected_mode or strict_profile.get("expected_mode", "all")

    if expected_layout is not None:
        strict_profile["expected_layout"] = expected_layout

    if expected_run_id_pattern is not None:
        try:
            re.compile(expected_run_id_pattern)
        except re.error as exc:
            raise ValueError(
                f"--batch-output-verify-expected-run-id-pattern must be a valid regex: {exc}"
            ) from exc

        strict_profile["expected_run_id_pattern"] = expected_run_id_pattern

    if expected_event_count is not None:
        strict_profile["expected_event_count"] = expected_event_count

    if expected_verified_count is not None:
        strict_profile["expected_verified_count"] = expected_verified_count

    if expected_checked_count is not None:
        strict_profile["expected_checked_count"] = expected_checked_count

    if expected_missing_count is not None:
        strict_profile["expected_missing_count"] = expected_missing_count

    if expected_mismatched_count is not None:
        strict_profile["expected_mismatched_count"] = expected_mismatched_count

    if expected_manifest_missing_count is not None:
        strict_profile["expected_manifest_missing_count"] = expected_manifest_missing_count

    if expected_invalid_hashes_count is not None:
        strict_profile["expected_invalid_hashes_count"] = expected_invalid_hashes_count

    if expected_unexpected_manifest_count is not None:
        strict_profile["expected_unexpected_manifest_count"] = expected_unexpected_manifest_count

    if expected_status is not None:
        strict_profile["expected_status"] = expected_status

    if expected_strict_mismatches_count is not None:
        strict_profile["expected_strict_mismatches_count"] = expected_strict_mismatches_count

    if expected_event_artifact_count is not None:
        strict_profile["expected_event_artifact_count"] = expected_event_artifact_count

    if expected_manifest_entry_count is not None:
        strict_profile["expected_manifest_entry_count"] = expected_manifest_entry_count

    if expected_selected_artifact_count is not None:
        strict_profile["expected_selected_artifact_count"] = expected_selected_artifact_count

    if expected_manifest_selected_entry_count is not None:
        strict_profile["expected_manifest_selected_entry_count"] = expected_manifest_selected_entry_count

    if require_run_id:
        strict_profile["require_run_id"] = True

    return strict_profile


def _resolve_batch_output_compare_strict_profile(
    *,
    enabled: bool,
    profile: str | None,
    expected_status: str | None,
    expected_compared_count: int | None,
    expected_matched_count: int | None,
    expected_changed_count: int | None,
    expected_baseline_only_count: int | None,
    expected_candidate_only_count: int | None,
    expected_missing_baseline_count: int | None,
    expected_missing_candidate_count: int | None,
    expected_metadata_mismatches_count: int | None,
    expected_selected_baseline_count: int | None,
    expected_selected_candidate_count: int | None,
) -> dict[str, object] | None:
    if not enabled:
        return None

    preset_profiles: dict[str, dict[str, object]] = {
        "clean": {
            "expected_status": "ok",
            "expected_changed_count": 0,
            "expected_baseline_only_count": 0,
            "expected_candidate_only_count": 0,
            "expected_missing_baseline_count": 0,
            "expected_missing_candidate_count": 0,
            "expected_metadata_mismatches_count": 0,
        },
        "metadata-only": {
            "expected_status": "error",
            "expected_changed_count": 0,
            "expected_baseline_only_count": 0,
            "expected_candidate_only_count": 0,
            "expected_missing_baseline_count": 0,
            "expected_missing_candidate_count": 0,
        },
        "expected-asymmetric-drift": {
            "expected_status": "error",
            "expected_changed_count": 0,
        },
    }

    strict_profile: dict[str, object] = {}
    if profile is not None:
        strict_profile.update(preset_profiles[profile])

    if expected_status is not None:
        strict_profile["expected_status"] = expected_status
    if expected_compared_count is not None:
        strict_profile["expected_compared_count"] = expected_compared_count
    if expected_matched_count is not None:
        strict_profile["expected_matched_count"] = expected_matched_count
    if expected_changed_count is not None:
        strict_profile["expected_changed_count"] = expected_changed_count
    if expected_baseline_only_count is not None:
        strict_profile["expected_baseline_only_count"] = expected_baseline_only_count
    if expected_candidate_only_count is not None:
        strict_profile["expected_candidate_only_count"] = expected_candidate_only_count
    if expected_missing_baseline_count is not None:
        strict_profile["expected_missing_baseline_count"] = expected_missing_baseline_count
    if expected_missing_candidate_count is not None:
        strict_profile["expected_missing_candidate_count"] = expected_missing_candidate_count
    if expected_metadata_mismatches_count is not None:
        strict_profile["expected_metadata_mismatches_count"] = expected_metadata_mismatches_count
    if expected_selected_baseline_count is not None:
        strict_profile["expected_selected_baseline_count"] = expected_selected_baseline_count
    if expected_selected_candidate_count is not None:
        strict_profile["expected_selected_candidate_count"] = expected_selected_candidate_count

    return strict_profile


def _batch_output_dir_has_manifest(output_dir: str | None) -> bool:
    if output_dir is None:
        return False

    summary_path = Path(output_dir) / "summary.json"
    if not summary_path.exists() or not summary_path.is_file():
        return False

    try:
        summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return isinstance(summary_payload, dict) and "artifact_sha256" in summary_payload


def _verify_batch_output_artifacts(
    output_dir: str,
    *,
    strict_profile: dict[str, object] | None = None,
    include_glob: str | None = None,
    exclude_glob: str | None = None,
) -> dict[str, object]:
    output_root = Path(output_dir)
    if not output_root.exists() or not output_root.is_dir():
        raise ValueError("--batch-output-verify must point to an existing directory")

    summary_path = output_root / "summary.json"
    if not summary_path.exists() or not summary_path.is_file():
        raise ValueError("--batch-output-verify directory must contain summary.json")

    try:
        summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"--batch-output-verify summary.json must contain valid JSON: {exc}") from exc

    if not isinstance(summary_payload, dict):
        raise ValueError("--batch-output-verify summary.json must be a JSON object")

    event_artifacts = summary_payload.get("event_artifacts")
    if not isinstance(event_artifacts, list) or not all(
        isinstance(item, str) and item for item in event_artifacts
    ):
        raise ValueError(
            "--batch-output-verify summary.json must contain non-empty string event_artifacts list"
        )

    selected_artifacts = _filter_batch_artifact_paths(
        event_artifacts,
        include_glob=include_glob,
        exclude_glob=exclude_glob,
    )
    if not selected_artifacts:
        include_label = include_glob if include_glob is not None else "<none>"
        exclude_label = exclude_glob if exclude_glob is not None else "<none>"
        raise ValueError(
            "--batch-output-verify selectors matched no artifacts "
            f"(include={include_label!r}, exclude={exclude_label!r})"
        )

    manifest_payload = summary_payload.get("artifact_sha256")
    if not isinstance(manifest_payload, dict):
        raise ValueError(
            "--batch-output-verify summary.json must contain artifact_sha256 object "
            "(run eval with --batch-output-manifest)"
        )

    missing_artifacts: list[str] = []
    missing_manifest_entries: list[str] = []
    invalid_manifest_hashes: list[dict[str, str]] = []
    mismatched_artifacts: list[dict[str, str]] = []
    verified = 0

    for artifact_relative_path in selected_artifacts:
        expected_hash = manifest_payload.get(artifact_relative_path)
        if not isinstance(expected_hash, str):
            missing_manifest_entries.append(artifact_relative_path)
            continue
        if not _is_sha256_hex(expected_hash):
            invalid_manifest_hashes.append(
                {
                    "artifact": artifact_relative_path,
                    "expected": expected_hash,
                }
            )
            continue

        if not _is_safe_batch_artifact_relative_path(artifact_relative_path):
            missing_artifacts.append(artifact_relative_path)
            continue

        artifact_path = output_root / artifact_relative_path
        if not artifact_path.exists() or not artifact_path.is_file():
            missing_artifacts.append(artifact_relative_path)
            continue

        actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            mismatched_artifacts.append(
                {
                    "artifact": artifact_relative_path,
                    "expected": expected_hash,
                    "actual": actual_hash,
                }
            )
            continue

        verified += 1

    checked_count = len(selected_artifacts)
    selected_manifest_entry_count = sum(
        1 for artifact_relative_path in selected_artifacts if artifact_relative_path in manifest_payload
    )

    unexpected_manifest_entries = sorted(
        key for key in manifest_payload.keys() if isinstance(key, str) and key not in event_artifacts
    )

    base_status = "ok"
    if (
        missing_artifacts
        or missing_manifest_entries
        or invalid_manifest_hashes
        or mismatched_artifacts
        or unexpected_manifest_entries
    ):
        base_status = "error"

    strict_profile_mismatches: list[dict[str, object]] = []
    if strict_profile is not None:
        expected_mode = strict_profile["expected_mode"]
        actual_mode = summary_payload.get("mode")
        if actual_mode != expected_mode:
            strict_profile_mismatches.append(
                {
                    "field": "mode",
                    "expected": expected_mode,
                    "actual": str(actual_mode),
                }
            )

        expected_layout = strict_profile.get("expected_layout")
        if expected_layout is not None:
            if "layout" not in summary_payload:
                actual_layout = "flat"
            else:
                layout_payload = summary_payload.get("layout")
                actual_layout = layout_payload if isinstance(layout_payload, str) else "<invalid>"

            if actual_layout != expected_layout:
                strict_profile_mismatches.append(
                    {
                        "field": "layout",
                        "expected": expected_layout,
                        "actual": actual_layout,
                    }
                )

        expected_event_count = strict_profile.get("expected_event_count")
        if isinstance(expected_event_count, int) and not isinstance(expected_event_count, bool):
            summary_node = summary_payload.get("summary")
            if isinstance(summary_node, dict):
                raw_event_count = summary_node.get("event_count")
                if isinstance(raw_event_count, int) and not isinstance(raw_event_count, bool):
                    actual_event_count: int | str = raw_event_count
                elif "event_count" in summary_node:
                    actual_event_count = "<invalid>"
                else:
                    actual_event_count = "<missing>"
            else:
                actual_event_count = "<missing>"

            if actual_event_count != expected_event_count:
                strict_profile_mismatches.append(
                    {
                        "field": "summary.event_count",
                        "expected": expected_event_count,
                        "actual": actual_event_count,
                    }
                )

        expected_event_artifact_count = strict_profile.get("expected_event_artifact_count")
        if isinstance(expected_event_artifact_count, int) and not isinstance(
            expected_event_artifact_count, bool
        ):
            actual_event_artifact_count = len(event_artifacts)
            if actual_event_artifact_count != expected_event_artifact_count:
                strict_profile_mismatches.append(
                    {
                        "field": "event_artifacts.count",
                        "expected": expected_event_artifact_count,
                        "actual": actual_event_artifact_count,
                    }
                )

        expected_manifest_entry_count = strict_profile.get("expected_manifest_entry_count")
        if isinstance(expected_manifest_entry_count, int) and not isinstance(
            expected_manifest_entry_count, bool
        ):
            actual_manifest_entry_count = len(manifest_payload)
            if actual_manifest_entry_count != expected_manifest_entry_count:
                strict_profile_mismatches.append(
                    {
                        "field": "artifact_sha256.count",
                        "expected": expected_manifest_entry_count,
                        "actual": actual_manifest_entry_count,
                    }
                )

        expected_selected_artifact_count = strict_profile.get("expected_selected_artifact_count")
        if isinstance(expected_selected_artifact_count, int) and not isinstance(
            expected_selected_artifact_count, bool
        ):
            if checked_count != expected_selected_artifact_count:
                strict_profile_mismatches.append(
                    {
                        "field": "selected_artifacts.count",
                        "expected": expected_selected_artifact_count,
                        "actual": checked_count,
                    }
                )

        expected_manifest_selected_entry_count = strict_profile.get(
            "expected_manifest_selected_entry_count"
        )
        if isinstance(expected_manifest_selected_entry_count, int) and not isinstance(
            expected_manifest_selected_entry_count, bool
        ):
            if selected_manifest_entry_count != expected_manifest_selected_entry_count:
                strict_profile_mismatches.append(
                    {
                        "field": "selected_manifest_entries.count",
                        "expected": expected_manifest_selected_entry_count,
                        "actual": selected_manifest_entry_count,
                    }
                )

        expected_verified_count = strict_profile.get("expected_verified_count")
        if isinstance(expected_verified_count, int) and not isinstance(expected_verified_count, bool):
            if verified != expected_verified_count:
                strict_profile_mismatches.append(
                    {
                        "field": "verified",
                        "expected": expected_verified_count,
                        "actual": verified,
                    }
                )

        expected_checked_count = strict_profile.get("expected_checked_count")
        if isinstance(expected_checked_count, int) and not isinstance(expected_checked_count, bool):
            if checked_count != expected_checked_count:
                strict_profile_mismatches.append(
                    {
                        "field": "checked",
                        "expected": expected_checked_count,
                        "actual": checked_count,
                    }
                )

        expected_missing_count = strict_profile.get("expected_missing_count")
        if isinstance(expected_missing_count, int) and not isinstance(expected_missing_count, bool):
            missing_count = len(missing_artifacts)
            if missing_count != expected_missing_count:
                strict_profile_mismatches.append(
                    {
                        "field": "missing_artifacts.count",
                        "expected": expected_missing_count,
                        "actual": missing_count,
                    }
                )

        expected_mismatched_count = strict_profile.get("expected_mismatched_count")
        if isinstance(expected_mismatched_count, int) and not isinstance(expected_mismatched_count, bool):
            mismatched_count = len(mismatched_artifacts)
            if mismatched_count != expected_mismatched_count:
                strict_profile_mismatches.append(
                    {
                        "field": "mismatched_artifacts.count",
                        "expected": expected_mismatched_count,
                        "actual": mismatched_count,
                    }
                )

        expected_manifest_missing_count = strict_profile.get("expected_manifest_missing_count")
        if isinstance(expected_manifest_missing_count, int) and not isinstance(
            expected_manifest_missing_count, bool
        ):
            manifest_missing_count = len(missing_manifest_entries)
            if manifest_missing_count != expected_manifest_missing_count:
                strict_profile_mismatches.append(
                    {
                        "field": "missing_manifest_entries.count",
                        "expected": expected_manifest_missing_count,
                        "actual": manifest_missing_count,
                    }
                )

        expected_invalid_hashes_count = strict_profile.get("expected_invalid_hashes_count")
        if isinstance(expected_invalid_hashes_count, int) and not isinstance(
            expected_invalid_hashes_count, bool
        ):
            invalid_hashes_count = len(invalid_manifest_hashes)
            if invalid_hashes_count != expected_invalid_hashes_count:
                strict_profile_mismatches.append(
                    {
                        "field": "invalid_manifest_hashes.count",
                        "expected": expected_invalid_hashes_count,
                        "actual": invalid_hashes_count,
                    }
                )

        expected_unexpected_manifest_count = strict_profile.get(
            "expected_unexpected_manifest_count"
        )
        if isinstance(expected_unexpected_manifest_count, int) and not isinstance(
            expected_unexpected_manifest_count, bool
        ):
            unexpected_manifest_count = len(unexpected_manifest_entries)
            if unexpected_manifest_count != expected_unexpected_manifest_count:
                strict_profile_mismatches.append(
                    {
                        "field": "unexpected_manifest_entries.count",
                        "expected": expected_unexpected_manifest_count,
                        "actual": unexpected_manifest_count,
                    }
                )

        expected_status = strict_profile.get("expected_status")
        if isinstance(expected_status, str):
            if base_status != expected_status:
                strict_profile_mismatches.append(
                    {
                        "field": "status",
                        "expected": expected_status,
                        "actual": base_status,
                    }
                )

        expected_strict_mismatches_count = strict_profile.get(
            "expected_strict_mismatches_count"
        )
        if isinstance(expected_strict_mismatches_count, int) and not isinstance(
            expected_strict_mismatches_count, bool
        ):
            strict_mismatch_count = len(strict_profile_mismatches)
            if strict_mismatch_count != expected_strict_mismatches_count:
                strict_profile_mismatches.append(
                    {
                        "field": "strict_profile_mismatches.count",
                        "expected": expected_strict_mismatches_count,
                        "actual": strict_mismatch_count,
                    }
                )

        run_payload = summary_payload.get("run")
        if not isinstance(run_payload, dict):
            actual_run_id = "<missing>"
        else:
            run_id_payload = run_payload.get("id")
            actual_run_id = run_id_payload if isinstance(run_id_payload, str) else "<missing>"

        require_run_id = bool(strict_profile.get("require_run_id"))
        if require_run_id and actual_run_id == "<missing>":
            strict_profile_mismatches.append(
                {
                    "field": "run.id",
                    "expected": "present",
                    "actual": actual_run_id,
                }
            )

        expected_run_id_pattern = strict_profile.get("expected_run_id_pattern")
        if isinstance(expected_run_id_pattern, str):
            if actual_run_id == "<missing>":
                if not require_run_id:
                    strict_profile_mismatches.append(
                        {
                            "field": "run.id",
                            "expected": expected_run_id_pattern,
                            "actual": actual_run_id,
                        }
                    )
            elif re.fullmatch(expected_run_id_pattern, actual_run_id) is None:
                strict_profile_mismatches.append(
                    {
                        "field": "run.id",
                        "expected": expected_run_id_pattern,
                        "actual": actual_run_id,
                    }
                )

    status = base_status
    if strict_profile_mismatches:
        status = "error"

    verify_result: dict[str, object] = {
        "status": status,
        "checked": checked_count,
        "verified": verified,
        "missing_artifacts": missing_artifacts,
        "missing_manifest_entries": missing_manifest_entries,
        "invalid_manifest_hashes": invalid_manifest_hashes,
        "mismatched_artifacts": mismatched_artifacts,
        "unexpected_manifest_entries": unexpected_manifest_entries,
        "selected_artifacts_count": checked_count,
        "selected_manifest_entries_count": selected_manifest_entry_count,
    }

    if strict_profile is not None:
        verify_result["strict_profile"] = strict_profile
        verify_result["strict_profile_mismatches"] = strict_profile_mismatches

    return verify_result


def _render_batch_output_verify_summary(
    verify_summary: dict[str, object], *, summary: bool
) -> str:
    if summary:
        status = verify_summary.get("status")
        checked = verify_summary.get("checked")
        verified = verify_summary.get("verified")

        missing_artifacts = verify_summary.get("missing_artifacts")
        missing_manifest_entries = verify_summary.get("missing_manifest_entries")
        invalid_manifest_hashes = verify_summary.get("invalid_manifest_hashes")
        mismatched_artifacts = verify_summary.get("mismatched_artifacts")
        unexpected_manifest_entries = verify_summary.get("unexpected_manifest_entries")
        selected_artifacts_count = verify_summary.get("selected_artifacts_count")
        selected_manifest_entries_count = verify_summary.get("selected_manifest_entries_count")
        strict_profile_mismatches = verify_summary.get("strict_profile_mismatches")

        rendered = (
            f"status={status} checked={checked} verified={verified} "
            f"missing={len(missing_artifacts) if isinstance(missing_artifacts, list) else 0} "
            f"manifest_missing={len(missing_manifest_entries) if isinstance(missing_manifest_entries, list) else 0} "
            f"invalid_hashes={len(invalid_manifest_hashes) if isinstance(invalid_manifest_hashes, list) else 0} "
            f"mismatched={len(mismatched_artifacts) if isinstance(mismatched_artifacts, list) else 0} "
            "unexpected_manifest="
            f"{len(unexpected_manifest_entries) if isinstance(unexpected_manifest_entries, list) else 0} "
            f"selected={selected_artifacts_count if isinstance(selected_artifacts_count, int) and not isinstance(selected_artifacts_count, bool) else 0} "
            f"selected_manifest={selected_manifest_entries_count if isinstance(selected_manifest_entries_count, int) and not isinstance(selected_manifest_entries_count, bool) else 0}"
        )

        if isinstance(strict_profile_mismatches, list):
            rendered = f"{rendered} strict_mismatches={len(strict_profile_mismatches)}"

        return rendered

    return json.dumps(verify_summary, separators=(",", ":"), ensure_ascii=False)


def _compare_batch_output_artifacts(
    candidate_dir: str,
    *,
    against_dir: str,
    include_glob: str | None = None,
    exclude_glob: str | None = None,
    strict_profile: dict[str, object] | None = None,
    candidate_flag: str = "--batch-output-compare",
    against_flag: str = "--batch-output-compare-against",
    selector_flag: str = "--batch-output-compare selectors",
) -> dict[str, object]:
    candidate_root = Path(candidate_dir)
    if not candidate_root.exists() or not candidate_root.is_dir():
        raise ValueError(f"{candidate_flag} must point to an existing directory")

    baseline_root = Path(against_dir)
    if not baseline_root.exists() or not baseline_root.is_dir():
        raise ValueError(f"{against_flag} must point to an existing directory")

    candidate_summary_path = candidate_root / "summary.json"
    if not candidate_summary_path.exists() or not candidate_summary_path.is_file():
        raise ValueError(f"{candidate_flag} directory must contain summary.json")

    baseline_summary_path = baseline_root / "summary.json"
    if not baseline_summary_path.exists() or not baseline_summary_path.is_file():
        raise ValueError(f"{against_flag} directory must contain summary.json")

    try:
        candidate_summary_payload = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{candidate_flag} summary.json must contain valid JSON: {exc}"
        ) from exc

    try:
        baseline_summary_payload = json.loads(baseline_summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{against_flag} summary.json must contain valid JSON: {exc}"
        ) from exc

    if not isinstance(candidate_summary_payload, dict):
        raise ValueError(f"{candidate_flag} summary.json must be a JSON object")
    if not isinstance(baseline_summary_payload, dict):
        raise ValueError(f"{against_flag} summary.json must be a JSON object")

    candidate_event_artifacts = candidate_summary_payload.get("event_artifacts")
    if not isinstance(candidate_event_artifacts, list) or not all(
        isinstance(item, str) and item for item in candidate_event_artifacts
    ):
        raise ValueError(
            f"{candidate_flag} summary.json must contain string event_artifacts list"
        )

    baseline_event_artifacts = baseline_summary_payload.get("event_artifacts")
    if not isinstance(baseline_event_artifacts, list) or not all(
        isinstance(item, str) and item for item in baseline_event_artifacts
    ):
        raise ValueError(
            f"{against_flag} summary.json must contain string event_artifacts list"
        )

    selected_candidate_artifacts = _filter_batch_artifact_paths(
        candidate_event_artifacts,
        include_glob=include_glob,
        exclude_glob=exclude_glob,
    )
    selected_baseline_artifacts = _filter_batch_artifact_paths(
        baseline_event_artifacts,
        include_glob=include_glob,
        exclude_glob=exclude_glob,
    )
    if (
        (include_glob is not None or exclude_glob is not None)
        and not selected_candidate_artifacts
        and not selected_baseline_artifacts
    ):
        include_label = include_glob if include_glob is not None else "<none>"
        exclude_label = exclude_glob if exclude_glob is not None else "<none>"
        raise ValueError(
            f"{selector_flag} matched no artifacts "
            f"(include={include_label!r}, exclude={exclude_label!r})"
        )

    def collect_artifact_hashes(
        output_root: Path,
        artifact_paths: list[str],
    ) -> tuple[dict[str, str], list[str]]:
        artifact_hashes: dict[str, str] = {}
        missing_artifacts: list[str] = []
        for artifact_relative_path in sorted(set(artifact_paths)):
            if not _is_safe_batch_artifact_relative_path(artifact_relative_path):
                missing_artifacts.append(artifact_relative_path)
                continue

            artifact_path = output_root / artifact_relative_path
            if not artifact_path.exists() or not artifact_path.is_file():
                missing_artifacts.append(artifact_relative_path)
                continue

            artifact_hashes[artifact_relative_path] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

        return artifact_hashes, missing_artifacts

    baseline_hashes, missing_baseline_artifacts = collect_artifact_hashes(
        baseline_root,
        selected_baseline_artifacts,
    )
    candidate_hashes, missing_candidate_artifacts = collect_artifact_hashes(
        candidate_root,
        selected_candidate_artifacts,
    )

    baseline_set = set(selected_baseline_artifacts)
    candidate_set = set(selected_candidate_artifacts)
    shared_artifacts = sorted(baseline_set & candidate_set)
    baseline_only_artifacts = sorted(baseline_set - candidate_set)
    candidate_only_artifacts = sorted(candidate_set - baseline_set)

    changed_artifacts: list[dict[str, str]] = []
    compared = 0
    matched = 0
    for artifact_relative_path in shared_artifacts:
        baseline_hash = baseline_hashes.get(artifact_relative_path)
        candidate_hash = candidate_hashes.get(artifact_relative_path)
        if baseline_hash is None:
            missing_baseline_artifacts.append(artifact_relative_path)
            continue
        if candidate_hash is None:
            missing_candidate_artifacts.append(artifact_relative_path)
            continue

        compared += 1
        if baseline_hash == candidate_hash:
            matched += 1
            continue

        changed_artifacts.append(
            {
                "artifact": artifact_relative_path,
                "baseline": baseline_hash,
                "candidate": candidate_hash,
            }
        )

    missing_baseline_artifacts = sorted(set(missing_baseline_artifacts))
    missing_candidate_artifacts = sorted(set(missing_candidate_artifacts))

    def summary_metric(summary_payload: dict[str, object], field: str) -> int | str:
        summary_node = summary_payload.get("summary")
        if not isinstance(summary_node, dict):
            return "<missing>"
        if field not in summary_node:
            return "<missing>"

        value = summary_node[field]
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return "<invalid>"

    def summary_metric_fields(summary_payload: dict[str, object]) -> set[str]:
        summary_node = summary_payload.get("summary")
        if not isinstance(summary_node, dict):
            return set()
        return {field for field in summary_node if isinstance(field, str)}

    def layout_value(summary_payload: dict[str, object]) -> str:
        if "layout" not in summary_payload:
            return "flat"

        layout_payload = summary_payload.get("layout")
        if isinstance(layout_payload, str):
            return layout_payload
        return "<invalid>"

    def mode_value(summary_payload: dict[str, object]) -> str:
        if "mode" not in summary_payload:
            return "<missing>"

        mode_payload = summary_payload.get("mode")
        if isinstance(mode_payload, str):
            return mode_payload
        return "<invalid>"

    def artifact_sha256_value(
        summary_payload: dict[str, object],
        *,
        selected_artifacts: list[str],
    ) -> dict[str, str] | str:
        if "artifact_sha256" not in summary_payload:
            return "<missing>"

        mapping_payload = summary_payload.get("artifact_sha256")
        if not isinstance(mapping_payload, dict):
            return "<invalid>"

        selected_artifact_set = set(selected_artifacts)
        normalized_mapping: dict[str, str] = {}
        for artifact_relative_path, artifact_hash in mapping_payload.items():
            if (
                not isinstance(artifact_relative_path, str)
                or not artifact_relative_path
                or not isinstance(artifact_hash, str)
            ):
                return "<invalid>"
            if artifact_relative_path in selected_artifact_set:
                normalized_mapping[artifact_relative_path] = artifact_hash

        return {
            artifact_relative_path: normalized_mapping[artifact_relative_path]
            for artifact_relative_path in sorted(normalized_mapping)
        }

    def top_level_metadata_value(summary_payload: dict[str, object], field: str) -> object:
        if field not in summary_payload:
            return "<missing>"
        return summary_payload[field]

    metadata_mismatches: list[dict[str, object]] = []
    if selected_baseline_artifacts != selected_candidate_artifacts:
        metadata_mismatches.append(
            {
                "field": "event_artifacts",
                "baseline": selected_baseline_artifacts,
                "candidate": selected_candidate_artifacts,
            }
        )

    metadata_fields: list[tuple[str, object, object]] = [
        ("mode", mode_value(baseline_summary_payload), mode_value(candidate_summary_payload)),
        ("layout", layout_value(baseline_summary_payload), layout_value(candidate_summary_payload)),
        (
            "artifact_sha256",
            artifact_sha256_value(
                baseline_summary_payload,
                selected_artifacts=selected_baseline_artifacts,
            ),
            artifact_sha256_value(
                candidate_summary_payload,
                selected_artifacts=selected_candidate_artifacts,
            ),
        ),
    ]

    summary_fields = sorted(
        summary_metric_fields(baseline_summary_payload) | summary_metric_fields(candidate_summary_payload)
    )
    for field in summary_fields:
        metadata_fields.append(
            (
                f"summary.{field}",
                summary_metric(baseline_summary_payload, field),
                summary_metric(candidate_summary_payload, field),
            )
        )

    ignored_top_level_metadata_fields = {
        "artifact_sha256",
        "event_artifacts",
        "layout",
        "mode",
        "run",
        "summary",
    }
    top_level_fields = sorted(
        (set(baseline_summary_payload) | set(candidate_summary_payload))
        - ignored_top_level_metadata_fields
    )
    for field in top_level_fields:
        metadata_fields.append(
            (
                field,
                top_level_metadata_value(baseline_summary_payload, field),
                top_level_metadata_value(candidate_summary_payload, field),
            )
        )

    for field, baseline_value, candidate_value in metadata_fields:
        if baseline_value != candidate_value:
            metadata_mismatches.append(
                {
                    "field": field,
                    "baseline": baseline_value,
                    "candidate": candidate_value,
                }
            )

    compare_status = "ok"
    if (
        baseline_only_artifacts
        or candidate_only_artifacts
        or missing_baseline_artifacts
        or missing_candidate_artifacts
        or changed_artifacts
        or metadata_mismatches
    ):
        compare_status = "error"

    status = compare_status
    strict_profile_mismatches: list[dict[str, object]] = []
    if strict_profile is not None:
        expected_status = strict_profile.get("expected_status")
        if isinstance(expected_status, str) and compare_status != expected_status:
            strict_profile_mismatches.append(
                {
                    "field": "status",
                    "expected": expected_status,
                    "actual": compare_status,
                }
            )

        expected_compared_count = strict_profile.get("expected_compared_count")
        if isinstance(expected_compared_count, int) and not isinstance(expected_compared_count, bool):
            if compared != expected_compared_count:
                strict_profile_mismatches.append(
                    {
                        "field": "compared",
                        "expected": expected_compared_count,
                        "actual": compared,
                    }
                )

        expected_matched_count = strict_profile.get("expected_matched_count")
        if isinstance(expected_matched_count, int) and not isinstance(expected_matched_count, bool):
            if matched != expected_matched_count:
                strict_profile_mismatches.append(
                    {
                        "field": "matched",
                        "expected": expected_matched_count,
                        "actual": matched,
                    }
                )

        changed_count = len(changed_artifacts)
        expected_changed_count = strict_profile.get("expected_changed_count")
        if isinstance(expected_changed_count, int) and not isinstance(expected_changed_count, bool):
            if changed_count != expected_changed_count:
                strict_profile_mismatches.append(
                    {
                        "field": "changed_artifacts.count",
                        "expected": expected_changed_count,
                        "actual": changed_count,
                    }
                )

        baseline_only_count = len(baseline_only_artifacts)
        expected_baseline_only_count = strict_profile.get("expected_baseline_only_count")
        if isinstance(expected_baseline_only_count, int) and not isinstance(
            expected_baseline_only_count, bool
        ):
            if baseline_only_count != expected_baseline_only_count:
                strict_profile_mismatches.append(
                    {
                        "field": "baseline_only_artifacts.count",
                        "expected": expected_baseline_only_count,
                        "actual": baseline_only_count,
                    }
                )

        candidate_only_count = len(candidate_only_artifacts)
        expected_candidate_only_count = strict_profile.get("expected_candidate_only_count")
        if isinstance(expected_candidate_only_count, int) and not isinstance(
            expected_candidate_only_count, bool
        ):
            if candidate_only_count != expected_candidate_only_count:
                strict_profile_mismatches.append(
                    {
                        "field": "candidate_only_artifacts.count",
                        "expected": expected_candidate_only_count,
                        "actual": candidate_only_count,
                    }
                )

        missing_baseline_count = len(missing_baseline_artifacts)
        expected_missing_baseline_count = strict_profile.get("expected_missing_baseline_count")
        if isinstance(expected_missing_baseline_count, int) and not isinstance(
            expected_missing_baseline_count, bool
        ):
            if missing_baseline_count != expected_missing_baseline_count:
                strict_profile_mismatches.append(
                    {
                        "field": "missing_baseline_artifacts.count",
                        "expected": expected_missing_baseline_count,
                        "actual": missing_baseline_count,
                    }
                )

        missing_candidate_count = len(missing_candidate_artifacts)
        expected_missing_candidate_count = strict_profile.get("expected_missing_candidate_count")
        if isinstance(expected_missing_candidate_count, int) and not isinstance(
            expected_missing_candidate_count, bool
        ):
            if missing_candidate_count != expected_missing_candidate_count:
                strict_profile_mismatches.append(
                    {
                        "field": "missing_candidate_artifacts.count",
                        "expected": expected_missing_candidate_count,
                        "actual": missing_candidate_count,
                    }
                )

        metadata_mismatch_count = len(metadata_mismatches)
        expected_metadata_mismatches_count = strict_profile.get(
            "expected_metadata_mismatches_count"
        )
        if isinstance(expected_metadata_mismatches_count, int) and not isinstance(
            expected_metadata_mismatches_count, bool
        ):
            if metadata_mismatch_count != expected_metadata_mismatches_count:
                strict_profile_mismatches.append(
                    {
                        "field": "metadata_mismatches.count",
                        "expected": expected_metadata_mismatches_count,
                        "actual": metadata_mismatch_count,
                    }
                )

        selected_baseline_count = len(selected_baseline_artifacts)
        expected_selected_baseline_count = strict_profile.get("expected_selected_baseline_count")
        if isinstance(expected_selected_baseline_count, int) and not isinstance(
            expected_selected_baseline_count, bool
        ):
            if selected_baseline_count != expected_selected_baseline_count:
                strict_profile_mismatches.append(
                    {
                        "field": "selected_baseline_artifacts.count",
                        "expected": expected_selected_baseline_count,
                        "actual": selected_baseline_count,
                    }
                )

        selected_candidate_count = len(selected_candidate_artifacts)
        expected_selected_candidate_count = strict_profile.get("expected_selected_candidate_count")
        if isinstance(expected_selected_candidate_count, int) and not isinstance(
            expected_selected_candidate_count, bool
        ):
            if selected_candidate_count != expected_selected_candidate_count:
                strict_profile_mismatches.append(
                    {
                        "field": "selected_candidate_artifacts.count",
                        "expected": expected_selected_candidate_count,
                        "actual": selected_candidate_count,
                    }
                )

        status = "error" if strict_profile_mismatches else "ok"

    compare_result: dict[str, object] = {
        "status": status,
    }
    if strict_profile is not None:
        compare_result["compare_status"] = compare_status
    compare_result.update(
        {
            "compared": compared,
            "matched": matched,
            "baseline_only_artifacts": baseline_only_artifacts,
            "candidate_only_artifacts": candidate_only_artifacts,
            "missing_baseline_artifacts": missing_baseline_artifacts,
            "missing_candidate_artifacts": missing_candidate_artifacts,
            "changed_artifacts": changed_artifacts,
            "metadata_mismatches": metadata_mismatches,
            "selected_baseline_artifacts_count": len(selected_baseline_artifacts),
            "selected_candidate_artifacts_count": len(selected_candidate_artifacts),
        }
    )
    if strict_profile is not None:
        compare_result["strict_profile"] = strict_profile
        compare_result["strict_profile_mismatches"] = strict_profile_mismatches
    return compare_result


def _render_batch_output_compare_summary(
    compare_summary: dict[str, object], *, summary: bool
) -> str:
    if summary:
        status = compare_summary.get("status")
        compare_status = compare_summary.get("compare_status")
        compared = compare_summary.get("compared")
        matched = compare_summary.get("matched")
        baseline_only_artifacts = compare_summary.get("baseline_only_artifacts")
        candidate_only_artifacts = compare_summary.get("candidate_only_artifacts")
        missing_baseline_artifacts = compare_summary.get("missing_baseline_artifacts")
        missing_candidate_artifacts = compare_summary.get("missing_candidate_artifacts")
        changed_artifacts = compare_summary.get("changed_artifacts")
        metadata_mismatches = compare_summary.get("metadata_mismatches")
        selected_baseline_artifacts_count = compare_summary.get("selected_baseline_artifacts_count")
        selected_candidate_artifacts_count = compare_summary.get("selected_candidate_artifacts_count")
        strict_profile_mismatches = compare_summary.get("strict_profile_mismatches")

        rendered = f"status={status} "
        if isinstance(compare_status, str):
            rendered = f"{rendered}compare_status={compare_status} "
        rendered = (
            f"{rendered}compared={compared} matched={matched} "
            f"changed={len(changed_artifacts) if isinstance(changed_artifacts, list) else 0} "
            f"baseline_only={len(baseline_only_artifacts) if isinstance(baseline_only_artifacts, list) else 0} "
            f"candidate_only={len(candidate_only_artifacts) if isinstance(candidate_only_artifacts, list) else 0} "
            f"missing_baseline={len(missing_baseline_artifacts) if isinstance(missing_baseline_artifacts, list) else 0} "
            f"missing_candidate={len(missing_candidate_artifacts) if isinstance(missing_candidate_artifacts, list) else 0} "
            f"metadata_mismatches={len(metadata_mismatches) if isinstance(metadata_mismatches, list) else 0} "
            f"selected_baseline={selected_baseline_artifacts_count if isinstance(selected_baseline_artifacts_count, int) and not isinstance(selected_baseline_artifacts_count, bool) else 0} "
            f"selected_candidate={selected_candidate_artifacts_count if isinstance(selected_candidate_artifacts_count, int) and not isinstance(selected_candidate_artifacts_count, bool) else 0}"
        )
        if isinstance(strict_profile_mismatches, list):
            rendered = f"{rendered} strict_mismatches={len(strict_profile_mismatches)}"
        return rendered

    return json.dumps(compare_summary, separators=(",", ":"), ensure_ascii=False)


def _is_safe_batch_artifact_relative_path(path_value: str) -> bool:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return False

    for part in candidate.parts:
        if part in {"", ".", ".."}:
            return False

    return True


def _is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    allowed = set("0123456789abcdef")
    return all(ch in allowed for ch in value.lower())


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


def _write_batch_output_summary_file(path: str, envelope: dict[str, object]) -> None:
    rendered_envelope = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
    Path(path).write_text(f"{rendered_envelope}\n", encoding="utf-8")


def _render_program_pack_replay_output(envelope: dict[str, object], *, summary: bool) -> str:
    if summary:
        summary_payload = envelope.get("summary") if isinstance(envelope.get("summary"), dict) else {}
        fixture_count = (
            summary_payload.get("fixture_count")
            if isinstance(summary_payload.get("fixture_count"), int)
            else 0
        )
        matched_count = (
            summary_payload.get("matched_count")
            if isinstance(summary_payload.get("matched_count"), int)
            else 0
        )
        mismatch_count = (
            summary_payload.get("mismatch_count")
            if isinstance(summary_payload.get("mismatch_count"), int)
            else 0
        )
        runtime_error_count = (
            summary_payload.get("runtime_error_count")
            if isinstance(summary_payload.get("runtime_error_count"), int)
            else 0
        )
        total_fixture_count = (
            summary_payload.get("total_fixture_count")
            if isinstance(summary_payload.get("total_fixture_count"), int)
            else fixture_count
        )
        fixture_class_counts = (
            summary_payload.get("fixture_class_counts")
            if isinstance(summary_payload.get("fixture_class_counts"), dict)
            else {}
        )
        ok_fixture_count = (
            fixture_class_counts.get("ok")
            if isinstance(fixture_class_counts.get("ok"), int)
            else matched_count
        )
        expectation_mismatch_fixture_count = (
            fixture_class_counts.get("expectation_mismatch")
            if isinstance(fixture_class_counts.get("expectation_mismatch"), int)
            else mismatch_count - runtime_error_count
        )
        runtime_error_fixture_class_count = (
            fixture_class_counts.get("runtime_error")
            if isinstance(fixture_class_counts.get("runtime_error"), int)
            else runtime_error_count
        )
        pack_id = envelope.get("pack_id") if isinstance(envelope.get("pack_id"), str) else "<unknown>"
        rule_source_status = (
            envelope.get("rule_source_status")
            if isinstance(envelope.get("rule_source_status"), str)
            else "unknown"
        )
        status = envelope.get("status") if isinstance(envelope.get("status"), str) else "error"
        replay_status = (
            envelope.get("replay_status")
            if isinstance(envelope.get("replay_status"), str)
            else None
        )
        strict_profile_mismatches = envelope.get("strict_profile_mismatches")
        fixture_scope = (
            f"{fixture_count}/{total_fixture_count}"
            if total_fixture_count != fixture_count
            else str(fixture_count)
        )
        fixture_classes = (
            f"ok:{ok_fixture_count},expectation_mismatch:{expectation_mismatch_fixture_count},"
            f"runtime_error:{runtime_error_fixture_class_count}"
        )
        rendered = f"status={status} "
        if isinstance(replay_status, str):
            rendered = f"{rendered}replay_status={replay_status} "
        rendered = (
            f"{rendered}pack={pack_id} fixtures={fixture_scope} matched={matched_count} "
            f"mismatches={mismatch_count} runtime_errors={runtime_error_count} "
            f"rule_source={rule_source_status} fixture_classes={fixture_classes}"
        )
        if isinstance(strict_profile_mismatches, list):
            rendered = f"{rendered} strict_mismatches={len(strict_profile_mismatches)}"
        return rendered

    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)


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
