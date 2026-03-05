from __future__ import annotations

import json
from pathlib import Path
import unittest

from compact import parse_and_format_compact, parse_compact
from runtime.eval import eval_policies

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "examples" / "program-packs" / "dedup-cluster"


class DedupClusterProgramPackTests(unittest.TestCase):
    def test_policy_program_is_canonical_compact(self) -> None:
        source = (PACK_DIR / "policy.erz").read_text(encoding="utf-8")
        self.assertEqual(source, parse_and_format_compact(source))

    def test_baseline_mapping_samples_match_deterministic_key_derivation(self) -> None:
        payload = self._load_baseline_mapping()
        mapping = payload["deterministic_mapping"]

        for sample in payload["samples"]:
            with self.subTest(sample=sample["id"]):
                derived = self._derive_mapped_event(sample["raw_event"], mapping)
                self.assertEqual(derived, sample["mapped_event"])

    def test_program_pack_samples_emit_expected_actions_and_trace(self) -> None:
        mapping_payload = self._load_baseline_mapping()
        rules = self._load_policy_rules()

        self.assertEqual(len(rules), 4)

        for sample in mapping_payload["samples"]:
            with self.subTest(sample=sample["id"]):
                event = sample["mapped_event"]
                context = sample["context"]

                first_actions, first_trace = eval_policies(
                    event=event,
                    rules=rules,
                    now=context["now"],
                    seed=context["seed"],
                )
                second_actions, second_trace = eval_policies(
                    event=event,
                    rules=rules,
                    now=context["now"],
                    seed=context["seed"],
                )

                self.assertEqual(first_actions, second_actions)
                self.assertEqual(first_trace, second_trace)

                self.assertEqual(first_actions, sample["expected_actions"])
                self.assertEqual(first_trace, sample["expected_trace"])

    def _load_policy_rules(self) -> list[dict[str, object]]:
        program = parse_compact((PACK_DIR / "policy.erz").read_text(encoding="utf-8"))
        return [statement["fields"] for statement in program if statement["tag"] == "rl"]

    def _load_baseline_mapping(self) -> dict[str, object]:
        return json.loads((PACK_DIR / "baseline-mapping.json").read_text(encoding="utf-8"))

    def _derive_mapped_event(
        self,
        raw_event: dict[str, object],
        mapping: dict[str, object],
    ) -> dict[str, object]:
        category_prefix = str(mapping["category_payload_key_prefix"])
        time_window_minutes = int(mapping["time_window_minutes"])
        geo_radius_meters = int(mapping["geo_radius_meters"])

        payload: dict[str, object] = {
            "category": raw_event["category"],
            f"{category_prefix}{raw_event['category']}": True,
        }

        if "dedupe_key" in raw_event:
            payload["dedupe_key"] = raw_event["dedupe_key"]

        if int(raw_event["minutes_since_anchor"]) <= time_window_minutes:
            payload[str(mapping["time_within_key"])] = True
        else:
            payload[str(mapping["time_outside_key"])] = True

        if int(raw_event["distance_meters"]) <= geo_radius_meters:
            payload[str(mapping["geo_within_key"])] = True
        else:
            payload[str(mapping["geo_outside_key"])] = True

        return {
            "type": raw_event["type"],
            "payload": payload,
        }


if __name__ == "__main__":
    unittest.main()
