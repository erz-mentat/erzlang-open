# Release Artifacts Index

This directory stores release evidence exported by `python3 scripts/release_snapshot.py`.

## Quickstart pointer

From repo root, run:

```bash
./scripts/check.sh && python3 scripts/release_snapshot.py
```

Use this after a green full-lane gate pass to refresh both dated and `latest.*` release evidence artifacts.

## Naming semantics

- Dated snapshot pair (immutable by convention):
  - `release-snapshot-<UTCSTAMP>.json`
  - `release-snapshot-<UTCSTAMP>.md`
- `<UTCSTAMP>` format is `YYYYMMDDTHHMMSSZ` (UTC).
- Snapshot content includes benchmark/gate evidence sourced from `bench/token-harness/results/latest.json`.

## `latest` pointer semantics

- `latest.json` and `latest.md` are overwrite-on-export pointers.
- They mirror the payload produced by the **most recent snapshot export run**.
- `latest.*` is not a symlink and is not selected by filename sort; it is updated by the last script invocation.

## Retention and cleanup policy

- No automatic pruning is performed by `scripts/release_snapshot.py`.
- Keep `latest.json` + `latest.md` plus at least one dated snapshot pair.
- When pruning, delete dated pairs together (`.json` + `.md`) and keep the newest retained pair aligned with your release notes.
- Cleanup is explicit/manual to keep gate runs and evidence export non-mutating by default.

## Manual retention runbook (non-destructive first)

Preconditions checklist (execute in order before running commands):
1. Confirm `repo-root` context, `pwd` is this repo and `docs/` plus `scripts/` resolve correctly.
2. Confirm `latest.*` artifacts stay preserved (`docs/release-artifacts/latest.json` + `docs/release-artifacts/latest.md`).
3. Confirm prune candidates are `matched pair` dated snapshots only (`release-snapshot-<stamp>.json` + `release-snapshot-<stamp>.md`), never one side alone.

From repo root:

```bash
# 1) List dated snapshots (oldest -> newest)
ls -1 docs/release-artifacts/release-snapshot-*.json | sort

# 2) Preview prune plan (default APPLY=False keeps this dry-run only)
python3 - <<'PY'
from pathlib import Path

KEEP = 3
APPLY = False

artifact_dir = Path("docs/release-artifacts")
json_files = sorted(artifact_dir.glob("release-snapshot-*.json"))
stamps = [path.name[len("release-snapshot-") : -len(".json")] for path in json_files]
keep_stamps = set(stamps[-KEEP:])

for stamp in stamps:
    pair = [
        artifact_dir / f"release-snapshot-{stamp}.json",
        artifact_dir / f"release-snapshot-{stamp}.md",
    ]
    action = "KEEP" if stamp in keep_stamps else "PRUNE"
    print(action, *[str(path) for path in pair], sep=" | ")
    if APPLY and action == "PRUNE":
        for path in pair:
            if path.exists():
                path.unlink()

print("PRESERVE", artifact_dir / "latest.json", sep=" | ")
print("PRESERVE", artifact_dir / "latest.md", sep=" | ")
PY
```

Set `APPLY = True` only after reviewing dry-run output and re-checking the ordered preconditions above (`repo-root`, `latest.*` preservation, matched-pair-only deletions).
