from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from transform import TransformError, pack_document, pack_json_text, unpack_compact_refs

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "bench" / "token-harness" / "fixtures"


class TransformPackUnpackTests(unittest.TestCase):
    def test_pack_is_deterministic_for_equivalent_json(self) -> None:
        document_a = {
            "refs": {
                "txt_001": "Unfall auf der Kreuzung, zwei Fahrzeuge, keine sichtbaren Verletzten.",
            },
            "event": {
                "geo": {"lon": 13.4050, "lat": 52.5200},
                "timestamp": "2026-02-24T15:00:00Z",
                "text_ref": "@txt_001",
                "source": "telegram",
                "type": "ingest_event",
                "id": "evt_001",
            },
        }
        document_b = {
            "event": {
                "id": "evt_001",
                "type": "ingest_event",
                "source": "telegram",
                "text_ref": "@txt_001",
                "timestamp": "2026-02-24T15:00:00Z",
                "geo": {"lat": 52.5200, "lon": 13.4050},
            },
            "refs": {
                "txt_001": "Unfall auf der Kreuzung, zwei Fahrzeuge, keine sichtbaren Verletzten.",
            },
        }

        packed_a = pack_document(document_a)
        packed_b = pack_document(document_b)

        self.assertEqual(packed_a, packed_b)
        self.assertEqual(
            packed_a,
            "\n".join(
                [
                    "erz{v:0.1}",
                    'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}',
                    'rf{id:"txt_001",v:"Unfall auf der Kreuzung, zwei Fahrzeuge, keine sichtbaren Verletzten."}',
                    "",
                ]
            ),
        )

    def test_pack_then_unpack_is_lossless_for_supported_fixtures(self) -> None:
        for fixture_name in (
            "ingest_event",
            "normalize_event",
            "act_event",
            "ingest_event_nested_payload",
            "normalize_event_nested_payload",
            "act_event_nested_payload",
        ):
            with self.subTest(fixture=fixture_name):
                baseline = json.loads((FIXTURES / f"{fixture_name}.baseline.json").read_text(encoding="utf-8"))
                packed = pack_document(baseline)
                unpacked = unpack_compact_refs(packed)
                self.assertEqual(_canonicalize(unpacked), _canonicalize(baseline))

    def test_unpack_existing_compact_fixtures_matches_baseline(self) -> None:
        for fixture_name in (
            "ingest_event",
            "normalize_event",
            "act_event",
            "ingest_event_nested_payload",
            "normalize_event_nested_payload",
            "act_event_nested_payload",
        ):
            with self.subTest(fixture=fixture_name):
                compact_text = (FIXTURES / f"{fixture_name}.erz").read_text(encoding="utf-8")
                unpacked = unpack_compact_refs(compact_text)
                baseline = json.loads((FIXTURES / f"{fixture_name}.baseline.json").read_text(encoding="utf-8"))
                self.assertEqual(_canonicalize(unpacked), _canonicalize(baseline))

    def test_pack_json_text_rejects_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            pack_json_text('{"event":')

    def test_pack_refs_support_prefixed_keys_and_stay_deterministic(self) -> None:
        document_a = {
            "event": {
                "id": "evt_001",
                "type": "ingest_event",
                "source": "telegram",
                "text_ref": "@txt_main",
                "timestamp": "2026-02-24T15:00:00Z",
                "geo": {"lat": 52.52, "lon": 13.405},
            },
            "refs": {
                "@txt_aux": "Zusatztext",
                "txt_main": "Haupttext",
            },
        }
        document_b = {
            "event": {
                "id": "evt_001",
                "type": "ingest_event",
                "source": "telegram",
                "text_ref": "@txt_main",
                "timestamp": "2026-02-24T15:00:00Z",
                "geo": {"lat": 52.52, "lon": 13.405},
            },
            "refs": {
                "txt_aux": "Zusatztext",
                "@txt_main": "Haupttext",
            },
        }

        packed_a = pack_document(document_a)
        packed_b = pack_document(document_b)

        self.assertEqual(packed_a, packed_b)
        self.assertIn('rf{id:"txt_aux",v:"Zusatztext"}', packed_a)
        self.assertIn('rf{id:"txt_main",v:"Haupttext"}', packed_a)

    def test_pack_accepts_alias_fields_for_backward_compatibility(self) -> None:
        alias_document = {
            "event": {
                "id": "evt_202",
                "type": "normalize_event",
                "payload": {
                    "src": "voice_note",
                    "ingRef": "@evt_001",
                    "lang": "de",
                    "timezone": "Europe/Berlin",
                    "ent": [
                        {"kind": "location", "value": "A100 Ausfahrt Spandau", "confidence": 0.91},
                        {"kind": "vehicle_count", "value": "2", "confidence": 0.88},
                    ],
                    "normTextRef": "@txt_norm_202",
                },
            },
            "refs": {
                "@txt_norm_202": "Verkehrsunfall auf der A100, Ausfahrt Spandau. Zwei Fahrzeuge beteiligt, keine sichtbaren Verletzten.",
            },
        }
        canonical_document = {
            "event": {
                "id": "evt_202",
                "type": "normalize_event",
                "source": "voice_note",
                "ingest_ref": "@evt_001",
                "language": "de",
                "timezone": "Europe/Berlin",
                "entities": [
                    {"kind": "location", "value": "A100 Ausfahrt Spandau", "confidence": 0.91},
                    {"kind": "vehicle_count", "value": "2", "confidence": 0.88},
                ],
                "normalized_text_ref": "@txt_norm_202",
            },
            "refs": {
                "txt_norm_202": "Verkehrsunfall auf der A100, Ausfahrt Spandau. Zwei Fahrzeuge beteiligt, keine sichtbaren Verletzten.",
            },
        }

        self.assertEqual(pack_document(alias_document), pack_document(canonical_document))

    def test_pack_supports_nested_payload_ref_objects_and_refs_list(self) -> None:
        alias_document = {
            "event": {
                "id": "evt_777",
                "type": "ingest_event",
                "payload": {
                    "src": "telegram",
                    "textRef": {"id": "txt_777"},
                    "ts": "2026-02-24T18:00:00Z",
                    "geo": {"latitude": 52.5, "longitude": 13.4},
                },
            },
            "refs": [
                {"id": "@txt_777", "text": "Kurzmeldung aus dem Leitstand."},
            ],
        }

        canonical_document = {
            "event": {
                "id": "evt_777",
                "type": "ingest_event",
                "source": "telegram",
                "text_ref": "@txt_777",
                "timestamp": "2026-02-24T18:00:00Z",
                "geo": {"lat": 52.5, "lon": 13.4},
            },
            "refs": {
                "txt_777": "Kurzmeldung aus dem Leitstand.",
            },
        }

        self.assertEqual(pack_document(alias_document), pack_document(canonical_document))

    def test_pack_accepts_refs_list_and_nested_action_aliases(self) -> None:
        alias_document = {
            "event": {
                "id": "evt_303",
                "type": "act",
                "payload": {
                    "decRef": "@dec_303",
                    "actions": [
                        {
                            "t": "notify",
                            "params": {
                                "target": "ops_dispatch",
                                "templateRef": "@tpl_ops",
                            },
                        },
                        {
                            "type": "ticket",
                            "params": {
                                "sys": "incident_hub",
                                "prio": "high",
                                "ddk": "evt_001",
                            },
                        },
                    ],
                    "deadline_seconds": 300,
                },
            },
            "decision": {
                "id": "dec_303",
                "score": 0.83,
                "rc": [
                    {"code": "injury_unknown"},
                    {"value": "traffic_blocked"},
                    "rush_hour",
                ],
            },
            "refs": [
                {
                    "$ref": "@tpl_ops",
                    "text": "Bitte Einsatzlage prüfen und Rückmeldung innerhalb von 5 Minuten.",
                }
            ],
        }
        canonical_document = {
            "event": {
                "id": "evt_303",
                "type": "act_event",
                "decision_ref": "@dec_303",
                "actions": [
                    {
                        "type": "notify_channel",
                        "target": "ops_dispatch",
                        "template_ref": "@tpl_ops",
                    },
                    {
                        "type": "create_ticket",
                        "system": "incident_hub",
                        "priority": "high",
                        "dedupe_key": "evt_001",
                    },
                ],
                "deadline_s": 300,
            },
            "decision": {
                "id": "dec_303",
                "score": 0.83,
                "reason_codes": ["injury_unknown", "traffic_blocked", "rush_hour"],
            },
            "refs": {
                "tpl_ops": "Bitte Einsatzlage prüfen und Rückmeldung innerhalb von 5 Minuten.",
            },
        }

        self.assertEqual(pack_document(alias_document), pack_document(canonical_document))

    def test_pack_rejects_colliding_ref_ids_in_refs_list(self) -> None:
        document = {
            "event": {
                "id": "evt_001",
                "type": "ingest_event",
                "source": "telegram",
                "text_ref": "@txt_main",
                "timestamp": "2026-02-24T15:00:00Z",
                "geo": {"lat": 52.52, "lon": 13.405},
            },
            "refs": [
                {"id": "txt_main", "value": "A"},
                {"id": "@txt_main", "value": "B"},
            ],
        }

        with self.assertRaisesRegex(TransformError, "colliding ref ids"):
            pack_document(document)

    def test_pack_rejects_missing_ref_bindings(self) -> None:
        document = {
            "event": {
                "id": "evt_001",
                "type": "ingest_event",
                "source": "telegram",
                "text_ref": "@txt_missing",
                "timestamp": "2026-02-24T15:00:00Z",
                "geo": {"lat": 52.52, "lon": 13.405},
            },
            "refs": {
                "txt_other": "Andere Referenz",
            },
        }

        with self.assertRaisesRegex(TransformError, "missing ref id"):
            pack_document(document)

    def test_pack_rejects_colliding_ref_keys(self) -> None:
        document = {
            "event": {
                "id": "evt_001",
                "type": "ingest_event",
                "source": "telegram",
                "text_ref": "@txt_main",
                "timestamp": "2026-02-24T15:00:00Z",
                "geo": {"lat": 52.52, "lon": 13.405},
            },
            "refs": {
                "txt_main": "A",
                "@txt_main": "B",
            },
        }

        with self.assertRaisesRegex(TransformError, "colliding ref ids"):
            pack_document(document)

    def test_unpack_rejects_missing_refs(self) -> None:
        source = "\n".join(
            [
                "erz{v:0.1}",
                'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_missing,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}',
                "",
            ]
        )

        with self.assertRaisesRegex(TransformError, "missing ref id"):
            unpack_compact_refs(source)

    def test_unpack_rejects_invalid_rf_id(self) -> None:
        source = "\n".join(
            [
                "erz{v:0.1}",
                'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}',
                'rf{id:"txt?001",v:"Ungültig"}',
                "",
            ]
        )

        with self.assertRaisesRegex(TransformError, "invalid ref id"):
            unpack_compact_refs(source)

    def test_unpack_rejects_ref_collisions_after_canonicalization(self) -> None:
        source = "\n".join(
            [
                "erz{v:0.1}",
                'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}',
                'rf{id:"txt_001",v:"A"}',
                'rf{id:"@txt_001",v:"B"}',
                "",
            ]
        )

        with self.assertRaisesRegex(TransformError, "Duplicate ref id 'txt_001'"):
            unpack_compact_refs(source)

    def test_unpack_accepts_legacy_alias_keys_for_backward_compatibility(self) -> None:
        source = "\n".join(
            [
                "erz{v:0.1}",
                'ev{id:"evt_303",t:act,payload:{decisionRef:@dec_303,actions:[{type:notify,target:ops_dispatch,templateRef:@tpl_ops},{type:ticket,system:incident_hub,priority:high,dedupeKey:"evt_001"}],deadlineSec:300}}',
                'dc{id:"dec_303",score:0.83,reasonCodes:[injury_unknown,traffic_blocked,rush_hour]}',
                'rf{id:"@tpl_ops",v:"Bitte Einsatzlage prüfen und Rückmeldung innerhalb von 5 Minuten."}',
                "",
            ]
        )

        unpacked = unpack_compact_refs(source)

        self.assertEqual(
            _canonicalize(unpacked),
            _canonicalize(
                {
                    "event": {
                        "id": "evt_303",
                        "type": "act_event",
                        "decision_ref": "@dec_303",
                        "actions": [
                            {
                                "type": "notify_channel",
                                "target": "ops_dispatch",
                                "template_ref": "@tpl_ops",
                            },
                            {
                                "type": "create_ticket",
                                "system": "incident_hub",
                                "priority": "high",
                                "dedupe_key": "evt_001",
                            },
                        ],
                        "deadline_s": 300,
                    },
                    "decision": {
                        "id": "dec_303",
                        "score": 0.83,
                        "reason_codes": ["injury_unknown", "traffic_blocked", "rush_hour"],
                    },
                    "refs": {
                        "tpl_ops": "Bitte Einsatzlage prüfen und Rückmeldung innerhalb von 5 Minuten.",
                    },
                }
            ),
        )

    def test_unpack_accepts_long_type_and_geo_alias_payload(self) -> None:
        source = "\n".join(
            [
                "erz{v:0.1}",
                'ev{id:"evt_001",type:ingest_event,payload:{source:telegram,textRef:@txt_001,timestamp:"2026-02-24T15:00:00Z",geo:{latitude:52.52,longitude:13.405}}}',
                'rf{id:"@txt_001",value:"Unfall auf der Kreuzung, zwei Fahrzeuge, keine sichtbaren Verletzten."}',
                "",
            ]
        )

        unpacked = unpack_compact_refs(source)

        self.assertEqual(
            _canonicalize(unpacked),
            _canonicalize(
                {
                    "event": {
                        "id": "evt_001",
                        "type": "ingest_event",
                        "source": "telegram",
                        "text_ref": "@txt_001",
                        "timestamp": "2026-02-24T15:00:00Z",
                        "geo": {"lat": 52.52, "lon": 13.405},
                    },
                    "refs": {
                        "txt_001": "Unfall auf der Kreuzung, zwei Fahrzeuge, keine sichtbaren Verletzten.",
                    },
                }
            ),
        )


class PackUnpackCliTests(unittest.TestCase):
    def test_pack_and_unpack_cli_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "input.json"
            baseline_payload = json.loads(
                (FIXTURES / "normalize_event.baseline.json").read_text(encoding="utf-8")
            )
            baseline_path.write_text(
                json.dumps(baseline_payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            packed_result = self._run_cli("pack", str(baseline_path))
            self.assertEqual(packed_result.returncode, 0)
            self.assertIn("ev{", packed_result.stdout)
            self.assertIn("rf{", packed_result.stdout)

            compact_path = Path(tmp_dir) / "packed.erz"
            compact_path.write_text(packed_result.stdout, encoding="utf-8")

            unpack_result = self._run_cli("unpack", str(compact_path))
            self.assertEqual(unpack_result.returncode, 0)
            unpacked_payload = json.loads(unpack_result.stdout)

            self.assertEqual(_canonicalize(unpacked_payload), _canonicalize(baseline_payload))

    def test_pack_default_error_mode_stays_human_readable(self) -> None:
        completed = self._run_cli("pack", "-", stdin_text="{}")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertTrue(completed.stderr.startswith("error: "))

        with self.assertRaises(json.JSONDecodeError):
            json.loads(completed.stderr)

    def test_unpack_default_error_mode_stays_human_readable(self) -> None:
        completed = self._run_cli(
            "unpack",
            "-",
            stdin_text='ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}\n',
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertTrue(completed.stderr.startswith("error: "))

        with self.assertRaises(json.JSONDecodeError):
            json.loads(completed.stderr)

    def _run_cli(
        self,
        *args: str,
        stdin_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cli.main", *args],
            cwd=ROOT,
            text=True,
            input=stdin_text,
            capture_output=True,
            check=False,
        )


def _canonicalize(value: object) -> object:
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value.keys())}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


if __name__ == "__main__":
    unittest.main()
