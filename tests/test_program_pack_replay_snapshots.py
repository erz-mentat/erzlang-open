from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PACK_FIXTURES = ROOT / "examples" / "program-packs"
PROGRAM_PACK_INDEX = PROGRAM_PACK_FIXTURES / "program-pack-index.json"
REFRESH_HELPER = ROOT / "scripts" / "refresh_program_pack_replay_contracts.py"
AGGREGATE_OUTPUT_STEM = "program-pack-index"


def _contract_output_paths(stem: str) -> list[str]:
    return [
        f"{stem}.replay.expected.summary.txt",
        f"{stem}.replay.expected.json",
        f"{stem}.replay.handoff-bundle.expected.json",
    ]


def _pack_output_stems() -> tuple[str, ...]:
    payload = json.loads(PROGRAM_PACK_INDEX.read_text(encoding="utf-8"))
    raw_entries = payload.get("packs") if isinstance(payload, dict) else None
    if not isinstance(raw_entries, list) or not raw_entries:
        raise AssertionError("expected non-empty program-pack index packs array")

    stems: list[str] = []
    for entry in raw_entries:
        raw_path = entry if isinstance(entry, str) else entry.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise AssertionError("expected string pack path entries in program-pack index")
        stem = Path(raw_path).name
        if not stem:
            raise AssertionError("expected terminal path name in program-pack index")
        stems.append(stem)

    if len(stems) != len(set(stems)):
        raise AssertionError("expected unique pack output stems in program-pack index")
    return tuple(stems)


PACK_OUTPUT_STEMS = _pack_output_stems()


class ProgramPackReplaySnapshotTests(unittest.TestCase):
    def _run_refresh_helper(self, fixture_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(REFRESH_HELPER),
                "--repo-root",
                str(ROOT),
                "--fixture-root",
                str(fixture_root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_program_pack_replay_refresh_helper_regenerates_tracked_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "program-packs"
            shutil.copytree(PROGRAM_PACK_FIXTURES, replay_root)

            generated_paths = [
                relative_path
                for stem in (*PACK_OUTPUT_STEMS, AGGREGATE_OUTPUT_STEM)
                for relative_path in _contract_output_paths(stem)
            ]
            for relative_path in generated_paths:
                path = replay_root / relative_path
                if path.exists():
                    path.unlink()

            refresh_run = self._run_refresh_helper(replay_root)

            regenerated_outputs = {
                relative_path: (replay_root / relative_path).read_text(encoding="utf-8")
                for relative_path in generated_paths
            }

        self.assertEqual(refresh_run.returncode, 0)
        self.assertEqual(refresh_run.stderr, "")
        self.assertIn("refreshed program-pack replay contract outputs:", refresh_run.stdout)
        self.assertEqual(
            regenerated_outputs,
            {
                relative_path: (PROGRAM_PACK_FIXTURES / relative_path).read_text(encoding="utf-8")
                for relative_path in generated_paths
            },
        )

    def test_pack_replay_sidecars_are_reproducible_for_each_checked_in_pack(self) -> None:
        for stem in PACK_OUTPUT_STEMS:
            with self.subTest(pack=stem):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    replay_root = Path(tmp_dir) / "program-packs"
                    shutil.copytree(PROGRAM_PACK_FIXTURES, replay_root)

                    summary_file = replay_root / f"{stem}.replay.expected.summary.txt"
                    json_file = replay_root / f"{stem}.replay.expected.json"
                    bundle_file = replay_root / f"{stem}.replay.handoff-bundle.expected.json"

                    for path in [summary_file, json_file, bundle_file]:
                        if path.exists():
                            path.unlink()

                    result = self._run_refresh_helper(replay_root)

                    summary_text = summary_file.read_text(encoding="utf-8")
                    json_text = json_file.read_text(encoding="utf-8")
                    bundle_text = bundle_file.read_text(encoding="utf-8")

                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                self.assertEqual(
                    summary_text,
                    (PROGRAM_PACK_FIXTURES / f"{stem}.replay.expected.summary.txt").read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    json_text,
                    (PROGRAM_PACK_FIXTURES / f"{stem}.replay.expected.json").read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    bundle_text,
                    (PROGRAM_PACK_FIXTURES / f"{stem}.replay.handoff-bundle.expected.json").read_text(
                        encoding="utf-8"
                    ),
                )

    def test_program_pack_index_replay_sidecars_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay_root = Path(tmp_dir) / "program-packs"
            shutil.copytree(PROGRAM_PACK_FIXTURES, replay_root)

            summary_file = replay_root / "program-pack-index.replay.expected.summary.txt"
            json_file = replay_root / "program-pack-index.replay.expected.json"
            bundle_file = replay_root / "program-pack-index.replay.handoff-bundle.expected.json"

            for path in [summary_file, json_file, bundle_file]:
                if path.exists():
                    path.unlink()

            result = self._run_refresh_helper(replay_root)

            summary_text = summary_file.read_text(encoding="utf-8")
            json_text = json_file.read_text(encoding="utf-8")
            bundle_text = bundle_file.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            summary_text,
            (PROGRAM_PACK_FIXTURES / "program-pack-index.replay.expected.summary.txt").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(
            json_text,
            (PROGRAM_PACK_FIXTURES / "program-pack-index.replay.expected.json").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(
            bundle_text,
            (PROGRAM_PACK_FIXTURES / "program-pack-index.replay.handoff-bundle.expected.json").read_text(
                encoding="utf-8"
            ),
        )


if __name__ == "__main__":
    unittest.main()
