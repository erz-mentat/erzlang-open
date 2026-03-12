#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/erz-public-check.XXXXXX")"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cd "$REPO_ROOT"

step() {
  printf "\n[%s] %s\n" "$1" "$2"
}

step "1/7" "CLI smoke: fmt + parse + validate"
python3 -m cli.main validate examples/sample.erz >"$TMP_DIR/validate.out"
grep -qx "valid" "$TMP_DIR/validate.out"

python3 -m cli.main parse examples/sample.erz >"$TMP_DIR/original.json"
python3 -m cli.main fmt examples/sample.erz >"$TMP_DIR/formatted.erz"
python3 -m cli.main validate "$TMP_DIR/formatted.erz" >"$TMP_DIR/formatted.validate.out"
grep -qx "valid" "$TMP_DIR/formatted.validate.out"
python3 -m cli.main parse "$TMP_DIR/formatted.erz" >"$TMP_DIR/formatted.json"
python3 -m cli.main fmt "$TMP_DIR/formatted.erz" >"$TMP_DIR/formatted.twice.erz"

cmp -s "$TMP_DIR/original.json" "$TMP_DIR/formatted.json"
cmp -s "$TMP_DIR/formatted.erz" "$TMP_DIR/formatted.twice.erz"

echo "  ok: parse/validate/fmt roundtrip smoke passed"

step "2/7" "Few-shot parser cases"
python3 scripts/validate_fewshot.py >"$TMP_DIR/fewshot.out"
cat "$TMP_DIR/fewshot.out"

step "3/7" "Runtime eval frozen fixtures"
python3 -m cli.main eval examples/eval/program-paths.erz --input examples/eval/event-path-ok.json >"$TMP_DIR/event-path-ok.actual.json"
cmp -s "$TMP_DIR/event-path-ok.actual.json" examples/eval/event-path-ok.expected.envelope.json
python3 -m cli.main eval examples/eval/program-paths.erz --input examples/eval/event-path-no-action.json --summary >"$TMP_DIR/event-path-no-action.actual.summary.txt"
cmp -s "$TMP_DIR/event-path-no-action.actual.summary.txt" examples/eval/event-path-no-action.expected.summary.txt

python3 -m cli.main eval examples/eval/program-strings.erz --input examples/eval/event-string-ok.json >"$TMP_DIR/event-string-ok.actual.json"
cmp -s "$TMP_DIR/event-string-ok.actual.json" examples/eval/event-string-ok.expected.envelope.json
python3 -m cli.main eval examples/eval/program-strings.erz --input examples/eval/event-string-no-action.json --summary >"$TMP_DIR/event-string-no-action.actual.summary.txt"
cmp -s "$TMP_DIR/event-string-no-action.actual.summary.txt" examples/eval/event-string-no-action.expected.summary.txt

python3 -m cli.main eval examples/eval/program-lengths.erz --input examples/eval/event-length-ok.json >"$TMP_DIR/event-length-ok.actual.json"
cmp -s "$TMP_DIR/event-length-ok.actual.json" examples/eval/event-length-ok.expected.envelope.json
python3 -m cli.main eval examples/eval/program-lengths.erz --input examples/eval/event-length-no-action.json --summary >"$TMP_DIR/event-length-no-action.actual.summary.txt"
cmp -s "$TMP_DIR/event-length-no-action.actual.summary.txt" examples/eval/event-length-no-action.expected.summary.txt

python3 -m cli.main eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-ok.json >"$TMP_DIR/event-threshold-ok.actual.json"
cmp -s "$TMP_DIR/event-threshold-ok.actual.json" examples/eval/event-threshold-ok.expected.envelope.json
python3 -m cli.main eval examples/eval/program-thresholds.erz --input examples/eval/event-threshold-no-action.json --summary >"$TMP_DIR/event-threshold-no-action.actual.summary.txt"
cmp -s "$TMP_DIR/event-threshold-no-action.actual.summary.txt" examples/eval/event-threshold-no-action.expected.summary.txt

echo "  ok: frozen eval fixture outputs match"

step "4/7" "Batch verify/compare public fixtures"
python3 -m cli.main eval --batch-output-verify examples/eval/threshold-handoff/baseline --summary --batch-output-verify-profile default --batch-output-verify-require-run-id --batch-output-verify-expected-run-id-pattern '^threshold-ci-.*$' --batch-output-verify-expected-event-count 3 >"$TMP_DIR/baseline.verify.summary.txt"
cmp -s "$TMP_DIR/baseline.verify.summary.txt" examples/eval/threshold-handoff/baseline.verify.expected.summary.txt

python3 -m cli.main eval --batch-output-verify examples/eval/threshold-handoff/triage-by-status --summary --batch-output-verify-profile triage-by-status --batch-output-verify-require-run-id --batch-output-verify-expected-run-id-pattern '^threshold-ci-.*$' --batch-output-verify-expected-event-count 3 >"$TMP_DIR/triage.verify.summary.txt"
cmp -s "$TMP_DIR/triage.verify.summary.txt" examples/eval/threshold-handoff/triage.verify.expected.summary.txt

python3 -m cli.main eval --batch-output-compare examples/eval/threshold-handoff/triage-by-status --batch-output-compare-against examples/eval/threshold-handoff/baseline --summary --batch-output-compare-profile expected-asymmetric-drift --batch-output-compare-expected-baseline-only-count 3 --batch-output-compare-expected-candidate-only-count 2 --batch-output-compare-expected-selected-baseline-count 3 --batch-output-compare-expected-selected-candidate-count 2 --batch-output-compare-expected-metadata-mismatches-count 4 >"$TMP_DIR/triage-vs-baseline.compare.summary.txt"
cmp -s "$TMP_DIR/triage-vs-baseline.compare.summary.txt" examples/eval/threshold-handoff/triage-vs-baseline.compare.expected.summary.txt

echo "  ok: batch verify/compare fixtures match frozen outputs"

step "5/7" "Program-pack replay strict presets + sidecars"
python3 -m cli.main pack-replay examples/program-packs/ingest-normalize --summary --strict-profile ingest-normalize-clean >"$TMP_DIR/ingest-normalize.summary.txt"
python3 -m cli.main pack-replay examples/program-packs/dedup-cluster --summary --strict-profile dedup-cluster-clean --summary-file "$TMP_DIR/dedup.summary.sidecar.txt" --json-file "$TMP_DIR/dedup.summary.json" >"$TMP_DIR/dedup.summary.txt"
cmp -s "$TMP_DIR/dedup.summary.txt" "$TMP_DIR/dedup.summary.sidecar.txt"
python3 -m json.tool "$TMP_DIR/dedup.summary.json" > /dev/null
python3 -m cli.main pack-replay examples/program-packs/alert-routing --summary --strict-profile alert-routing-clean >"$TMP_DIR/alert-routing.summary.txt"

echo "  ok: pack replay strict presets passed"

step "6/7" "Runtime/schema trace contract sync"
python3 scripts/gates/trace_contract_gate.py

step "7/7" "Public doc/release anchors"
grep -q "v0.1.1-public" CHANGELOG.md
grep -q "v0.1 release-close checklist" docs/acceptance-metrics.md
grep -q "scripts/check.sh" docs/migrations.md

echo "All active public quality gates passed."
