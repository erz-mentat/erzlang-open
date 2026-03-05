#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/erz-check.XXXXXX")"
BENCH_JSON="bench/token-harness/results/latest.json"
BENCH_MD="bench/token-harness/results/latest.md"
BENCH_JSON_BACKUP="$TMP_DIR/latest.json.before"
BENCH_MD_BACKUP="$TMP_DIR/latest.md.before"
BENCH_JSON_EXISTED=0
BENCH_MD_EXISTED=0

cleanup() {
  if [[ "$BENCH_JSON_EXISTED" == "1" && -f "$BENCH_JSON_BACKUP" ]]; then
    cp "$BENCH_JSON_BACKUP" "$BENCH_JSON"
  else
    rm -f "$BENCH_JSON"
  fi

  if [[ "$BENCH_MD_EXISTED" == "1" && -f "$BENCH_MD_BACKUP" ]]; then
    cp "$BENCH_MD_BACKUP" "$BENCH_MD"
  else
    rm -f "$BENCH_MD"
  fi

  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cd "$REPO_ROOT"

if [[ -f "$BENCH_JSON" ]]; then
  cp "$BENCH_JSON" "$BENCH_JSON_BACKUP"
  BENCH_JSON_EXISTED=1
fi

if [[ -f "$BENCH_MD" ]]; then
  cp "$BENCH_MD" "$BENCH_MD_BACKUP"
  BENCH_MD_EXISTED=1
fi

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

step "2/7" "Unit tests"
python3 -m unittest discover -s tests -v

step "3/7" "Few-shot parser cases"
python3 scripts/validate_fewshot.py >"$TMP_DIR/fewshot.out"
cat "$TMP_DIR/fewshot.out"

step "4/7" "Benchmark harness"
python3 bench/token-harness/measure.py >"$TMP_DIR/bench.out"
# Keep helper stderr unredirected so canonical `gate failure [...]` diagnostics pass through unchanged.
python3 scripts/gates/benchmark_gate.py

step "5/7" "Runtime/schema trace contract sync"
python3 scripts/gates/trace_contract_gate.py

step "6/7" "Migration/compatibility discipline anchors"
python3 scripts/gates/migration_anchor_gate.py

step "7/7" "Quality gates complete"
echo "All active quality gates passed."
