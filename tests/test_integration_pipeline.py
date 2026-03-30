from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from compact import CompactParseError, CompactValidationError, SCHEMA, parse_compact
from runtime.errors import ERROR_ENVELOPE_FIELD_ORDER, build_error_envelope, render_error_envelope_json
from runtime.eval import (
    TRACE_OPTIONAL_FIELDS,
    TRACE_REQUIRED_FIELDS,
    eval_policies,
    eval_policies_envelope,
    validate_trace,
    validate_trace_step,
)
from transform import TransformError, pack_document, unpack_compact_refs


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema" / "ir.v0.1.schema.json"
MIGRATIONS_DOC_PATH = REPO_ROOT / "docs" / "migrations.md"
QUALITY_GATES_DOC_PATH = REPO_ROOT / "docs" / "quality-gates.md"
README_DOC_PATH = REPO_ROOT / "README.md"
RUNTIME_DETERMINISM_DOC_PATH = REPO_ROOT / "docs" / "runtime-determinism.md"
ERROR_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "errors"
EVAL_FIXTURES = REPO_ROOT / "examples" / "eval"


class IntegrationPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.migrations_doc = MIGRATIONS_DOC_PATH.read_text(encoding="utf-8")
        cls.quality_gates_doc = QUALITY_GATES_DOC_PATH.read_text(encoding="utf-8")
        cls.readme_doc = README_DOC_PATH.read_text(encoding="utf-8")
        cls.runtime_determinism_doc = RUNTIME_DETERMINISM_DOC_PATH.read_text(encoding="utf-8")

    def test_trace_pipeline_compact_parse_then_runtime_validation_then_schema_parity(self) -> None:
        source = (
            'tr{rule_id:"r42",matched_clauses:["event_type_present","payload_has:severity"],'
            'score:1.0,calibrated_probability:0.92,timestamp:"2026-02-25T14:00:00Z",seed:"seed-42"}'
        )

        program = parse_compact(source)
        self.assertEqual(len(program), 1)
        self.assertEqual(program[0]["tag"], "tr")
        parsed_step = program[0]["fields"]

        validated_step = validate_trace_step(parsed_step)
        self.assertEqual(validated_step, parsed_step)

        validated_trace = validate_trace([parsed_step], fired_rule_ids=["r42"])
        self.assertEqual(validated_trace, [parsed_step])

        trace_schema = self.schema["$defs"]["trace"]
        schema_required = set(trace_schema["required"])
        schema_fields = set(trace_schema["properties"].keys())

        runtime_required = set(TRACE_REQUIRED_FIELDS)
        runtime_fields = runtime_required | set(TRACE_OPTIONAL_FIELDS)

        compact_trace_schema = SCHEMA["tr"]
        compact_fields = set(compact_trace_schema.required) | set(compact_trace_schema.optional)

        self.assertEqual(schema_required, runtime_required)
        self.assertEqual(schema_fields, runtime_fields)
        self.assertEqual(compact_fields, runtime_fields)

        self.assertEqual(set(parsed_step.keys()) - schema_fields, set())
        self.assertTrue(schema_required.issubset(parsed_step.keys()))

        calibrated_probability_schema = trace_schema["properties"]["calibrated_probability"]
        self.assertGreaterEqual(
            parsed_step["calibrated_probability"],
            calibrated_probability_schema["minimum"],
        )
        self.assertLessEqual(
            parsed_step["calibrated_probability"],
            calibrated_probability_schema["maximum"],
        )

    def test_trace_pipeline_handles_required_only_compact_trace(self) -> None:
        source = 'tr{rule_id:"r-min",matched_clauses:["event_type_present"]}'
        parsed_step = parse_compact(source)[0]["fields"]

        self.assertEqual(validate_trace_step(parsed_step), parsed_step)
        self.assertEqual(validate_trace([parsed_step], fired_rule_ids=["r-min"]), [parsed_step])

        trace_schema = self.schema["$defs"]["trace"]
        schema_required = set(trace_schema["required"])

        self.assertEqual(schema_required, set(TRACE_REQUIRED_FIELDS))
        self.assertEqual(set(parsed_step.keys()), schema_required)
        for field in TRACE_OPTIONAL_FIELDS:
            self.assertNotIn(field, parsed_step)
            self.assertIn(field, trace_schema["properties"])

    def test_migration_anchor_trace_token_order_matches_active_runtime_schema_order(self) -> None:
        trace_schema = self.schema["$defs"]["trace"]
        required_in_schema = set(trace_schema.get("required", []))
        properties_in_schema = set(trace_schema.get("properties", {}).keys())

        active_required = [field for field in TRACE_REQUIRED_FIELDS if field in required_in_schema]
        active_optional = [field for field in TRACE_OPTIONAL_FIELDS if field in properties_in_schema]

        required_in_migrations = self._parse_anchor_tokens(
            text=self.migrations_doc,
            prefix="- Gate anchor trace required:",
            doc_name="docs/migrations.md",
        )
        optional_in_migrations = self._parse_anchor_tokens(
            text=self.migrations_doc,
            prefix="- Gate anchor trace optional:",
            doc_name="docs/migrations.md",
        )

        self.assertEqual(required_in_migrations, active_required)
        self.assertEqual(optional_in_migrations, active_optional)

    def test_migration_anchor_profiles_match_quality_gates_and_have_headings(self) -> None:
        profiles_in_migrations = self._parse_anchor_tokens(
            text=self.migrations_doc,
            prefix="- Gate anchor profiles:",
            doc_name="docs/migrations.md",
        )
        profiles_in_quality_gates = self._parse_anchor_tokens(
            text=self.quality_gates_doc,
            prefix="- Gate anchor profiles:",
            doc_name="docs/quality-gates.md",
        )

        self.assertEqual(profiles_in_migrations, profiles_in_quality_gates)

        migration_headings = [
            line[3:].strip() for line in self.migrations_doc.splitlines() if line.startswith("## ")
        ]
        missing_profile_headings = [
            profile
            for profile in profiles_in_migrations
            if not any(profile in heading for heading in migration_headings)
        ]

        self.assertEqual(missing_profile_headings, [])

    def test_gate_b8_wording_canary_for_details_order_and_runtime_parity(self) -> None:
        heading = "### Gate B8: Machine-readable error envelope contract (v0.2 prep)"
        lines = self.quality_gates_doc.splitlines()
        self.assertEqual(
            lines.count(heading),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 heading",
        )

        gate_start = lines.index(heading) + 1
        gate_end = len(lines)
        for index in range(gate_start, len(lines)):
            if lines[index].startswith("### Gate ") or lines[index].startswith("## "):
                gate_end = index
                break

        gate_b8_lines = lines[gate_start:gate_end]
        expected_bullet_snippets = [
            "`details` ordered-item contract is explicit and stable (`error_type`, then `command`) across snapshot parity lanes.",
            "Runtime stage/details-command parity is locked across adapter + direct builder lanes by comparing adapter failures against direct `build_error_envelope(...)` outputs (`stage=\"runtime\"`, `details.command=\"eval\"`).",
        ]

        for snippet in expected_bullet_snippets:
            self.assertEqual(
                sum(1 for line in gate_b8_lines if line.strip() == f"- {snippet}"),
                1,
                "docs/quality-gates.md: expected exactly one standalone Gate B8 bullet with wording "
                f"snippet: {snippet}",
            )

    def test_fn_031_readme_runtime_doc_parity_with_gate_b8_wording_canary(self) -> None:
        readme_expected_lines = [
            "- Ordered-details-Vertrag ist fix: `details` serialisiert immer zuerst `error_type`, dann `command` (CLI + direkte Envelope-Builder-Pfade)",
            "- Runtime-Parität ist fix: Runtime-Fehler führen immer `stage=\"runtime\"` und `details.command=\"eval\"`; Adapter-Fehler werden gegen direkte `build_error_envelope(...)`-Outputs verglichen",
        ]
        runtime_expected_lines = [
            "- Ordered details contract is deterministic: `error.details` serializes `error_type` first, then `command`.",
            "- Stable runtime parity contract for adapter + direct-builder lanes: adapter failures and direct `build_error_envelope(...)` outputs keep `stage=\"runtime\"` and `details.command=\"eval\"`.",
        ]

        readme_lines = self.readme_doc.splitlines()
        runtime_lines = self.runtime_determinism_doc.splitlines()

        for line in readme_expected_lines:
            self.assertEqual(
                sum(1 for candidate in readme_lines if candidate.strip() == line.strip()),
                1,
                f"README.md: expected exactly one line for Gate B8 parity canary: {line}",
            )

        for line in runtime_expected_lines:
            self.assertEqual(
                sum(1 for candidate in runtime_lines if candidate.strip() == line.strip()),
                1,
                "docs/runtime-determinism.md: expected exactly one line for Gate B8 parity canary: "
                f"{line}",
            )

    def test_fn_032_canonical_runtime_snapshot_names_cross_doc_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        migration_v02_lines = self._extract_section_lines(
            text=self.migrations_doc,
            heading=(
                "## v0.1 (Sprint-6 compatibility/ref-hardening profile) -> "
                "v0.1 (v0.2-prep error-envelope compatibility profile)"
            ),
            doc_name="docs/migrations.md",
        )

        for fixture_name in ("runtime_contract.stderr", "runtime_value.stderr"):
            self.assertEqual(
                sum(fixture_name in line for line in gate_b8_lines),
                1,
                "docs/quality-gates.md: expected canonical runtime fixture name exactly once in Gate B8 "
                f"section: {fixture_name}",
            )
            self.assertEqual(
                sum(fixture_name in line for line in migration_v02_lines),
                1,
                "docs/migrations.md: expected canonical runtime fixture name exactly once in v0.2-prep "
                f"migration section: {fixture_name}",
            )

    def test_fn_033_gate_b8_fail_condition_wording_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        fail_line_prefix = "- **Fail if:**"
        fail_lines = [line.strip() for line in gate_b8_lines if line.strip().startswith(fail_line_prefix)]

        self.assertEqual(
            len(fail_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 fail-condition line",
        )

        fail_line = fail_lines[0]
        expected_fragments = [
            "`details` ordered-item invariants drift",
            "runtime stage/details-command parity across adapter/direct-builder lanes regresses",
        ]

        for fragment in expected_fragments:
            self.assertIn(
                fragment,
                fail_line,
                "docs/quality-gates.md: expected Gate B8 fail-condition wording fragment: "
                f"{fragment}",
            )

    def test_fn_034_gate_b8_fail_condition_line_boundary_singularity_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )

        fail_line_prefix = "- **Fail if:**"
        fail_line_indexes = [
            index
            for index, line in enumerate(gate_b8_lines)
            if line.strip().startswith(fail_line_prefix)
        ]

        self.assertEqual(
            len(fail_line_indexes),
            1,
            "docs/quality-gates.md: expected exactly one standalone Gate B8 fail-condition line",
        )

        fail_line_index = fail_line_indexes[0]
        expected_fail_line = (
            "- **Fail if:** JSON mode drifts, field shape/order changes, `details` ordered-item "
            "invariants drift, transform span snapshots drift, adapter-shape invariants regress, "
            "non-contract passthrough behavior regresses, runtime stage/details-command parity "
            "across adapter/direct-builder lanes regresses, runtime consumer contract guidance "
            "drifts, or stable-code mapping/snapshots drift."
        )

        self.assertEqual(
            gate_b8_lines[fail_line_index].strip(),
            expected_fail_line,
            "docs/quality-gates.md: Gate B8 fail-condition must remain a single-line literal",
        )

        continuation_lines = [
            line
            for line in gate_b8_lines[fail_line_index + 1 :]
            if line.strip() and not line.lstrip().startswith("- ")
        ]
        self.assertEqual(
            continuation_lines,
            [],
            "docs/quality-gates.md: Gate B8 fail-condition line must stay standalone (no wrapped "
            "continuation lines)",
        )

    def test_fn_035_readme_runtime_token_literal_cross_check_canary(self) -> None:
        tokens = [
            "`stage=\"runtime\"`",
            "`details.command=\"eval\"`",
            "`error_type`",
            "`command`",
        ]

        readme_lines = self.readme_doc.splitlines()
        readme_start_marker = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        self.assertIn(
            readme_start_marker,
            readme_lines,
            "README.md: missing error-envelope section marker",
        )
        readme_start = readme_lines.index(readme_start_marker) + 1
        readme_end = len(readme_lines)
        for index in range(readme_start, len(readme_lines)):
            if readme_lines[index].startswith("### "):
                readme_end = index
                break

        readme_bullets = [
            line.strip() for line in readme_lines[readme_start:readme_end] if line.lstrip().startswith("- ")
        ]
        readme_bullet_blob = "\n".join(readme_bullets)

        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_start_marker = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"
        self.assertIn(
            runtime_start_marker,
            runtime_lines,
            "docs/runtime-determinism.md: missing deterministic envelope adapter section marker",
        )
        runtime_start = runtime_lines.index(runtime_start_marker) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_bullets = [
            line.strip()
            for line in runtime_lines[runtime_start:runtime_end]
            if line.lstrip().startswith("- ")
        ]
        runtime_bullet_blob = "\n".join(runtime_bullets)

        for token in tokens:
            self.assertEqual(
                readme_bullet_blob.count(token),
                1,
                "README.md: expected exactly one token literal in envelope-contract bullets: "
                f"{token}",
            )
            self.assertEqual(
                runtime_bullet_blob.count(token),
                1,
                "docs/runtime-determinism.md: expected exactly one token literal in "
                f"envelope-contract bullets: {token}",
            )

    def test_fn_037_gate_b8_docs_canary_triage_index_singularity_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        triage_index_line = (
            "- Docs-canary coverage triage index (FN-031..FN-035): cross-doc parity wording "
            "(README/runtime), canonical runtime snapshot-name parity, Gate B8 fail-line "
            "wording/singularity, and README/runtime token-literal parity."
        )

        self.assertEqual(
            sum(1 for line in gate_b8_lines if line.strip() == triage_index_line),
            1,
            "docs/quality-gates.md: expected exactly one standalone Gate B8 docs-canary triage "
            "index line",
        )

    def test_fn_038_gate_b8_docs_canary_triage_index_token_presence_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        triage_index_lines = [
            line.strip()
            for line in gate_b8_lines
            if line.strip().startswith("- Docs-canary coverage triage index (FN-031..FN-035):")
        ]

        self.assertEqual(
            len(triage_index_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 docs-canary triage index bullet",
        )

        triage_index_line = triage_index_lines[0]
        coverage_tokens = [
            "README/runtime",
            "snapshot-name parity",
            "fail-line wording/singularity",
            "token-literal parity",
        ]
        for token in coverage_tokens:
            self.assertIn(
                token,
                triage_index_line,
                "docs/quality-gates.md: missing Gate B8 docs-canary triage coverage token: "
                f"{token}",
            )

    def test_fn_039_docs_section_boundary_canary_for_envelope_contract_bullets(self) -> None:
        readme_lines = self.readme_doc.splitlines()
        readme_start_marker = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        self.assertIn(
            readme_start_marker,
            readme_lines,
            "README.md: missing error-envelope section marker",
        )
        readme_start = readme_lines.index(readme_start_marker) + 1
        readme_end = len(readme_lines)
        for index in range(readme_start, len(readme_lines)):
            if readme_lines[index].startswith("### "):
                readme_end = index
                break

        readme_section_lines = readme_lines[readme_start:readme_end]
        readme_outside_lines = readme_lines[:readme_start] + readme_lines[readme_end:]
        readme_boundary_bullets = [
            "- Ordered-details-Vertrag ist fix: `details` serialisiert immer zuerst `error_type`, dann "
            "`command` (CLI + direkte Envelope-Builder-Pfade)",
            "- Runtime-Parität ist fix: Runtime-Fehler führen immer `stage=\"runtime\"` und "
            "`details.command=\"eval\"`; Adapter-Fehler werden gegen direkte "
            "`build_error_envelope(...)`-Outputs verglichen",
        ]
        for bullet in readme_boundary_bullets:
            self.assertEqual(
                sum(1 for line in readme_section_lines if line.strip() == bullet),
                1,
                "README.md: expected exactly one envelope-contract boundary bullet inside the "
                f"error-envelope section: {bullet}",
            )
            self.assertEqual(
                sum(1 for line in readme_outside_lines if line.strip() == bullet),
                0,
                "README.md: envelope-contract boundary bullet must not appear outside the "
                f"error-envelope section: {bullet}",
            )

        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_start_marker = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"
        self.assertIn(
            runtime_start_marker,
            runtime_lines,
            "docs/runtime-determinism.md: missing deterministic envelope adapter section marker",
        )
        runtime_start = runtime_lines.index(runtime_start_marker) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_section_lines = runtime_lines[runtime_start:runtime_end]
        runtime_outside_lines = runtime_lines[:runtime_start] + runtime_lines[runtime_end:]
        runtime_boundary_bullets = [
            "- Stable runtime parity contract for adapter + direct-builder lanes: adapter failures "
            "and direct `build_error_envelope(...)` outputs keep `stage=\"runtime\"` and "
            "`details.command=\"eval\"`.",
            "- Ordered details contract is deterministic: `error.details` serializes `error_type` "
            "first, then `command`.",
        ]
        for bullet in runtime_boundary_bullets:
            self.assertEqual(
                sum(1 for line in runtime_section_lines if line.strip() == bullet),
                1,
                "docs/runtime-determinism.md: expected exactly one envelope-contract boundary "
                f"bullet inside deterministic adapter section: {bullet}",
            )
            self.assertEqual(
                sum(1 for line in runtime_outside_lines if line.strip() == bullet),
                0,
                "docs/runtime-determinism.md: envelope-contract boundary bullet must not appear "
                f"outside deterministic adapter section: {bullet}",
            )

    def test_fn_040_gate_b8_triage_index_phrase_order_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        triage_index_lines = [
            line.strip()
            for line in gate_b8_lines
            if line.strip().startswith("- Docs-canary coverage triage index (FN-031..FN-035):")
        ]
        self.assertEqual(
            len(triage_index_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 docs-canary triage index bullet",
        )

        triage_index_line = triage_index_lines[0]
        ordered_tokens = [
            "README/runtime",
            "snapshot-name parity",
            "fail-line wording/singularity",
            "token-literal parity",
        ]

        previous_index = -1
        for token in ordered_tokens:
            token_index = triage_index_line.find(token)
            self.assertNotEqual(
                token_index,
                -1,
                "docs/quality-gates.md: missing Gate B8 triage-index phrase token: "
                f"{token}",
            )
            self.assertGreater(
                token_index,
                previous_index,
                "docs/quality-gates.md: Gate B8 triage-index phrase order drift detected; "
                f"token out of order: {token}",
            )
            previous_index = token_index

    def test_fn_041_readme_envelope_section_heading_boundary_singularity_canary(self) -> None:
        readme_lines = self.readme_doc.splitlines()
        readme_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"

        self.assertEqual(
            readme_lines.count(readme_heading),
            1,
            "README.md: expected exactly one error-envelope section heading",
        )

        readme_start = readme_lines.index(readme_heading) + 1
        readme_end = len(readme_lines)
        for index in range(readme_start, len(readme_lines)):
            if readme_lines[index].startswith("### "):
                readme_end = index
                break

        readme_section_lines = readme_lines[readme_start:readme_end]
        expected_boundary_bullets = [
            "- Ordered-details-Vertrag ist fix: `details` serialisiert immer zuerst `error_type`, dann "
            "`command` (CLI + direkte Envelope-Builder-Pfade)",
            "- Runtime-Parität ist fix: Runtime-Fehler führen immer `stage=\"runtime\"` und "
            "`details.command=\"eval\"`; Adapter-Fehler werden gegen direkte "
            "`build_error_envelope(...)`-Outputs verglichen",
        ]

        for bullet in expected_boundary_bullets:
            self.assertEqual(
                sum(1 for line in readme_section_lines if line.strip() == bullet),
                1,
                "README.md: expected exactly one envelope bullet inside error-envelope section: "
                f"{bullet}",
            )
            self.assertEqual(
                sum(1 for line in readme_lines if line.strip() == bullet),
                1,
                "README.md: envelope-contract bullet must remain unique and section-scoped: "
                f"{bullet}",
            )

    def test_fn_042_runtime_determinism_adapter_section_boundary_singularity_canary(self) -> None:
        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"

        self.assertEqual(
            runtime_lines.count(runtime_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one deterministic adapter section marker",
        )

        runtime_start = runtime_lines.index(runtime_heading) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_section_lines = runtime_lines[runtime_start:runtime_end]
        expected_boundary_bullets = [
            "- Stable runtime parity contract for adapter + direct-builder lanes: adapter failures "
            "and direct `build_error_envelope(...)` outputs keep `stage=\"runtime\"` and "
            "`details.command=\"eval\"`.",
            "- Ordered details contract is deterministic: `error.details` serializes `error_type` "
            "first, then `command`.",
        ]

        for bullet in expected_boundary_bullets:
            self.assertEqual(
                sum(1 for line in runtime_section_lines if line.strip() == bullet),
                1,
                "docs/runtime-determinism.md: expected exactly one envelope bullet inside "
                f"deterministic adapter section: {bullet}",
            )
            self.assertEqual(
                sum(1 for line in runtime_lines if line.strip() == bullet),
                1,
                "docs/runtime-determinism.md: envelope-contract bullet must remain unique and "
                f"section-scoped: {bullet}",
            )

    def test_fn_043_gate_b8_triage_index_punctuation_connector_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        triage_index_lines = [
            line.strip()
            for line in gate_b8_lines
            if line.strip().startswith("- Docs-canary coverage triage index (FN-031..FN-035):")
        ]
        self.assertEqual(
            len(triage_index_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 docs-canary triage index bullet",
        )

        triage_index_line = triage_index_lines[0]
        triage_body = triage_index_line.split(":", 1)[1].strip().rstrip(".")

        self.assertIn(
            ", and ",
            triage_body,
            "docs/quality-gates.md: expected final triage-index connector to be `, and`",
        )

        pre_and, final_fragment = triage_body.rsplit(", and ", 1)
        comma_fragments = [fragment.strip() for fragment in pre_and.split(", ")]
        fragments = comma_fragments + [final_fragment.strip()]
        self.assertEqual(
            fragments,
            [
                "cross-doc parity wording (README/runtime)",
                "canonical runtime snapshot-name parity",
                "Gate B8 fail-line wording/singularity",
                "README/runtime token-literal parity",
            ],
            "docs/quality-gates.md: triage-index connector/punctuation contract drift",
        )

    def test_fn_044_readme_envelope_section_adjacency_boundary_canary(self) -> None:
        readme_lines = self.readme_doc.splitlines()
        section_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"

        self.assertIn(section_heading, readme_lines, "README.md: missing error-envelope section heading")
        section_start = readme_lines.index(section_heading) + 1

        next_heading_index = len(readme_lines)
        for index in range(section_start, len(readme_lines)):
            if readme_lines[index].startswith("### "):
                next_heading_index = index
                break

        self.assertNotEqual(
            next_heading_index,
            len(readme_lines),
            "README.md: missing adjacent heading after error-envelope section",
        )
        self.assertEqual(
            readme_lines[next_heading_index].strip(),
            "### Check-Lanes (Quality Gates)",
            "README.md: error-envelope section must terminate at adjacent Check-Lanes heading",
        )

        section_lines = readme_lines[section_start:next_heading_index]
        check_lanes_tail = readme_lines[next_heading_index + 1 :]

        section_tokens = [
            "Ordered-details-Vertrag ist fix",
            "Runtime-Parität ist fix",
            "runtime.eval.eval_policies_envelope(...)",
        ]
        for token in section_tokens:
            self.assertGreater(
                sum(token in line for line in section_lines),
                0,
                "README.md: expected token inside error-envelope section: "
                f"{token}",
            )
            self.assertEqual(
                sum(token in line for line in check_lanes_tail),
                0,
                "README.md: error-envelope token must not bleed into adjacent sections: "
                f"{token}",
            )

        last_non_empty_before_heading = ""
        for line in reversed(section_lines):
            if line.strip():
                last_non_empty_before_heading = line.strip()
                break

        self.assertEqual(
            last_non_empty_before_heading,
            "- Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller",
            "README.md: error-envelope section boundary drift before Check-Lanes heading",
        )

    def test_fn_045_runtime_deterministic_adapter_bullet_order_canary(self) -> None:
        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"

        self.assertIn(
            runtime_heading,
            runtime_lines,
            "docs/runtime-determinism.md: missing deterministic adapter section marker",
        )

        runtime_start = runtime_lines.index(runtime_heading) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_section_lines = runtime_lines[runtime_start:runtime_end]
        ordered_bullets = [
            "- Stable code mapping for captured runtime failures:",
            "- Stable runtime parity contract for adapter + direct-builder lanes: adapter failures and direct `build_error_envelope(...)` outputs keep `stage=\"runtime\"` and `details.command=\"eval\"`.",
            "- Ordered details contract is deterministic: `error.details` serializes `error_type` first, then `command`.",
        ]

        indices = []
        for bullet in ordered_bullets:
            self.assertEqual(
                sum(1 for line in runtime_section_lines if line.strip() == bullet),
                1,
                "docs/runtime-determinism.md: expected exactly one deterministic adapter bullet: "
                f"{bullet}",
            )
            indices.append(next(i for i, line in enumerate(runtime_section_lines) if line.strip() == bullet))

        self.assertEqual(
            indices,
            sorted(indices),
            "docs/runtime-determinism.md: deterministic adapter bullet order drift (code mapping -> runtime parity -> ordered details)",
        )

    def test_fn_046_gate_b8_triage_index_terminal_punctuation_exactness_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        triage_index_lines = [
            line.strip()
            for line in gate_b8_lines
            if line.strip().startswith("- Docs-canary coverage triage index (FN-031..FN-035):")
        ]

        self.assertEqual(
            len(triage_index_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 docs-canary triage index bullet",
        )

        triage_index_line = triage_index_lines[0]
        triage_body = triage_index_line.split(":", 1)[1].strip()
        trailing_punctuation_match = re.search(r"([.!?]+)$", triage_body)
        self.assertIsNotNone(
            trailing_punctuation_match,
            "docs/quality-gates.md: triage-index bullet must end with terminal punctuation",
        )
        self.assertEqual(
            trailing_punctuation_match.group(1),
            ".",
            "docs/quality-gates.md: triage-index terminal punctuation drift, expected exactly one trailing period",
        )

    def test_fn_047_readme_envelope_to_check_lanes_blank_line_boundary_canary(self) -> None:
        readme_lines = self.readme_doc.splitlines()
        terminal_bullet = (
            "- Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller"
        )
        check_lanes_heading = "### Check-Lanes (Quality Gates)"

        terminal_indices = [
            index for index, line in enumerate(readme_lines) if line.strip() == terminal_bullet
        ]
        self.assertEqual(
            len(terminal_indices),
            1,
            "README.md: expected exactly one terminal error-envelope bullet",
        )
        self.assertIn(
            check_lanes_heading,
            readme_lines,
            "README.md: missing Check-Lanes heading after error-envelope section",
        )

        terminal_index = terminal_indices[0]
        check_lanes_index = readme_lines.index(check_lanes_heading)
        self.assertLess(
            terminal_index,
            check_lanes_index,
            "README.md: terminal error-envelope bullet must appear before Check-Lanes heading",
        )

        separator_lines = readme_lines[terminal_index + 1 : check_lanes_index]
        self.assertEqual(
            len(separator_lines),
            1,
            "README.md: expected exactly one separator line between error-envelope tail and Check-Lanes heading",
        )
        self.assertEqual(
            separator_lines[0],
            "",
            "README.md: separator line between error-envelope tail and Check-Lanes heading must be a single blank line",
        )

    def test_fn_048_runtime_code_mapping_sub_bullet_scope_order_canary(self) -> None:
        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"

        self.assertIn(
            runtime_heading,
            runtime_lines,
            "docs/runtime-determinism.md: missing deterministic adapter section marker",
        )

        runtime_start = runtime_lines.index(runtime_heading) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_section_lines = runtime_lines[runtime_start:runtime_end]
        code_mapping_parent = "- Stable code mapping for captured runtime failures:"
        type_error_sub_bullet = "- `TypeError -> ERZ_RUNTIME_CONTRACT`"
        value_error_sub_bullet = "- `ValueError -> ERZ_RUNTIME_VALUE`"
        runtime_parity_bullet = (
            "- Stable runtime parity contract for adapter + direct-builder lanes: adapter failures "
            "and direct `build_error_envelope(...)` outputs keep `stage=\"runtime\"` and "
            "`details.command=\"eval\"`."
        )
        ordered_details_bullet = (
            "- Ordered details contract is deterministic: `error.details` serializes `error_type` "
            "first, then `command`."
        )

        for bullet in [
            code_mapping_parent,
            type_error_sub_bullet,
            value_error_sub_bullet,
            runtime_parity_bullet,
            ordered_details_bullet,
        ]:
            self.assertEqual(
                sum(1 for line in runtime_section_lines if line.strip() == bullet),
                1,
                "docs/runtime-determinism.md: expected exactly one deterministic adapter bullet: "
                f"{bullet}",
            )

        parent_index = next(
            index for index, line in enumerate(runtime_section_lines) if line.strip() == code_mapping_parent
        )
        type_error_index = next(
            index
            for index, line in enumerate(runtime_section_lines)
            if line.strip() == type_error_sub_bullet
        )
        value_error_index = next(
            index
            for index, line in enumerate(runtime_section_lines)
            if line.strip() == value_error_sub_bullet
        )
        runtime_parity_index = next(
            index
            for index, line in enumerate(runtime_section_lines)
            if line.strip() == runtime_parity_bullet
        )
        ordered_details_index = next(
            index
            for index, line in enumerate(runtime_section_lines)
            if line.strip() == ordered_details_bullet
        )

        self.assertEqual(
            [type_error_index, value_error_index],
            [parent_index + 1, parent_index + 2],
            "docs/runtime-determinism.md: runtime code-mapping sub-bullets must remain directly nested under the code-mapping parent bullet",
        )
        self.assertTrue(
            runtime_section_lines[type_error_index].startswith("     - ")
            and runtime_section_lines[value_error_index].startswith("     - "),
            "docs/runtime-determinism.md: runtime code-mapping sub-bullets must keep nested indentation",
        )
        self.assertLess(
            value_error_index,
            runtime_parity_index,
            "docs/runtime-determinism.md: runtime code-mapping sub-bullets must appear before runtime parity bullet",
        )
        self.assertLess(
            runtime_parity_index,
            ordered_details_index,
            "docs/runtime-determinism.md: runtime parity bullet must remain before ordered-details bullet",
        )

    def test_fn_049_gate_b8_triage_index_label_range_literal_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        triage_index_lines = [
            line.strip()
            for line in gate_b8_lines
            if line.strip().startswith("- Docs-canary coverage triage index (")
        ]
        self.assertEqual(
            len(triage_index_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 docs-canary triage index bullet",
        )

        triage_index_line = triage_index_lines[0]
        expected_label_prefix = "- Docs-canary coverage triage index (FN-031..FN-035):"
        self.assertTrue(
            triage_index_line.startswith(expected_label_prefix),
            "docs/quality-gates.md: Gate B8 triage-index label-range literal drift, expected exact `(FN-031..FN-035)`",
        )

        range_tokens = re.findall(r"\(FN-\d+\.\.FN-\d+\)", triage_index_line)
        self.assertEqual(
            range_tokens,
            ["(FN-031..FN-035)"],
            "docs/quality-gates.md: Gate B8 triage-index label must contain exactly one canonical range literal `(FN-031..FN-035)`",
        )

    def test_fn_050_readme_runtime_adapter_nested_bullet_indentation_canary(self) -> None:
        readme_lines = self.readme_doc.splitlines()
        section_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        runtime_adapter_parent = "- Runtime-Adapter: `runtime.eval.eval_policies_envelope(...)`"

        self.assertIn(section_heading, readme_lines, "README.md: missing error-envelope section heading")
        section_start = readme_lines.index(section_heading) + 1
        section_end = len(readme_lines)
        for index in range(section_start, len(readme_lines)):
            if readme_lines[index].startswith("### "):
                section_end = index
                break

        section_lines = readme_lines[section_start:section_end]
        self.assertEqual(
            sum(1 for line in section_lines if line.strip() == runtime_adapter_parent),
            1,
            "README.md: expected exactly one runtime-adapter parent bullet in error-envelope section",
        )

        parent_index = next(
            index for index, line in enumerate(section_lines) if line.strip() == runtime_adapter_parent
        )

        nested_lines: list[tuple[int, str]] = []
        for index in range(parent_index + 1, len(section_lines)):
            current_line = section_lines[index]
            if current_line.startswith("  - "):
                nested_lines.append((index, current_line))
                continue
            break

        expected_nested_bullets = [
            "- Erfolg: `{ \"actions\": [...], \"trace\": [...] }` (ohne `error` Feld)",
            "- Laufzeitvertrag-/Wertfehler: `{ \"actions\": [], \"trace\": [], \"error\": { ...Envelope... } }`",
            "- Failure-Shape ist deterministisch, wiederholte Läufe liefern dieselbe Payload-Struktur",
            "- Code-Mapping ist stabil: `TypeError -> ERZ_RUNTIME_CONTRACT`, `ValueError -> ERZ_RUNTIME_VALUE`",
            "- Runtime-Parität ist fix: Runtime-Fehler führen immer `stage=\"runtime\"` und `details.command=\"eval\"`; Adapter-Fehler werden gegen direkte `build_error_envelope(...)`-Outputs verglichen",
            "- Consumer-Guidance: Fehler über das Vorhandensein von `error` erkennen (nicht über leere `actions`/`trace`)",
            "- Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller",
        ]

        self.assertEqual(
            len(nested_lines),
            len(expected_nested_bullets),
            "README.md: runtime-adapter nested bullet block size drift",
        )
        self.assertEqual(
            [index for index, _ in nested_lines],
            list(range(parent_index + 1, parent_index + 1 + len(expected_nested_bullets))),
            "README.md: runtime-adapter sub-bullets must remain contiguous directly under the parent bullet",
        )
        self.assertTrue(
            all(line.startswith("  - ") for _, line in nested_lines),
            "README.md: runtime-adapter sub-bullets must keep two-space nested indentation",
        )

        nested_line_stripped = [line.strip() for _, line in nested_lines]
        self.assertEqual(
            nested_line_stripped,
            expected_nested_bullets,
            "README.md: runtime-adapter nested bullet literals/order drift",
        )

    def test_fn_051_runtime_deterministic_adapter_tail_bullet_adjacency_canary(self) -> None:
        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"

        self.assertIn(
            runtime_heading,
            runtime_lines,
            "docs/runtime-determinism.md: missing deterministic adapter section marker",
        )

        runtime_start = runtime_lines.index(runtime_heading) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_section_lines = runtime_lines[runtime_start:runtime_end]
        non_contract_bullet = "- Non-contract internal failures are re-raised unchanged (no envelope swallowing)."
        repeated_runs_bullet = (
            "- Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer."
        )

        self.assertEqual(
            sum(1 for line in runtime_section_lines if line.strip() == non_contract_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one non-contract-tail bullet in deterministic adapter section",
        )
        self.assertEqual(
            sum(1 for line in runtime_section_lines if line.strip() == repeated_runs_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one repeated-runs tail bullet in deterministic adapter section",
        )

        non_contract_index = next(
            index for index, line in enumerate(runtime_section_lines) if line.strip() == non_contract_bullet
        )
        repeated_runs_index = next(
            index for index, line in enumerate(runtime_section_lines) if line.strip() == repeated_runs_bullet
        )

        self.assertEqual(
            repeated_runs_index,
            non_contract_index + 1,
            "docs/runtime-determinism.md: non-contract tail bullet must remain immediately before repeated-runs bullet",
        )

    def test_fn_052_gate_b8_triage_index_canonical_fragment_count_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )

        triage_index_lines = [
            line.strip()
            for line in gate_b8_lines
            if line.strip().startswith("- Docs-canary coverage triage index (FN-031..FN-035):")
        ]
        self.assertEqual(
            len(triage_index_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 triage-index line",
        )

        triage_index_line = triage_index_lines[0]
        triage_body = triage_index_line.split(
            "- Docs-canary coverage triage index (FN-031..FN-035):", maxsplit=1
        )[1].strip()
        self.assertTrue(
            triage_body.endswith("."),
            "docs/quality-gates.md: Gate B8 triage-index line must keep terminal period",
        )

        triage_body_no_period = triage_body[:-1]
        self.assertIn(
            ", and ",
            triage_body_no_period,
            "docs/quality-gates.md: Gate B8 triage-index line must keep canonical final `, and` connector",
        )

        head, tail = triage_body_no_period.rsplit(", and ", maxsplit=1)
        fragments = [fragment.strip() for fragment in head.split(",")]
        fragments.append(tail.strip())

        expected_fragments = [
            "cross-doc parity wording (README/runtime)",
            "canonical runtime snapshot-name parity",
            "Gate B8 fail-line wording/singularity",
            "README/runtime token-literal parity",
        ]

        self.assertEqual(
            len(fragments),
            4,
            "docs/quality-gates.md: Gate B8 triage-index body must keep exactly four canonical comma-separated fragments",
        )
        self.assertEqual(
            fragments,
            expected_fragments,
            "docs/quality-gates.md: Gate B8 triage-index fragment drift detected",
        )

    def test_fn_053_readme_runtime_adapter_nested_tail_terminal_literal_canary(self) -> None:
        readme_lines = self.readme_doc.splitlines()
        section_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        runtime_adapter_parent = "- Runtime-Adapter: `runtime.eval.eval_policies_envelope(...)`"

        self.assertIn(section_heading, readme_lines, "README.md: missing error-envelope section heading")
        section_start = readme_lines.index(section_heading) + 1
        section_end = len(readme_lines)
        for index in range(section_start, len(readme_lines)):
            if readme_lines[index].startswith("### "):
                section_end = index
                break

        section_lines = readme_lines[section_start:section_end]
        self.assertEqual(
            sum(1 for line in section_lines if line.strip() == runtime_adapter_parent),
            1,
            "README.md: expected exactly one runtime-adapter parent bullet in error-envelope section",
        )

        parent_index = next(
            index for index, line in enumerate(section_lines) if line.strip() == runtime_adapter_parent
        )

        nested_line_stripped: list[str] = []
        for index in range(parent_index + 1, len(section_lines)):
            current_line = section_lines[index]
            if current_line.startswith("  - "):
                nested_line_stripped.append(current_line.strip())
                continue
            break

        expected_tail_literal = "- Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller"

        self.assertEqual(
            sum(1 for line in nested_line_stripped if line == expected_tail_literal),
            1,
            "README.md: expected exactly one runtime-adapter nested tail literal for non-contract forwarding",
        )
        self.assertEqual(
            nested_line_stripped[-1],
            expected_tail_literal,
            "README.md: runtime-adapter nested tail literal must remain the terminal nested bullet",
        )

    def test_fn_054_runtime_deterministic_adapter_repeated_runs_terminal_line_boundary_canary(self) -> None:
        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"

        self.assertIn(
            runtime_heading,
            runtime_lines,
            "docs/runtime-determinism.md: missing deterministic adapter section marker",
        )

        runtime_start = runtime_lines.index(runtime_heading) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_section_lines = runtime_lines[runtime_start:runtime_end]
        non_empty_section_lines = [line.strip() for line in runtime_section_lines if line.strip()]

        non_contract_bullet = "- Non-contract internal failures are re-raised unchanged (no envelope swallowing)."
        repeated_runs_bullet = (
            "- Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer."
        )

        self.assertEqual(
            sum(1 for line in non_empty_section_lines if line == non_contract_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one non-contract-tail bullet in deterministic adapter section",
        )
        self.assertEqual(
            sum(1 for line in non_empty_section_lines if line == repeated_runs_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one repeated-runs bullet in deterministic adapter section",
        )
        self.assertEqual(
            non_empty_section_lines[-1],
            repeated_runs_bullet,
            "docs/runtime-determinism.md: repeated-runs bullet must remain terminal non-empty line of deterministic adapter section",
        )

        non_contract_index = non_empty_section_lines.index(non_contract_bullet)
        repeated_runs_index = non_empty_section_lines.index(repeated_runs_bullet)
        self.assertEqual(
            repeated_runs_index,
            non_contract_index + 1,
            "docs/runtime-determinism.md: repeated-runs bullet must remain immediately after non-contract tail bullet",
        )

    def test_fn_055_gate_b8_triage_index_delimiter_shape_exactness_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )

        triage_index_lines = [
            line.strip()
            for line in gate_b8_lines
            if line.strip().startswith("- Docs-canary coverage triage index (FN-031..FN-035):")
        ]
        self.assertEqual(
            len(triage_index_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 triage-index line",
        )

        triage_index_line = triage_index_lines[0]
        triage_body = triage_index_line.split(
            "- Docs-canary coverage triage index (FN-031..FN-035):", maxsplit=1
        )[1].strip()
        self.assertTrue(
            triage_body.endswith("."),
            "docs/quality-gates.md: Gate B8 triage-index line must keep terminal period",
        )

        triage_body_no_period = triage_body[:-1]
        expected_body_no_period = (
            "cross-doc parity wording (README/runtime), canonical runtime snapshot-name parity, "
            "Gate B8 fail-line wording/singularity, and README/runtime token-literal parity"
        )

        self.assertEqual(
            triage_body_no_period,
            expected_body_no_period,
            "docs/quality-gates.md: Gate B8 triage-index delimiter shape drift, expected `, ` between first fragments and `, and ` before the terminal fragment",
        )
        self.assertEqual(
            triage_body_no_period.count(", and "),
            1,
            "docs/quality-gates.md: Gate B8 triage-index must keep exactly one `, and ` delimiter",
        )

    def test_fn_056_readme_runtime_adapter_nested_tail_duplicate_guard_canary(self) -> None:
        readme_lines = self.readme_doc.splitlines()
        section_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        runtime_adapter_parent = "- Runtime-Adapter: `runtime.eval.eval_policies_envelope(...)`"
        expected_tail_literal = "- Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller"

        self.assertIn(section_heading, readme_lines, "README.md: missing error-envelope section heading")
        section_start = readme_lines.index(section_heading) + 1
        section_end = len(readme_lines)
        for index in range(section_start, len(readme_lines)):
            if readme_lines[index].startswith("### "):
                section_end = index
                break

        section_lines = readme_lines[section_start:section_end]
        self.assertEqual(
            sum(1 for line in section_lines if line.strip() == runtime_adapter_parent),
            1,
            "README.md: expected exactly one runtime-adapter parent bullet in error-envelope section",
        )

        parent_index = next(
            index for index, line in enumerate(section_lines) if line.strip() == runtime_adapter_parent
        )

        nested_line_stripped: list[str] = []
        for index in range(parent_index + 1, len(section_lines)):
            current_line = section_lines[index]
            if current_line.startswith("  - "):
                nested_line_stripped.append(current_line.strip())
                continue
            break

        total_occurrences = sum(1 for line in readme_lines if line.strip() == expected_tail_literal)
        nested_occurrences = sum(1 for line in nested_line_stripped if line == expected_tail_literal)

        self.assertEqual(
            total_occurrences,
            1,
            "README.md: non-contract forwarding tail literal must appear exactly once in the entire document",
        )
        self.assertEqual(
            nested_occurrences,
            1,
            "README.md: non-contract forwarding tail literal must appear in runtime-adapter nested bullets",
        )
        self.assertEqual(
            nested_occurrences,
            total_occurrences,
            "README.md: non-contract forwarding tail literal must not appear outside runtime-adapter nested bullet block",
        )

    def test_fn_057_runtime_deterministic_adapter_terminal_tail_pair_boundary_canary(self) -> None:
        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"

        self.assertIn(
            runtime_heading,
            runtime_lines,
            "docs/runtime-determinism.md: missing deterministic adapter section marker",
        )

        runtime_start = runtime_lines.index(runtime_heading) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_section_lines = runtime_lines[runtime_start:runtime_end]
        non_empty_section_lines = [line.strip() for line in runtime_section_lines if line.strip()]

        non_contract_bullet = "- Non-contract internal failures are re-raised unchanged (no envelope swallowing)."
        repeated_runs_bullet = (
            "- Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer."
        )

        self.assertGreaterEqual(
            len(non_empty_section_lines),
            2,
            "docs/runtime-determinism.md: deterministic adapter section must contain at least two non-empty lines",
        )
        self.assertEqual(
            sum(1 for line in non_empty_section_lines if line == non_contract_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one non-contract-tail bullet in deterministic adapter section",
        )
        self.assertEqual(
            sum(1 for line in non_empty_section_lines if line == repeated_runs_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one repeated-runs bullet in deterministic adapter section",
        )
        self.assertEqual(
            non_empty_section_lines[-2:],
            [non_contract_bullet, repeated_runs_bullet],
            "docs/runtime-determinism.md: deterministic adapter section must end with exact two-line tail pair (non-contract, then repeated-runs)",
        )

    def test_fn_058_gate_b8_triage_index_lead_token_singularity_canary(self) -> None:
        gate_b8_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )

        expected_lead_token = "- Docs-canary coverage triage index (FN-031..FN-035):"
        triage_lead_lines = [
            line.strip()
            for line in gate_b8_lines
            if line.strip().startswith("- Docs-canary coverage triage index")
        ]

        self.assertEqual(
            len(triage_lead_lines),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 docs-canary triage-index lead-token line",
        )
        self.assertTrue(
            triage_lead_lines[0].startswith(expected_lead_token),
            "docs/quality-gates.md: Gate B8 triage-index lead token must remain exact `(FN-031..FN-035)` line prefix",
        )

        variant_prefixed_lines = [
            line for line in triage_lead_lines if not line.startswith(expected_lead_token)
        ]
        self.assertEqual(
            variant_prefixed_lines,
            [],
            "docs/quality-gates.md: Gate B8 must not contain variant-prefixed triage-index lead-token lines",
        )

    def test_fn_059_readme_runtime_adapter_nested_tail_indentation_shape_canary(self) -> None:
        readme_lines = self.readme_doc.splitlines()
        section_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        runtime_adapter_parent = "- Runtime-Adapter: `runtime.eval.eval_policies_envelope(...)`"
        expected_tail_literal = "- Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller"

        self.assertIn(section_heading, readme_lines, "README.md: missing error-envelope section heading")
        section_start = readme_lines.index(section_heading) + 1
        section_end = len(readme_lines)
        for index in range(section_start, len(readme_lines)):
            if readme_lines[index].startswith("### "):
                section_end = index
                break

        section_lines = readme_lines[section_start:section_end]
        self.assertEqual(
            sum(1 for line in section_lines if line.strip() == runtime_adapter_parent),
            1,
            "README.md: expected exactly one runtime-adapter parent bullet in error-envelope section",
        )

        parent_index = next(
            index for index, line in enumerate(section_lines) if line.strip() == runtime_adapter_parent
        )

        nested_tail_raw_lines: list[str] = []
        for index in range(parent_index + 1, len(section_lines)):
            current_line = section_lines[index]
            if current_line.startswith("  - "):
                if current_line.strip() == expected_tail_literal:
                    nested_tail_raw_lines.append(current_line)
                continue
            break

        total_occurrences = sum(1 for line in readme_lines if line.strip() == expected_tail_literal)
        top_level_occurrences = sum(1 for line in readme_lines if line == expected_tail_literal)

        self.assertEqual(
            total_occurrences,
            1,
            "README.md: non-contract forwarding tail literal must appear exactly once",
        )
        self.assertEqual(
            len(nested_tail_raw_lines),
            1,
            "README.md: non-contract forwarding tail literal must appear exactly once as nested runtime-adapter bullet",
        )
        self.assertEqual(
            top_level_occurrences,
            0,
            "README.md: non-contract forwarding tail literal must not appear as top-level bullet",
        )
        self.assertTrue(
            nested_tail_raw_lines[0].startswith("  - "),
            "README.md: non-contract forwarding tail literal must keep exact two-space nested bullet indentation under runtime-adapter parent",
        )

    def test_fn_060_runtime_deterministic_adapter_tail_pair_duplication_guard_canary(self) -> None:
        runtime_lines = self.runtime_determinism_doc.splitlines()
        runtime_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"

        self.assertIn(
            runtime_heading,
            runtime_lines,
            "docs/runtime-determinism.md: missing deterministic adapter section marker",
        )

        runtime_start = runtime_lines.index(runtime_heading) + 1
        runtime_end = len(runtime_lines)
        for index in range(runtime_start, len(runtime_lines)):
            if re.match(r"^\d+\. ", runtime_lines[index]) or runtime_lines[index].startswith("## "):
                runtime_end = index
                break

        runtime_section_lines = runtime_lines[runtime_start:runtime_end]
        non_empty_section_lines = [line.strip() for line in runtime_section_lines if line.strip()]

        non_contract_bullet = "- Non-contract internal failures are re-raised unchanged (no envelope swallowing)."
        repeated_runs_bullet = (
            "- Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer."
        )

        tail_pair_candidate_indices = [
            index
            for index, line in enumerate(non_empty_section_lines)
            if line in {non_contract_bullet, repeated_runs_bullet}
        ]

        self.assertEqual(
            sum(1 for line in non_empty_section_lines if line == non_contract_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one non-contract-tail bullet in deterministic adapter section",
        )
        self.assertEqual(
            sum(1 for line in non_empty_section_lines if line == repeated_runs_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one repeated-runs tail bullet in deterministic adapter section",
        )
        self.assertEqual(
            tail_pair_candidate_indices,
            [len(non_empty_section_lines) - 2, len(non_empty_section_lines) - 1],
            "docs/runtime-determinism.md: deterministic adapter tail-pair bullets must appear exactly once and only as terminal two non-empty lines",
        )

    def test_fn_061_gate_b8_triage_index_lead_line_anchor_uniqueness_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading = "### Gate B8: Machine-readable error envelope contract (v0.2 prep)"
        expected_lead_line = (
            "- Docs-canary coverage triage index (FN-031..FN-035): cross-doc parity wording "
            "(README/runtime), canonical runtime snapshot-name parity, Gate B8 fail-line "
            "wording/singularity, and README/runtime token-literal parity."
        )

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 heading",
        )

        gate_start = lines.index(heading) + 1
        gate_end = len(lines)
        for index in range(gate_start, len(lines)):
            if lines[index].startswith("### Gate ") or lines[index].startswith("## "):
                gate_end = index
                break

        gate_b8_lines = lines[gate_start:gate_end]
        outside_gate_b8_lines = lines[:gate_start] + lines[gate_end:]

        self.assertEqual(
            sum(1 for line in gate_b8_lines if line.strip() == expected_lead_line),
            1,
            "docs/quality-gates.md: canonical Gate B8 triage-index lead line must appear exactly once inside Gate B8",
        )
        self.assertEqual(
            sum(1 for line in outside_gate_b8_lines if line.strip() == expected_lead_line),
            0,
            "docs/quality-gates.md: canonical Gate B8 triage-index lead line must not appear outside Gate B8",
        )

    def test_fn_062_readme_runtime_adapter_tail_literal_section_scope_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        section_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        expected_tail_literal = "- Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller"

        self.assertEqual(
            lines.count(section_heading),
            1,
            "README.md: expected exactly one `Fehler-Envelope in --json-errors` section heading",
        )

        section_start = lines.index(section_heading) + 1
        section_end = len(lines)
        for index in range(section_start, len(lines)):
            if lines[index].startswith("### "):
                section_end = index
                break

        section_lines = lines[section_start:section_end]
        outside_section_lines = lines[:section_start] + lines[section_end:]

        self.assertEqual(
            sum(1 for line in section_lines if line.strip() == expected_tail_literal),
            1,
            "README.md: non-contract forwarding tail literal must appear exactly once inside `Fehler-Envelope in --json-errors` section",
        )
        self.assertEqual(
            sum(1 for line in outside_section_lines if line.strip() == expected_tail_literal),
            0,
            "README.md: non-contract forwarding tail literal must not appear outside `Fehler-Envelope in --json-errors` section",
        )

    def test_fn_063_runtime_deterministic_adapter_tail_pair_blank_line_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"

        non_contract_bullet = "- Non-contract internal failures are re-raised unchanged (no envelope swallowing)."
        repeated_runs_bullet = (
            "- Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer."
        )

        self.assertIn(heading, lines, "docs/runtime-determinism.md: missing deterministic adapter section marker")

        section_start = lines.index(heading) + 1
        section_end = len(lines)
        for index in range(section_start, len(lines)):
            if re.match(r"^\d+\. ", lines[index]) or lines[index].startswith("## "):
                section_end = index
                break

        section_lines = lines[section_start:section_end]
        non_empty_with_indices = [
            (index, line.strip()) for index, line in enumerate(section_lines) if line.strip()
        ]

        self.assertGreaterEqual(
            len(non_empty_with_indices),
            2,
            "docs/runtime-determinism.md: deterministic adapter section must contain at least two non-empty lines",
        )

        self.assertEqual(
            non_empty_with_indices[-2][1],
            non_contract_bullet,
            "docs/runtime-determinism.md: deterministic adapter penultimate non-empty line must be non-contract-tail bullet",
        )
        self.assertEqual(
            non_empty_with_indices[-1][1],
            repeated_runs_bullet,
            "docs/runtime-determinism.md: deterministic adapter terminal non-empty line must be repeated-runs tail bullet",
        )

        repeated_runs_raw_index = non_empty_with_indices[-1][0]
        trailing_lines_before_next_heading = section_lines[repeated_runs_raw_index + 1 :]

        self.assertTrue(
            all(not line.strip() for line in trailing_lines_before_next_heading),
            "docs/runtime-determinism.md: only blank separator lines are allowed after deterministic adapter tail pair before next heading boundary",
        )

    def test_fn_064_gate_b8_triage_index_lead_line_standalone_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading = "### Gate B8: Machine-readable error envelope contract (v0.2 prep)"
        triage_prefix = "- Docs-canary coverage triage index (FN-031..FN-035):"

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 heading",
        )

        gate_start = lines.index(heading) + 1
        gate_end = len(lines)
        for index in range(gate_start, len(lines)):
            if lines[index].startswith("### Gate ") or lines[index].startswith("## "):
                gate_end = index
                break

        gate_b8_lines = lines[gate_start:gate_end]
        triage_indices = [
            index for index, line in enumerate(gate_b8_lines) if line.strip().startswith(triage_prefix)
        ]

        self.assertEqual(
            len(triage_indices),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 triage-index lead line",
        )

        triage_line_index = triage_indices[0]
        triage_line = gate_b8_lines[triage_line_index].strip()
        self.assertTrue(
            triage_line.endswith("."),
            "docs/quality-gates.md: Gate B8 triage-index lead line must keep terminal period",
        )

        continuation_candidate = (
            gate_b8_lines[triage_line_index + 1]
            if triage_line_index + 1 < len(gate_b8_lines)
            else ""
        )
        self.assertTrue(
            (not continuation_candidate.strip())
            or continuation_candidate.lstrip().startswith("- "),
            "docs/quality-gates.md: Gate B8 triage-index lead line must remain standalone, no continuation-line spillover",
        )

    def test_fn_065_readme_runtime_adapter_tail_literal_parent_scope_adjacency_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        section_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        runtime_parent_bullet = "- Runtime-Adapter: `runtime.eval.eval_policies_envelope(...)`"
        expected_tail_literal = "Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller"

        self.assertEqual(
            lines.count(section_heading),
            1,
            "README.md: expected exactly one `Fehler-Envelope in --json-errors` section heading",
        )

        section_start = lines.index(section_heading) + 1
        section_end = len(lines)
        for index in range(section_start, len(lines)):
            if lines[index].startswith("### "):
                section_end = index
                break

        section_lines = lines[section_start:section_end]
        parent_indices = [
            index for index, line in enumerate(section_lines) if line.strip() == runtime_parent_bullet
        ]

        self.assertEqual(
            len(parent_indices),
            1,
            "README.md: expected exactly one runtime-adapter parent bullet in error-envelope section",
        )

        parent_index = parent_indices[0]
        nested_block = []
        for line in section_lines[parent_index + 1 :]:
            if line.startswith("  - "):
                nested_block.append(line)
                continue
            if line.strip() == "":
                break
            if line.startswith("- "):
                break
            nested_block.append(line)

        nested_tail_line = f"  - {expected_tail_literal}"
        self.assertEqual(
            nested_block.count(nested_tail_line),
            1,
            "README.md: non-contract forwarding tail literal must appear exactly once as nested runtime-adapter bullet",
        )

        non_empty_nested = [line for line in nested_block if line.strip()]
        self.assertTrue(
            non_empty_nested,
            "README.md: runtime-adapter nested bullet block must not be empty",
        )
        self.assertEqual(
            non_empty_nested[-1],
            nested_tail_line,
            "README.md: non-contract forwarding tail literal must remain terminal nested bullet under runtime-adapter parent",
        )

    def test_fn_066_runtime_deterministic_adapter_tail_pair_heading_adjacency_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        section_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"
        next_heading = "## Rule Engine v0 semantics"
        non_contract_bullet = "- Non-contract internal failures are re-raised unchanged (no envelope swallowing)."
        repeated_runs_bullet = (
            "- Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer."
        )

        self.assertIn(section_heading, lines, "docs/runtime-determinism.md: missing deterministic adapter section marker")
        self.assertEqual(
            lines.count(next_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `## Rule Engine v0 semantics` heading",
        )

        section_start = lines.index(section_heading) + 1
        next_heading_index = lines.index(next_heading)
        self.assertGreater(
            next_heading_index,
            section_start,
            "docs/runtime-determinism.md: rule-engine heading must appear after deterministic adapter section",
        )

        section_lines = lines[section_start:next_heading_index]
        self.assertEqual(
            sum(1 for line in section_lines if line.strip() == non_contract_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one non-contract tail bullet in deterministic adapter section",
        )
        self.assertEqual(
            sum(1 for line in section_lines if line.strip() == repeated_runs_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one repeated-runs bullet in deterministic adapter section",
        )

        non_contract_index = next(
            index for index, line in enumerate(section_lines) if line.strip() == non_contract_bullet
        )
        repeated_index = next(
            index for index, line in enumerate(section_lines) if line.strip() == repeated_runs_bullet
        )

        self.assertEqual(
            repeated_index,
            non_contract_index + 1,
            "docs/runtime-determinism.md: deterministic adapter tail pair must keep non-contract bullet immediately before repeated-runs bullet",
        )

        trailing_lines = section_lines[repeated_index + 1 :]
        self.assertEqual(
            len(trailing_lines),
            1,
            "docs/runtime-determinism.md: expected exactly one separator line between repeated-runs bullet and `## Rule Engine v0 semantics` heading",
        )
        self.assertEqual(
            trailing_lines[0].strip(),
            "",
            "docs/runtime-determinism.md: separator between repeated-runs bullet and `## Rule Engine v0 semantics` heading must be blank",
        )

    def test_fn_067_gate_b8_triage_index_successor_line_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading = "### Gate B8: Machine-readable error envelope contract (v0.2 prep)"
        triage_prefix = "- Docs-canary coverage triage index (FN-031..FN-035):"
        fail_prefix = "- **Fail if:**"

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 heading",
        )

        gate_start = lines.index(heading) + 1
        gate_end = len(lines)
        for index in range(gate_start, len(lines)):
            if lines[index].startswith("### Gate ") or lines[index].startswith("## "):
                gate_end = index
                break

        gate_b8_lines = lines[gate_start:gate_end]
        triage_indices = [
            index for index, line in enumerate(gate_b8_lines) if line.strip().startswith(triage_prefix)
        ]

        self.assertEqual(
            len(triage_indices),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 triage-index lead line",
        )

        triage_index = triage_indices[0]
        self.assertLess(
            triage_index + 1,
            len(gate_b8_lines),
            "docs/quality-gates.md: Gate B8 triage-index lead line must have an immediate successor line",
        )

        successor_line = gate_b8_lines[triage_index + 1].strip()
        self.assertTrue(
            successor_line.startswith(fail_prefix),
            "docs/quality-gates.md: immediate successor line after Gate B8 triage-index lead line must be the `- **Fail if:** ...` bullet",
        )

    def test_fn_068_readme_runtime_adapter_tail_to_heading_separator_exactness_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        section_heading = "Fehler-Envelope in `--json-errors` Modus (v0.2 prep):"
        check_lanes_heading = "### Check-Lanes (Quality Gates)"
        nested_tail_line = "  - Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller"

        self.assertEqual(
            lines.count(section_heading),
            1,
            "README.md: expected exactly one `Fehler-Envelope in --json-errors` section heading",
        )
        self.assertEqual(
            lines.count(check_lanes_heading),
            1,
            "README.md: expected exactly one `### Check-Lanes (Quality Gates)` heading",
        )
        self.assertEqual(
            lines.count(nested_tail_line),
            1,
            "README.md: expected exactly one runtime-adapter nested tail bullet literal",
        )

        tail_index = lines.index(nested_tail_line)
        heading_index = lines.index(check_lanes_heading)

        self.assertEqual(
            heading_index,
            tail_index + 2,
            "README.md: runtime-adapter tail bullet must be followed by exactly one blank separator line before `### Check-Lanes (Quality Gates)`",
        )
        self.assertEqual(
            lines[tail_index + 1].strip(),
            "",
            "README.md: separator line between runtime-adapter tail bullet and `### Check-Lanes (Quality Gates)` must be blank",
        )

    def test_fn_069_runtime_deterministic_adapter_to_rule_engine_heading_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        section_heading = "6. **Deterministic envelope adapter shape (`eval_policies_envelope`)**"
        next_heading = "## Rule Engine v0 semantics"
        repeated_runs_bullet = (
            "- Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer."
        )

        self.assertIn(section_heading, lines, "docs/runtime-determinism.md: missing deterministic adapter section marker")
        self.assertEqual(
            lines.count(next_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `## Rule Engine v0 semantics` heading",
        )

        section_start = lines.index(section_heading) + 1
        section_end = lines.index(next_heading)
        section_lines = lines[section_start:section_end]

        repeated_runs_indices = [
            index for index, line in enumerate(section_lines) if line.strip() == repeated_runs_bullet
        ]
        self.assertEqual(
            len(repeated_runs_indices),
            1,
            "docs/runtime-determinism.md: expected exactly one repeated-runs tail bullet in deterministic adapter section",
        )

        repeated_runs_index = repeated_runs_indices[0]
        trailing_lines = section_lines[repeated_runs_index + 1 :]

        self.assertEqual(
            len(trailing_lines),
            1,
            "docs/runtime-determinism.md: deterministic adapter section must end with exactly one separator line before `## Rule Engine v0 semantics`",
        )
        self.assertEqual(
            trailing_lines[0].strip(),
            "",
            "docs/runtime-determinism.md: only one blank separator line is allowed between deterministic adapter tail and `## Rule Engine v0 semantics`",
        )

    def test_fn_070_gate_b8_fail_line_terminal_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading = "### Gate B8: Machine-readable error envelope contract (v0.2 prep)"
        fail_prefix = "- **Fail if:**"

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 heading",
        )

        gate_start = lines.index(heading) + 1
        gate_end = len(lines)
        for index in range(gate_start, len(lines)):
            if lines[index].startswith("### Gate ") or lines[index].startswith("## "):
                gate_end = index
                break

        gate_b8_lines = lines[gate_start:gate_end]
        fail_indices = [
            index for index, line in enumerate(gate_b8_lines) if line.strip().startswith(fail_prefix)
        ]

        self.assertEqual(
            len(fail_indices),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 fail-condition bullet",
        )

        fail_index = fail_indices[0]
        trailing_non_empty = [line for line in gate_b8_lines[fail_index + 1 :] if line.strip()]
        self.assertEqual(
            trailing_non_empty,
            [],
            "docs/quality-gates.md: Gate B8 fail-condition bullet must be terminal before section boundary (no trailing non-empty lines)",
        )

    def test_fn_071_readme_check_lanes_heading_predecessor_boundary_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        check_lanes_heading = "### Check-Lanes (Quality Gates)"
        nested_tail_line = "  - Nicht-Vertragsfehler werden nicht verschluckt und gehen weiter an den Caller"

        self.assertEqual(
            lines.count(check_lanes_heading),
            1,
            "README.md: expected exactly one `### Check-Lanes (Quality Gates)` heading",
        )
        self.assertEqual(
            lines.count(nested_tail_line),
            1,
            "README.md: expected exactly one runtime-adapter nested tail bullet literal",
        )

        heading_index = lines.index(check_lanes_heading)
        tail_index = lines.index(nested_tail_line)

        self.assertGreater(
            heading_index,
            0,
            "README.md: `### Check-Lanes (Quality Gates)` heading must have a predecessor line",
        )
        self.assertEqual(
            lines[heading_index - 1].strip(),
            "",
            "README.md: immediate predecessor line for `### Check-Lanes (Quality Gates)` must be blank",
        )
        self.assertEqual(
            heading_index,
            tail_index + 2,
            "README.md: `### Check-Lanes (Quality Gates)` must be separated from runtime-adapter tail by exactly one blank line",
        )

    def test_fn_072_runtime_rule_engine_heading_immediate_predecessor_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        next_heading = "## Rule Engine v0 semantics"
        repeated_runs_bullet = (
            "- Repeated runs with identical failing input produce byte-equivalent JSON once serialized via the shared envelope renderer."
        )

        self.assertEqual(
            lines.count(next_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `## Rule Engine v0 semantics` heading",
        )
        self.assertEqual(
            lines.count(f"   {repeated_runs_bullet}"),
            1,
            "docs/runtime-determinism.md: expected exactly one deterministic-adapter repeated-runs tail bullet",
        )

        heading_index = lines.index(next_heading)
        self.assertGreater(
            heading_index,
            1,
            "docs/runtime-determinism.md: `## Rule Engine v0 semantics` must have immediate predecessor context",
        )
        self.assertEqual(
            lines[heading_index - 1].strip(),
            "",
            "docs/runtime-determinism.md: immediate predecessor line before `## Rule Engine v0 semantics` must be blank",
        )
        self.assertEqual(
            lines[heading_index - 2].strip(),
            repeated_runs_bullet,
            "docs/runtime-determinism.md: blank predecessor before `## Rule Engine v0 semantics` must be immediately preceded by repeated-runs tail bullet",
        )

    def test_fn_073_gate_b8_fail_line_section_scope_singularity_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        fail_line = (
            "- **Fail if:** JSON mode drifts, field shape/order changes, `details` ordered-item invariants drift, "
            "transform span snapshots drift, adapter-shape invariants regress, non-contract passthrough behavior regresses, "
            "runtime stage/details-command parity across adapter/direct-builder lanes regresses, runtime consumer contract "
            "guidance drifts, or stable-code mapping/snapshots drift."
        )

        section_count = section_lines.count(fail_line)
        doc_count = self.quality_gates_doc.splitlines().count(fail_line)

        self.assertEqual(
            section_count,
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 fail-condition line inside Gate B8 section",
        )
        self.assertEqual(
            doc_count,
            1,
            "docs/quality-gates.md: Gate B8 fail-condition line must appear exactly once in the entire document",
        )

    def test_fn_074_readme_check_lanes_heading_successor_boundary_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        heading = "### Check-Lanes (Quality Gates)"

        self.assertEqual(
            lines.count(heading),
            1,
            "README.md: expected exactly one `### Check-Lanes (Quality Gates)` heading",
        )

        heading_index = lines.index(heading)
        self.assertLess(
            heading_index + 2,
            len(lines),
            "README.md: `### Check-Lanes (Quality Gates)` must be followed by a blank line and opening ```bash fence",
        )
        self.assertEqual(
            lines[heading_index + 1].strip(),
            "",
            "README.md: `### Check-Lanes (Quality Gates)` must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[heading_index + 2].strip(),
            "```bash",
            "README.md: first non-empty line after `### Check-Lanes (Quality Gates)` must be opening ```bash fence",
        )

    def test_fn_075_runtime_rule_engine_heading_successor_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        heading = "## Rule Engine v0 semantics"
        successor_heading = "### Rule form"

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `## Rule Engine v0 semantics` heading",
        )

        heading_index = lines.index(heading)
        self.assertLess(
            heading_index + 2,
            len(lines),
            "docs/runtime-determinism.md: `## Rule Engine v0 semantics` must be followed by a blank line and `### Rule form`",
        )
        self.assertEqual(
            lines[heading_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: `## Rule Engine v0 semantics` must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[heading_index + 2].strip(),
            successor_heading,
            "docs/runtime-determinism.md: first non-empty line after `## Rule Engine v0 semantics` must be `### Rule form`",
        )

    def test_fn_076_gate_b8_fail_line_predecessor_adjacency_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.quality_gates_doc,
            heading="### Gate B8: Machine-readable error envelope contract (v0.2 prep)",
            doc_name="docs/quality-gates.md",
        )
        triage_line = (
            "  - Docs-canary coverage triage index (FN-031..FN-035): cross-doc parity wording (README/runtime), "
            "canonical runtime snapshot-name parity, Gate B8 fail-line wording/singularity, and README/runtime "
            "token-literal parity."
        )
        fail_line = (
            "- **Fail if:** JSON mode drifts, field shape/order changes, `details` ordered-item invariants drift, "
            "transform span snapshots drift, adapter-shape invariants regress, non-contract passthrough behavior regresses, "
            "runtime stage/details-command parity across adapter/direct-builder lanes regresses, runtime consumer contract "
            "guidance drifts, or stable-code mapping/snapshots drift."
        )

        self.assertEqual(
            section_lines.count(triage_line),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 docs-canary triage-index bullet",
        )
        self.assertEqual(
            section_lines.count(fail_line),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 fail-condition line",
        )

        triage_index = section_lines.index(triage_line)
        fail_index = section_lines.index(fail_line)

        self.assertEqual(
            fail_index,
            triage_index + 1,
            "docs/quality-gates.md: Gate B8 fail-condition line must be immediately preceded by docs-canary triage-index bullet",
        )

    def test_fn_077_readme_check_lanes_code_fence_close_to_note_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.readme_doc,
            heading="### Check-Lanes (Quality Gates)",
            doc_name="README.md",
        )
        opening_fence = "```bash"
        closing_fence = "```"
        wrapper_note = "`check-full.sh` ist ein dünner Wrapper um `check.sh`; beide führen denselben Full-Lane-Gatesatz aus."

        self.assertEqual(
            section_lines.count(opening_fence),
            1,
            "README.md: expected exactly one opening ```bash fence inside `### Check-Lanes (Quality Gates)` section",
        )
        closing_indices = [index for index, line in enumerate(section_lines) if line.strip() == closing_fence]
        self.assertEqual(
            len(closing_indices),
            1,
            "README.md: expected exactly one closing ``` fence inside `### Check-Lanes (Quality Gates)` section",
        )
        self.assertEqual(
            section_lines.count(wrapper_note),
            1,
            "README.md: expected exactly one `check-full.sh` wrapper-equivalence note in `### Check-Lanes (Quality Gates)` section",
        )

        closing_index = closing_indices[0]
        self.assertLess(
            closing_index + 2,
            len(section_lines),
            "README.md: closing check-lanes code fence must be followed by a blank separator line and wrapper note",
        )
        self.assertEqual(
            section_lines[closing_index + 1].strip(),
            "",
            "README.md: closing check-lanes code fence must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            section_lines[closing_index + 2].strip(),
            wrapper_note,
            "README.md: first non-empty line after closing check-lanes code fence must be the wrapper-equivalence note",
        )

    def test_fn_078_runtime_rule_form_heading_successor_content_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        heading = "### Rule form"
        lead_sentence = "`rule.when` is interpreted as a **simple AND-clause list**:"

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `### Rule form` heading",
        )
        self.assertEqual(
            lines.count(lead_sentence),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical `rule.when` lead sentence",
        )

        heading_index = lines.index(heading)
        self.assertLess(
            heading_index + 2,
            len(lines),
            "docs/runtime-determinism.md: `### Rule form` must be followed by a blank line and canonical `rule.when` lead sentence",
        )
        self.assertEqual(
            lines[heading_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: `### Rule form` must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[heading_index + 2].strip(),
            lead_sentence,
            "docs/runtime-determinism.md: first non-empty line after `### Rule form` must be the canonical `rule.when` lead sentence",
        )

    def test_fn_079_gate_b8_triage_fail_pair_singularity_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading = "### Gate B8: Machine-readable error envelope contract (v0.2 prep)"
        triage_line = (
            "  - Docs-canary coverage triage index (FN-031..FN-035): cross-doc parity wording (README/runtime), "
            "canonical runtime snapshot-name parity, Gate B8 fail-line wording/singularity, and README/runtime "
            "token-literal parity."
        )
        fail_line = (
            "- **Fail if:** JSON mode drifts, field shape/order changes, `details` ordered-item invariants drift, "
            "transform span snapshots drift, adapter-shape invariants regress, non-contract passthrough behavior regresses, "
            "runtime stage/details-command parity across adapter/direct-builder lanes regresses, runtime consumer contract "
            "guidance drifts, or stable-code mapping/snapshots drift."
        )

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/quality-gates.md: expected exactly one Gate B8 heading",
        )

        gate_start = lines.index(heading) + 1
        gate_end = len(lines)
        for index in range(gate_start, len(lines)):
            if lines[index].startswith("### Gate ") or lines[index].startswith("## "):
                gate_end = index
                break

        pair_start_indices = [
            index
            for index in range(len(lines) - 1)
            if lines[index] == triage_line and lines[index + 1] == fail_line
        ]
        self.assertEqual(
            len(pair_start_indices),
            1,
            "docs/quality-gates.md: expected exactly one triage-index/fail-line adjacency pair in the document",
        )
        pair_start = pair_start_indices[0]
        self.assertGreaterEqual(
            pair_start,
            gate_start,
            "docs/quality-gates.md: triage-index/fail-line adjacency pair must start inside Gate B8 section",
        )
        self.assertLess(
            pair_start + 1,
            gate_end,
            "docs/quality-gates.md: triage-index/fail-line adjacency pair must be fully contained in Gate B8 section",
        )

        gate_b8_lines = lines[gate_start:gate_end]
        gate_pair_count = sum(
            1
            for index in range(len(gate_b8_lines) - 1)
            if gate_b8_lines[index] == triage_line and gate_b8_lines[index + 1] == fail_line
        )
        self.assertEqual(
            gate_pair_count,
            1,
            "docs/quality-gates.md: expected exactly one triage-index/fail-line adjacency pair inside Gate B8 section",
        )

    def test_fn_080_readme_check_lanes_wrapper_note_successor_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.readme_doc,
            heading="### Check-Lanes (Quality Gates)",
            doc_name="README.md",
        )
        wrapper_note = "`check-full.sh` ist ein dünner Wrapper um `check.sh`; beide führen denselben Full-Lane-Gatesatz aus."
        gate_helper_sentence = "Gate-interne Contract-/Anchor-Prüfungen laufen dabei über Helper unter `scripts/gates/`."

        self.assertEqual(
            section_lines.count(wrapper_note),
            1,
            "README.md: expected exactly one `check-full.sh` wrapper-equivalence note in `### Check-Lanes (Quality Gates)` section",
        )
        self.assertEqual(
            section_lines.count(gate_helper_sentence),
            1,
            "README.md: expected exactly one gate-helper sentence in `### Check-Lanes (Quality Gates)` section",
        )

        wrapper_index = section_lines.index(wrapper_note)
        self.assertLess(
            wrapper_index + 1,
            len(section_lines),
            "README.md: wrapper-equivalence note must be followed by the gate-helper sentence",
        )
        self.assertEqual(
            section_lines[wrapper_index + 1].strip(),
            gate_helper_sentence,
            "README.md: wrapper-equivalence note must be followed by exactly one newline and then the gate-helper sentence",
        )

    def test_fn_081_runtime_rule_form_lead_sentence_successor_bullet_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.runtime_determinism_doc,
            heading="### Rule form",
            doc_name="docs/runtime-determinism.md",
        )
        lead_sentence = "`rule.when` is interpreted as a **simple AND-clause list**:"
        first_bullet = "- All clauses in `when` must match for the rule to fire."

        self.assertEqual(
            section_lines.count(lead_sentence),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical `rule.when` lead sentence in `### Rule form` section",
        )
        self.assertEqual(
            section_lines.count(first_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one first rule-form bullet in `### Rule form` section",
        )

        lead_index = section_lines.index(lead_sentence)
        self.assertLess(
            lead_index + 2,
            len(section_lines),
            "docs/runtime-determinism.md: `rule.when` lead sentence must be followed by a blank line and the first rule-form bullet",
        )
        self.assertEqual(
            section_lines[lead_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: `rule.when` lead sentence must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            section_lines[lead_index + 2].strip(),
            first_bullet,
            "docs/runtime-determinism.md: first non-empty line after `rule.when` lead sentence must be the first rule-form bullet",
        )

    def test_fn_082_gate_b8_fail_line_successor_heading_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        fail_line = (
            "- **Fail if:** JSON mode drifts, field shape/order changes, `details` ordered-item invariants drift, "
            "transform span snapshots drift, adapter-shape invariants regress, non-contract passthrough behavior regresses, "
            "runtime stage/details-command parity across adapter/direct-builder lanes regresses, runtime consumer contract "
            "guidance drifts, or stable-code mapping/snapshots drift."
        )
        successor_heading = "## Active compatibility profile references (machine-checked)"

        self.assertEqual(
            lines.count(fail_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical Gate B8 fail-condition line",
        )
        self.assertEqual(
            lines.count(successor_heading),
            1,
            "docs/quality-gates.md: expected exactly one `## Active compatibility profile references (machine-checked)` heading",
        )

        fail_index = lines.index(fail_line)
        self.assertLess(
            fail_index + 2,
            len(lines),
            "docs/quality-gates.md: Gate B8 fail-condition line must be followed by a blank separator and successor compatibility heading",
        )
        self.assertEqual(
            lines[fail_index + 1].strip(),
            "",
            "docs/quality-gates.md: Gate B8 fail-condition line must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[fail_index + 2].strip(),
            successor_heading,
            "docs/quality-gates.md: first non-empty successor after Gate B8 fail-condition line must be `## Active compatibility profile references (machine-checked)`",
        )

    def test_fn_083_readme_gate_helper_sentence_successor_heading_boundary_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        gate_helper_sentence = "Gate-interne Contract-/Anchor-Prüfungen laufen dabei über Helper unter `scripts/gates/`."
        successor_heading = "### Release-Evidence Quickstart"

        self.assertEqual(
            lines.count(gate_helper_sentence),
            1,
            "README.md: expected exactly one canonical gate-helper sentence",
        )
        self.assertEqual(
            lines.count(successor_heading),
            1,
            "README.md: expected exactly one `### Release-Evidence Quickstart` heading",
        )

        sentence_index = lines.index(gate_helper_sentence)
        self.assertLess(
            sentence_index + 2,
            len(lines),
            "README.md: gate-helper sentence must be followed by a blank separator and `### Release-Evidence Quickstart` heading",
        )
        self.assertEqual(
            lines[sentence_index + 1].strip(),
            "",
            "README.md: gate-helper sentence must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[sentence_index + 2].strip(),
            successor_heading,
            "README.md: first non-empty successor after gate-helper sentence must be `### Release-Evidence Quickstart`",
        )

    def test_fn_084_runtime_rule_form_first_bullet_successor_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.runtime_determinism_doc,
            heading="### Rule form",
            doc_name="docs/runtime-determinism.md",
        )
        first_bullet = "- All clauses in `when` must match for the rule to fire."
        second_bullet = "- If any clause fails, the rule does not fire."

        self.assertEqual(
            section_lines.count(first_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one first rule-form bullet in `### Rule form` section",
        )
        self.assertEqual(
            section_lines.count(second_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one second rule-form bullet in `### Rule form` section",
        )

        first_index = section_lines.index(first_bullet)
        self.assertLess(
            first_index + 1,
            len(section_lines),
            "docs/runtime-determinism.md: first rule-form bullet must be followed by the second bullet",
        )
        self.assertEqual(
            section_lines[first_index + 1].strip(),
            second_bullet,
            "docs/runtime-determinism.md: first rule-form bullet must be immediately followed by the second bullet with no intervening blank lines",
        )

    def test_fn_085_gate_profile_heading_successor_anchor_line_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading = "## Active compatibility profile references (machine-checked)"
        anchor_line = "- Gate anchor profiles: `Sprint-5 calibration additive profile`, `Sprint-6 compatibility/ref-hardening profile`"

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/quality-gates.md: expected exactly one `## Active compatibility profile references (machine-checked)` heading",
        )
        self.assertEqual(
            lines.count(anchor_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical `- Gate anchor profiles: ...` line",
        )

        heading_index = lines.index(heading)
        self.assertLess(
            heading_index + 2,
            len(lines),
            "docs/quality-gates.md: compatibility-profile heading must be followed by a blank separator and the gate anchor profiles line",
        )
        self.assertEqual(
            lines[heading_index + 1].strip(),
            "",
            "docs/quality-gates.md: compatibility-profile heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[heading_index + 2].strip(),
            anchor_line,
            "docs/quality-gates.md: first non-empty successor after compatibility-profile heading must be the canonical gate anchor profiles line",
        )

    def test_fn_086_readme_release_evidence_heading_successor_fence_boundary_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        heading = "### Release-Evidence Quickstart"
        opening_fence = "```bash"

        self.assertEqual(
            lines.count(heading),
            1,
            "README.md: expected exactly one `### Release-Evidence Quickstart` heading",
        )

        heading_index = lines.index(heading)
        self.assertLess(
            heading_index + 2,
            len(lines),
            "README.md: release-evidence heading must be followed by a blank separator and opening ```bash fence",
        )
        self.assertEqual(
            lines[heading_index + 1].strip(),
            "",
            "README.md: release-evidence heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[heading_index + 2].strip(),
            opening_fence,
            "README.md: first non-empty successor after release-evidence heading must be an opening ```bash fence",
        )

    def test_fn_087_runtime_rule_form_second_bullet_successor_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.runtime_determinism_doc,
            heading="### Rule form",
            doc_name="docs/runtime-determinism.md",
        )
        second_bullet = "- If any clause fails, the rule does not fire."
        third_bullet = "- No expression language is supported (no `&&`, `||`, `and`, `or`, `not`, parentheses)."

        self.assertEqual(
            section_lines.count(second_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one second rule-form bullet in `### Rule form` section",
        )
        self.assertEqual(
            section_lines.count(third_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one third rule-form bullet in `### Rule form` section",
        )

        second_index = section_lines.index(second_bullet)
        self.assertLess(
            second_index + 1,
            len(section_lines),
            "docs/runtime-determinism.md: second rule-form bullet must be followed by the third bullet",
        )
        self.assertEqual(
            section_lines[second_index + 1].strip(),
            third_bullet,
            "docs/runtime-determinism.md: second rule-form bullet must be immediately followed by the third bullet with no intervening blank lines",
        )

    def test_fn_088_gate_profile_anchor_line_successor_delimiter_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        anchor_line = "- Gate anchor profiles: `Sprint-5 calibration additive profile`, `Sprint-6 compatibility/ref-hardening profile`"
        delimiter = "---"

        self.assertEqual(
            lines.count(anchor_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical `- Gate anchor profiles: ...` line",
        )

        anchor_index = lines.index(anchor_line)
        self.assertLess(
            anchor_index + 2,
            len(lines),
            "docs/quality-gates.md: gate anchor profiles line must be followed by a blank separator and horizontal-rule delimiter",
        )
        self.assertEqual(
            lines[anchor_index + 1].strip(),
            "",
            "docs/quality-gates.md: gate anchor profiles line must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[anchor_index + 2].strip(),
            delimiter,
            "docs/quality-gates.md: first non-empty successor after gate anchor profiles line must be `---`",
        )

    def test_fn_089_readme_release_evidence_fence_successor_command_comment_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.readme_doc,
            heading="### Release-Evidence Quickstart",
            doc_name="README.md",
        )
        opening_fence = "```bash"
        command_comment = "# Full Lane + Snapshot-Export (explizit/manual)"

        self.assertEqual(
            section_lines.count(opening_fence),
            1,
            "README.md: expected exactly one opening ```bash fence in `### Release-Evidence Quickstart` section",
        )
        self.assertEqual(
            section_lines.count(command_comment),
            1,
            "README.md: expected exactly one canonical release-evidence command-comment line",
        )

        fence_index = section_lines.index(opening_fence)
        self.assertLess(
            fence_index + 1,
            len(section_lines),
            "README.md: opening ```bash fence must be followed by the canonical release-evidence command-comment line",
        )
        self.assertEqual(
            section_lines[fence_index + 1].strip(),
            command_comment,
            "README.md: opening ```bash fence must be immediately followed by canonical release-evidence command-comment line with no intervening blank lines",
        )

    def test_fn_090_runtime_rule_form_third_bullet_successor_default_clause_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.runtime_determinism_doc,
            heading="### Rule form",
            doc_name="docs/runtime-determinism.md",
        )
        third_bullet = "- No expression language is supported (no `&&`, `||`, `and`, `or`, `not`, parentheses)."
        default_clause = "If `when` is omitted (or empty), v0 uses default clause `event_type_present` for backward compatibility."

        self.assertEqual(
            section_lines.count(third_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one third rule-form bullet in `### Rule form` section",
        )
        self.assertEqual(
            section_lines.count(default_clause),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical default-clause sentence in `### Rule form` section",
        )

        third_index = section_lines.index(third_bullet)
        self.assertLess(
            third_index + 2,
            len(section_lines),
            "docs/runtime-determinism.md: third rule-form bullet must be followed by a blank separator and default-clause sentence",
        )
        self.assertEqual(
            section_lines[third_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: third rule-form bullet must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            section_lines[third_index + 2].strip(),
            default_clause,
            "docs/runtime-determinism.md: first non-empty successor after third rule-form bullet must be canonical default-clause sentence",
        )

    def test_fn_091_gate_profile_anchor_delimiter_successor_heading_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        anchor_line = "- Gate anchor profiles: `Sprint-5 calibration additive profile`, `Sprint-6 compatibility/ref-hardening profile`"
        delimiter = "---"
        successor_heading = "## v0.1 release-close benchmark snapshot (2026-03-02)"

        self.assertEqual(
            lines.count(anchor_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical `- Gate anchor profiles: ...` line",
        )
        self.assertEqual(
            lines.count(successor_heading),
            1,
            "docs/quality-gates.md: expected exactly one `## v0.1 release-close benchmark snapshot (2026-03-02)` heading",
        )

        anchor_index = lines.index(anchor_line)
        self.assertLess(
            anchor_index + 4,
            len(lines),
            "docs/quality-gates.md: gate anchor profiles delimiter must be followed by a blank separator and benchmark snapshot heading",
        )
        self.assertEqual(
            lines[anchor_index + 2].strip(),
            delimiter,
            "docs/quality-gates.md: gate anchor profiles line successor delimiter must remain `---`",
        )
        self.assertEqual(
            lines[anchor_index + 3].strip(),
            "",
            "docs/quality-gates.md: delimiter after gate anchor profiles line must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[anchor_index + 4].strip(),
            successor_heading,
            "docs/quality-gates.md: first non-empty successor after delimiter must be `## v0.1 release-close benchmark snapshot (2026-03-02)`",
        )

    def test_fn_092_readme_release_evidence_command_comment_successor_command_line_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.readme_doc,
            heading="### Release-Evidence Quickstart",
            doc_name="README.md",
        )
        command_comment = "# Full Lane + Snapshot-Export (explizit/manual)"
        command_line = "./scripts/check.sh && python3 scripts/release_snapshot.py"

        self.assertEqual(
            section_lines.count(command_comment),
            1,
            "README.md: expected exactly one canonical release-evidence command-comment line",
        )
        self.assertEqual(
            section_lines.count(command_line),
            1,
            "README.md: expected exactly one canonical release-evidence command line",
        )

        comment_index = section_lines.index(command_comment)
        self.assertLess(
            comment_index + 1,
            len(section_lines),
            "README.md: release-evidence command-comment line must be followed by canonical release-evidence command line",
        )
        self.assertEqual(
            section_lines[comment_index + 1].strip(),
            command_line,
            "README.md: release-evidence command-comment line must be immediately followed by canonical release-evidence command line with no intervening blank lines",
        )

    def test_fn_093_runtime_rule_form_default_clause_successor_heading_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        default_clause = "If `when` is omitted (or empty), v0 uses default clause `event_type_present` for backward compatibility."
        successor_heading = "### Supported clause grammar"

        self.assertEqual(
            lines.count(default_clause),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical default-clause sentence",
        )
        self.assertEqual(
            lines.count(successor_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `### Supported clause grammar` heading",
        )

        default_index = lines.index(default_clause)
        self.assertLess(
            default_index + 2,
            len(lines),
            "docs/runtime-determinism.md: default-clause sentence must be followed by a blank separator and `### Supported clause grammar` heading",
        )
        self.assertEqual(
            lines[default_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: default-clause sentence must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[default_index + 2].strip(),
            successor_heading,
            "docs/runtime-determinism.md: first non-empty successor after default-clause sentence must be `### Supported clause grammar`",
        )

    def test_fn_094_gate_benchmark_heading_successor_run_reference_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading = "## v0.1 release-close benchmark snapshot (2026-03-02)"
        run_reference = "Run reference:"

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/quality-gates.md: expected exactly one `## v0.1 release-close benchmark snapshot (2026-03-02)` heading",
        )
        self.assertEqual(
            lines.count(run_reference),
            1,
            "docs/quality-gates.md: expected exactly one `Run reference:` line",
        )

        heading_index = lines.index(heading)
        self.assertLess(
            heading_index + 2,
            len(lines),
            "docs/quality-gates.md: benchmark snapshot heading must be followed by a blank separator and `Run reference:` line",
        )
        self.assertEqual(
            lines[heading_index + 1].strip(),
            "",
            "docs/quality-gates.md: benchmark snapshot heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[heading_index + 2].strip(),
            run_reference,
            "docs/quality-gates.md: first non-empty successor after benchmark snapshot heading must be `Run reference:`",
        )

    def test_fn_095_readme_release_evidence_command_line_successor_closing_fence_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.readme_doc,
            heading="### Release-Evidence Quickstart",
            doc_name="README.md",
        )
        command_line = "./scripts/check.sh && python3 scripts/release_snapshot.py"
        closing_fence = "```"

        self.assertEqual(
            section_lines.count(command_line),
            1,
            "README.md: expected exactly one canonical release-evidence command line",
        )
        self.assertEqual(
            section_lines.count(closing_fence),
            1,
            "README.md: expected exactly one closing code fence in `### Release-Evidence Quickstart` section",
        )

        command_index = section_lines.index(command_line)
        self.assertLess(
            command_index + 1,
            len(section_lines),
            "README.md: release-evidence command line must be followed by closing code fence",
        )
        self.assertEqual(
            section_lines[command_index + 1].strip(),
            closing_fence,
            "README.md: release-evidence command line must be immediately followed by closing code fence with no intervening blank lines",
        )

    def test_fn_096_runtime_supported_clause_heading_successor_lead_sentence_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        heading = "### Supported clause grammar"
        lead_sentence = "Only these clause forms are valid:"

        self.assertEqual(
            lines.count(heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `### Supported clause grammar` heading",
        )
        self.assertEqual(
            lines.count(lead_sentence),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical supported-clause lead sentence",
        )

        heading_index = lines.index(heading)
        self.assertLess(
            heading_index + 2,
            len(lines),
            "docs/runtime-determinism.md: supported-clause heading must be followed by a blank separator and canonical lead sentence",
        )
        self.assertEqual(
            lines[heading_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: supported-clause heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[heading_index + 2].strip(),
            lead_sentence,
            "docs/runtime-determinism.md: first non-empty successor after supported-clause heading must be canonical lead sentence",
        )

    def test_fn_097_gate_run_reference_successor_first_command_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        run_reference = "Run reference:"
        first_command = "- Command: `./scripts/check.sh`"

        self.assertEqual(
            lines.count(run_reference),
            1,
            "docs/quality-gates.md: expected exactly one `Run reference:` line",
        )
        self.assertEqual(
            lines.count(first_command),
            1,
            "docs/quality-gates.md: expected exactly one canonical run-reference first command bullet",
        )

        run_reference_index = lines.index(run_reference)
        self.assertLess(
            run_reference_index + 1,
            len(lines),
            "docs/quality-gates.md: `Run reference:` must be immediately followed by canonical first command bullet",
        )
        self.assertEqual(
            lines[run_reference_index + 1].strip(),
            first_command,
            "docs/quality-gates.md: `Run reference:` must be immediately followed by `- Command: `./scripts/check.sh`` with no intervening blank lines",
        )

    def test_fn_098_readme_release_evidence_closing_fence_successor_bullet_boundary_canary(self) -> None:
        section_lines = self._extract_section_lines(
            text=self.readme_doc,
            heading="### Release-Evidence Quickstart",
            doc_name="README.md",
        )
        closing_fence = "```"
        first_bullet = "- Frische Evidence: `docs/release-artifacts/latest.{json,md}`"

        self.assertEqual(
            section_lines.count(closing_fence),
            1,
            "README.md: expected exactly one closing code fence in `### Release-Evidence Quickstart` section",
        )
        self.assertEqual(
            section_lines.count(first_bullet),
            1,
            "README.md: expected exactly one canonical fresh-evidence bullet",
        )

        fence_index = section_lines.index(closing_fence)
        self.assertLess(
            fence_index + 2,
            len(section_lines),
            "README.md: release-evidence closing fence must be followed by one blank separator and canonical fresh-evidence bullet",
        )
        self.assertEqual(
            section_lines[fence_index + 1].strip(),
            "",
            "README.md: release-evidence closing fence must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            section_lines[fence_index + 2].strip(),
            first_bullet,
            "README.md: first non-empty successor after release-evidence closing fence must be canonical fresh-evidence bullet",
        )

    def test_fn_099_runtime_supported_clause_lead_sentence_successor_first_bullet_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        lead_sentence = "Only these clause forms are valid:"
        first_bullet = "- `event_type_present`"

        self.assertEqual(
            lines.count(lead_sentence),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical supported-clause lead sentence",
        )
        self.assertEqual(
            lines.count(first_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first supported-clause bullet",
        )

        lead_index = lines.index(lead_sentence)
        self.assertLess(
            lead_index + 2,
            len(lines),
            "docs/runtime-determinism.md: supported-clause lead sentence must be followed by one blank separator and canonical first bullet",
        )
        self.assertEqual(
            lines[lead_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: supported-clause lead sentence must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[lead_index + 2].strip(),
            first_bullet,
            "docs/runtime-determinism.md: first non-empty successor after supported-clause lead sentence must be `- `event_type_present``",
        )

    def test_fn_100_gate_command_line_successor_executed_line_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        command_line = "- Command: `./scripts/check.sh`"
        executed_line = "- Executed: 2026-03-02 21:50-21:52 +0100"

        self.assertEqual(
            lines.count(command_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical release run command line",
        )
        self.assertEqual(
            lines.count(executed_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical release run executed line",
        )

        command_index = lines.index(command_line)
        self.assertLess(
            command_index + 1,
            len(lines),
            "docs/quality-gates.md: command line must be immediately followed by executed line",
        )
        self.assertEqual(
            lines[command_index + 1].strip(),
            executed_line,
            "docs/quality-gates.md: `- Command: `./scripts/check.sh`` must be immediately followed by `- Executed: 2026-03-02 21:50-21:52 +0100`",
        )

    def test_fn_101_readme_fresh_evidence_successor_snapshot_index_boundary_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        fresh_evidence_line = "- Frische Evidence: `docs/release-artifacts/latest.{json,md}`"
        snapshot_index_line = "- Snapshot-Index + Retention-Runbook: `docs/release-artifacts/README.md`"

        self.assertEqual(
            lines.count(fresh_evidence_line),
            1,
            "README.md: expected exactly one canonical fresh-evidence line",
        )
        self.assertEqual(
            lines.count(snapshot_index_line),
            1,
            "README.md: expected exactly one canonical snapshot-index line",
        )

        fresh_evidence_index = lines.index(fresh_evidence_line)
        self.assertLess(
            fresh_evidence_index + 1,
            len(lines),
            "README.md: fresh-evidence line must be immediately followed by snapshot-index line",
        )
        self.assertEqual(
            lines[fresh_evidence_index + 1].strip(),
            snapshot_index_line,
            "README.md: `- Frische Evidence: `docs/release-artifacts/latest.{json,md}`` must be immediately followed by `- Snapshot-Index + Retention-Runbook: `docs/release-artifacts/README.md``",
        )

    def test_fn_102_runtime_supported_clause_first_bullet_successor_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        first_bullet = "- `event_type_present`"
        second_bullet = "- `event_type_equals:<value>`"

        self.assertEqual(
            lines.count(first_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first supported-clause bullet",
        )
        self.assertEqual(
            lines.count(second_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second supported-clause bullet",
        )

        first_bullet_index = lines.index(first_bullet)
        self.assertLess(
            first_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: first supported-clause bullet must be immediately followed by second bullet",
        )
        self.assertEqual(
            lines[first_bullet_index + 1].strip(),
            second_bullet,
            "docs/runtime-determinism.md: `- `event_type_present`` must be immediately followed by `- `event_type_equals:<value>`` with no intervening blank lines",
        )

    def test_fn_103_gate_executed_line_successor_gate_result_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        executed_line = "- Executed: 2026-03-02 21:50-21:52 +0100"
        gate_result_line = "- Gate result: pass (`[7/7] Quality gates complete`, `All active quality gates passed.`)"

        self.assertEqual(
            lines.count(executed_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical release run executed line",
        )
        self.assertEqual(
            lines.count(gate_result_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical release run gate-result line",
        )

        executed_index = lines.index(executed_line)
        self.assertLess(
            executed_index + 1,
            len(lines),
            "docs/quality-gates.md: executed line must be immediately followed by gate-result line",
        )
        self.assertEqual(
            lines[executed_index + 1].strip(),
            gate_result_line,
            "docs/quality-gates.md: `- Executed: 2026-03-02 21:50-21:52 +0100` must be immediately followed by `- Gate result: pass (`[7/7] Quality gates complete`, `All active quality gates passed.`)`",
        )

    def test_fn_104_readme_snapshot_index_successor_source_of_truth_boundary_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        snapshot_index_line = "- Snapshot-Index + Retention-Runbook: `docs/release-artifacts/README.md`"
        source_of_truth_line = "- Source-of-truth-Regel: `bench/token-harness/results/latest.json` bleibt gate-gepinnt,"

        self.assertEqual(
            lines.count(snapshot_index_line),
            1,
            "README.md: expected exactly one canonical snapshot-index line",
        )
        self.assertEqual(
            lines.count(source_of_truth_line),
            1,
            "README.md: expected exactly one canonical source-of-truth line",
        )

        snapshot_index = lines.index(snapshot_index_line)
        self.assertLess(
            snapshot_index + 1,
            len(lines),
            "README.md: snapshot-index line must be immediately followed by source-of-truth line",
        )
        self.assertEqual(
            lines[snapshot_index + 1].strip(),
            source_of_truth_line,
            "README.md: `- Snapshot-Index + Retention-Runbook: `docs/release-artifacts/README.md`` must be immediately followed by `- Source-of-truth-Regel: `bench/token-harness/results/latest.json` bleibt gate-gepinnt,`",
        )

    def test_fn_105_runtime_supported_clause_second_bullet_successor_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        second_bullet = "- `event_type_equals:<value>`"
        third_bullet = "- `event_type_in:<csv-or-json-list>`"

        self.assertEqual(
            lines.count(second_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second supported-clause bullet",
        )
        self.assertEqual(
            lines.count(third_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical third supported-clause bullet",
        )

        second_bullet_index = lines.index(second_bullet)
        self.assertLess(
            second_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: second supported-clause bullet must be immediately followed by third bullet",
        )
        self.assertEqual(
            lines[second_bullet_index + 1].strip(),
            third_bullet,
            "docs/runtime-determinism.md: `- `event_type_equals:<value>`` must be immediately followed by `- `event_type_in:<csv-or-json-list>`` with no intervening blank lines",
        )

    def test_fn_106_gate_gate_result_successor_benchmark_heading_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        gate_result_line = "- Gate result: pass (`[7/7] Quality gates complete`, `All active quality gates passed.`)"
        benchmark_heading = "Benchmark threshold evidence (Gate B4):"

        self.assertEqual(
            lines.count(gate_result_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical release run gate-result line",
        )
        self.assertEqual(
            lines.count(benchmark_heading),
            1,
            "docs/quality-gates.md: expected exactly one benchmark-threshold evidence heading",
        )

        gate_result_index = lines.index(gate_result_line)
        self.assertLess(
            gate_result_index + 2,
            len(lines),
            "docs/quality-gates.md: gate-result line must be followed by one blank separator and benchmark-threshold heading",
        )
        self.assertEqual(
            lines[gate_result_index + 1].strip(),
            "",
            "docs/quality-gates.md: gate-result line must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[gate_result_index + 2].strip(),
            benchmark_heading,
            "docs/quality-gates.md: first non-empty successor after gate-result line must be `Benchmark threshold evidence (Gate B4):`",
        )

    def test_fn_107_readme_source_of_truth_successor_continuation_boundary_canary(self) -> None:
        lines = self.readme_doc.splitlines()
        source_of_truth_line = "- Source-of-truth-Regel: `bench/token-harness/results/latest.json` bleibt gate-gepinnt,"
        continuation_line = "  `docs/release-artifacts/latest.json` bildet die Freshness-Pointer-Evidence."

        self.assertEqual(
            lines.count(source_of_truth_line),
            1,
            "README.md: expected exactly one canonical source-of-truth first line",
        )
        self.assertEqual(
            lines.count(continuation_line),
            1,
            "README.md: expected exactly one canonical source-of-truth continuation line",
        )

        source_of_truth_index = lines.index(source_of_truth_line)
        self.assertLess(
            source_of_truth_index + 1,
            len(lines),
            "README.md: source-of-truth first line must be immediately followed by continuation line",
        )
        self.assertEqual(
            lines[source_of_truth_index + 1],
            continuation_line,
            "README.md: `- Source-of-truth-Regel: ...` must be immediately followed by canonical continuation line with preserved two-space indentation",
        )

    def test_fn_108_runtime_supported_clause_third_bullet_successor_unsupported_line_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        third_bullet = "- `event_type_in:<csv-or-json-list>`"
        fourth_bullet = "- `event_type_not_in:<csv-or-json-list>`"

        self.assertEqual(
            lines.count(third_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical third supported-clause bullet",
        )
        self.assertEqual(
            lines.count(fourth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fourth supported-clause bullet",
        )

        third_bullet_index = lines.index(third_bullet)
        self.assertLess(
            third_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: third supported-clause bullet must be immediately followed by fourth bullet",
        )
        self.assertEqual(
            lines[third_bullet_index + 1].strip(),
            fourth_bullet,
            "docs/runtime-determinism.md: `- `event_type_in:<csv-or-json-list>`` must be immediately followed by `- `event_type_not_in:<csv-or-json-list>`` with no intervening blank lines",
        )

    def test_fn_108a_runtime_supported_clause_fourth_bullet_successor_fifth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        fourth_bullet = "- `event_type_not_in:<csv-or-json-list>`"
        fifth_bullet = "- `payload_has:<top_level_key>`"

        self.assertEqual(
            lines.count(fourth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fourth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(fifth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fifth supported-clause bullet",
        )

        fourth_bullet_index = lines.index(fourth_bullet)
        self.assertLess(
            fourth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: fourth supported-clause bullet must be immediately followed by fifth bullet",
        )
        self.assertEqual(
            lines[fourth_bullet_index + 1].strip(),
            fifth_bullet,
            "docs/runtime-determinism.md: `- `event_type_not_in:<csv-or-json-list>`` must be immediately followed by `- `payload_has:<top_level_key>`` with no intervening blank lines",
        )

    def test_fn_108b_runtime_supported_clause_fifth_bullet_successor_sixth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        fifth_bullet = "- `payload_has:<top_level_key>`"
        sixth_bullet = "- `payload_path_exists:<dot.path>`"

        self.assertEqual(
            lines.count(fifth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fifth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(sixth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical sixth supported-clause bullet",
        )

        fifth_bullet_index = lines.index(fifth_bullet)
        self.assertLess(
            fifth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: fifth supported-clause bullet must be immediately followed by sixth bullet",
        )
        self.assertEqual(
            lines[fifth_bullet_index + 1].strip(),
            sixth_bullet,
            "docs/runtime-determinism.md: `- `payload_has:<top_level_key>`` must be immediately followed by `- `payload_path_exists:<dot.path>`` with no intervening blank lines",
        )

    def test_fn_108c_runtime_supported_clause_sixth_bullet_successor_seventh_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        sixth_bullet = "- `payload_path_exists:<dot.path>`"
        seventh_bullet = "- `payload_path_equals:<dot.path>=<value>`"

        self.assertEqual(
            lines.count(sixth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical sixth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(seventh_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical seventh supported-clause bullet",
        )

        sixth_bullet_index = lines.index(sixth_bullet)
        self.assertLess(
            sixth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: sixth supported-clause bullet must be immediately followed by seventh bullet",
        )
        self.assertEqual(
            lines[sixth_bullet_index + 1].strip(),
            seventh_bullet,
            "docs/runtime-determinism.md: `- `payload_path_exists:<dot.path>`` must be immediately followed by `- `payload_path_equals:<dot.path>=<value>`` with no intervening blank lines",
        )

    def test_fn_108d_runtime_supported_clause_seventh_bullet_successor_eighth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        seventh_bullet = "- `payload_path_gt:<dot.path>=<number>`"
        eighth_bullet = "- `payload_path_gte:<dot.path>=<number>`"

        self.assertEqual(
            lines.count(seventh_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical seventh supported-clause bullet",
        )
        self.assertEqual(
            lines.count(eighth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical eighth supported-clause bullet",
        )

        seventh_bullet_index = lines.index(seventh_bullet)
        self.assertLess(
            seventh_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: seventh supported-clause bullet must be immediately followed by eighth bullet",
        )
        self.assertEqual(
            lines[seventh_bullet_index + 1].strip(),
            eighth_bullet,
            "docs/runtime-determinism.md: `- `payload_path_gt:<dot.path>=<number>`` must be immediately followed by `- `payload_path_gte:<dot.path>=<number>`` with no intervening blank lines",
        )

    def test_fn_108e_runtime_supported_clause_eighth_bullet_successor_ninth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        eighth_bullet = "- `payload_path_gte:<dot.path>=<number>`"
        ninth_bullet = "- `payload_path_lt:<dot.path>=<number>`"

        self.assertEqual(
            lines.count(eighth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical eighth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(ninth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical ninth supported-clause bullet",
        )

        eighth_bullet_index = lines.index(eighth_bullet)
        self.assertLess(
            eighth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: eighth supported-clause bullet must be immediately followed by ninth bullet",
        )
        self.assertEqual(
            lines[eighth_bullet_index + 1].strip(),
            ninth_bullet,
            "docs/runtime-determinism.md: `- `payload_path_gte:<dot.path>=<number>`` must be immediately followed by `- `payload_path_lt:<dot.path>=<number>`` with no intervening blank lines",
        )

    def test_fn_108f_runtime_supported_clause_ninth_bullet_successor_tenth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        ninth_bullet = "- `payload_path_lt:<dot.path>=<number>`"
        tenth_bullet = "- `payload_path_lte:<dot.path>=<number>`"

        self.assertEqual(
            lines.count(ninth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical ninth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(tenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical tenth supported-clause bullet",
        )

        ninth_bullet_index = lines.index(ninth_bullet)
        self.assertLess(
            ninth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: ninth supported-clause bullet must be immediately followed by tenth bullet",
        )
        self.assertEqual(
            lines[ninth_bullet_index + 1].strip(),
            tenth_bullet,
            "docs/runtime-determinism.md: `- `payload_path_lt:<dot.path>=<number>`` must be immediately followed by `- `payload_path_lte:<dot.path>=<number>`` with no intervening blank lines",
        )

    def test_fn_108g_runtime_supported_clause_tenth_bullet_successor_eleventh_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        tenth_bullet = "- `payload_path_lte:<dot.path>=<number>`"
        eleventh_bullet = "- `payload_path_is_null:<dot.path>`"

        self.assertEqual(
            lines.count(tenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical tenth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(eleventh_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical eleventh supported-clause bullet",
        )

        tenth_bullet_index = lines.index(tenth_bullet)
        self.assertLess(
            tenth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: tenth supported-clause bullet must be immediately followed by eleventh bullet",
        )
        self.assertEqual(
            lines[tenth_bullet_index + 1].strip(),
            eleventh_bullet,
            "docs/runtime-determinism.md: `- `payload_path_lte:<dot.path>=<number>`` must be immediately followed by `- `payload_path_is_null:<dot.path>`` with no intervening blank lines",
        )

    def test_fn_108h_runtime_supported_clause_eleventh_bullet_successor_twelfth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        eleventh_bullet = "- `payload_path_is_null:<dot.path>`"
        twelfth_bullet = "- `payload_path_is_bool:<dot.path>`"

        self.assertEqual(
            lines.count(eleventh_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical eleventh supported-clause bullet",
        )
        self.assertEqual(
            lines.count(twelfth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical twelfth supported-clause bullet",
        )

        eleventh_bullet_index = lines.index(eleventh_bullet)
        self.assertLess(
            eleventh_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: eleventh supported-clause bullet must be immediately followed by twelfth bullet",
        )
        self.assertEqual(
            lines[eleventh_bullet_index + 1].strip(),
            twelfth_bullet,
            "docs/runtime-determinism.md: `- `payload_path_is_null:<dot.path>`` must be immediately followed by `- `payload_path_is_bool:<dot.path>`` with no intervening blank lines",
        )

    def test_fn_108i_runtime_supported_clause_twelfth_bullet_successor_thirteenth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        twelfth_bullet = "- `payload_path_is_bool:<dot.path>`"
        thirteenth_bullet = "- `payload_path_is_number:<dot.path>`"

        self.assertEqual(
            lines.count(twelfth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical twelfth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(thirteenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical thirteenth supported-clause bullet",
        )

        twelfth_bullet_index = lines.index(twelfth_bullet)
        self.assertLess(
            twelfth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: twelfth supported-clause bullet must be immediately followed by thirteenth bullet",
        )
        self.assertEqual(
            lines[twelfth_bullet_index + 1].strip(),
            thirteenth_bullet,
            "docs/runtime-determinism.md: `- `payload_path_is_bool:<dot.path>`` must be immediately followed by `- `payload_path_is_number:<dot.path>`` with no intervening blank lines",
        )

    def test_fn_108j_runtime_supported_clause_thirteenth_bullet_successor_fourteenth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        thirteenth_bullet = "- `payload_path_is_number:<dot.path>`"
        fourteenth_bullet = "- `payload_path_is_string:<dot.path>`"

        self.assertEqual(
            lines.count(thirteenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical thirteenth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(fourteenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fourteenth supported-clause bullet",
        )

        thirteenth_bullet_index = lines.index(thirteenth_bullet)
        self.assertLess(
            thirteenth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: thirteenth supported-clause bullet must be immediately followed by fourteenth bullet",
        )
        self.assertEqual(
            lines[thirteenth_bullet_index + 1].strip(),
            fourteenth_bullet,
            "docs/runtime-determinism.md: `- `payload_path_is_number:<dot.path>`` must be immediately followed by `- `payload_path_is_string:<dot.path>`` with no intervening blank lines",
        )

    def test_fn_108k_runtime_supported_clause_fourteenth_bullet_successor_fifteenth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        fourteenth_bullet = "- `payload_path_is_string:<dot.path>`"
        fifteenth_bullet = "- `payload_path_is_list:<dot.path>`"

        self.assertEqual(
            lines.count(fourteenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fourteenth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(fifteenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fifteenth supported-clause bullet",
        )

        fourteenth_bullet_index = lines.index(fourteenth_bullet)
        self.assertLess(
            fourteenth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: fourteenth supported-clause bullet must be immediately followed by fifteenth bullet",
        )
        self.assertEqual(
            lines[fourteenth_bullet_index + 1].strip(),
            fifteenth_bullet,
            "docs/runtime-determinism.md: `- `payload_path_is_string:<dot.path>`` must be immediately followed by `- `payload_path_is_list:<dot.path>`` with no intervening blank lines",
        )

    def test_fn_108l_runtime_supported_clause_fifteenth_bullet_successor_sixteenth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        fifteenth_bullet = "- `payload_path_is_list:<dot.path>`"
        sixteenth_bullet = "- `payload_path_is_object:<dot.path>`"

        self.assertEqual(
            lines.count(fifteenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fifteenth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(sixteenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical sixteenth supported-clause bullet",
        )

        fifteenth_bullet_index = lines.index(fifteenth_bullet)
        self.assertLess(
            fifteenth_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: fifteenth supported-clause bullet must be immediately followed by sixteenth bullet",
        )
        self.assertEqual(
            lines[fifteenth_bullet_index + 1].strip(),
            sixteenth_bullet,
            "docs/runtime-determinism.md: `- `payload_path_is_list:<dot.path>`` must be immediately followed by `- `payload_path_is_object:<dot.path>`` with no intervening blank lines",
        )

    def test_fn_108m_runtime_supported_clause_sixteenth_bullet_successor_unsupported_line_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        sixteenth_bullet = "- `payload_path_is_object:<dot.path>`"
        unsupported_line = (
            "Unsupported clauses raise a `TypeError` (rule evaluation aborts for that policy set)."
        )

        self.assertEqual(
            lines.count(sixteenth_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical sixteenth supported-clause bullet",
        )
        self.assertEqual(
            lines.count(unsupported_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical unsupported-clause TypeError line",
        )

        sixteenth_bullet_index = lines.index(sixteenth_bullet)
        self.assertLess(
            sixteenth_bullet_index + 2,
            len(lines),
            "docs/runtime-determinism.md: sixteenth supported-clause bullet must be followed by one blank separator and unsupported-clause TypeError line",
        )
        self.assertEqual(
            lines[sixteenth_bullet_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: sixteenth supported-clause bullet must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[sixteenth_bullet_index + 2].strip(),
            unsupported_line,
            "docs/runtime-determinism.md: first non-empty successor after `- `payload_path_is_object:<dot.path>`` must be canonical unsupported-clause TypeError line",
        )

    def test_fn_109_gate_benchmark_heading_successor_baseline_line_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        benchmark_heading = "Benchmark threshold evidence (Gate B4):"
        baseline_line = "- Baseline tokens: `1389`"

        self.assertEqual(
            lines.count(benchmark_heading),
            1,
            "docs/quality-gates.md: expected exactly one benchmark-threshold evidence heading",
        )
        self.assertEqual(
            lines.count(baseline_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical baseline-tokens line",
        )

        benchmark_heading_index = lines.index(benchmark_heading)
        self.assertLess(
            benchmark_heading_index + 1,
            len(lines),
            "docs/quality-gates.md: benchmark-threshold evidence heading must be immediately followed by baseline-tokens line",
        )
        self.assertEqual(
            lines[benchmark_heading_index + 1].strip(),
            baseline_line,
            "docs/quality-gates.md: `Benchmark threshold evidence (Gate B4):` must be immediately followed by `- Baseline tokens: `1389``",
        )

    def test_fn_110_readme_source_of_truth_continuation_successor_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        continuation_line = "  `docs/release-artifacts/latest.json` bildet die Freshness-Pointer-Evidence."
        examples_heading = "Weitere Beispiele:"

        self.assertEqual(
            lines.count(continuation_line),
            1,
            "README.md: expected exactly one canonical source-of-truth continuation line",
        )
        self.assertEqual(
            lines.count(examples_heading),
            1,
            "README.md: expected exactly one `Weitere Beispiele:` heading",
        )

        continuation_line_index = lines.index(continuation_line)
        self.assertLess(
            continuation_line_index + 2,
            len(lines),
            "README.md: source-of-truth continuation line must be followed by one blank separator and `Weitere Beispiele:` heading",
        )
        self.assertEqual(
            lines[continuation_line_index + 1].strip(),
            "",
            "README.md: source-of-truth continuation line must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[continuation_line_index + 2].strip(),
            examples_heading,
            "README.md: first non-empty successor after canonical source-of-truth continuation line must be `Weitere Beispiele:`",
        )

    def test_fn_111_runtime_unsupported_clause_line_successor_action_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        unsupported_line = (
            "Unsupported clauses raise a `TypeError` (rule evaluation aborts for that policy set)."
        )
        action_heading = "### Action emission semantics"

        self.assertEqual(
            lines.count(unsupported_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical unsupported-clause TypeError line",
        )
        self.assertEqual(
            lines.count(action_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `### Action emission semantics` heading",
        )

        unsupported_line_index = lines.index(unsupported_line)
        self.assertLess(
            unsupported_line_index + 2,
            len(lines),
            "docs/runtime-determinism.md: unsupported-clause TypeError line must be followed by one blank separator and action-emission heading",
        )
        self.assertEqual(
            lines[unsupported_line_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: unsupported-clause TypeError line must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[unsupported_line_index + 2].strip(),
            action_heading,
            "docs/runtime-determinism.md: first non-empty successor after unsupported-clause TypeError line must be `### Action emission semantics`",
        )

    def test_fn_112_gate_baseline_line_successor_erz_line_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        baseline_line = "- Baseline tokens: `1389`"
        erz_line = "- erz tokens: `709`"

        self.assertEqual(
            lines.count(baseline_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical baseline-tokens line",
        )
        self.assertEqual(
            lines.count(erz_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical erz-tokens line",
        )

        baseline_line_index = lines.index(baseline_line)
        self.assertLess(
            baseline_line_index + 1,
            len(lines),
            "docs/quality-gates.md: baseline-tokens line must be immediately followed by erz-tokens line",
        )
        self.assertEqual(
            lines[baseline_line_index + 1].strip(),
            erz_line,
            "docs/quality-gates.md: `- Baseline tokens: `1389`` must be immediately followed by `- erz tokens: `709``",
        )

    def test_fn_113_readme_weitere_beispiele_heading_successor_first_example_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        examples_heading = "Weitere Beispiele:"
        first_example_line = "- `examples/sprint3_mixed.erz`"

        self.assertEqual(
            lines.count(examples_heading),
            1,
            "README.md: expected exactly one `Weitere Beispiele:` heading",
        )
        self.assertEqual(
            lines.count(first_example_line),
            1,
            "README.md: expected exactly one canonical first `Weitere Beispiele` bullet",
        )

        examples_heading_index = lines.index(examples_heading)
        self.assertLess(
            examples_heading_index + 2,
            len(lines),
            "README.md: `Weitere Beispiele:` heading must be followed by one blank separator and first example bullet",
        )
        self.assertEqual(
            lines[examples_heading_index + 1].strip(),
            "",
            "README.md: `Weitere Beispiele:` heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[examples_heading_index + 2].strip(),
            first_example_line,
            "README.md: first non-empty successor after `Weitere Beispiele:` must be `- `examples/sprint3_mixed.erz``",
        )

    def test_fn_114_runtime_action_heading_successor_first_bullet_boundary_canary(self) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        action_heading = "### Action emission semantics"
        first_bullet = "- `then` actions are emitted as declarative output records only."

        self.assertEqual(
            lines.count(action_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one `### Action emission semantics` heading",
        )
        self.assertEqual(
            lines.count(first_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first action-emission bullet",
        )

        action_heading_index = lines.index(action_heading)
        self.assertLess(
            action_heading_index + 2,
            len(lines),
            "docs/runtime-determinism.md: action-emission heading must be followed by one blank separator and first bullet",
        )
        self.assertEqual(
            lines[action_heading_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: action-emission heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[action_heading_index + 2].strip(),
            first_bullet,
            "docs/runtime-determinism.md: first non-empty successor after `### Action emission semantics` must be `- `then` actions are emitted as declarative output records only.`",
        )

    def test_fn_115_gate_erz_line_successor_token_saving_line_boundary_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        erz_line = "- erz tokens: `709`"
        token_saving_line = "- Token saving: `48.96%`"

        self.assertEqual(
            lines.count(erz_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical erz-tokens line",
        )
        self.assertEqual(
            lines.count(token_saving_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical token-saving line",
        )

        erz_line_index = lines.index(erz_line)
        self.assertLess(
            erz_line_index + 1,
            len(lines),
            "docs/quality-gates.md: erz-tokens line must be immediately followed by token-saving line",
        )
        self.assertEqual(
            lines[erz_line_index + 1].strip(),
            token_saving_line,
            "docs/quality-gates.md: `- erz tokens: `709`` must be immediately followed by `- Token saving: `48.96%``",
        )

    def test_fn_116_readme_first_example_successor_second_example_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        first_example_line = "- `examples/sprint3_mixed.erz`"
        second_example_line = "- `examples/sprint3_policy.erz`"

        self.assertEqual(
            lines.count(first_example_line),
            1,
            "README.md: expected exactly one canonical first `Weitere Beispiele` bullet",
        )
        self.assertEqual(
            lines.count(second_example_line),
            1,
            "README.md: expected exactly one canonical second `Weitere Beispiele` bullet",
        )

        first_example_line_index = lines.index(first_example_line)
        self.assertLess(
            first_example_line_index + 1,
            len(lines),
            "README.md: first `Weitere Beispiele` bullet must be immediately followed by second example bullet",
        )
        self.assertEqual(
            lines[first_example_line_index + 1].strip(),
            second_example_line,
            "README.md: `- `examples/sprint3_mixed.erz`` must be immediately followed by `- `examples/sprint3_policy.erz``",
        )

    def test_fn_117_runtime_first_action_bullet_successor_second_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        first_bullet = "- `then` actions are emitted as declarative output records only."
        second_bullet = "- Runtime does **not** execute action kinds."

        self.assertEqual(
            lines.count(first_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first action-emission bullet",
        )
        self.assertEqual(
            lines.count(second_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second action-emission bullet",
        )

        first_bullet_index = lines.index(first_bullet)
        self.assertLess(
            first_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: first action-emission bullet must be immediately followed by second bullet",
        )
        self.assertEqual(
            lines[first_bullet_index + 1].strip(),
            second_bullet,
            "docs/runtime-determinism.md: `- `then` actions are emitted as declarative output records only.` must be immediately followed by `- Runtime does **not** execute action kinds.`",
        )

    def test_fn_118_gate_token_saving_line_successor_target_line_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        token_saving_line = "- Token saving: `48.96%`"
        target_line = "- Target: `>= 25.0%` -> `met`"

        self.assertEqual(
            lines.count(token_saving_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical token-saving line",
        )
        self.assertEqual(
            lines.count(target_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical target line",
        )

        token_saving_line_index = lines.index(token_saving_line)
        self.assertLess(
            token_saving_line_index + 1,
            len(lines),
            "docs/quality-gates.md: token-saving line must be immediately followed by target line",
        )
        self.assertEqual(
            lines[token_saving_line_index + 1].strip(),
            target_line,
            "docs/quality-gates.md: `- Token saving: `48.96%`` must be immediately followed by `- Target: `>= 25.0%` -> `met``",
        )

    def test_fn_119_readme_second_example_successor_sprint7_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        second_example_line = "- `examples/sprint3_policy.erz`"
        sprint7_heading = "Sprint-7 Program Packs (siehe auch `examples/program-packs/README.md`):"

        self.assertEqual(
            lines.count(second_example_line),
            1,
            "README.md: expected exactly one canonical second `Weitere Beispiele` bullet",
        )
        self.assertEqual(
            lines.count(sprint7_heading),
            1,
            "README.md: expected exactly one canonical `Sprint-7 Program Packs` heading",
        )

        second_example_line_index = lines.index(second_example_line)
        self.assertLess(
            second_example_line_index + 2,
            len(lines),
            "README.md: second `Weitere Beispiele` bullet must be followed by one blank separator and Sprint-7 heading",
        )
        self.assertEqual(
            lines[second_example_line_index + 1].strip(),
            "",
            "README.md: second `Weitere Beispiele` bullet must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[second_example_line_index + 2].strip(),
            sprint7_heading,
            "README.md: first non-empty successor after `- `examples/sprint3_policy.erz`` must be `Sprint-7 Program Packs (siehe auch `examples/program-packs/README.md`):`",
        )

    def test_fn_120_runtime_second_action_bullet_successor_third_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        second_bullet = "- Runtime does **not** execute action kinds."
        third_bullet = '- Missing `then` defaults to: `{"kind": "act", "params": {"rule_id": <rule.id>}}`.'

        self.assertEqual(
            lines.count(second_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second action-emission bullet",
        )
        self.assertEqual(
            lines.count(third_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical third action-emission bullet",
        )

        second_bullet_index = lines.index(second_bullet)
        self.assertLess(
            second_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: second action-emission bullet must be immediately followed by third bullet",
        )
        self.assertEqual(
            lines[second_bullet_index + 1].strip(),
            third_bullet,
            'docs/runtime-determinism.md: `- Runtime does **not** execute action kinds.` must be immediately followed by `- Missing `then` defaults to: `{"kind": "act", "params": {"rule_id": <rule.id>}}`.`',
        )

    def test_fn_121_gate_target_line_successor_fixture_floor_line_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        target_line = "- Target: `>= 25.0%` -> `met`"
        fixture_floor_line = "- Fixture floor: `10/10` pairs -> `met`"

        self.assertEqual(
            lines.count(target_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical target line",
        )
        self.assertEqual(
            lines.count(fixture_floor_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical fixture-floor line",
        )

        target_line_index = lines.index(target_line)
        self.assertLess(
            target_line_index + 1,
            len(lines),
            "docs/quality-gates.md: target line must be immediately followed by fixture-floor line",
        )
        self.assertEqual(
            lines[target_line_index + 1].strip(),
            fixture_floor_line,
            "docs/quality-gates.md: `- Target: `>= 25.0%` -> `met`` must be immediately followed by `- Fixture floor: `10/10` pairs -> `met``",
        )

    def test_fn_122_readme_sprint7_heading_successor_first_pack_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        sprint7_heading = "Sprint-7 Program Packs (siehe auch `examples/program-packs/README.md`):"
        first_pack_bullet = "- `examples/program-packs/ingest-normalize/` (Pack #1)"

        self.assertEqual(
            lines.count(sprint7_heading),
            1,
            "README.md: expected exactly one canonical `Sprint-7 Program Packs` heading",
        )
        self.assertEqual(
            lines.count(first_pack_bullet),
            1,
            "README.md: expected exactly one canonical first program-pack bullet",
        )

        sprint7_heading_index = lines.index(sprint7_heading)
        self.assertLess(
            sprint7_heading_index + 1,
            len(lines),
            "README.md: Sprint-7 heading must be immediately followed by first program-pack bullet",
        )
        self.assertEqual(
            lines[sprint7_heading_index + 1].strip(),
            first_pack_bullet,
            "README.md: `Sprint-7 Program Packs (siehe auch `examples/program-packs/README.md`):` must be immediately followed by `- `examples/program-packs/ingest-normalize/` (Pack #1)`",
        )

    def test_fn_123_runtime_third_action_bullet_successor_score_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        third_bullet = '- Missing `then` defaults to: `{"kind": "act", "params": {"rule_id": <rule.id>}}`.'
        score_heading = "### Score semantics"

        self.assertEqual(
            lines.count(third_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical third action-emission bullet",
        )
        self.assertEqual(
            lines.count(score_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical score-semantics heading",
        )

        third_bullet_index = lines.index(third_bullet)
        self.assertLess(
            third_bullet_index + 2,
            len(lines),
            "docs/runtime-determinism.md: third action-emission bullet must be followed by one blank separator and the score-semantics heading",
        )
        self.assertEqual(
            lines[third_bullet_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: third action-emission bullet must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[third_bullet_index + 2].strip(),
            score_heading,
            'docs/runtime-determinism.md: first non-empty successor after `- Missing `then` defaults to: `{"kind": "act", "params": {"rule_id": <rule.id>}}`.` must be `### Score semantics`',
        )

    def test_fn_124_gate_fixture_floor_line_successor_calibration_floor_line_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        fixture_floor_line = "- Fixture floor: `10/10` pairs -> `met`"
        calibration_floor_line = "- Calibration fixture floor: `2/2` pairs -> `met`"

        self.assertEqual(
            lines.count(fixture_floor_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical fixture-floor line",
        )
        self.assertEqual(
            lines.count(calibration_floor_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical calibration-fixture-floor line",
        )

        fixture_floor_line_index = lines.index(fixture_floor_line)
        self.assertLess(
            fixture_floor_line_index + 1,
            len(lines),
            "docs/quality-gates.md: fixture-floor line must be immediately followed by calibration-fixture-floor line",
        )
        self.assertEqual(
            lines[fixture_floor_line_index + 1].strip(),
            calibration_floor_line,
            "docs/quality-gates.md: `- Fixture floor: `10/10` pairs -> `met`` must be immediately followed by `- Calibration fixture floor: `2/2` pairs -> `met``",
        )

    def test_fn_125_readme_sprint7_first_pack_successor_second_pack_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        first_pack_bullet = "- `examples/program-packs/ingest-normalize/` (Pack #1)"
        second_pack_bullet = "- `examples/program-packs/dedup-cluster/` (Pack #2)"

        self.assertEqual(
            lines.count(first_pack_bullet),
            1,
            "README.md: expected exactly one canonical first program-pack bullet",
        )
        self.assertEqual(
            lines.count(second_pack_bullet),
            1,
            "README.md: expected exactly one canonical second program-pack bullet",
        )

        first_pack_bullet_index = lines.index(first_pack_bullet)
        self.assertLess(
            first_pack_bullet_index + 1,
            len(lines),
            "README.md: first program-pack bullet must be immediately followed by second program-pack bullet",
        )
        self.assertEqual(
            lines[first_pack_bullet_index + 1].strip(),
            second_pack_bullet,
            "README.md: `- `examples/program-packs/ingest-normalize/` (Pack #1)` must be immediately followed by `- `examples/program-packs/dedup-cluster/` (Pack #2)`",
        )

    def test_fn_126_runtime_score_heading_successor_first_score_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        score_heading = "### Score semantics"
        first_score_bullet = "- `score` is structural match coverage for fired rules:"

        self.assertEqual(
            lines.count(score_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical score-semantics heading",
        )
        self.assertEqual(
            lines.count(first_score_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first score bullet",
        )

        score_heading_index = lines.index(score_heading)
        self.assertLess(
            score_heading_index + 2,
            len(lines),
            "docs/runtime-determinism.md: score-semantics heading must be followed by one blank separator and first score bullet",
        )
        self.assertEqual(
            lines[score_heading_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: score-semantics heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[score_heading_index + 2].strip(),
            first_score_bullet,
            "docs/runtime-determinism.md: first non-empty successor after `### Score semantics` must be `- `score` is structural match coverage for fired rules:`",
        )

    def test_fn_127_gate_calibration_floor_line_successor_cross_links_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        calibration_floor_line = "- Calibration fixture floor: `2/2` pairs -> `met`"
        cross_links_heading = "Release-close cross-links:"

        self.assertEqual(
            lines.count(calibration_floor_line),
            1,
            "docs/quality-gates.md: expected exactly one canonical calibration-fixture-floor line",
        )
        self.assertEqual(
            lines.count(cross_links_heading),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-close cross-links heading",
        )

        calibration_floor_line_index = lines.index(calibration_floor_line)
        self.assertLess(
            calibration_floor_line_index + 2,
            len(lines),
            "docs/quality-gates.md: calibration-fixture-floor line must be followed by one blank separator and release-close cross-links heading",
        )
        self.assertEqual(
            lines[calibration_floor_line_index + 1].strip(),
            "",
            "docs/quality-gates.md: calibration-fixture-floor line must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[calibration_floor_line_index + 2].strip(),
            cross_links_heading,
            "docs/quality-gates.md: first non-empty successor after `- Calibration fixture floor: `2/2` pairs -> `met`` must be `Release-close cross-links:`",
        )

    def test_fn_128_readme_sprint7_second_pack_successor_third_pack_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        second_pack_bullet = "- `examples/program-packs/dedup-cluster/` (Pack #2)"
        third_pack_bullet = "- `examples/program-packs/alert-routing/` (Pack #3)"

        self.assertEqual(
            lines.count(second_pack_bullet),
            1,
            "README.md: expected exactly one canonical second program-pack bullet",
        )
        self.assertEqual(
            lines.count(third_pack_bullet),
            1,
            "README.md: expected exactly one canonical third program-pack bullet",
        )

        second_pack_bullet_index = lines.index(second_pack_bullet)
        self.assertLess(
            second_pack_bullet_index + 1,
            len(lines),
            "README.md: second program-pack bullet must be immediately followed by third program-pack bullet",
        )
        self.assertEqual(
            lines[second_pack_bullet_index + 1].strip(),
            third_pack_bullet,
            "README.md: `- `examples/program-packs/dedup-cluster/` (Pack #2)` must be immediately followed by `- `examples/program-packs/alert-routing/` (Pack #3)`",
        )

    def test_fn_129_runtime_first_score_bullet_successor_continuation_line_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        first_score_bullet = "- `score` is structural match coverage for fired rules:"
        continuation_line = "  `len(matched_clauses) / len(rule.when)`."

        self.assertEqual(
            lines.count(first_score_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first score bullet",
        )
        self.assertEqual(
            lines.count(continuation_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical score continuation line",
        )

        first_score_bullet_index = lines.index(first_score_bullet)
        self.assertLess(
            first_score_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: first score bullet must be immediately followed by continuation line",
        )
        self.assertEqual(
            lines[first_score_bullet_index + 1],
            continuation_line,
            "docs/runtime-determinism.md: `- `score` is structural match coverage for fired rules:` must be immediately followed by `  `len(matched_clauses) / len(rule.when)`.`",
        )

    def test_fn_130_gate_release_cross_links_heading_successor_first_link_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        cross_links_heading = "Release-close cross-links:"
        first_link_bullet = (
            '- Acceptance freeze checklist: `docs/acceptance-metrics.md` ("v0.1 release-close checklist")'
        )

        self.assertEqual(
            lines.count(cross_links_heading),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-close cross-links heading",
        )
        self.assertEqual(
            lines.count(first_link_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical first release-close cross-link bullet",
        )

        cross_links_heading_index = lines.index(cross_links_heading)
        self.assertLess(
            cross_links_heading_index + 1,
            len(lines),
            "docs/quality-gates.md: release-close cross-links heading must be immediately followed by first cross-link bullet",
        )
        self.assertEqual(
            lines[cross_links_heading_index + 1].strip(),
            first_link_bullet,
            'docs/quality-gates.md: `Release-close cross-links:` must be immediately followed by `- Acceptance freeze checklist: `docs/acceptance-metrics.md` ("v0.1 release-close checklist")`',
        )

    def test_fn_131_readme_sprint7_third_pack_successor_calibration_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        third_pack_bullet = "- `examples/program-packs/alert-routing/` (Pack #3)"
        calibration_heading = "### Calibration (Sprint-5 kickoff)"

        self.assertEqual(
            lines.count(third_pack_bullet),
            1,
            "README.md: expected exactly one canonical third program-pack bullet",
        )
        self.assertEqual(
            lines.count(calibration_heading),
            1,
            "README.md: expected exactly one canonical calibration heading",
        )

        third_pack_bullet_index = lines.index(third_pack_bullet)
        self.assertLess(
            third_pack_bullet_index + 2,
            len(lines),
            "README.md: third program-pack bullet must be followed by one blank separator and calibration heading",
        )
        self.assertEqual(
            lines[third_pack_bullet_index + 1].strip(),
            "",
            "README.md: third program-pack bullet must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[third_pack_bullet_index + 2].strip(),
            calibration_heading,
            "README.md: first non-empty successor after `- `examples/program-packs/alert-routing/` (Pack #3)` must be `### Calibration (Sprint-5 kickoff)`",
        )

    def test_fn_132_runtime_score_continuation_line_successor_second_score_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        continuation_line = "  `len(matched_clauses) / len(rule.when)`."
        second_score_bullet = (
            "- Because only fully matched AND-rules fire in v0, fired rules currently emit `score = 1.0`."
        )

        self.assertEqual(
            lines.count(continuation_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical score continuation line",
        )
        self.assertEqual(
            lines.count(second_score_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second score bullet",
        )

        continuation_line_index = lines.index(continuation_line)
        self.assertLess(
            continuation_line_index + 1,
            len(lines),
            "docs/runtime-determinism.md: score continuation line must be immediately followed by second score bullet",
        )
        self.assertEqual(
            lines[continuation_line_index + 1].strip(),
            second_score_bullet,
            "docs/runtime-determinism.md: `  `len(matched_clauses) / len(rule.when)`.` must be immediately followed by `- Because only fully matched AND-rules fire in v0, fired rules currently emit `score = 1.0`.`",
        )

    def test_fn_133_gate_first_release_cross_link_bullet_successor_second_link_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        first_link_bullet = (
            '- Acceptance freeze checklist: `docs/acceptance-metrics.md` ("v0.1 release-close checklist")'
        )
        second_link_bullet = (
            '- Migration freeze note: `docs/migrations.md` ("v0.1 release-close freeze")'
        )

        self.assertEqual(
            lines.count(first_link_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical first release-close cross-link bullet",
        )
        self.assertEqual(
            lines.count(second_link_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical second release-close cross-link bullet",
        )

        first_link_bullet_index = lines.index(first_link_bullet)
        self.assertLess(
            first_link_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: first release-close cross-link bullet must be immediately followed by second cross-link bullet",
        )
        self.assertEqual(
            lines[first_link_bullet_index + 1].strip(),
            second_link_bullet,
            'docs/quality-gates.md: `- Acceptance freeze checklist: `docs/acceptance-metrics.md` ("v0.1 release-close checklist")` must be immediately followed by `- Migration freeze note: `docs/migrations.md` ("v0.1 release-close freeze")`',
        )

    def test_fn_134_readme_calibration_heading_successor_first_calibration_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        calibration_heading = "### Calibration (Sprint-5 kickoff)"
        first_calibration_bullet = (
            "- Minimal piecewise-linear calibration scaffold: `runtime/calibration.py`"
        )

        self.assertEqual(
            lines.count(calibration_heading),
            1,
            "README.md: expected exactly one canonical calibration heading",
        )
        self.assertEqual(
            lines.count(first_calibration_bullet),
            1,
            "README.md: expected exactly one canonical first calibration bullet",
        )

        calibration_heading_index = lines.index(calibration_heading)
        self.assertLess(
            calibration_heading_index + 2,
            len(lines),
            "README.md: calibration heading must be followed by one blank separator and first calibration bullet",
        )
        self.assertEqual(
            lines[calibration_heading_index + 1].strip(),
            "",
            "README.md: calibration heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[calibration_heading_index + 2].strip(),
            first_calibration_bullet,
            "README.md: first non-empty successor after `### Calibration (Sprint-5 kickoff)` must be `- Minimal piecewise-linear calibration scaffold: `runtime/calibration.py``",
        )

    def test_fn_135_runtime_second_score_bullet_successor_third_score_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        second_score_bullet = (
            "- Because only fully matched AND-rules fire in v0, fired rules currently emit `score = 1.0`."
        )
        third_score_bullet = "- If `include_score=False`, `score` is omitted."

        self.assertEqual(
            lines.count(second_score_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second score bullet",
        )
        self.assertEqual(
            lines.count(third_score_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical third score bullet",
        )

        second_score_bullet_index = lines.index(second_score_bullet)
        self.assertLess(
            second_score_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: second score bullet must be immediately followed by third score bullet",
        )
        self.assertEqual(
            lines[second_score_bullet_index + 1].strip(),
            third_score_bullet,
            "docs/runtime-determinism.md: `- Because only fully matched AND-rules fire in v0, fired rules currently emit `score = 1.0`.` must be immediately followed by `- If `include_score=False`, `score` is omitted.`",
        )

    def test_fn_136_gate_second_release_cross_link_bullet_successor_third_link_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        second_link_bullet = (
            '- Migration freeze note: `docs/migrations.md` ("v0.1 release-close freeze")'
        )
        third_link_bullet = (
            '- Ship status summary: `docs/review-sprint1.md` ("v0.1 ship-ready summary")'
        )

        self.assertEqual(
            lines.count(second_link_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical second release-close cross-link bullet",
        )
        self.assertEqual(
            lines.count(third_link_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical third release-close cross-link bullet",
        )

        second_link_bullet_index = lines.index(second_link_bullet)
        self.assertLess(
            second_link_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: second release-close cross-link bullet must be immediately followed by third cross-link bullet",
        )
        self.assertEqual(
            lines[second_link_bullet_index + 1].strip(),
            third_link_bullet,
            'docs/quality-gates.md: `- Migration freeze note: `docs/migrations.md` ("v0.1 release-close freeze")` must be immediately followed by `- Ship status summary: `docs/review-sprint1.md` ("v0.1 ship-ready summary")`',
        )

    def test_fn_137_readme_first_calibration_bullet_successor_api_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        first_calibration_bullet = (
            "- Minimal piecewise-linear calibration scaffold: `runtime/calibration.py`"
        )
        api_bullet = "- API: `map_raw_score_to_probability(raw_score, calibration)`"

        self.assertEqual(
            lines.count(first_calibration_bullet),
            1,
            "README.md: expected exactly one canonical first calibration bullet",
        )
        self.assertEqual(
            lines.count(api_bullet),
            1,
            "README.md: expected exactly one canonical calibration API bullet",
        )

        first_calibration_bullet_index = lines.index(first_calibration_bullet)
        self.assertLess(
            first_calibration_bullet_index + 1,
            len(lines),
            "README.md: first calibration bullet must be immediately followed by calibration API bullet",
        )
        self.assertEqual(
            lines[first_calibration_bullet_index + 1].strip(),
            api_bullet,
            "README.md: `- Minimal piecewise-linear calibration scaffold: `runtime/calibration.py`` must be immediately followed by `- API: `map_raw_score_to_probability(raw_score, calibration)``",
        )

    def test_fn_138_runtime_third_score_bullet_successor_calibration_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        third_score_bullet = "- If `include_score=False`, `score` is omitted."
        calibration_heading = "### Calibration integration semantics (Sprint-5)"

        self.assertEqual(
            lines.count(third_score_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical third score bullet",
        )
        self.assertEqual(
            lines.count(calibration_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical calibration integration heading",
        )

        third_score_bullet_index = lines.index(third_score_bullet)
        self.assertLess(
            third_score_bullet_index + 2,
            len(lines),
            "docs/runtime-determinism.md: third score bullet must be followed by one blank separator and calibration integration heading",
        )
        self.assertEqual(
            lines[third_score_bullet_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: third score bullet must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[third_score_bullet_index + 2].strip(),
            calibration_heading,
            "docs/runtime-determinism.md: first non-empty successor after `- If `include_score=False`, `score` is omitted.` must be `### Calibration integration semantics (Sprint-5)`",
        )

    def test_fn_139_gate_third_release_cross_link_bullet_successor_release_evidence_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        third_link_bullet = (
            '- Ship status summary: `docs/review-sprint1.md` ("v0.1 ship-ready summary")'
        )
        release_evidence_heading = "Release evidence automation:"

        self.assertEqual(
            lines.count(third_link_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical third release-close cross-link bullet",
        )
        self.assertEqual(
            lines.count(release_evidence_heading),
            1,
            "docs/quality-gates.md: expected exactly one canonical release evidence heading",
        )

        third_link_bullet_index = lines.index(third_link_bullet)
        self.assertLess(
            third_link_bullet_index + 2,
            len(lines),
            "docs/quality-gates.md: third release-close cross-link bullet must be followed by one blank separator and release evidence heading",
        )
        self.assertEqual(
            lines[third_link_bullet_index + 1].strip(),
            "",
            "docs/quality-gates.md: third release-close cross-link bullet must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[third_link_bullet_index + 2].strip(),
            release_evidence_heading,
            'docs/quality-gates.md: first non-empty successor after `- Ship status summary: `docs/review-sprint1.md` ("v0.1 ship-ready summary")` must be `Release evidence automation:`',
        )

    def test_fn_140_readme_calibration_api_bullet_successor_details_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        api_bullet = "- API: `map_raw_score_to_probability(raw_score, calibration)`"
        details_bullet = "- Details + guard semantics: `docs/calibration-v0.md`"

        self.assertEqual(
            lines.count(api_bullet),
            1,
            "README.md: expected exactly one canonical calibration API bullet",
        )
        self.assertEqual(
            lines.count(details_bullet),
            1,
            "README.md: expected exactly one canonical calibration details bullet",
        )

        api_bullet_index = lines.index(api_bullet)
        self.assertLess(
            api_bullet_index + 1,
            len(lines),
            "README.md: calibration API bullet must be immediately followed by calibration details bullet",
        )
        self.assertEqual(
            lines[api_bullet_index + 1].strip(),
            details_bullet,
            "README.md: `- API: `map_raw_score_to_probability(raw_score, calibration)`` must be immediately followed by `- Details + guard semantics: `docs/calibration-v0.md``",
        )

    def test_fn_141_runtime_calibration_heading_successor_first_calibration_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        calibration_heading = "### Calibration integration semantics (Sprint-5)"
        first_calibration_bullet = (
            "- `eval_policies(..., calibration=<config>)` applies deterministic piecewise-linear mapping"
        )

        self.assertEqual(
            lines.count(calibration_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical calibration integration heading",
        )
        self.assertEqual(
            lines.count(first_calibration_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first calibration integration bullet",
        )

        calibration_heading_index = lines.index(calibration_heading)
        self.assertLess(
            calibration_heading_index + 2,
            len(lines),
            "docs/runtime-determinism.md: calibration integration heading must be followed by one blank separator and first calibration bullet",
        )
        self.assertEqual(
            lines[calibration_heading_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: calibration integration heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[calibration_heading_index + 2].strip(),
            first_calibration_bullet,
            "docs/runtime-determinism.md: first non-empty successor after `### Calibration integration semantics (Sprint-5)` must be `- `eval_policies(..., calibration=<config>)` applies deterministic piecewise-linear mapping`",
        )

    def test_fn_142_gate_release_evidence_heading_successor_hook_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        release_evidence_heading = "Release evidence automation:"
        hook_bullet = "- Optional post-pass hook (opt-in, `scripts/check.sh` unchanged by default): `./scripts/check.sh && python3 scripts/release_snapshot.py`."

        self.assertEqual(
            lines.count(release_evidence_heading),
            1,
            "docs/quality-gates.md: expected exactly one canonical release evidence heading",
        )
        self.assertEqual(
            lines.count(hook_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical optional post-pass hook bullet",
        )

        release_evidence_heading_index = lines.index(release_evidence_heading)
        self.assertLess(
            release_evidence_heading_index + 1,
            len(lines),
            "docs/quality-gates.md: release evidence heading must be immediately followed by optional post-pass hook bullet",
        )
        self.assertEqual(
            lines[release_evidence_heading_index + 1].strip(),
            hook_bullet,
            "docs/quality-gates.md: `Release evidence automation:` must be immediately followed by `- Optional post-pass hook (opt-in, `scripts/check.sh` unchanged by default): `./scripts/check.sh && python3 scripts/release_snapshot.py`.`",
        )

    def test_fn_143_readme_calibration_details_bullet_successor_canonical_formatting_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        details_bullet = "- Details + guard semantics: `docs/calibration-v0.md`"
        canonical_formatting_heading = "### Canonical Formatting"

        self.assertEqual(
            lines.count(details_bullet),
            1,
            "README.md: expected exactly one canonical calibration details bullet",
        )
        self.assertEqual(
            lines.count(canonical_formatting_heading),
            1,
            "README.md: expected exactly one canonical `### Canonical Formatting` heading",
        )

        details_bullet_index = lines.index(details_bullet)
        self.assertLess(
            details_bullet_index + 2,
            len(lines),
            "README.md: calibration details bullet must be followed by one blank separator and canonical formatting heading",
        )
        self.assertEqual(
            lines[details_bullet_index + 1].strip(),
            "",
            "README.md: calibration details bullet must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[details_bullet_index + 2].strip(),
            canonical_formatting_heading,
            "README.md: first non-empty successor after `- Details + guard semantics: `docs/calibration-v0.md`` must be `### Canonical Formatting`",
        )

    def test_fn_144_runtime_first_calibration_bullet_successor_continuation_line_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        first_calibration_bullet = (
            "- `eval_policies(..., calibration=<config>)` applies deterministic piecewise-linear mapping"
        )
        continuation_line = "(`runtime.calibration.map_raw_score_to_probability`) to the structural raw score."

        self.assertEqual(
            lines.count(first_calibration_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first calibration integration bullet",
        )
        self.assertEqual(
            sum(1 for line in lines if line.strip() == continuation_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical continuation line for first calibration integration bullet",
        )

        first_calibration_bullet_index = lines.index(first_calibration_bullet)
        self.assertLess(
            first_calibration_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: first calibration integration bullet must be immediately followed by its continuation line",
        )
        self.assertEqual(
            lines[first_calibration_bullet_index + 1].strip(),
            continuation_line,
            "docs/runtime-determinism.md: `- `eval_policies(..., calibration=<config>)` applies deterministic piecewise-linear mapping` must be immediately followed by `(`runtime.calibration.map_raw_score_to_probability`) to the structural raw score.`",
        )

    def test_fn_145_gate_hook_bullet_successor_hook_line_boundary_bullet_canary(self) -> None:
        lines = self.quality_gates_doc.splitlines()
        hook_bullet = "- Optional post-pass hook (opt-in, `scripts/check.sh` unchanged by default): `./scripts/check.sh && python3 scripts/release_snapshot.py`."
        hook_line_boundary_bullet = "- Hook-line boundary/order contract (RL-040/RL-041): keep exactly one standalone `Optional post-pass hook` bullet and keep it before the `Dated snapshots are written...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_040_quality_gates_release_hook_bullet_line_singularity_boundary_canary`, `test_rl_041_quality_gates_release_hook_before_dated_snapshot_bullet_order_canary`)."

        self.assertEqual(
            lines.count(hook_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical optional post-pass hook bullet",
        )
        self.assertEqual(
            lines.count(hook_line_boundary_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical hook-line boundary/order contract bullet",
        )

        hook_bullet_index = lines.index(hook_bullet)
        self.assertLess(
            hook_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: optional post-pass hook bullet must be immediately followed by hook-line boundary/order contract bullet",
        )
        self.assertEqual(
            lines[hook_bullet_index + 1].strip(),
            hook_line_boundary_bullet,
            "docs/quality-gates.md: `- Optional post-pass hook (opt-in, `scripts/check.sh` unchanged by default): `./scripts/check.sh && python3 scripts/release_snapshot.py`.` must be immediately followed by the `- Hook-line boundary/order contract (RL-040/RL-041): ...` bullet",
        )

    def test_fn_146_readme_canonical_formatting_heading_successor_first_formatting_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        canonical_formatting_heading = "### Canonical Formatting"
        first_formatting_bullet = "- deterministische Feldreihenfolge pro Statement"

        self.assertEqual(
            lines.count(canonical_formatting_heading),
            1,
            "README.md: expected exactly one canonical `### Canonical Formatting` heading",
        )
        self.assertEqual(
            lines.count(first_formatting_bullet),
            1,
            "README.md: expected exactly one canonical first formatting bullet",
        )

        canonical_formatting_heading_index = lines.index(canonical_formatting_heading)
        self.assertLess(
            canonical_formatting_heading_index + 2,
            len(lines),
            "README.md: canonical formatting heading must be followed by one blank separator and first formatting bullet",
        )
        self.assertEqual(
            lines[canonical_formatting_heading_index + 1].strip(),
            "",
            "README.md: canonical formatting heading must be followed by exactly one blank separator line",
        )
        self.assertEqual(
            lines[canonical_formatting_heading_index + 2].strip(),
            first_formatting_bullet,
            "README.md: first non-empty successor after `### Canonical Formatting` must be `- deterministische Feldreihenfolge pro Statement`",
        )

    def test_fn_147_runtime_calibration_continuation_line_successor_mapped_value_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        continuation_line = "(`runtime.calibration.map_raw_score_to_probability`) to the structural raw score."
        mapped_value_bullet = "- The mapped value is emitted as `trace[].calibrated_probability`."

        self.assertEqual(
            sum(1 for line in lines if line.strip() == continuation_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical continuation line for first calibration integration bullet",
        )
        self.assertEqual(
            lines.count(mapped_value_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical mapped-value calibration bullet",
        )

        continuation_line_index = next(
            index for index, line in enumerate(lines) if line.strip() == continuation_line
        )
        self.assertLess(
            continuation_line_index + 1,
            len(lines),
            "docs/runtime-determinism.md: calibration continuation line must be immediately followed by mapped-value calibration bullet",
        )
        self.assertEqual(
            lines[continuation_line_index + 1].strip(),
            mapped_value_bullet,
            "docs/runtime-determinism.md: `(`runtime.calibration.map_raw_score_to_probability`) to the structural raw score.` must be immediately followed by `- The mapped value is emitted as `trace[].calibrated_probability`.`",
        )

    def test_fn_148_gate_hook_line_boundary_bullet_successor_dated_snapshot_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        hook_line_boundary_bullet = "- Hook-line boundary/order contract (RL-040/RL-041): keep exactly one standalone `Optional post-pass hook` bullet and keep it before the `Dated snapshots are written...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_040_quality_gates_release_hook_bullet_line_singularity_boundary_canary`, `test_rl_041_quality_gates_release_hook_before_dated_snapshot_bullet_order_canary`)."
        dated_snapshot_bullet = "- Dated snapshots are written to `docs/release-artifacts/release-snapshot-<UTCSTAMP>.{json,md}` and mirrored to `docs/release-artifacts/latest.{json,md}`."

        self.assertEqual(
            lines.count(hook_line_boundary_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical hook-line boundary/order contract bullet",
        )
        self.assertEqual(
            lines.count(dated_snapshot_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical dated-snapshot bullet",
        )

        hook_line_boundary_bullet_index = lines.index(hook_line_boundary_bullet)
        self.assertLess(
            hook_line_boundary_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: hook-line boundary/order contract bullet must be immediately followed by dated-snapshot bullet",
        )
        self.assertEqual(
            lines[hook_line_boundary_bullet_index + 1].strip(),
            dated_snapshot_bullet,
            "docs/quality-gates.md: `- Hook-line boundary/order contract (RL-040/RL-041): ...` must be immediately followed by `- Dated snapshots are written to `docs/release-artifacts/release-snapshot-<UTCSTAMP>.{json,md}` and mirrored to `docs/release-artifacts/latest.{json,md}`.`",
        )

    def test_fn_149_readme_first_formatting_bullet_successor_second_formatting_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        first_formatting_bullet = "- deterministische Feldreihenfolge pro Statement"
        second_formatting_bullet = "- sortierte Objekt-Keys"

        self.assertEqual(
            lines.count(first_formatting_bullet),
            1,
            "README.md: expected exactly one canonical first formatting bullet",
        )
        self.assertEqual(
            lines.count(second_formatting_bullet),
            1,
            "README.md: expected exactly one canonical second formatting bullet",
        )

        first_formatting_bullet_index = lines.index(first_formatting_bullet)
        self.assertLess(
            first_formatting_bullet_index + 1,
            len(lines),
            "README.md: first formatting bullet must be immediately followed by second formatting bullet",
        )
        self.assertEqual(
            lines[first_formatting_bullet_index + 1].strip(),
            second_formatting_bullet,
            "README.md: `- deterministische Feldreihenfolge pro Statement` must be immediately followed by `- sortierte Objekt-Keys`",
        )

    def test_fn_150_runtime_mapped_value_bullet_successor_optional_calibration_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        mapped_value_bullet = "- The mapped value is emitted as `trace[].calibrated_probability`."
        optional_calibration_bullet = "- Calibration is optional; when omitted, trace shape remains backward compatible."

        self.assertEqual(
            lines.count(mapped_value_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical mapped-value calibration bullet",
        )
        self.assertEqual(
            lines.count(optional_calibration_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical optional-calibration bullet",
        )

        mapped_value_bullet_index = lines.index(mapped_value_bullet)
        self.assertLess(
            mapped_value_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: mapped-value calibration bullet must be immediately followed by optional-calibration bullet",
        )
        self.assertEqual(
            lines[mapped_value_bullet_index + 1].strip(),
            optional_calibration_bullet,
            "docs/runtime-determinism.md: `- The mapped value is emitted as `trace[].calibrated_probability`.` must be immediately followed by `- Calibration is optional; when omitted, trace shape remains backward compatible.`",
        )

    def test_fn_151_gate_dated_snapshot_bullet_successor_dated_snapshot_boundary_contract_bullet_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        dated_snapshot_bullet = "- Dated snapshots are written to `docs/release-artifacts/release-snapshot-<UTCSTAMP>.{json,md}` and mirrored to `docs/release-artifacts/latest.{json,md}`."
        dated_snapshot_boundary_contract_bullet = "- Dated-snapshot bullet boundary contract (RL-043/RL-044): keep exactly one standalone `Dated snapshots are written...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_043_quality_gates_dated_snapshot_bullet_singularity_canary`, `test_rl_044_quality_gates_dated_snapshot_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(dated_snapshot_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical dated-snapshot bullet",
        )
        self.assertEqual(
            lines.count(dated_snapshot_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical dated-snapshot boundary-contract bullet",
        )

        dated_snapshot_bullet_index = lines.index(dated_snapshot_bullet)
        self.assertLess(
            dated_snapshot_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: dated-snapshot bullet must be immediately followed by dated-snapshot boundary-contract bullet",
        )
        self.assertEqual(
            lines[dated_snapshot_bullet_index + 1].strip(),
            dated_snapshot_boundary_contract_bullet,
            "docs/quality-gates.md: `- Dated snapshots are written to `docs/release-artifacts/release-snapshot-<UTCSTAMP>.{json,md}` and mirrored to `docs/release-artifacts/latest.{json,md}`.` must be immediately followed by `- Dated-snapshot bullet boundary contract (RL-043/RL-044): ...`",
        )

    def test_fn_152_readme_second_formatting_bullet_successor_third_formatting_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        second_formatting_bullet = "- sortierte Objekt-Keys"
        third_formatting_bullet = "- keine optionalen Leerzeichen"

        self.assertEqual(
            lines.count(second_formatting_bullet),
            1,
            "README.md: expected exactly one canonical second formatting bullet",
        )
        self.assertEqual(
            lines.count(third_formatting_bullet),
            1,
            "README.md: expected exactly one canonical third formatting bullet",
        )

        second_formatting_bullet_index = lines.index(second_formatting_bullet)
        self.assertLess(
            second_formatting_bullet_index + 1,
            len(lines),
            "README.md: second formatting bullet must be immediately followed by third formatting bullet",
        )
        self.assertEqual(
            lines[second_formatting_bullet_index + 1].strip(),
            third_formatting_bullet,
            "README.md: `- sortierte Objekt-Keys` must be immediately followed by `- keine optionalen Leerzeichen`",
        )

    def test_fn_153_runtime_optional_calibration_bullet_successor_calibration_input_effects_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        optional_calibration_bullet = "- Calibration is optional; when omitted, trace shape remains backward compatible."
        calibration_input_effects_bullet = "- Calibration input affects trace output only; it does not change rule matching or action emission."

        self.assertEqual(
            lines.count(optional_calibration_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical optional-calibration bullet",
        )
        self.assertEqual(
            lines.count(calibration_input_effects_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical calibration-input-effects bullet",
        )

        optional_calibration_bullet_index = lines.index(optional_calibration_bullet)
        self.assertLess(
            optional_calibration_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: optional-calibration bullet must be immediately followed by calibration-input-effects bullet",
        )
        self.assertEqual(
            lines[optional_calibration_bullet_index + 1].strip(),
            calibration_input_effects_bullet,
            "docs/runtime-determinism.md: `- Calibration is optional; when omitted, trace shape remains backward compatible.` must be immediately followed by `- Calibration input affects trace output only; it does not change rule matching or action emission.`",
        )

    def test_fn_154_gate_dated_snapshot_boundary_contract_bullet_successor_naming_policy_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        dated_snapshot_boundary_contract_bullet = "- Dated-snapshot bullet boundary contract (RL-043/RL-044): keep exactly one standalone `Dated snapshots are written...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_043_quality_gates_dated_snapshot_bullet_singularity_canary`, `test_rl_044_quality_gates_dated_snapshot_bullet_line_boundary_canary`)."
        naming_policy_bullet = "- Naming/latest-pointer/cleanup policy plus manual prune command snippets are indexed in `docs/release-artifacts/README.md`."

        self.assertEqual(
            lines.count(dated_snapshot_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical dated-snapshot boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(naming_policy_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical naming-policy bullet",
        )

        dated_snapshot_boundary_contract_bullet_index = lines.index(
            dated_snapshot_boundary_contract_bullet
        )
        self.assertLess(
            dated_snapshot_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: dated-snapshot boundary-contract bullet must be immediately followed by naming-policy bullet",
        )
        self.assertEqual(
            lines[dated_snapshot_boundary_contract_bullet_index + 1].strip(),
            naming_policy_bullet,
            "docs/quality-gates.md: `- Dated-snapshot bullet boundary contract (RL-043/RL-044): ...` must be immediately followed by `- Naming/latest-pointer/cleanup policy plus manual prune command snippets are indexed in `docs/release-artifacts/README.md`.`",
        )

    def test_fn_155_readme_third_formatting_bullet_successor_fourth_formatting_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        third_formatting_bullet = "- keine optionalen Leerzeichen"
        fourth_formatting_bullet = (
            "- stabiler Output für denselben unterstützten Input"
        )

        self.assertEqual(
            lines.count(third_formatting_bullet),
            1,
            "README.md: expected exactly one canonical third formatting bullet",
        )
        self.assertEqual(
            lines.count(fourth_formatting_bullet),
            1,
            "README.md: expected exactly one canonical fourth formatting bullet",
        )

        third_formatting_bullet_index = lines.index(third_formatting_bullet)
        self.assertLess(
            third_formatting_bullet_index + 1,
            len(lines),
            "README.md: third formatting bullet must be immediately followed by fourth formatting bullet",
        )
        self.assertEqual(
            lines[third_formatting_bullet_index + 1].strip(),
            fourth_formatting_bullet,
            "README.md: `- keine optionalen Leerzeichen` must be immediately followed by `- stabiler Output für denselben unterstützten Input`",
        )

    def test_fn_156_runtime_calibration_input_effects_bullet_successor_no_wall_clock_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        calibration_input_effects_bullet = "- Calibration input affects trace output only; it does not change rule matching or action emission."
        no_wall_clock_bullet = "- No wall-clock reads or randomness are introduced by calibration flow."

        self.assertEqual(
            lines.count(calibration_input_effects_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical calibration-input-effects bullet",
        )
        self.assertEqual(
            lines.count(no_wall_clock_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical no-wall-clock bullet",
        )

        calibration_input_effects_bullet_index = lines.index(
            calibration_input_effects_bullet
        )
        self.assertLess(
            calibration_input_effects_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: calibration-input-effects bullet must be immediately followed by no-wall-clock bullet",
        )
        self.assertEqual(
            lines[calibration_input_effects_bullet_index + 1].strip(),
            no_wall_clock_bullet,
            "docs/runtime-determinism.md: `- Calibration input affects trace output only; it does not change rule matching or action emission.` must be immediately followed by `- No wall-clock reads or randomness are introduced by calibration flow.`",
        )


    def test_fn_157_gate_naming_policy_bullet_successor_naming_policy_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        naming_policy_bullet = "- Naming/latest-pointer/cleanup policy plus manual prune command snippets are indexed in `docs/release-artifacts/README.md`."
        naming_policy_boundary_contract_bullet = "- Naming-policy bullet boundary contract (RL-046/RL-047): keep exactly one standalone `Naming/latest-pointer/cleanup policy...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_046_quality_gates_naming_policy_bullet_singularity_canary`, `test_rl_047_quality_gates_naming_policy_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(naming_policy_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical naming-policy bullet",
        )
        self.assertEqual(
            lines.count(naming_policy_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical naming-policy boundary-contract bullet",
        )

        naming_policy_bullet_index = lines.index(naming_policy_bullet)
        self.assertLess(
            naming_policy_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: naming-policy bullet must be immediately followed by naming-policy boundary-contract bullet",
        )
        self.assertEqual(
            lines[naming_policy_bullet_index + 1].strip(),
            naming_policy_boundary_contract_bullet,
            "docs/quality-gates.md: `- Naming/latest-pointer/cleanup policy plus manual prune command snippets are indexed in `docs/release-artifacts/README.md`.` must be immediately followed by `- Naming-policy bullet boundary contract (RL-046/RL-047): ...`",
        )

    def test_fn_158_readme_fourth_formatting_bullet_terminal_line_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        fourth_formatting_bullet = "- stabiler Output für denselben unterstützten Input"

        self.assertEqual(
            lines.count(fourth_formatting_bullet),
            1,
            "README.md: expected exactly one canonical fourth formatting bullet",
        )

        fourth_formatting_bullet_index = lines.index(fourth_formatting_bullet)
        trailing_lines = lines[fourth_formatting_bullet_index + 1 :]
        self.assertTrue(
            all(not line.strip() for line in trailing_lines),
            "README.md: `- stabiler Output für denselben unterstützten Input` must be the terminal non-empty line",
        )

    def test_fn_159_runtime_no_wall_clock_bullet_successor_separation_guard_heading_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        no_wall_clock_bullet = "- No wall-clock reads or randomness are introduced by calibration flow."
        separation_guard_heading = "### Separation guard (severity/confidence)"

        self.assertEqual(
            lines.count(no_wall_clock_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical no-wall-clock bullet",
        )
        self.assertEqual(
            lines.count(separation_guard_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical separation-guard heading",
        )

        no_wall_clock_bullet_index = lines.index(no_wall_clock_bullet)
        self.assertLess(
            no_wall_clock_bullet_index + 2,
            len(lines),
            "docs/runtime-determinism.md: no-wall-clock bullet must be followed by one blank separator line and then separation-guard heading",
        )
        self.assertEqual(
            lines[no_wall_clock_bullet_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: expected exactly one blank separator line after the no-wall-clock bullet",
        )
        self.assertEqual(
            lines[no_wall_clock_bullet_index + 2].strip(),
            separation_guard_heading,
            "docs/runtime-determinism.md: `- No wall-clock reads or randomness are introduced by calibration flow.` must be followed by exactly one blank separator line and then `### Separation guard (severity/confidence)`",
        )

    def test_fn_160_gate_naming_policy_boundary_contract_bullet_successor_release_artifact_index_quickstart_pointer_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        naming_policy_boundary_contract_bullet = "- Naming-policy bullet boundary contract (RL-046/RL-047): keep exactly one standalone `Naming/latest-pointer/cleanup policy...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_046_quality_gates_naming_policy_bullet_singularity_canary`, `test_rl_047_quality_gates_naming_policy_bullet_line_boundary_canary`)."
        release_artifact_index_quickstart_pointer_bullet = "- Release artifact index quickstart pointer is explicit and command-aligned with this release automation hook."

        self.assertEqual(
            lines.count(naming_policy_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical naming-policy boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(release_artifact_index_quickstart_pointer_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-artifact-index-quickstart-pointer bullet",
        )

        naming_policy_boundary_contract_bullet_index = lines.index(
            naming_policy_boundary_contract_bullet
        )
        self.assertLess(
            naming_policy_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: naming-policy boundary-contract bullet must be immediately followed by release-artifact-index-quickstart-pointer bullet",
        )
        self.assertEqual(
            lines[naming_policy_boundary_contract_bullet_index + 1].strip(),
            release_artifact_index_quickstart_pointer_bullet,
            "docs/quality-gates.md: `- Naming-policy bullet boundary contract (RL-046/RL-047): ...` must be immediately followed by `- Release artifact index quickstart pointer is explicit and command-aligned with this release automation hook.`",
        )

    def test_fn_161_readme_canonical_formatting_section_terminal_boundary_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        canonical_formatting_heading = "### Canonical Formatting"
        expected_canonical_formatting_bullets = [
            "- deterministische Feldreihenfolge pro Statement",
            "- sortierte Objekt-Keys",
            "- keine optionalen Leerzeichen",
            "- stabiler Output für denselben unterstützten Input",
        ]

        self.assertEqual(
            lines.count(canonical_formatting_heading),
            1,
            "README.md: expected exactly one canonical formatting heading",
        )

        heading_indices = [index for index, line in enumerate(lines) if line.startswith("### ")]
        canonical_formatting_heading_index = lines.index(canonical_formatting_heading)
        self.assertEqual(
            canonical_formatting_heading_index,
            max(heading_indices),
            "README.md: `### Canonical Formatting` must be the final `###` section heading",
        )

        for bullet in expected_canonical_formatting_bullets:
            self.assertEqual(
                lines.count(bullet),
                1,
                f"README.md: expected exactly one canonical formatting bullet: {bullet}",
            )

        section_lines = lines[canonical_formatting_heading_index + 1 :]
        section_bullets = [line.strip() for line in section_lines if line.strip().startswith("- ")]
        self.assertEqual(
            section_bullets,
            expected_canonical_formatting_bullets,
            "README.md: final `### Canonical Formatting` section must contain exactly the four canonical formatting bullets in order",
        )

    def test_fn_162_runtime_separation_guard_heading_successor_first_guard_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        separation_guard_heading = "### Separation guard (severity/confidence)"
        first_guard_bullet = (
            "- Runtime does **not** infer probabilistic semantics from payload fields like"
        )

        self.assertEqual(
            lines.count(separation_guard_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical separation-guard heading",
        )
        self.assertEqual(
            lines.count(first_guard_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first separation-guard bullet",
        )

        separation_guard_heading_index = lines.index(separation_guard_heading)
        self.assertLess(
            separation_guard_heading_index + 2,
            len(lines),
            "docs/runtime-determinism.md: separation-guard heading must be followed by one blank separator line and then first guard bullet",
        )
        self.assertEqual(
            lines[separation_guard_heading_index + 1].strip(),
            "",
            "docs/runtime-determinism.md: expected exactly one blank separator line after the separation-guard heading",
        )
        self.assertEqual(
            lines[separation_guard_heading_index + 2].strip(),
            first_guard_bullet,
            "docs/runtime-determinism.md: `### Separation guard (severity/confidence)` must be followed by exactly one blank separator line and then `- Runtime does **not** infer probabilistic semantics from payload fields like`",
        )

    def test_fn_163_gate_release_artifact_index_quickstart_pointer_bullet_successor_retention_runbook_shell_safety_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        release_artifact_index_quickstart_pointer_bullet = "- Release artifact index quickstart pointer is explicit and command-aligned with this release automation hook."
        retention_runbook_shell_safety_bullet = "- Retention runbook shell-safety contract is explicit and ordered as a checklist: `repo-root` precondition, preserve `latest.*`, then prune dated snapshots only as matched `.json` + `.md` pairs."

        self.assertEqual(
            lines.count(release_artifact_index_quickstart_pointer_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-artifact-index-quickstart-pointer bullet",
        )
        self.assertEqual(
            lines.count(retention_runbook_shell_safety_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical retention-runbook-shell-safety bullet",
        )

        release_artifact_index_quickstart_pointer_bullet_index = lines.index(
            release_artifact_index_quickstart_pointer_bullet
        )
        self.assertLess(
            release_artifact_index_quickstart_pointer_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: release-artifact-index-quickstart-pointer bullet must be immediately followed by retention-runbook-shell-safety bullet",
        )
        self.assertEqual(
            lines[release_artifact_index_quickstart_pointer_bullet_index + 1].strip(),
            retention_runbook_shell_safety_bullet,
            "docs/quality-gates.md: `- Release artifact index quickstart pointer is explicit and command-aligned with this release automation hook.` must be immediately followed by `- Retention runbook shell-safety contract is explicit and ordered as a checklist: ...`",
        )

    def test_fn_164_readme_canonical_formatting_section_non_bullet_content_exclusion_canary(
        self,
    ) -> None:
        lines = self.readme_doc.splitlines()
        canonical_formatting_heading = "### Canonical Formatting"
        expected_canonical_formatting_bullets = [
            "- deterministische Feldreihenfolge pro Statement",
            "- sortierte Objekt-Keys",
            "- keine optionalen Leerzeichen",
            "- stabiler Output für denselben unterstützten Input",
        ]

        self.assertEqual(
            lines.count(canonical_formatting_heading),
            1,
            "README.md: expected exactly one canonical formatting heading",
        )

        canonical_formatting_heading_index = lines.index(canonical_formatting_heading)
        section_lines = lines[canonical_formatting_heading_index + 1 :]
        non_empty_non_bullet_lines = [
            line for line in section_lines if line.strip() and not line.lstrip().startswith("- ")
        ]
        self.assertEqual(
            non_empty_non_bullet_lines,
            [],
            "README.md: final `### Canonical Formatting` section must not contain non-empty non-bullet lines",
        )

        section_bullets = [line.strip() for line in section_lines if line.strip()]
        self.assertEqual(
            section_bullets,
            expected_canonical_formatting_bullets,
            "README.md: final `### Canonical Formatting` section must contain no additional bullets beyond the four canonical formatting bullets",
        )

    def test_fn_165_runtime_separation_guard_first_bullet_continuation_line_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        first_guard_bullet = (
            "- Runtime does **not** infer probabilistic semantics from payload fields like"
        )
        continuation_line = "  `severity` or `confidence`."

        self.assertEqual(
            lines.count(first_guard_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first separation-guard bullet",
        )
        self.assertEqual(
            lines.count(continuation_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first separation-guard continuation line",
        )

        first_guard_bullet_index = lines.index(first_guard_bullet)
        self.assertLess(
            first_guard_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: first separation-guard bullet must be immediately followed by its continuation line",
        )
        self.assertEqual(
            lines[first_guard_bullet_index + 1],
            continuation_line,
            "docs/runtime-determinism.md: first separation-guard bullet must be immediately followed by the canonical continuation line",
        )

    def test_fn_166_gate_retention_runbook_shell_safety_bullet_successor_source_of_truth_rule_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        retention_runbook_shell_safety_bullet = "- Retention runbook shell-safety contract is explicit and ordered as a checklist: `repo-root` precondition, preserve `latest.*`, then prune dated snapshots only as matched `.json` + `.md` pairs."
        source_of_truth_rule_bullet = "- Source-of-truth rule: `bench/token-harness/results/latest.json` stays repo-pinned for non-mutating local gate runs, freshness is tracked via `docs/release-artifacts/latest.json`."

        self.assertEqual(
            lines.count(retention_runbook_shell_safety_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical retention-runbook-shell-safety bullet",
        )
        self.assertEqual(
            lines.count(source_of_truth_rule_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth rule bullet",
        )

        retention_runbook_shell_safety_bullet_index = lines.index(
            retention_runbook_shell_safety_bullet
        )
        self.assertLess(
            retention_runbook_shell_safety_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: retention-runbook-shell-safety bullet must be immediately followed by source-of-truth rule bullet",
        )
        self.assertEqual(
            lines[retention_runbook_shell_safety_bullet_index + 1].strip(),
            source_of_truth_rule_bullet,
            "docs/quality-gates.md: `- Retention runbook shell-safety contract is explicit and ordered as a checklist: ...` must be immediately followed by `- Source-of-truth rule: `bench/token-harness/results/latest.json` stays repo-pinned for non-mutating local gate runs, freshness is tracked via `docs/release-artifacts/latest.json`.`",
        )

    def test_fn_167_gate_source_of_truth_rule_bullet_successor_source_of_truth_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        source_of_truth_rule_bullet = "- Source-of-truth rule: `bench/token-harness/results/latest.json` stays repo-pinned for non-mutating local gate runs, freshness is tracked via `docs/release-artifacts/latest.json`."
        source_of_truth_boundary_contract_bullet = "- Source-of-truth bullet boundary contract (RL-049/RL-050): keep exactly one standalone `Source-of-truth rule: ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_049_quality_gates_source_of_truth_rule_bullet_singularity_canary`, `test_rl_050_quality_gates_source_of_truth_rule_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(source_of_truth_rule_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth rule bullet",
        )
        self.assertEqual(
            lines.count(source_of_truth_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth boundary-contract bullet",
        )

        source_of_truth_rule_bullet_index = lines.index(source_of_truth_rule_bullet)
        self.assertLess(
            source_of_truth_rule_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: source-of-truth rule bullet must be immediately followed by source-of-truth boundary-contract bullet",
        )
        self.assertEqual(
            lines[source_of_truth_rule_bullet_index + 1].strip(),
            source_of_truth_boundary_contract_bullet,
            "docs/quality-gates.md: `- Source-of-truth rule: ...` must be immediately followed by `- Source-of-truth bullet boundary contract (RL-049/RL-050): ...`",
        )

    def test_fn_168_runtime_separation_guard_continuation_line_successor_second_guard_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        continuation_line = "  `severity` or `confidence`."
        second_guard_bullet = (
            "- Both `score` and `calibrated_probability` are derived from structural clause match"
        )

        self.assertEqual(
            lines.count(continuation_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first separation-guard continuation line",
        )
        self.assertEqual(
            lines.count(second_guard_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second separation-guard bullet leading line",
        )

        continuation_line_index = lines.index(continuation_line)
        self.assertLess(
            continuation_line_index + 1,
            len(lines),
            "docs/runtime-determinism.md: first separation-guard continuation line must be immediately followed by second guard bullet",
        )
        self.assertEqual(
            lines[continuation_line_index + 1].strip(),
            second_guard_bullet,
            "docs/runtime-determinism.md: `  `severity` or `confidence`.` must be immediately followed by `- Both `score` and `calibrated_probability` are derived from structural clause match`",
        )

    def test_fn_169_gate_source_of_truth_boundary_contract_bullet_successor_hook_execution_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        source_of_truth_boundary_contract_bullet = "- Source-of-truth bullet boundary contract (RL-049/RL-050): keep exactly one standalone `Source-of-truth rule: ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_049_quality_gates_source_of_truth_rule_bullet_singularity_canary`, `test_rl_050_quality_gates_source_of_truth_rule_bullet_line_boundary_canary`)."
        hook_execution_bullet = "- Hook execution is explicit/manual, no gate script invokes release snapshot export automatically."

        self.assertEqual(
            lines.count(source_of_truth_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(hook_execution_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical hook-execution bullet",
        )

        source_of_truth_boundary_contract_bullet_index = lines.index(
            source_of_truth_boundary_contract_bullet
        )
        self.assertLess(
            source_of_truth_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: source-of-truth boundary-contract bullet must be immediately followed by hook-execution bullet",
        )
        self.assertEqual(
            lines[source_of_truth_boundary_contract_bullet_index + 1].strip(),
            hook_execution_bullet,
            "docs/quality-gates.md: `- Source-of-truth bullet boundary contract (RL-049/RL-050): ...` must be immediately followed by `- Hook execution is explicit/manual, no gate script invokes release snapshot export automatically.`",
        )

    def test_fn_170_gate_hook_execution_bullet_successor_quickstart_pointers_mirrored_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        hook_execution_bullet = "- Hook execution is explicit/manual, no gate script invokes release snapshot export automatically."
        quickstart_pointers_mirrored_bullet = "- Quickstart pointers are mirrored in top-level onboarding docs (`README.md`, `bench/token-harness/README.md`) for discoverability."

        self.assertEqual(
            lines.count(hook_execution_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical hook-execution bullet",
        )
        self.assertEqual(
            lines.count(quickstart_pointers_mirrored_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical quickstart-pointers-mirrored bullet",
        )

        hook_execution_bullet_index = lines.index(hook_execution_bullet)
        self.assertLess(
            hook_execution_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: hook-execution bullet must be immediately followed by quickstart-pointers-mirrored bullet",
        )
        self.assertEqual(
            lines[hook_execution_bullet_index + 1].strip(),
            quickstart_pointers_mirrored_bullet,
            "docs/quality-gates.md: `- Hook execution is explicit/manual, no gate script invokes release snapshot export automatically.` must be immediately followed by `- Quickstart pointers are mirrored in top-level onboarding docs (`README.md`, `bench/token-harness/README.md`) for discoverability.`",
        )

    def test_fn_171_runtime_second_guard_bullet_continuation_line_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        second_guard_bullet = (
            "- Both `score` and `calibrated_probability` are derived from structural clause match"
        )
        continuation_line = "  coverage only in v0."

        self.assertEqual(
            lines.count(second_guard_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second separation-guard bullet leading line",
        )
        self.assertEqual(
            lines.count(continuation_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second separation-guard continuation line",
        )

        second_guard_bullet_index = lines.index(second_guard_bullet)
        self.assertLess(
            second_guard_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: second separation-guard bullet must be immediately followed by its continuation line",
        )
        self.assertEqual(
            lines[second_guard_bullet_index + 1],
            continuation_line,
            "docs/runtime-determinism.md: second separation-guard bullet must be immediately followed by the canonical continuation line",
        )

    def test_fn_172_gate_quickstart_pointers_mirrored_bullet_successor_quickstart_pointer_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        quickstart_pointers_mirrored_bullet = "- Quickstart pointers are mirrored in top-level onboarding docs (`README.md`, `bench/token-harness/README.md`) for discoverability."
        quickstart_pointer_boundary_contract_bullet = "- Quickstart-pointer bullet boundary contract (RL-052/RL-053): keep exactly one standalone `Quickstart pointers are mirrored in top-level onboarding docs ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_052_quality_gates_quickstart_pointer_bullet_singularity_canary`, `test_rl_053_quality_gates_quickstart_pointer_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(quickstart_pointers_mirrored_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical quickstart-pointers-mirrored bullet",
        )
        self.assertEqual(
            lines.count(quickstart_pointer_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical quickstart-pointer boundary-contract bullet",
        )

        quickstart_pointers_mirrored_bullet_index = lines.index(
            quickstart_pointers_mirrored_bullet
        )
        self.assertLess(
            quickstart_pointers_mirrored_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: quickstart-pointers-mirrored bullet must be immediately followed by quickstart-pointer boundary-contract bullet",
        )
        self.assertEqual(
            lines[quickstart_pointers_mirrored_bullet_index + 1].strip(),
            quickstart_pointer_boundary_contract_bullet,
            "docs/quality-gates.md: `- Quickstart pointers are mirrored in top-level onboarding docs (`README.md`, `bench/token-harness/README.md`) for discoverability.` must be immediately followed by `- Quickstart-pointer bullet boundary contract (RL-052/RL-053): ...`",
        )

    def test_fn_173_runtime_second_guard_continuation_line_successor_current_limits_heading_spacing_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        continuation_line = "  coverage only in v0."
        current_limits_heading = "## Current limits"

        self.assertEqual(
            lines.count(continuation_line),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second separation-guard continuation line",
        )
        self.assertEqual(
            lines.count(current_limits_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical `## Current limits` heading",
        )

        continuation_line_index = lines.index(continuation_line)
        self.assertLess(
            continuation_line_index + 2,
            len(lines),
            "docs/runtime-determinism.md: second separation-guard continuation line must be followed by one blank line and `## Current limits`",
        )
        self.assertEqual(
            lines[continuation_line_index + 1],
            "",
            "docs/runtime-determinism.md: expected exactly one blank separator line between `coverage only in v0.` and `## Current limits`",
        )
        self.assertEqual(
            lines[continuation_line_index + 2].strip(),
            current_limits_heading,
            "docs/runtime-determinism.md: `  coverage only in v0.` must be followed by exactly one blank line and then `## Current limits`",
        )

    def test_fn_174_gate_quickstart_pointer_boundary_contract_bullet_successor_release_artifact_json_shape_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        quickstart_pointer_boundary_contract_bullet = "- Quickstart-pointer bullet boundary contract (RL-052/RL-053): keep exactly one standalone `Quickstart pointers are mirrored in top-level onboarding docs ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_052_quality_gates_quickstart_pointer_bullet_singularity_canary`, `test_rl_053_quality_gates_quickstart_pointer_bullet_line_boundary_canary`)."
        release_artifact_json_shape_bullet = "- Release artifact JSON shape contract is locked by `tests/test_release_snapshot.py` (`test_latest_json_shape_contract_for_release_evidence`)."

        self.assertEqual(
            lines.count(quickstart_pointer_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical quickstart-pointer boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(release_artifact_json_shape_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-artifact-json-shape bullet",
        )

        quickstart_pointer_boundary_contract_bullet_index = lines.index(
            quickstart_pointer_boundary_contract_bullet
        )
        self.assertLess(
            quickstart_pointer_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: quickstart-pointer boundary-contract bullet must be immediately followed by release-artifact-json-shape bullet",
        )
        self.assertEqual(
            lines[quickstart_pointer_boundary_contract_bullet_index + 1].strip(),
            release_artifact_json_shape_bullet,
            "docs/quality-gates.md: `- Quickstart-pointer bullet boundary contract (RL-052/RL-053): ...` must be immediately followed by `- Release artifact JSON shape contract is locked by ...`",
        )

    def test_fn_175_gate_release_artifact_json_shape_bullet_successor_release_artifact_json_shape_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        release_artifact_json_shape_bullet = "- Release artifact JSON shape contract is locked by `tests/test_release_snapshot.py` (`test_latest_json_shape_contract_for_release_evidence`)."
        release_artifact_json_shape_boundary_contract_bullet = "- Release-artifact-json-shape bullet boundary contract (RL-055/RL-056): keep exactly one standalone `Release artifact JSON shape contract is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_055_quality_gates_release_artifact_json_shape_bullet_singularity_canary`, `test_rl_056_quality_gates_release_artifact_json_shape_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(release_artifact_json_shape_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-artifact-json-shape bullet",
        )
        self.assertEqual(
            lines.count(release_artifact_json_shape_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-artifact-json-shape boundary-contract bullet",
        )

        release_artifact_json_shape_bullet_index = lines.index(
            release_artifact_json_shape_bullet
        )
        self.assertLess(
            release_artifact_json_shape_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: release-artifact-json-shape bullet must be immediately followed by release-artifact-json-shape boundary-contract bullet",
        )
        self.assertEqual(
            lines[release_artifact_json_shape_bullet_index + 1].strip(),
            release_artifact_json_shape_boundary_contract_bullet,
            "docs/quality-gates.md: `- Release artifact JSON shape contract is locked by ...` must be immediately followed by `- Release-artifact-json-shape bullet boundary contract (RL-055/RL-056): ...`",
        )

    def test_fn_176_runtime_current_limits_heading_successor_first_limit_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        current_limits_heading = "## Current limits"
        first_limit_bullet = "- Clause matching is intentionally narrow and deterministic."

        self.assertEqual(
            lines.count(current_limits_heading),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical `## Current limits` heading",
        )
        self.assertEqual(
            lines.count(first_limit_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first current-limits bullet",
        )

        current_limits_heading_index = lines.index(current_limits_heading)
        self.assertLess(
            current_limits_heading_index + 2,
            len(lines),
            "docs/runtime-determinism.md: `## Current limits` must be followed by one blank line and the first current-limits bullet",
        )
        self.assertEqual(
            lines[current_limits_heading_index + 1],
            "",
            "docs/runtime-determinism.md: expected exactly one blank separator line between `## Current limits` and `- Clause matching is intentionally narrow and deterministic.`",
        )
        self.assertEqual(
            lines[current_limits_heading_index + 2].strip(),
            first_limit_bullet,
            "docs/runtime-determinism.md: `## Current limits` must be followed by exactly one blank line and then `- Clause matching is intentionally narrow and deterministic.`",
        )

    def test_fn_177_gate_release_artifact_json_shape_boundary_contract_bullet_successor_checked_in_freshness_parity_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        release_artifact_json_shape_boundary_contract_bullet = "- Release-artifact-json-shape bullet boundary contract (RL-055/RL-056): keep exactly one standalone `Release artifact JSON shape contract is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_055_quality_gates_release_artifact_json_shape_bullet_singularity_canary`, `test_rl_056_quality_gates_release_artifact_json_shape_bullet_line_boundary_canary`)."
        checked_in_freshness_parity_bullet = "- Checked-in freshness/parity canary is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_latest_json_contract_parity`)."

        self.assertEqual(
            lines.count(release_artifact_json_shape_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-artifact-json-shape boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(checked_in_freshness_parity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical checked-in-freshness/parity bullet",
        )

        release_artifact_json_shape_boundary_contract_bullet_index = lines.index(
            release_artifact_json_shape_boundary_contract_bullet
        )
        self.assertLess(
            release_artifact_json_shape_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: release-artifact-json-shape boundary-contract bullet must be immediately followed by checked-in-freshness/parity bullet",
        )
        self.assertEqual(
            lines[
                release_artifact_json_shape_boundary_contract_bullet_index + 1
            ].strip(),
            checked_in_freshness_parity_bullet,
            "docs/quality-gates.md: `- Release-artifact-json-shape bullet boundary contract (RL-055/RL-056): ...` must be immediately followed by `- Checked-in freshness/parity canary is locked...`",
        )

    def test_fn_178_gate_checked_in_freshness_parity_bullet_successor_checked_in_freshness_parity_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        checked_in_freshness_parity_bullet = "- Checked-in freshness/parity canary is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_latest_json_contract_parity`)."
        checked_in_freshness_parity_boundary_contract_bullet = "- Checked-in-freshness/parity bullet boundary contract (RL-058/RL-059): keep exactly one standalone `Checked-in freshness/parity canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_058_quality_gates_checked_in_freshness_parity_bullet_singularity_canary`, `test_rl_059_quality_gates_checked_in_freshness_parity_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(checked_in_freshness_parity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical checked-in-freshness/parity bullet",
        )
        self.assertEqual(
            lines.count(checked_in_freshness_parity_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical checked-in-freshness/parity boundary-contract bullet",
        )

        checked_in_freshness_parity_bullet_index = lines.index(
            checked_in_freshness_parity_bullet
        )
        self.assertLess(
            checked_in_freshness_parity_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: checked-in-freshness/parity bullet must be immediately followed by checked-in-freshness/parity boundary-contract bullet",
        )
        self.assertEqual(
            lines[checked_in_freshness_parity_bullet_index + 1].strip(),
            checked_in_freshness_parity_boundary_contract_bullet,
            "docs/quality-gates.md: `- Checked-in freshness/parity canary is locked...` must be immediately followed by `- Checked-in-freshness/parity bullet boundary contract (RL-058/RL-059): ...`",
        )

    def test_fn_179_runtime_first_current_limits_bullet_successor_second_current_limits_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        first_current_limits_bullet = "- Clause matching is intentionally narrow and deterministic."
        second_current_limits_bullet = "- `payload_has` checks top-level payload keys only."

        self.assertEqual(
            lines.count(first_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical first current-limits bullet",
        )
        self.assertEqual(
            lines.count(second_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second current-limits bullet",
        )

        first_current_limits_bullet_index = lines.index(first_current_limits_bullet)
        self.assertLess(
            first_current_limits_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: first current-limits bullet must be immediately followed by second current-limits bullet",
        )
        self.assertEqual(
            lines[first_current_limits_bullet_index + 1].strip(),
            second_current_limits_bullet,
            "docs/runtime-determinism.md: `- Clause matching is intentionally narrow and deterministic.` must be immediately followed by `- `payload_has` checks top-level payload keys only.`",
        )

    def test_fn_180_gate_checked_in_freshness_parity_boundary_contract_bullet_successor_checked_in_latest_md_presence_source_marker_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        checked_in_freshness_parity_boundary_contract_bullet = "- Checked-in-freshness/parity bullet boundary contract (RL-058/RL-059): keep exactly one standalone `Checked-in freshness/parity canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_058_quality_gates_checked_in_freshness_parity_bullet_singularity_canary`, `test_rl_059_quality_gates_checked_in_freshness_parity_bullet_line_boundary_canary`)."
        checked_in_latest_md_presence_source_marker_bullet = "- Checked-in release markdown presence/source-marker canary is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_latest_md_presence_and_source_markers`)."

        self.assertEqual(
            lines.count(checked_in_freshness_parity_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical checked-in-freshness/parity boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(checked_in_latest_md_presence_source_marker_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical checked-in-latest-md presence/source-marker bullet",
        )

        checked_in_freshness_parity_boundary_contract_bullet_index = lines.index(
            checked_in_freshness_parity_boundary_contract_bullet
        )
        self.assertLess(
            checked_in_freshness_parity_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: checked-in-freshness/parity boundary-contract bullet must be immediately followed by checked-in-latest-md presence/source-marker bullet",
        )
        self.assertEqual(
            lines[
                checked_in_freshness_parity_boundary_contract_bullet_index + 1
            ].strip(),
            checked_in_latest_md_presence_source_marker_bullet,
            "docs/quality-gates.md: `- Checked-in-freshness/parity bullet boundary contract (RL-058/RL-059): ...` must be immediately followed by `- Checked-in release markdown presence/source-marker canary is locked...`",
        )

    def test_fn_181_gate_checked_in_latest_md_presence_source_marker_bullet_successor_checked_in_latest_md_presence_source_marker_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        checked_in_latest_md_presence_source_marker_bullet = "- Checked-in release markdown presence/source-marker canary is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_latest_md_presence_and_source_markers`)."
        checked_in_latest_md_presence_source_marker_boundary_contract_bullet = "- Checked-in-latest-md presence/source-marker bullet boundary contract (RL-061/RL-062): keep exactly one standalone `Checked-in release markdown presence/source-marker canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_061_quality_gates_checked_in_latest_md_presence_source_marker_bullet_singularity_canary`, `test_rl_062_quality_gates_checked_in_latest_md_presence_source_marker_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(checked_in_latest_md_presence_source_marker_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical checked-in-latest-md presence/source-marker bullet",
        )
        self.assertEqual(
            lines.count(
                checked_in_latest_md_presence_source_marker_boundary_contract_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical checked-in-latest-md presence/source-marker boundary-contract bullet",
        )

        checked_in_latest_md_presence_source_marker_bullet_index = lines.index(
            checked_in_latest_md_presence_source_marker_bullet
        )
        self.assertLess(
            checked_in_latest_md_presence_source_marker_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: checked-in-latest-md presence/source-marker bullet must be immediately followed by checked-in-latest-md presence/source-marker boundary-contract bullet",
        )
        self.assertEqual(
            lines[checked_in_latest_md_presence_source_marker_bullet_index + 1].strip(),
            checked_in_latest_md_presence_source_marker_boundary_contract_bullet,
            "docs/quality-gates.md: `- Checked-in release markdown presence/source-marker canary is locked...` must be immediately followed by `- Checked-in-latest-md presence/source-marker bullet boundary contract (RL-061/RL-062): ...`",
        )

    def test_fn_182_runtime_second_current_limits_bullet_successor_third_current_limits_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        second_current_limits_bullet = "- `payload_has` checks top-level payload keys only."
        third_current_limits_bullet = "- `payload_path_*` traverses dot-separated payload keys and numeric list indexes only, `payload_path_in` accepts finite scalar member sets only (CSV or JSON array), `payload_path_*_in_ci` is limited to string scalar/list membership only with string clause members, `payload_path_is_*` matches exact runtime JSON-like types only (`null|bool|number|string|list|object`, with bool excluded from number), `payload_path_equals_ci/not_equals_ci` plus `payload_path_equals_path_ci/not_equals_path_ci` are case-insensitive exact string-only checks, `payload_path_startswith/contains` are case-sensitive string-only checks, `payload_path_len_*` compares only string/list lengths plus mapping key counts against non-negative integer clause literals, `payload_path_*_path` compares two resolved payload paths only, with the `*_in_path` list-to-list families requiring non-empty list operands and restricting `_ci` variants to string lists, and `payload_path_gt/gte/lt/lte` plus `payload_path_*te_path` numeric families compare only finite numeric payload values."

        self.assertEqual(
            lines.count(second_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical second current-limits bullet",
        )
        self.assertEqual(
            lines.count(third_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical third current-limits bullet",
        )

        second_current_limits_bullet_index = lines.index(second_current_limits_bullet)
        self.assertLess(
            second_current_limits_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: second current-limits bullet must be immediately followed by third current-limits bullet",
        )
        self.assertEqual(
            lines[second_current_limits_bullet_index + 1].strip(),
            third_current_limits_bullet,
            "docs/runtime-determinism.md: `- `payload_has` checks top-level payload keys only.` must be immediately followed by `- `payload_path_*` traverses dot-separated payload keys and numeric list indexes only.`",
        )

    def test_fn_183_gate_checked_in_latest_md_presence_source_marker_boundary_contract_bullet_successor_quickstart_command_parity_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        checked_in_latest_md_presence_source_marker_boundary_contract_bullet = "- Checked-in-latest-md presence/source-marker bullet boundary contract (RL-061/RL-062): keep exactly one standalone `Checked-in release markdown presence/source-marker canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_061_quality_gates_checked_in_latest_md_presence_source_marker_bullet_singularity_canary`, `test_rl_062_quality_gates_checked_in_latest_md_presence_source_marker_bullet_line_boundary_canary`)."
        quickstart_command_parity_bullet = "- Quickstart command parity canary for onboarding docs is locked by `tests/test_release_snapshot.py` (`test_release_evidence_quickstart_command_parity_docs`)."

        self.assertEqual(
            lines.count(checked_in_latest_md_presence_source_marker_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical checked-in-latest-md presence/source-marker boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(quickstart_command_parity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical quickstart-command-parity bullet",
        )

        checked_in_latest_md_presence_source_marker_boundary_contract_bullet_index = (
            lines.index(
                checked_in_latest_md_presence_source_marker_boundary_contract_bullet
            )
        )
        self.assertLess(
            checked_in_latest_md_presence_source_marker_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: checked-in-latest-md presence/source-marker boundary-contract bullet must be immediately followed by quickstart-command-parity bullet",
        )
        self.assertEqual(
            lines[
                checked_in_latest_md_presence_source_marker_boundary_contract_bullet_index
                + 1
            ].strip(),
            quickstart_command_parity_bullet,
            "docs/quality-gates.md: `- Checked-in-latest-md presence/source-marker bullet boundary contract (RL-061/RL-062): ...` must be immediately followed by `- Quickstart command parity canary for onboarding docs is locked by ...`",
        )

    def test_fn_184_runtime_third_current_limits_bullet_successor_fourth_current_limits_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        third_current_limits_bullet = "- `payload_path_*` traverses dot-separated payload keys and numeric list indexes only, `payload_path_in` accepts finite scalar member sets only (CSV or JSON array), `payload_path_*_in_ci` is limited to string scalar/list membership only with string clause members, `payload_path_is_*` matches exact runtime JSON-like types only (`null|bool|number|string|list|object`, with bool excluded from number), `payload_path_equals_ci/not_equals_ci` plus `payload_path_equals_path_ci/not_equals_path_ci` are case-insensitive exact string-only checks, `payload_path_startswith/contains` are case-sensitive string-only checks, `payload_path_len_*` compares only string/list lengths plus mapping key counts against non-negative integer clause literals, `payload_path_*_path` compares two resolved payload paths only, with the `*_in_path` list-to-list families requiring non-empty list operands and restricting `_ci` variants to string lists, and `payload_path_gt/gte/lt/lte` plus `payload_path_*te_path` numeric families compare only finite numeric payload values."
        fourth_current_limits_bullet = "- No probabilistic or weighted rule scoring."

        self.assertEqual(
            lines.count(third_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical third current-limits bullet",
        )
        self.assertEqual(
            lines.count(fourth_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fourth current-limits bullet",
        )

        third_current_limits_bullet_index = lines.index(third_current_limits_bullet)
        self.assertLess(
            third_current_limits_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: third current-limits bullet must be immediately followed by fourth current-limits bullet",
        )
        self.assertEqual(
            lines[third_current_limits_bullet_index + 1].strip(),
            fourth_current_limits_bullet,
            "docs/runtime-determinism.md: `- `payload_path_*` traverses dot-separated payload keys and numeric list indexes only.` must be immediately followed by `- No probabilistic or weighted rule scoring.`",
        )

    def test_fn_185_gate_quickstart_command_parity_bullet_successor_quickstart_command_parity_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        quickstart_command_parity_bullet = "- Quickstart command parity canary for onboarding docs is locked by `tests/test_release_snapshot.py` (`test_release_evidence_quickstart_command_parity_docs`)."
        quickstart_command_parity_boundary_contract_bullet = "- Quickstart-command-parity bullet boundary contract (RL-064/RL-065): keep exactly one standalone `Quickstart command parity canary for onboarding docs is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_064_quality_gates_quickstart_command_parity_bullet_singularity_canary`, `test_rl_065_quality_gates_quickstart_command_parity_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(quickstart_command_parity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical quickstart-command-parity bullet",
        )
        self.assertEqual(
            lines.count(quickstart_command_parity_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical quickstart-command-parity boundary-contract bullet",
        )

        quickstart_command_parity_bullet_index = lines.index(
            quickstart_command_parity_bullet
        )
        self.assertLess(
            quickstart_command_parity_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: quickstart-command-parity bullet must be immediately followed by quickstart-command-parity boundary-contract bullet",
        )
        self.assertEqual(
            lines[quickstart_command_parity_bullet_index + 1].strip(),
            quickstart_command_parity_boundary_contract_bullet,
            "docs/quality-gates.md: `- Quickstart command parity canary for onboarding docs is locked by ...` must be immediately followed by `- Quickstart-command-parity bullet boundary contract (RL-064/RL-065): ...`",
        )

    def test_fn_186_gate_quickstart_command_parity_boundary_contract_bullet_successor_release_evidence_heading_singularity_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        quickstart_command_parity_boundary_contract_bullet = "- Quickstart-command-parity bullet boundary contract (RL-064/RL-065): keep exactly one standalone `Quickstart command parity canary for onboarding docs is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_064_quality_gates_quickstart_command_parity_bullet_singularity_canary`, `test_rl_065_quality_gates_quickstart_command_parity_bullet_line_boundary_canary`)."
        release_evidence_heading_singularity_bullet = "- Release-evidence heading singularity canary is locked by `tests/test_release_snapshot.py` (`test_quality_gates_release_evidence_heading_singularity`)."

        self.assertEqual(
            lines.count(quickstart_command_parity_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical quickstart-command-parity boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(release_evidence_heading_singularity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-evidence-heading-singularity bullet",
        )

        quickstart_command_parity_boundary_contract_bullet_index = lines.index(
            quickstart_command_parity_boundary_contract_bullet
        )
        self.assertLess(
            quickstart_command_parity_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: quickstart-command-parity boundary-contract bullet must be immediately followed by release-evidence-heading-singularity bullet",
        )
        self.assertEqual(
            lines[quickstart_command_parity_boundary_contract_bullet_index + 1].strip(),
            release_evidence_heading_singularity_bullet,
            "docs/quality-gates.md: `- Quickstart-command-parity bullet boundary contract (RL-064/RL-065): ...` must be immediately followed by `- Release-evidence heading singularity canary is locked by ...`",
        )

    def test_fn_187_runtime_fourth_current_limits_bullet_successor_fifth_current_limits_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        fourth_current_limits_bullet = "- No probabilistic or weighted rule scoring."
        fifth_current_limits_bullet = "- No runtime action dispatch/execution in v0."

        self.assertEqual(
            lines.count(fourth_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fourth current-limits bullet",
        )
        self.assertEqual(
            lines.count(fifth_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fifth current-limits bullet",
        )

        fourth_current_limits_bullet_index = lines.index(fourth_current_limits_bullet)
        self.assertLess(
            fourth_current_limits_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: fourth current-limits bullet must be immediately followed by fifth current-limits bullet",
        )
        self.assertEqual(
            lines[fourth_current_limits_bullet_index + 1].strip(),
            fifth_current_limits_bullet,
            "docs/runtime-determinism.md: `- No probabilistic or weighted rule scoring.` must be immediately followed by `- No runtime action dispatch/execution in v0.`",
        )

    def test_fn_188_gate_release_evidence_heading_singularity_bullet_successor_release_evidence_heading_singularity_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        release_evidence_heading_singularity_bullet = "- Release-evidence heading singularity canary is locked by `tests/test_release_snapshot.py` (`test_quality_gates_release_evidence_heading_singularity`)."
        release_evidence_heading_singularity_boundary_contract_bullet = "- Release-evidence-heading-singularity bullet boundary contract (RL-067/RL-068): keep exactly one standalone `Release-evidence heading singularity canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_067_quality_gates_release_evidence_heading_singularity_bullet_singularity_canary`, `test_rl_068_quality_gates_release_evidence_heading_singularity_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(release_evidence_heading_singularity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-evidence-heading-singularity bullet",
        )
        self.assertEqual(
            lines.count(release_evidence_heading_singularity_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-evidence-heading-singularity boundary-contract bullet",
        )

        release_evidence_heading_singularity_bullet_index = lines.index(
            release_evidence_heading_singularity_bullet
        )
        self.assertLess(
            release_evidence_heading_singularity_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: release-evidence-heading-singularity bullet must be immediately followed by release-evidence-heading-singularity boundary-contract bullet",
        )
        self.assertEqual(
            lines[release_evidence_heading_singularity_bullet_index + 1].strip(),
            release_evidence_heading_singularity_boundary_contract_bullet,
            "docs/quality-gates.md: `- Release-evidence heading singularity canary is locked by ...` must be immediately followed by `- Release-evidence-heading-singularity bullet boundary contract (RL-067/RL-068): ...`",
        )

    def test_fn_189_gate_release_evidence_heading_singularity_boundary_contract_bullet_successor_heading_boundary_canaries_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        release_evidence_heading_singularity_boundary_contract_bullet = "- Release-evidence-heading-singularity bullet boundary contract (RL-067/RL-068): keep exactly one standalone `Release-evidence heading singularity canary is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_067_quality_gates_release_evidence_heading_singularity_bullet_singularity_canary`, `test_rl_068_quality_gates_release_evidence_heading_singularity_bullet_line_boundary_canary`)."
        heading_boundary_canaries_bullet = "- Heading-boundary canaries are locked by `tests/test_release_snapshot.py`, release-evidence heading must stay standalone (`test_quality_gates_release_evidence_heading_line_boundary`), and the artifact index title must remain the first non-empty line (`test_release_artifact_index_title_first_non_empty_line_boundary`)."

        self.assertEqual(
            lines.count(release_evidence_heading_singularity_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-evidence-heading-singularity boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(heading_boundary_canaries_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical heading-boundary-canaries bullet",
        )

        release_evidence_heading_singularity_boundary_contract_bullet_index = lines.index(
            release_evidence_heading_singularity_boundary_contract_bullet
        )
        self.assertLess(
            release_evidence_heading_singularity_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: release-evidence-heading-singularity boundary-contract bullet must be immediately followed by heading-boundary-canaries bullet",
        )
        self.assertEqual(
            lines[
                release_evidence_heading_singularity_boundary_contract_bullet_index + 1
            ].strip(),
            heading_boundary_canaries_bullet,
            "docs/quality-gates.md: `- Release-evidence-heading-singularity bullet boundary contract (RL-067/RL-068): ...` must be immediately followed by `- Heading-boundary canaries are locked by ...`",
        )

    def test_fn_190_runtime_fifth_current_limits_bullet_successor_sixth_current_limits_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        fifth_current_limits_bullet = "- No runtime action dispatch/execution in v0."
        sixth_current_limits_bullet = "- Trace shape and fired-rule alignment are validated in-process (no external validator dependency required)."

        self.assertEqual(
            lines.count(fifth_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical fifth current-limits bullet",
        )
        self.assertEqual(
            lines.count(sixth_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical sixth current-limits bullet",
        )

        fifth_current_limits_bullet_index = lines.index(fifth_current_limits_bullet)
        self.assertLess(
            fifth_current_limits_bullet_index + 1,
            len(lines),
            "docs/runtime-determinism.md: fifth current-limits bullet must be immediately followed by sixth current-limits bullet",
        )
        self.assertEqual(
            lines[fifth_current_limits_bullet_index + 1].strip(),
            sixth_current_limits_bullet,
            "docs/runtime-determinism.md: `- No runtime action dispatch/execution in v0.` must be immediately followed by `- Trace shape and fired-rule alignment are validated in-process (no external validator dependency required).`",
        )

    def test_fn_191_gate_heading_boundary_canaries_bullet_successor_heading_boundary_canaries_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading_boundary_canaries_bullet = "- Heading-boundary canaries are locked by `tests/test_release_snapshot.py`, release-evidence heading must stay standalone (`test_quality_gates_release_evidence_heading_line_boundary`), and the artifact index title must remain the first non-empty line (`test_release_artifact_index_title_first_non_empty_line_boundary`)."
        heading_boundary_canaries_boundary_contract_bullet = "- Heading-boundary-canaries bullet boundary contract (RL-070/RL-071): keep exactly one standalone `Heading-boundary canaries are locked by ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_070_quality_gates_heading_boundary_canaries_bullet_singularity_canary`, `test_rl_071_quality_gates_heading_boundary_canaries_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(heading_boundary_canaries_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical heading-boundary-canaries bullet",
        )
        self.assertEqual(
            lines.count(heading_boundary_canaries_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical heading-boundary-canaries boundary-contract bullet",
        )

        heading_boundary_canaries_bullet_index = lines.index(heading_boundary_canaries_bullet)
        self.assertLess(
            heading_boundary_canaries_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: heading-boundary-canaries bullet must be immediately followed by heading-boundary-canaries boundary-contract bullet",
        )
        self.assertEqual(
            lines[heading_boundary_canaries_bullet_index + 1].strip(),
            heading_boundary_canaries_boundary_contract_bullet,
            "docs/quality-gates.md: `- Heading-boundary canaries are locked by ...` must be immediately followed by `- Heading-boundary-canaries bullet boundary contract (RL-070/RL-071): ...`",
        )

    def test_fn_192_gate_heading_boundary_canaries_boundary_contract_bullet_successor_artifact_index_line_boundary_canaries_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        heading_boundary_canaries_boundary_contract_bullet = "- Heading-boundary-canaries bullet boundary contract (RL-070/RL-071): keep exactly one standalone `Heading-boundary canaries are locked by ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_070_quality_gates_heading_boundary_canaries_bullet_singularity_canary`, `test_rl_071_quality_gates_heading_boundary_canaries_bullet_line_boundary_canary`)."
        artifact_index_line_boundary_canaries_bullet = "- Artifact-index line-boundary canaries are locked by `tests/test_release_snapshot.py`, quickstart heading must stay standalone (`test_release_artifact_index_quickstart_heading_line_boundary`), and the retention checklist marker must stay standalone (`test_release_artifact_index_retention_preconditions_anchor_marker_line_boundary`)."

        self.assertEqual(
            lines.count(heading_boundary_canaries_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical heading-boundary-canaries boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(artifact_index_line_boundary_canaries_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index line-boundary-canaries bullet",
        )

        heading_boundary_canaries_boundary_contract_bullet_index = lines.index(
            heading_boundary_canaries_boundary_contract_bullet
        )
        self.assertLess(
            heading_boundary_canaries_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: heading-boundary-canaries boundary-contract bullet must be immediately followed by artifact-index line-boundary-canaries bullet",
        )
        self.assertEqual(
            lines[heading_boundary_canaries_boundary_contract_bullet_index + 1].strip(),
            artifact_index_line_boundary_canaries_bullet,
            "docs/quality-gates.md: `- Heading-boundary-canaries bullet boundary contract (RL-070/RL-071): ...` must be immediately followed by `- Artifact-index line-boundary canaries are locked by ...`",
        )

    def test_fn_193_runtime_sixth_current_limits_bullet_terminal_line_boundary_canary(
        self,
    ) -> None:
        lines = self.runtime_determinism_doc.splitlines()
        sixth_current_limits_bullet = "- Trace shape and fired-rule alignment are validated in-process (no external validator dependency required)."

        self.assertEqual(
            lines.count(sixth_current_limits_bullet),
            1,
            "docs/runtime-determinism.md: expected exactly one canonical sixth current-limits bullet",
        )

        non_empty_lines = [line.strip() for line in lines if line.strip()]
        self.assertTrue(
            non_empty_lines,
            "docs/runtime-determinism.md: expected at least one non-empty line",
        )
        self.assertEqual(
            non_empty_lines[-1],
            sixth_current_limits_bullet,
            "docs/runtime-determinism.md: `- Trace shape and fired-rule alignment are validated in-process (no external validator dependency required).` must remain the final non-empty line",
        )

    def test_fn_194_gate_artifact_index_line_boundary_canaries_bullet_successor_artifact_index_line_boundary_canaries_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        artifact_index_line_boundary_canaries_bullet = "- Artifact-index line-boundary canaries are locked by `tests/test_release_snapshot.py`, quickstart heading must stay standalone (`test_release_artifact_index_quickstart_heading_line_boundary`), and the retention checklist marker must stay standalone (`test_release_artifact_index_retention_preconditions_anchor_marker_line_boundary`)."
        artifact_index_line_boundary_canaries_boundary_contract_bullet = "- Artifact-index-line-boundary-canaries bullet boundary contract (RL-073/RL-074): keep exactly one standalone `Artifact-index line-boundary canaries are locked by ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_073_quality_gates_artifact_index_line_boundary_canaries_bullet_singularity_canary`, `test_rl_074_quality_gates_artifact_index_line_boundary_canaries_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(artifact_index_line_boundary_canaries_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index line-boundary-canaries bullet",
        )
        self.assertEqual(
            lines.count(artifact_index_line_boundary_canaries_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index-line-boundary-canaries boundary-contract bullet",
        )

        artifact_index_line_boundary_canaries_bullet_index = lines.index(
            artifact_index_line_boundary_canaries_bullet
        )
        self.assertLess(
            artifact_index_line_boundary_canaries_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: artifact-index line-boundary-canaries bullet must be immediately followed by artifact-index-line-boundary-canaries boundary-contract bullet",
        )
        self.assertEqual(
            lines[artifact_index_line_boundary_canaries_bullet_index + 1].strip(),
            artifact_index_line_boundary_canaries_boundary_contract_bullet,
            "docs/quality-gates.md: `- Artifact-index line-boundary canaries are locked by ...` must be immediately followed by `- Artifact-index-line-boundary-canaries bullet boundary contract (RL-073/RL-074): ...`",
        )

    def test_fn_195_gate_artifact_index_line_boundary_canaries_boundary_contract_bullet_successor_artifact_index_order_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        artifact_index_line_boundary_canaries_boundary_contract_bullet = "- Artifact-index-line-boundary-canaries bullet boundary contract (RL-073/RL-074): keep exactly one standalone `Artifact-index line-boundary canaries are locked by ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_073_quality_gates_artifact_index_line_boundary_canaries_bullet_singularity_canary`, `test_rl_074_quality_gates_artifact_index_line_boundary_canaries_bullet_line_boundary_canary`)."
        artifact_index_order_boundary_contract_bullet = "- Artifact-index order-boundary contract (RL-034/RL-035): keep `## Quickstart pointer` after `# Release Artifacts Index`, and keep `Preconditions checklist (execute in order before running commands):` after `## Quickstart pointer` to preserve stable release-evidence indexing."

        self.assertEqual(
            lines.count(artifact_index_line_boundary_canaries_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index-line-boundary-canaries boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(artifact_index_order_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index order-boundary-contract bullet",
        )

        artifact_index_line_boundary_canaries_boundary_contract_bullet_index = lines.index(
            artifact_index_line_boundary_canaries_boundary_contract_bullet
        )
        self.assertLess(
            artifact_index_line_boundary_canaries_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: artifact-index-line-boundary-canaries boundary-contract bullet must be immediately followed by artifact-index order-boundary-contract bullet",
        )
        self.assertEqual(
            lines[
                artifact_index_line_boundary_canaries_boundary_contract_bullet_index + 1
            ].strip(),
            artifact_index_order_boundary_contract_bullet,
            "docs/quality-gates.md: `- Artifact-index-line-boundary-canaries bullet boundary contract (RL-073/RL-074): ...` must be immediately followed by `- Artifact-index order-boundary contract (RL-034/RL-035): ...`",
        )

    def test_fn_196_gate_artifact_index_order_boundary_contract_bullet_successor_artifact_index_order_boundary_contract_bullet_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        artifact_index_order_boundary_contract_bullet = "- Artifact-index order-boundary contract (RL-034/RL-035): keep `## Quickstart pointer` after `# Release Artifacts Index`, and keep `Preconditions checklist (execute in order before running commands):` after `## Quickstart pointer` to preserve stable release-evidence indexing."
        artifact_index_order_boundary_contract_bullet_boundary_contract_bullet = "- Artifact-index-order-boundary-contract bullet boundary contract (RL-076/RL-077): keep exactly one standalone `Artifact-index order-boundary contract (RL-034/RL-035): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_076_quality_gates_artifact_index_order_boundary_contract_bullet_singularity_canary`, `test_rl_077_quality_gates_artifact_index_order_boundary_contract_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(artifact_index_order_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index order-boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(
                artifact_index_order_boundary_contract_bullet_boundary_contract_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index-order-boundary-contract bullet boundary-contract bullet",
        )

        artifact_index_order_boundary_contract_bullet_index = lines.index(
            artifact_index_order_boundary_contract_bullet
        )
        self.assertLess(
            artifact_index_order_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: artifact-index order-boundary-contract bullet must be immediately followed by artifact-index-order-boundary-contract bullet boundary-contract bullet",
        )
        self.assertEqual(
            lines[artifact_index_order_boundary_contract_bullet_index + 1].strip(),
            artifact_index_order_boundary_contract_bullet_boundary_contract_bullet,
            "docs/quality-gates.md: `- Artifact-index order-boundary contract (RL-034/RL-035): ...` must be immediately followed by `- Artifact-index-order-boundary-contract bullet boundary contract (RL-076/RL-077): ...`",
        )

    def test_fn_197_gate_artifact_index_order_boundary_contract_bullet_boundary_contract_bullet_successor_artifact_index_line_index_order_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        artifact_index_order_boundary_contract_bullet_boundary_contract_bullet = "- Artifact-index-order-boundary-contract bullet boundary contract (RL-076/RL-077): keep exactly one standalone `Artifact-index order-boundary contract (RL-034/RL-035): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_076_quality_gates_artifact_index_order_boundary_contract_bullet_singularity_canary`, `test_rl_077_quality_gates_artifact_index_order_boundary_contract_bullet_line_boundary_canary`)."
        artifact_index_line_index_order_boundary_contract_bullet = "- Artifact-index line-index order-boundary contract (RL-037/RL-038): keep the first `## Quickstart pointer` line index after the title heading line index, and keep the first `Preconditions checklist (execute in order before running commands):` line index after the quickstart heading line index to preserve stable release-evidence indexing."

        self.assertEqual(
            lines.count(artifact_index_order_boundary_contract_bullet_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index-order-boundary-contract bullet boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(artifact_index_line_index_order_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index line-index order-boundary-contract bullet",
        )

        artifact_index_order_boundary_contract_bullet_boundary_contract_bullet_index = lines.index(
            artifact_index_order_boundary_contract_bullet_boundary_contract_bullet
        )
        self.assertLess(
            artifact_index_order_boundary_contract_bullet_boundary_contract_bullet_index
            + 1,
            len(lines),
            "docs/quality-gates.md: artifact-index-order-boundary-contract bullet boundary-contract bullet must be immediately followed by artifact-index line-index order-boundary-contract bullet",
        )
        self.assertEqual(
            lines[
                artifact_index_order_boundary_contract_bullet_boundary_contract_bullet_index
                + 1
            ].strip(),
            artifact_index_line_index_order_boundary_contract_bullet,
            "docs/quality-gates.md: `- Artifact-index-order-boundary-contract bullet boundary contract (RL-076/RL-077): ...` must be immediately followed by `- Artifact-index line-index order-boundary contract (RL-037/RL-038): ...`",
        )

    def test_fn_198_gate_artifact_index_line_index_order_boundary_contract_bullet_successor_artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        artifact_index_line_index_order_boundary_contract_bullet = "- Artifact-index line-index order-boundary contract (RL-037/RL-038): keep the first `## Quickstart pointer` line index after the title heading line index, and keep the first `Preconditions checklist (execute in order before running commands):` line index after the quickstart heading line index to preserve stable release-evidence indexing."
        artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet = "- Artifact-index-line-index-order-boundary-contract bullet boundary contract (RL-079/RL-080): keep exactly one standalone `Artifact-index line-index order-boundary contract (RL-037/RL-038): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_079_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_singularity_canary`, `test_rl_080_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(artifact_index_line_index_order_boundary_contract_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index line-index order-boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(
                artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index-line-index-order-boundary-contract bullet boundary-contract bullet",
        )

        artifact_index_line_index_order_boundary_contract_bullet_index = lines.index(
            artifact_index_line_index_order_boundary_contract_bullet
        )
        self.assertLess(
            artifact_index_line_index_order_boundary_contract_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: artifact-index line-index order-boundary-contract bullet must be immediately followed by artifact-index-line-index-order-boundary-contract bullet boundary-contract bullet",
        )
        self.assertEqual(
            lines[artifact_index_line_index_order_boundary_contract_bullet_index + 1].strip(),
            artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet,
            "docs/quality-gates.md: `- Artifact-index line-index order-boundary contract (RL-037/RL-038): ...` must be immediately followed by `- Artifact-index-line-index-order-boundary-contract bullet boundary contract (RL-079/RL-080): ...`",
        )

    def test_fn_199_gate_artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet_successor_release_artifact_index_title_heading_presence_singularity_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet = "- Artifact-index-line-index-order-boundary-contract bullet boundary contract (RL-079/RL-080): keep exactly one standalone `Artifact-index line-index order-boundary contract (RL-037/RL-038): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_079_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_singularity_canary`, `test_rl_080_quality_gates_artifact_index_line_index_order_boundary_contract_bullet_line_boundary_canary`)."
        release_artifact_index_title_heading_presence_singularity_bullet = "- Release artifact index title-heading presence/singularity canaries are locked by `tests/test_release_snapshot.py` (`test_release_artifact_index_title_heading_presence`, `test_release_artifact_index_title_heading_singularity`)."

        self.assertEqual(
            lines.count(
                artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical artifact-index-line-index-order-boundary-contract bullet boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(release_artifact_index_title_heading_presence_singularity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release artifact index title-heading presence/singularity bullet",
        )

        artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet_index = lines.index(
            artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet
        )
        self.assertLess(
            artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet_index
            + 1,
            len(lines),
            "docs/quality-gates.md: artifact-index-line-index-order-boundary-contract bullet boundary-contract bullet must be immediately followed by release artifact index title-heading presence/singularity bullet",
        )
        self.assertEqual(
            lines[
                artifact_index_line_index_order_boundary_contract_bullet_boundary_contract_bullet_index
                + 1
            ].strip(),
            release_artifact_index_title_heading_presence_singularity_bullet,
            "docs/quality-gates.md: `- Artifact-index-line-index-order-boundary-contract bullet boundary contract (RL-079/RL-080): ...` must be immediately followed by `- Release artifact index title-heading presence/singularity canaries are locked by ...`",
        )

    def test_fn_200_gate_release_artifact_index_title_heading_presence_singularity_bullet_successor_release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        release_artifact_index_title_heading_presence_singularity_bullet = "- Release artifact index title-heading presence/singularity canaries are locked by `tests/test_release_snapshot.py` (`test_release_artifact_index_title_heading_presence`, `test_release_artifact_index_title_heading_singularity`)."
        release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet = "- Release-artifact-index-title-heading-presence/singularity bullet boundary contract (RL-082/RL-083): keep exactly one standalone `Release artifact index title-heading presence/singularity canaries are locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_082_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_singularity_canary`, `test_rl_083_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(release_artifact_index_title_heading_presence_singularity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical release artifact index title-heading presence/singularity bullet",
        )
        self.assertEqual(
            lines.count(
                release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-artifact-index-title-heading-presence/singularity bullet boundary-contract bullet",
        )

        release_artifact_index_title_heading_presence_singularity_bullet_index = lines.index(
            release_artifact_index_title_heading_presence_singularity_bullet
        )
        self.assertLess(
            release_artifact_index_title_heading_presence_singularity_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: release artifact index title-heading presence/singularity bullet must be immediately followed by release-artifact-index-title-heading-presence/singularity bullet boundary-contract bullet",
        )
        self.assertEqual(
            lines[release_artifact_index_title_heading_presence_singularity_bullet_index + 1].strip(),
            release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet,
            "docs/quality-gates.md: `- Release artifact index title-heading presence/singularity canaries are locked by ...` must be immediately followed by `- Release-artifact-index-title-heading-presence/singularity bullet boundary contract (RL-082/RL-083): ...`",
        )

    def test_fn_201_gate_release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet_successor_source_of_truth_string_parity_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet = "- Release-artifact-index-title-heading-presence/singularity bullet boundary contract (RL-082/RL-083): keep exactly one standalone `Release artifact index title-heading presence/singularity canaries are locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_082_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_singularity_canary`, `test_rl_083_quality_gates_release_artifact_index_title_heading_presence_singularity_bullet_line_boundary_canary`)."
        source_of_truth_string_parity_bullet = "- Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_source_of_truth_rule_parity_between_latest_json_and_latest_md`)."

        self.assertEqual(
            lines.count(
                release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical release-artifact-index-title-heading-presence/singularity bullet boundary-contract bullet",
        )
        self.assertEqual(
            lines.count(source_of_truth_string_parity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth string parity bullet",
        )

        release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet_index = lines.index(
            release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet
        )
        self.assertLess(
            release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet_index
            + 1,
            len(lines),
            "docs/quality-gates.md: release-artifact-index-title-heading-presence/singularity bullet boundary-contract bullet must be immediately followed by source-of-truth string parity bullet",
        )
        self.assertEqual(
            lines[
                release_artifact_index_title_heading_presence_singularity_bullet_boundary_contract_bullet_index
                + 1
            ].strip(),
            source_of_truth_string_parity_bullet,
            "docs/quality-gates.md: `- Release-artifact-index-title-heading-presence/singularity bullet boundary contract (RL-082/RL-083): ...` must be immediately followed by `- Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is locked by ...`",
        )

    def test_fn_202_gate_source_of_truth_string_parity_bullet_successor_source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        source_of_truth_string_parity_bullet = "- Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is locked by `tests/test_release_snapshot.py` (`test_repo_checked_in_source_of_truth_rule_parity_between_latest_json_and_latest_md`)."
        source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet = "- Source-of-truth-string-parity bullet boundary contract (RL-085/RL-086): keep exactly one standalone `Source-of-truth string parity canary between checked-in latest.json and latest.md is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_085_quality_gates_source_of_truth_string_parity_bullet_singularity_canary`, `test_rl_086_quality_gates_source_of_truth_string_parity_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(source_of_truth_string_parity_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth string parity bullet",
        )
        self.assertEqual(
            lines.count(source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth-string-parity bullet boundary-contract (RL-085/RL-086) bullet",
        )

        source_of_truth_string_parity_bullet_index = lines.index(source_of_truth_string_parity_bullet)
        self.assertLess(
            source_of_truth_string_parity_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: source-of-truth string parity bullet must be immediately followed by source-of-truth-string-parity bullet boundary-contract (RL-085/RL-086) bullet",
        )
        self.assertEqual(
            lines[source_of_truth_string_parity_bullet_index + 1].strip(),
            source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet,
            "docs/quality-gates.md: `- Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is locked by ...` must be immediately followed by `- Source-of-truth-string-parity bullet boundary contract (RL-085/RL-086): ...`",
        )

    def test_fn_203_gate_source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet_successor_source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet = "- Source-of-truth-string-parity bullet boundary contract (RL-085/RL-086): keep exactly one standalone `Source-of-truth string parity canary between checked-in latest.json and latest.md is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_085_quality_gates_source_of_truth_string_parity_bullet_singularity_canary`, `test_rl_086_quality_gates_source_of_truth_string_parity_bullet_line_boundary_canary`)."
        source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet = "- Source-of-truth-string-parity bullet boundary contract (RL-088/RL-089): keep exactly one standalone `Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary`, `test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary`)."

        self.assertEqual(
            lines.count(source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth-string-parity bullet boundary-contract (RL-085/RL-086) bullet",
        )
        self.assertEqual(
            lines.count(source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth-string-parity bullet boundary-contract (RL-088/RL-089) bullet",
        )

        source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet_index = lines.index(
            source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet
        )
        self.assertLess(
            source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet_index
            + 1,
            len(lines),
            "docs/quality-gates.md: source-of-truth-string-parity bullet boundary-contract (RL-085/RL-086) bullet must be immediately followed by source-of-truth-string-parity bullet boundary-contract (RL-088/RL-089) bullet",
        )
        self.assertEqual(
            lines[
                source_of_truth_string_parity_bullet_boundary_contract_rl_085_rl_086_bullet_index
                + 1
            ].strip(),
            source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet,
            "docs/quality-gates.md: `- Source-of-truth-string-parity bullet boundary contract (RL-085/RL-086): ...` must be immediately followed by `- Source-of-truth-string-parity bullet boundary contract (RL-088/RL-089): ...`",
        )

    def test_fn_204_gate_source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet_successor_source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet = "- Source-of-truth-string-parity bullet boundary contract (RL-088/RL-089): keep exactly one standalone `Source-of-truth string parity canary between checked-in `latest.json` and `latest.md` is locked...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary`, `test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary`)."
        source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet = "- Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): keep the RL-088/RL-089 boundary-contract bullet with exactly one ``latest.json`` + ``latest.md`` token pair and exactly one reference each to `test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary` and `test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary`, locked by `tests/test_release_snapshot.py` (`test_rl_091_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_token_literal_canary`, `test_rl_092_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_test_reference_pair_canary`)."

        self.assertEqual(
            lines.count(source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth-string-parity bullet boundary-contract (RL-088/RL-089) bullet",
        )
        self.assertEqual(
            lines.count(
                source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092) bullet",
        )

        source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet_index = lines.index(
            source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet
        )
        self.assertLess(
            source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet_index
            + 1,
            len(lines),
            "docs/quality-gates.md: source-of-truth-string-parity bullet boundary-contract (RL-088/RL-089) bullet must be immediately followed by source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092) bullet",
        )
        self.assertEqual(
            lines[
                source_of_truth_string_parity_bullet_boundary_contract_rl_088_rl_089_bullet_index
                + 1
            ].strip(),
            source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet,
            "docs/quality-gates.md: `- Source-of-truth-string-parity bullet boundary contract (RL-088/RL-089): ...` must be immediately followed by `- Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): ...`",
        )

    def test_fn_205_gate_source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet_successor_source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet = "- Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): keep the RL-088/RL-089 boundary-contract bullet with exactly one ``latest.json`` + ``latest.md`` token pair and exactly one reference each to `test_rl_088_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_singularity_canary` and `test_rl_089_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_line_boundary_canary`, locked by `tests/test_release_snapshot.py` (`test_rl_091_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_token_literal_canary`, `test_rl_092_quality_gates_source_of_truth_string_parity_boundary_contract_bullet_test_reference_pair_canary`)."
        source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet = "- Source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095): keep exactly one standalone `Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_094_quality_gates_source_of_truth_string_parity_token_reference_note_singularity_canary`, `test_rl_095_quality_gates_source_of_truth_string_parity_token_reference_note_line_boundary_canary`)."

        self.assertEqual(
            lines.count(
                source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092) bullet",
        )
        self.assertEqual(
            lines.count(
                source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095) bullet",
        )

        source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet_index = lines.index(
            source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet
        )
        self.assertLess(
            source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet_index
            + 1,
            len(lines),
            "docs/quality-gates.md: source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092) bullet must be immediately followed by source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095) bullet",
        )
        self.assertEqual(
            lines[
                source_of_truth_string_parity_boundary_contract_token_reference_canaries_rl_091_rl_092_bullet_index
                + 1
            ].strip(),
            source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet,
            "docs/quality-gates.md: `- Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): ...` must be immediately followed by `- Source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095): ...`",
        )

    def test_fn_206_gate_source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet_terminal_separator_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet = "- Source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095): keep exactly one standalone `Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_094_quality_gates_source_of_truth_string_parity_token_reference_note_singularity_canary`, `test_rl_095_quality_gates_source_of_truth_string_parity_token_reference_note_line_boundary_canary`)."

        self.assertEqual(
            lines.count(
                source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet
            ),
            1,
            "docs/quality-gates.md: expected exactly one canonical source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095) bullet",
        )

        source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet_index = lines.index(
            source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet
        )
        self.assertLess(
            source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet_index
            + 2,
            len(lines),
            "docs/quality-gates.md: source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095) bullet must be followed by exactly one blank line and then `---`",
        )
        self.assertEqual(
            lines[
                source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet_index
                + 1
            ].strip(),
            "",
            "docs/quality-gates.md: expected exactly one blank separator line after source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095) bullet",
        )
        self.assertEqual(
            lines[
                source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet_index
                + 2
            ].strip(),
            "---",
            "docs/quality-gates.md: expected `---` immediately after the single blank separator line following source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095) bullet",
        )

    def test_fn_207_gate_sprint_section_separator_successor_sprint_3_hardening_gates_heading_spacing_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet = "- Source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095): keep exactly one standalone `Source-of-truth-string-parity boundary-contract token/reference canaries (RL-091/RL-092): ...` bullet, locked by `tests/test_release_snapshot.py` (`test_rl_094_quality_gates_source_of_truth_string_parity_token_reference_note_singularity_canary`, `test_rl_095_quality_gates_source_of_truth_string_parity_token_reference_note_line_boundary_canary`)."
        sprint_3_hardening_gates_heading = "## Sprint-3 hardening gates (still relevant)"

        source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet_index = lines.index(
            source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet
        )
        separator_line_index = (
            source_of_truth_string_parity_token_reference_note_boundary_canaries_rl_094_rl_095_bullet_index
            + 2
        )

        self.assertEqual(
            lines[separator_line_index].strip(),
            "---",
            "docs/quality-gates.md: expected sprint-section separator `---` after source-of-truth-string-parity token/reference note-boundary canaries (RL-094/RL-095) bullet",
        )
        self.assertLess(
            separator_line_index + 2,
            len(lines),
            "docs/quality-gates.md: sprint-section separator must be followed by exactly one blank line and then `## Sprint-3 hardening gates (still relevant)`",
        )
        self.assertEqual(
            lines[separator_line_index + 1].strip(),
            "",
            "docs/quality-gates.md: expected exactly one blank separator line after sprint-section `---`",
        )
        self.assertEqual(
            lines[separator_line_index + 2].strip(),
            sprint_3_hardening_gates_heading,
            "docs/quality-gates.md: sprint-section `---` must be followed by exactly one blank separator line and then `## Sprint-3 hardening gates (still relevant)`",
        )

    def test_fn_208_gate_sprint_3_hardening_gates_heading_successor_intro_line_spacing_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        sprint_3_hardening_gates_heading = "## Sprint-3 hardening gates (still relevant)"
        sprint_3_intro_line = "Sprint-3 extends baseline confidence requirements."

        sprint_3_hardening_gates_heading_index = lines.index(
            sprint_3_hardening_gates_heading
        )
        self.assertLess(
            sprint_3_hardening_gates_heading_index + 2,
            len(lines),
            "docs/quality-gates.md: `## Sprint-3 hardening gates (still relevant)` must be followed by exactly one blank line and then `Sprint-3 extends baseline confidence requirements.`",
        )
        self.assertEqual(
            lines[sprint_3_hardening_gates_heading_index + 1].strip(),
            "",
            "docs/quality-gates.md: expected exactly one blank separator line after `## Sprint-3 hardening gates (still relevant)`",
        )
        self.assertEqual(
            lines[sprint_3_hardening_gates_heading_index + 2].strip(),
            sprint_3_intro_line,
            "docs/quality-gates.md: `## Sprint-3 hardening gates (still relevant)` must be followed by exactly one blank separator line and then `Sprint-3 extends baseline confidence requirements.`",
        )

    def test_fn_209_gate_sprint_3_intro_line_successor_gate_s3_1_heading_spacing_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        sprint_3_intro_line = "Sprint-3 extends baseline confidence requirements."
        gate_s3_1_heading = "### Gate S3-1: Fixture breadth"

        sprint_3_intro_line_index = lines.index(sprint_3_intro_line)
        self.assertLess(
            sprint_3_intro_line_index + 2,
            len(lines),
            "docs/quality-gates.md: `Sprint-3 extends baseline confidence requirements.` must be followed by exactly one blank line and then `### Gate S3-1: Fixture breadth`",
        )
        self.assertEqual(
            lines[sprint_3_intro_line_index + 1].strip(),
            "",
            "docs/quality-gates.md: expected exactly one blank separator line after `Sprint-3 extends baseline confidence requirements.`",
        )
        self.assertEqual(
            lines[sprint_3_intro_line_index + 2].strip(),
            gate_s3_1_heading,
            "docs/quality-gates.md: `Sprint-3 extends baseline confidence requirements.` must be followed by exactly one blank separator line and then `### Gate S3-1: Fixture breadth`",
        )

    def test_fn_210_gate_gate_s3_1_heading_successor_first_fixture_breadth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        gate_s3_1_heading = "### Gate S3-1: Fixture breadth"
        first_fixture_breadth_bullet = (
            "- Benchmark corpus should stay at **>= 10** representative fixture pairs."
        )

        gate_s3_1_heading_index = lines.index(gate_s3_1_heading)
        self.assertLess(
            gate_s3_1_heading_index + 1,
            len(lines),
            "docs/quality-gates.md: `### Gate S3-1: Fixture breadth` must be immediately followed by `- Benchmark corpus should stay at **>= 10** representative fixture pairs.`",
        )
        self.assertEqual(
            lines[gate_s3_1_heading_index + 1].strip(),
            first_fixture_breadth_bullet,
            "docs/quality-gates.md: `### Gate S3-1: Fixture breadth` must be immediately followed by `- Benchmark corpus should stay at **>= 10** representative fixture pairs.`",
        )

    def test_fn_211_gate_s3_1_first_fixture_breadth_bullet_successor_second_fixture_breadth_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        first_fixture_breadth_bullet = (
            "- Benchmark corpus should stay at **>= 10** representative fixture pairs."
        )
        second_fixture_breadth_bullet = "- Fail if fixture count drops below threshold."

        first_fixture_breadth_bullet_index = lines.index(first_fixture_breadth_bullet)
        self.assertLess(
            first_fixture_breadth_bullet_index + 1,
            len(lines),
            "docs/quality-gates.md: `- Benchmark corpus should stay at **>= 10** representative fixture pairs.` must be immediately followed by `- Fail if fixture count drops below threshold.`",
        )
        self.assertEqual(
            lines[first_fixture_breadth_bullet_index + 1].strip(),
            second_fixture_breadth_bullet,
            "docs/quality-gates.md: `- Benchmark corpus should stay at **>= 10** representative fixture pairs.` must be immediately followed by `- Fail if fixture count drops below threshold.`",
        )

    def test_fn_212_gate_s3_1_second_fixture_breadth_bullet_successor_gate_s3_2_heading_spacing_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        second_fixture_breadth_bullet = "- Fail if fixture count drops below threshold."
        gate_s3_2_heading = "### Gate S3-2: Roundtrip determinism at corpus level"

        second_fixture_breadth_bullet_index = lines.index(second_fixture_breadth_bullet)
        self.assertLess(
            second_fixture_breadth_bullet_index + 2,
            len(lines),
            "docs/quality-gates.md: `- Fail if fixture count drops below threshold.` must be followed by exactly one blank line and then `### Gate S3-2: Roundtrip determinism at corpus level`",
        )
        self.assertEqual(
            lines[second_fixture_breadth_bullet_index + 1].strip(),
            "",
            "docs/quality-gates.md: expected exactly one blank separator line after `- Fail if fixture count drops below threshold.`",
        )
        self.assertEqual(
            lines[second_fixture_breadth_bullet_index + 2].strip(),
            gate_s3_2_heading,
            "docs/quality-gates.md: `- Fail if fixture count drops below threshold.` must be followed by exactly one blank line and then `### Gate S3-2: Roundtrip determinism at corpus level`",
        )

    def test_fn_213_gate_gate_s3_2_heading_successor_first_roundtrip_determinism_bullet_boundary_canary(
        self,
    ) -> None:
        lines = self.quality_gates_doc.splitlines()
        gate_s3_2_heading = "### Gate S3-2: Roundtrip determinism at corpus level"
        first_roundtrip_determinism_bullet = (
            "- Parse/format/parse determinism for full supported fixture set."
        )

        gate_s3_2_heading_index = lines.index(gate_s3_2_heading)
        self.assertLess(
            gate_s3_2_heading_index + 1,
            len(lines),
            "docs/quality-gates.md: `### Gate S3-2: Roundtrip determinism at corpus level` must be immediately followed by `- Parse/format/parse determinism for full supported fixture set.`",
        )
        self.assertEqual(
            lines[gate_s3_2_heading_index + 1].strip(),
            first_roundtrip_determinism_bullet,
            "docs/quality-gates.md: `### Gate S3-2: Roundtrip determinism at corpus level` must be immediately followed by `- Parse/format/parse determinism for full supported fixture set.`",
        )

    def test_anchor_required_tokens_reordered_fails_strict_order_assertion(self) -> None:
        trace_schema = self.schema["$defs"]["trace"]
        required_in_schema = set(trace_schema.get("required", []))
        active_required = [field for field in TRACE_REQUIRED_FIELDS if field in required_in_schema]

        if len(active_required) < 2:
            self.skipTest("requires at least two active required trace fields")

        reordered_required = active_required[1:] + active_required[:1]
        fixture_doc = "\n".join(
            [
                "# fixture",
                "- Gate anchor trace required: "
                + ", ".join(f"`{token}`" for token in reordered_required),
            ]
        )

        required_in_fixture = self._parse_anchor_tokens(
            text=fixture_doc,
            prefix="- Gate anchor trace required:",
            doc_name="fixture/migrations.md",
        )

        with self.assertRaises(AssertionError):
            self.assertEqual(required_in_fixture, active_required)

    def test_anchor_optional_missing_token_fails_strict_presence_assertion(self) -> None:
        trace_schema = self.schema["$defs"]["trace"]
        properties_in_schema = set(trace_schema.get("properties", {}).keys())
        active_optional = [field for field in TRACE_OPTIONAL_FIELDS if field in properties_in_schema]

        if not active_optional:
            self.skipTest("requires at least one active optional trace field")

        optional_missing_one = active_optional[:-1]
        fixture_doc = "\n".join(
            [
                "# fixture",
                "- Gate anchor trace optional: "
                + ", ".join(f"`{token}`" for token in optional_missing_one),
            ]
        )

        optional_in_fixture = self._parse_anchor_tokens(
            text=fixture_doc,
            prefix="- Gate anchor trace optional:",
            doc_name="fixture/migrations.md",
        )

        with self.assertRaises(AssertionError):
            self.assertEqual(optional_in_fixture, active_optional)

    def test_anchor_profiles_mismatch_between_docs_fails_assertion(self) -> None:
        migrations_fixture = "\n".join(
            [
                "# fixture",
                "- Gate anchor profiles: `Sprint-5 calibration additive profile`, "
                "`Sprint-6 compatibility/ref-hardening profile`",
            ]
        )
        quality_gates_fixture = "\n".join(
            [
                "# fixture",
                "- Gate anchor profiles: `Sprint-5 calibration additive profile`, "
                "`Sprint-X incompatible profile`",
            ]
        )

        profiles_in_migrations = self._parse_anchor_tokens(
            text=migrations_fixture,
            prefix="- Gate anchor profiles:",
            doc_name="fixture/migrations.md",
        )
        profiles_in_quality_gates = self._parse_anchor_tokens(
            text=quality_gates_fixture,
            prefix="- Gate anchor profiles:",
            doc_name="fixture/quality-gates.md",
        )

        with self.assertRaises(AssertionError):
            self.assertEqual(profiles_in_migrations, profiles_in_quality_gates)

    def test_error_envelope_snapshot_parity_table_driven_lane(self) -> None:
        with self.assertRaises(CompactParseError) as parse_ctx:
            parse_compact('ev{type:"x"')

        with self.assertRaises(CompactValidationError) as validate_ctx:
            parse_compact("ev{payload:{}}")

        with self.assertRaises(TypeError) as runtime_ctx:
            validate_trace_step({"rule_id": "r1", "matched_clauses": []})

        with self.assertRaises(ValueError) as runtime_value_ctx:
            eval_policies(
                event={"type": "ingest", "payload": {"x": 1}},
                rules=[
                    {
                        "id": "r1",
                        "when": ["event_type_present"],
                        "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                    }
                ],
                calibration={"points": [{"raw_score": 0.0, "probability": 0.1}]},
            )

        with self.assertRaises(TransformError) as transform_unpack_ctx:
            unpack_compact_refs(
                'erz{v:0.1}\n'
                'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}\n'
                '#\n'
            )

        with self.assertRaises(TransformError) as transform_unpack_secondary_ctx:
            unpack_compact_refs(
                'erz{v:0.1}\n'
                'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}\n'
                'rf{id:txt_001,v:"hello"}\n'
                '!\n'
            )

        io_exc = FileNotFoundError(2, "No such file or directory", "missing-file.erz")

        cases = [
            {
                "name": "parse_syntax",
                "exc": parse_ctx.exception,
                "stage": "parse",
                "command": "parse",
                "snapshot": "parse_syntax.stderr",
                "expect_span_position": 11,
                "code": "ERZ_PARSE_SYNTAX",
                "error_type": "CompactParseError",
            },
            {
                "name": "validate_schema",
                "exc": validate_ctx.exception,
                "stage": "validate",
                "command": "validate",
                "snapshot": "validate_schema.stderr",
                "expect_span_position": None,
                "code": "ERZ_VALIDATE_SCHEMA",
                "error_type": "CompactValidationError",
            },
            {
                "name": "transform_unpack_unexpected_character",
                "exc": transform_unpack_ctx.exception,
                "stage": "transform",
                "command": "unpack",
                "snapshot": "transform_unpack_unexpected_char.stderr",
                "expect_span_position": 114,
                "code": "ERZ_TRANSFORM_ERROR",
                "error_type": "TransformError",
            },
            {
                "name": "transform_unpack_unexpected_character_secondary_span",
                "exc": transform_unpack_secondary_ctx.exception,
                "stage": "transform",
                "command": "unpack",
                "snapshot": "transform_unpack_unexpected_char_secondary.stderr",
                "expect_span_position": 139,
                "code": "ERZ_TRANSFORM_ERROR",
                "error_type": "TransformError",
            },
            {
                "name": "runtime_contract",
                "exc": runtime_ctx.exception,
                "stage": "runtime",
                "command": "eval",
                "snapshot": "runtime_contract.stderr",
                "expect_span_position": None,
                "code": "ERZ_RUNTIME_CONTRACT",
                "error_type": "TypeError",
            },
            {
                "name": "runtime_value",
                "exc": runtime_value_ctx.exception,
                "stage": "runtime",
                "command": "eval",
                "snapshot": "runtime_value.stderr",
                "expect_span_position": None,
                "code": "ERZ_RUNTIME_VALUE",
                "error_type": "ValueError",
            },
            {
                "name": "cli_io",
                "exc": io_exc,
                "stage": "cli",
                "command": "parse",
                "snapshot": "io_missing_file.stderr",
                "expect_span_position": None,
                "code": "ERZ_IO_ERROR",
                "error_type": "FileNotFoundError",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                envelope = build_error_envelope(
                    case["exc"],
                    stage=case["stage"],
                    command=case["command"],
                )
                self._assert_error_snapshot(
                    envelope=envelope,
                    snapshot_name=case["snapshot"],
                    expect_span_position=case["expect_span_position"],
                )
                self.assertEqual(envelope["code"], case["code"])
                self.assertEqual(envelope["stage"], case["stage"])
                self.assertEqual(envelope["details"]["command"], case["command"])
                self.assertEqual(envelope["details"]["error_type"], case["error_type"])

    def test_error_envelope_details_key_order_strictness_canary(self) -> None:
        with self.assertRaises(CompactParseError) as parse_ctx:
            parse_compact('ev{type:"x"')

        with self.assertRaises(CompactValidationError) as validate_ctx:
            parse_compact("ev{payload:{}}")

        with self.assertRaises(TransformError) as pack_ctx:
            pack_document({})

        with self.assertRaises(TransformError) as unpack_ctx:
            unpack_compact_refs(
                'ev{id:"evt_001",t:ingest,src:telegram,txt:@txt_001,ts:"2026-02-24T15:00:00Z",geo:{la:52.52,lo:13.405}}\n'
            )

        io_exc = FileNotFoundError(2, "No such file or directory", "missing-file.erz")

        cases = [
            {
                "name": "parse",
                "exc": parse_ctx.exception,
                "stage": "parse",
                "command": "parse",
                "snapshot": "parse_syntax.stderr",
                "expect_error_type": "CompactParseError",
            },
            {
                "name": "validate",
                "exc": validate_ctx.exception,
                "stage": "validate",
                "command": "validate",
                "snapshot": "validate_schema.stderr",
                "expect_error_type": "CompactValidationError",
            },
            {
                "name": "pack",
                "exc": pack_ctx.exception,
                "stage": "transform",
                "command": "pack",
                "snapshot": "transform_pack_missing_event.stderr",
                "expect_error_type": "TransformError",
            },
            {
                "name": "unpack",
                "exc": unpack_ctx.exception,
                "stage": "transform",
                "command": "unpack",
                "snapshot": "transform_unpack_missing_header.stderr",
                "expect_error_type": "TransformError",
            },
            {
                "name": "io",
                "exc": io_exc,
                "stage": "cli",
                "command": "parse",
                "snapshot": "io_missing_file.stderr",
                "expect_error_type": "FileNotFoundError",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                envelope = build_error_envelope(
                    case["exc"],
                    stage=case["stage"],
                    command=case["command"],
                )
                rendered = render_error_envelope_json(envelope) + "\n"
                snapshot = self._read_error_snapshot(case["snapshot"])
                self.assertEqual(rendered, snapshot)

                snapshot_envelope = json.loads(snapshot)
                self.assertEqual(list(envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
                self.assertEqual(list(snapshot_envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))

                self.assertEqual(list(envelope["details"].keys()), ["error_type", "command"])
                self.assertEqual(list(snapshot_envelope["details"].keys()), ["error_type", "command"])

                expected_detail_items = [
                    ("error_type", case["expect_error_type"]),
                    ("command", case["command"]),
                ]
                self.assertEqual(list(envelope["details"].items()), expected_detail_items)
                self.assertEqual(list(snapshot_envelope["details"].items()), expected_detail_items)

    def test_eval_policies_envelope_integration_success_shape_invariants(self) -> None:
        payload = eval_policies_envelope(
            event={"type": "ingest", "payload": {"x": 1}},
            rules=[
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                }
            ],
            include_score=False,
        )

        self.assertEqual(list(payload.keys()), ["actions", "trace"])
        self.assertNotIn("error", payload)
        self.assertEqual(payload["actions"], [{"kind": "act", "params": {"rule_id": "r1"}}])
        self.assertEqual(payload["trace"], [{"rule_id": "r1", "matched_clauses": ["event_type_present"]}])

    def test_eval_policies_envelope_integration_failure_shape_invariants(self) -> None:
        payload_1 = eval_policies_envelope(
            event={"type": "ingest", "payload": {"x": 1}},
            rules=[
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                }
            ],
            calibration={"points": [{"raw_score": 0.0, "probability": 0.1}]},
        )
        payload_2 = eval_policies_envelope(
            event={"type": "ingest", "payload": {"x": 1}},
            rules=[
                {
                    "id": "r1",
                    "when": ["event_type_present"],
                    "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                }
            ],
            calibration={"points": [{"raw_score": 0.0, "probability": 0.1}]},
        )

        self.assertEqual(payload_1, payload_2)
        self.assertEqual(list(payload_1.keys()), ["actions", "trace", "error"])
        self.assertEqual(payload_1["actions"], [])
        self.assertEqual(payload_1["trace"], [])

        error = payload_1["error"]
        self.assertEqual(list(error.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
        self.assertEqual(error["code"], "ERZ_RUNTIME_VALUE")
        self.assertEqual(error["stage"], "runtime")
        self.assertEqual(error["details"]["command"], "eval")
        self.assertEqual(error["details"]["error_type"], "ValueError")

    def test_runtime_value_parity_between_builder_and_eval_envelope(self) -> None:
        event = {"type": "ingest", "payload": {"x": 1}}
        rules = [
            {
                "id": "r1",
                "when": ["event_type_present"],
                "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
            }
        ]
        calibration = {"points": [{"raw_score": 0.0, "probability": 0.1}]}

        payload = eval_policies_envelope(
            event=event,
            rules=rules,
            calibration=calibration,
        )

        with self.assertRaises(ValueError) as ctx:
            eval_policies(
                event=event,
                rules=rules,
                calibration=calibration,
            )

        direct_envelope = build_error_envelope(
            ctx.exception,
            stage="runtime",
            command="eval",
        )
        self.assertEqual(payload["error"], direct_envelope)

        rendered = render_error_envelope_json(direct_envelope) + "\n"
        self.assertEqual(rendered, self._read_error_snapshot("runtime_value.stderr"))

    def test_runtime_envelope_stage_command_matrix_parity_canary(self) -> None:
        cases = [
            {
                "name": "runtime_contract",
                "inputs": {
                    "event": {"type": "ingest", "payload": {"x": 1}},
                    "rules": [
                        {
                            "id": "r1",
                            "when": "event_type_present",
                            "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                        }
                    ],
                },
                "expected_exc": TypeError,
                "expected_code": "ERZ_RUNTIME_CONTRACT",
                "expected_error_type": "TypeError",
            },
            {
                "name": "runtime_value",
                "inputs": {
                    "event": {"type": "ingest", "payload": {"x": 1}},
                    "rules": [
                        {
                            "id": "r1",
                            "when": ["event_type_present"],
                            "then": [{"kind": "act", "params": {"rule_id": "r1"}}],
                        }
                    ],
                    "calibration": {"points": [{"raw_score": 0.0, "probability": 0.1}]},
                },
                "expected_exc": ValueError,
                "expected_code": "ERZ_RUNTIME_VALUE",
                "expected_error_type": "ValueError",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                payload = eval_policies_envelope(**case["inputs"])
                self.assertEqual(list(payload.keys()), ["actions", "trace", "error"])
                self.assertEqual(payload["actions"], [])
                self.assertEqual(payload["trace"], [])

                adapter_error = payload["error"]
                self.assertEqual(adapter_error["code"], case["expected_code"])
                self.assertEqual(adapter_error["stage"], "runtime")
                self.assertEqual(adapter_error["details"]["command"], "eval")

                with self.assertRaises(case["expected_exc"]) as exc_ctx:
                    eval_policies(**case["inputs"])

                direct_error = build_error_envelope(
                    exc_ctx.exception,
                    stage="runtime",
                    command="eval",
                )
                self.assertEqual(adapter_error, direct_error)
                self.assertEqual(adapter_error["stage"], direct_error["stage"])
                self.assertEqual(
                    adapter_error["details"]["command"],
                    direct_error["details"]["command"],
                )

                expected_detail_items = [
                    ("error_type", case["expected_error_type"]),
                    ("command", "eval"),
                ]
                self.assertEqual(list(adapter_error["details"].items()), expected_detail_items)
                self.assertEqual(list(direct_error["details"].items()), expected_detail_items)

                rendered_adapter = render_error_envelope_json(adapter_error) + "\n"
                rendered_direct = render_error_envelope_json(direct_error) + "\n"
                self.assertEqual(rendered_adapter, rendered_direct)

    def test_fp_002_cli_eval_fixture_repeated_runs_byte_identical(self) -> None:
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
        ]

        first = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(first.stdout, second.stdout)

        envelope = json.loads(first.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace"])

    def test_fp_002_cli_eval_fixture_runtime_error_envelope_stability(self) -> None:
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
        ]

        first = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(first.stdout, second.stdout)

        envelope = json.loads(first.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "error"])
        self.assertEqual(envelope["actions"], [])
        self.assertEqual(envelope["trace"], [])
        self.assertEqual(envelope["error"]["stage"], "runtime")
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")
        self.assertEqual(envelope["error"]["details"]["command"], "eval")

    def test_fp_004_cli_eval_summary_mode_success_determinism(self) -> None:
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--summary",
        ]

        first = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(first.stdout, "status=ok actions=1 trace=1\n")
        self.assertEqual(first.stdout, second.stdout)

    def test_fp_004_cli_eval_summary_mode_runtime_error_determinism(self) -> None:
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
            "--summary",
        ]

        first = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(
            first.stdout,
            "status=error code=ERZ_RUNTIME_CONTRACT stage=runtime actions=0 trace=0\n",
        )
        self.assertEqual(first.stdout, second.stdout)

    def test_fp_005_cli_eval_strict_mode_runtime_error_exit_with_stable_payload(self) -> None:
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
            "--strict",
        ]

        first = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 1)
        self.assertEqual(second.returncode, 1)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(first.stdout, second.stdout)

        envelope = json.loads(first.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "error"])
        self.assertEqual(envelope["actions"], [])
        self.assertEqual(envelope["trace"], [])
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")
        self.assertEqual(envelope["error"]["stage"], "runtime")

    def test_fp_006_cli_eval_output_file_stdout_parity_and_repeated_write_stability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "eval-output.json"
            args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--output",
                str(output_path),
            ]

            first = subprocess.run(
                args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first_file = output_path.read_text(encoding="utf-8")

            second = subprocess.run(
                args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second_file = output_path.read_text(encoding="utf-8")

            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(first.stderr, "")
            self.assertEqual(second.stderr, "")

            self.assertEqual(first_file, first.stdout)
            self.assertEqual(second_file, second.stdout)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(first_file, second_file)

    def test_fp_007_cli_eval_refs_sidecar_allows_external_ref_bindings_with_deterministic_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            program_path = tmp_path / "program-no-rf.erz"
            refs_path = tmp_path / "refs-sidecar.json"

            program_path.write_text(
                "\n".join(
                    [
                        "erz{v:1}",
                        'rule{id:"route_ops",when:["event_type_present","payload_has:severity"],then:[{kind:"notify",params:{channel:"ops",severity_ref:"@sev_label"}}]}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            refs_path.write_text('{"refs":{"sev_label":"high"}}\n', encoding="utf-8")

            args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(program_path),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--refs",
                str(refs_path),
            ]

            first = subprocess.run(
                args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(first.stderr, "")
            self.assertEqual(second.stderr, "")
            self.assertEqual(first.stdout, second.stdout)

            envelope = json.loads(first.stdout)
            self.assertEqual(list(envelope.keys()), ["actions", "trace"])
            self.assertEqual(
                envelope["actions"],
                [{"kind": "notify", "params": {"channel": "ops", "severity_ref": "@sev_label"}}],
            )

    def test_fp_007_cli_eval_refs_sidecar_collision_policy_fails_with_stable_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            refs_path = Path(tmp_dir) / "refs-collision.json"
            refs_path.write_text('{"sev_label":"critical"}\n', encoding="utf-8")

            args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--input",
                str(EVAL_FIXTURES / "event-ok.json"),
                "--refs",
                str(refs_path),
            ]

            first = subprocess.run(
                args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(first.returncode, 1)
            self.assertEqual(second.returncode, 1)
            self.assertEqual(first.stdout, "")
            self.assertEqual(second.stdout, "")
            self.assertEqual(
                first.stderr,
                "error: --refs collision with program refs for id(s): @sev_label\n",
            )
            self.assertEqual(first.stderr, second.stderr)

    def test_fp_008_cli_eval_meta_mode_hash_contract_and_repeated_run_determinism(self) -> None:
        program_payload = (EVAL_FIXTURES / "program.erz").read_text(encoding="utf-8")
        event_payload = (EVAL_FIXTURES / "event-ok.json").read_text(encoding="utf-8")
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--meta",
        ]

        first = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(first.stdout, second.stdout)

        envelope = json.loads(first.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "meta"])
        self.assertEqual(
            list(envelope["meta"].keys()),
            ["program_sha256", "event_sha256"],
        )
        self.assertEqual(
            envelope["meta"]["program_sha256"],
            hashlib.sha256(program_payload.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            envelope["meta"]["event_sha256"],
            hashlib.sha256(event_payload.encode("utf-8")).hexdigest(),
        )

    def test_fp_008_cli_eval_meta_mode_generated_at_opt_in_field_order(self) -> None:
        generated_at = "2026-03-06T18:30:00Z"
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-ok.json"),
            "--meta",
            "--generated-at",
            generated_at,
        ]

        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

        envelope = json.loads(result.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "meta"])
        self.assertEqual(
            list(envelope["meta"].keys()),
            ["program_sha256", "event_sha256", "generated_at"],
        )
        self.assertEqual(envelope["meta"]["generated_at"], generated_at)

    def test_fp_008_cli_eval_meta_mode_runtime_error_keeps_ordered_error_shape(self) -> None:
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
            "--meta",
        ]

        first = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(first.stdout, second.stdout)

        envelope = json.loads(first.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "error", "meta"])
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")
        self.assertEqual(envelope["error"]["stage"], "runtime")

    def test_fp_009_cli_eval_exit_policy_presets_runtime_error_matrix_keeps_payload_stable(self) -> None:
        base_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
        ]

        default_run = subprocess.run(
            [*base_args, "--exit-policy", "default"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        strict_run = subprocess.run(
            [*base_args, "--exit-policy", "strict"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        strict_no_actions_run = subprocess.run(
            [*base_args, "--exit-policy", "strict-no-actions"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(default_run.returncode, 0)
        self.assertEqual(strict_run.returncode, 1)
        self.assertEqual(strict_no_actions_run.returncode, 1)

        self.assertEqual(default_run.stderr, "")
        self.assertEqual(strict_run.stderr, "")
        self.assertEqual(strict_no_actions_run.stderr, "")

        self.assertEqual(default_run.stdout, strict_run.stdout)
        self.assertEqual(default_run.stdout, strict_no_actions_run.stdout)

        envelope = json.loads(default_run.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace", "error"])
        self.assertEqual(envelope["actions"], [])
        self.assertEqual(envelope["trace"], [])
        self.assertEqual(envelope["error"]["code"], "ERZ_RUNTIME_CONTRACT")

    def test_fp_010_cli_eval_empty_action_fixture_exit_policy_matrix(self) -> None:
        base_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-no-action.json"),
        ]

        default_run = subprocess.run(
            [*base_args, "--exit-policy", "default"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        strict_run = subprocess.run(
            [*base_args, "--exit-policy", "strict"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        strict_no_actions_run = subprocess.run(
            [*base_args, "--exit-policy", "strict-no-actions"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(default_run.returncode, 0)
        self.assertEqual(strict_run.returncode, 0)
        self.assertEqual(strict_no_actions_run.returncode, 1)

        self.assertEqual(default_run.stderr, "")
        self.assertEqual(strict_run.stderr, "")
        self.assertEqual(strict_no_actions_run.stderr, "")

        self.assertEqual(default_run.stdout, strict_run.stdout)
        self.assertEqual(default_run.stdout, strict_no_actions_run.stdout)

        envelope = json.loads(default_run.stdout)
        self.assertEqual(list(envelope.keys()), ["actions", "trace"])
        self.assertEqual(envelope["actions"], [])
        self.assertEqual(envelope["trace"], [])

    def test_fp_011_cli_eval_summary_policy_suffix_is_deterministic(self) -> None:
        args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--input",
            str(EVAL_FIXTURES / "event-invalid.json"),
            "--summary",
            "--summary-policy",
            "--exit-policy",
            "strict",
        ]

        first = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 1)
        self.assertEqual(second.returncode, 1)
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")
        self.assertEqual(
            first.stdout,
            "status=error code=ERZ_RUNTIME_CONTRACT stage=runtime actions=0 trace=0 policy=strict exit=1\n",
        )
        self.assertEqual(first.stdout, second.stdout)

    def test_fp_012_cli_eval_batch_mode_aggregate_envelope_and_exit_matrix(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"
        base_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
        ]

        default_run = subprocess.run(
            [*base_args, "--exit-policy", "default"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        strict_run = subprocess.run(
            [*base_args, "--exit-policy", "strict"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        strict_no_actions_run = subprocess.run(
            [*base_args, "--exit-policy", "strict-no-actions"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(default_run.returncode, 0)
        self.assertEqual(strict_run.returncode, 1)
        self.assertEqual(strict_no_actions_run.returncode, 1)

        self.assertEqual(default_run.stderr, "")
        self.assertEqual(strict_run.stderr, "")
        self.assertEqual(strict_no_actions_run.stderr, "")

        self.assertEqual(default_run.stdout, strict_run.stdout)
        self.assertEqual(default_run.stdout, strict_no_actions_run.stdout)

        envelope = json.loads(default_run.stdout)
        self.assertEqual(list(envelope.keys()), ["events", "summary"])
        self.assertEqual(
            [event["event"] for event in envelope["events"]],
            ["01-ok.json", "02-no-action.json", "03-invalid.json"],
        )
        self.assertEqual(
            envelope["summary"],
            {
                "event_count": 3,
                "total_event_count": 3,
                "error_count": 1,
                "no_action_count": 1,
                "action_count": 1,
                "trace_count": 1,
            },
        )

    def test_fp_013_cli_eval_batch_include_exclude_globs_are_stable(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"
        include_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
            "--include",
            "*ok*.json",
        ]
        empty_selection_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
            "--include",
            "*.json",
            "--exclude",
            "*.json",
        ]

        include_run = subprocess.run(
            include_args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        include_run_repeat = subprocess.run(
            include_args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        empty_selection_run = subprocess.run(
            empty_selection_args,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(include_run.returncode, 0)
        self.assertEqual(include_run_repeat.returncode, 0)
        self.assertEqual(include_run.stderr, "")
        self.assertEqual(include_run.stdout, include_run_repeat.stdout)

        include_envelope = json.loads(include_run.stdout)
        self.assertEqual(
            [entry["event"] for entry in include_envelope["events"]],
            ["01-ok.json"],
        )
        self.assertEqual(
            include_envelope["summary"],
            {
                "event_count": 1,
                "total_event_count": 3,
                "error_count": 0,
                "no_action_count": 0,
                "action_count": 1,
                "trace_count": 1,
            },
        )

        self.assertEqual(empty_selection_run.returncode, 1)
        self.assertEqual(empty_selection_run.stdout, "")
        self.assertEqual(
            empty_selection_run.stderr,
            "error: --batch filters matched no .json files (include='*.json', exclude='*.json')\n",
        )

    def test_fp_014_cli_eval_batch_output_directory_writes_deterministic_artifacts(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"
        baseline_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            output_args = [*baseline_args, "--batch-output", str(output_dir)]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }
            second = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }

        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)

        self.assertEqual(baseline.stderr, "")
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")

        self.assertEqual(first.stdout, baseline.stdout)
        self.assertEqual(second.stdout, baseline.stdout)
        self.assertEqual(first_artifacts, second_artifacts)

        envelope = json.loads(first.stdout)
        self.assertEqual(
            sorted(second_artifacts.keys()),
            [
                "01-ok.envelope.json",
                "02-no-action.envelope.json",
                "03-invalid.envelope.json",
                "summary.json",
            ],
        )

        summary_artifact = json.loads(second_artifacts["summary.json"])
        self.assertEqual(list(summary_artifact.keys()), ["mode", "event_artifacts", "summary"])
        self.assertEqual(summary_artifact["mode"], "all")
        self.assertEqual(summary_artifact["summary"], envelope["summary"])

    def test_fp_015_cli_eval_batch_output_errors_only_keeps_stdout_and_writes_failure_subset(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"
        baseline_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
            "--exit-policy",
            "strict-no-actions",
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            output_args = [
                *baseline_args,
                "--batch-output",
                str(output_dir),
                "--batch-output-errors-only",
            ]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }
            second = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }

        self.assertEqual(baseline.returncode, 1)
        self.assertEqual(first.returncode, 1)
        self.assertEqual(second.returncode, 1)

        self.assertEqual(baseline.stderr, "")
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")

        self.assertEqual(first.stdout, baseline.stdout)
        self.assertEqual(second.stdout, baseline.stdout)
        self.assertEqual(first_artifacts, second_artifacts)
        self.assertEqual(
            sorted(second_artifacts.keys()),
            [
                "02-no-action.envelope.json",
                "03-invalid.envelope.json",
                "summary.json",
            ],
        )

        baseline_envelope = json.loads(baseline.stdout)
        summary_artifact = json.loads(second_artifacts["summary.json"])
        self.assertEqual(summary_artifact["mode"], "errors-only")
        self.assertEqual(
            summary_artifact["event_artifacts"],
            ["02-no-action.envelope.json", "03-invalid.envelope.json"],
        )
        self.assertEqual(summary_artifact["summary"], baseline_envelope["summary"])

    def test_fp_016_cli_eval_batch_output_manifest_sha256_map_is_deterministic(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"
        baseline_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            output_args = [
                *baseline_args,
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first_artifacts = {
                str(path.relative_to(output_dir)): path.read_text(encoding="utf-8")
                for path in sorted(output_dir.rglob("*.json"))
            }
            second = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second_artifacts = {
                str(path.relative_to(output_dir)): path.read_text(encoding="utf-8")
                for path in sorted(output_dir.rglob("*.json"))
            }

        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)

        self.assertEqual(baseline.stderr, "")
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")

        self.assertEqual(first.stdout, baseline.stdout)
        self.assertEqual(second.stdout, baseline.stdout)
        self.assertEqual(first_artifacts, second_artifacts)

        summary_artifact = json.loads(second_artifacts["summary.json"])
        self.assertEqual(
            list(summary_artifact.keys()),
            ["mode", "event_artifacts", "artifact_sha256", "summary"],
        )
        self.assertEqual(summary_artifact["mode"], "all")

        artifact_hashes = summary_artifact["artifact_sha256"]
        self.assertEqual(list(artifact_hashes.keys()), summary_artifact["event_artifacts"])
        for artifact_name in summary_artifact["event_artifacts"]:
            self.assertIn(artifact_name, second_artifacts)
            self.assertEqual(
                artifact_hashes[artifact_name],
                hashlib.sha256(second_artifacts[artifact_name].encode("utf-8")).hexdigest(),
            )

    def test_fp_017_cli_eval_batch_output_layout_by_status_groups_artifacts(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"
        baseline_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
            "--exit-policy",
            "strict-no-actions",
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            output_args = [
                *baseline_args,
                "--batch-output",
                str(output_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
            ]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first_artifacts = {
                str(path.relative_to(output_dir)): path.read_text(encoding="utf-8")
                for path in sorted(output_dir.rglob("*.json"))
            }
            second = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second_artifacts = {
                str(path.relative_to(output_dir)): path.read_text(encoding="utf-8")
                for path in sorted(output_dir.rglob("*.json"))
            }

        self.assertEqual(baseline.returncode, 1)
        self.assertEqual(first.returncode, 1)
        self.assertEqual(second.returncode, 1)

        self.assertEqual(baseline.stderr, "")
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")

        self.assertEqual(first.stdout, baseline.stdout)
        self.assertEqual(second.stdout, baseline.stdout)
        self.assertEqual(first_artifacts, second_artifacts)
        self.assertEqual(
            sorted(second_artifacts.keys()),
            [
                "error/03-invalid.envelope.json",
                "no-action/02-no-action.envelope.json",
                "summary.json",
            ],
        )

        baseline_envelope = json.loads(baseline.stdout)
        summary_artifact = json.loads(second_artifacts["summary.json"])
        self.assertEqual(list(summary_artifact.keys()), ["mode", "layout", "event_artifacts", "summary"])
        self.assertEqual(summary_artifact["mode"], "errors-only")
        self.assertEqual(summary_artifact["layout"], "by-status")
        self.assertEqual(
            summary_artifact["event_artifacts"],
            ["no-action/02-no-action.envelope.json", "error/03-invalid.envelope.json"],
        )
        self.assertEqual(summary_artifact["summary"], baseline_envelope["summary"])

    def test_fp_018_cli_eval_batch_output_run_id_metadata_stamps_summary_artifact(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"
        baseline_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            output_args = [
                *baseline_args,
                "--batch-output",
                str(output_dir),
                "--batch-output-run-id",
                "ci-run-2026-03-06T20-30-00Z",
            ]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }
            second = subprocess.run(
                output_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second_artifacts = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(output_dir.glob("*.json"))
            }

        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)

        self.assertEqual(baseline.stderr, "")
        self.assertEqual(first.stderr, "")
        self.assertEqual(second.stderr, "")

        self.assertEqual(first.stdout, baseline.stdout)
        self.assertEqual(second.stdout, baseline.stdout)
        self.assertEqual(first_artifacts, second_artifacts)

        summary_artifact = json.loads(second_artifacts["summary.json"])
        self.assertEqual(
            list(summary_artifact.keys()),
            ["mode", "run", "event_artifacts", "summary"],
        )
        self.assertEqual(summary_artifact["mode"], "all")
        self.assertEqual(summary_artifact["run"], {"id": "ci-run-2026-03-06T20-30-00Z"})

    def test_fp_019_cli_eval_batch_output_verify_mode_reports_deterministic_integrity_status(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"
        emit_args = [
            "python3",
            "-m",
            "cli.main",
            "eval",
            str(EVAL_FIXTURES / "program.erz"),
            "--batch",
            str(batch_dir),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_with_artifacts_args = [
                *emit_args,
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
                "--batch-output-layout",
                "by-status",
            ]
            verify_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
            ]

            emit_result = subprocess.run(
                emit_with_artifacts_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first_verify = subprocess.run(
                verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second_verify = subprocess.run(
                verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            summary_verify = subprocess.run(
                [*verify_args, "--summary"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            tampered_artifact = output_dir / "ok" / "01-ok.envelope.json"
            tampered_artifact.write_text('{"tampered":true}\n', encoding="utf-8")

            failed_verify = subprocess.run(
                verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(first_verify.returncode, 0)
        self.assertEqual(second_verify.returncode, 0)
        self.assertEqual(summary_verify.returncode, 0)
        self.assertEqual(failed_verify.returncode, 1)

        self.assertEqual(emit_result.stderr, "")
        self.assertEqual(first_verify.stderr, "")
        self.assertEqual(second_verify.stderr, "")
        self.assertEqual(summary_verify.stderr, "")
        self.assertEqual(failed_verify.stderr, "")

        self.assertEqual(first_verify.stdout, second_verify.stdout)
        self.assertEqual(
            summary_verify.stdout,
            "status=ok checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3\n",
        )

        verify_payload = json.loads(first_verify.stdout)
        self.assertEqual(verify_payload["status"], "ok")
        self.assertEqual(verify_payload["checked"], 3)
        self.assertEqual(verify_payload["verified"], 3)
        self.assertEqual(verify_payload["selected_artifacts_count"], 3)
        self.assertEqual(verify_payload["selected_manifest_entries_count"], 3)

        failed_payload = json.loads(failed_verify.stdout)
        self.assertEqual(failed_payload["status"], "error")
        self.assertEqual(failed_payload["checked"], 3)
        self.assertEqual(failed_payload["verified"], 2)
        self.assertEqual(failed_payload["selected_artifacts_count"], 3)
        self.assertEqual(failed_payload["selected_manifest_entries_count"], 3)
        self.assertEqual(len(failed_payload["mismatched_artifacts"]), 1)
        self.assertEqual(
            failed_payload["mismatched_artifacts"][0],
            {
                "artifact": "ok/01-ok.envelope.json",
                "expected": failed_payload["mismatched_artifacts"][0]["expected"],
                "actual": hashlib.sha256('{"tampered":true}\n'.encode("utf-8")).hexdigest(),
            },
        )

    def test_fp_020_cli_eval_batch_output_verify_strict_profile_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "ci-run-2026-03-07T09-30-00Z",
            ]
            strict_verify_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-layout",
                "by-status",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$",
            ]
            failing_verify_args = [
                *strict_verify_args,
                "--batch-output-verify-expected-mode",
                "errors-only",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_verify = subprocess.run(
                strict_verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_verify_summary = subprocess.run(
                [*strict_verify_args, "--summary"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            failing_verify = subprocess.run(
                failing_verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(strict_verify.returncode, 0)
        self.assertEqual(strict_verify_summary.returncode, 0)
        self.assertEqual(failing_verify.returncode, 1)

        self.assertEqual(emit_result.stderr, "")
        self.assertEqual(strict_verify.stderr, "")
        self.assertEqual(strict_verify_summary.stderr, "")
        self.assertEqual(failing_verify.stderr, "")

        self.assertEqual(
            strict_verify_summary.stdout,
            "status=ok checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=0\n",
        )

        strict_payload = json.loads(strict_verify.stdout)
        self.assertEqual(strict_payload["status"], "ok")
        self.assertEqual(strict_payload["strict_profile_mismatches"], [])

        failing_payload = json.loads(failing_verify.stdout)
        self.assertEqual(failing_payload["status"], "error")
        self.assertEqual(
            failing_payload["strict_profile_mismatches"],
            [{"field": "mode", "expected": "errors-only", "actual": "all"}],
        )

    def test_fp_021_cli_eval_batch_output_verify_profile_presets_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
            ]
            triage_verify_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-profile",
                "triage-by-status",
            ]
            default_verify_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-profile",
                "default",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            triage_verify = subprocess.run(
                triage_verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            triage_verify_summary = subprocess.run(
                [*triage_verify_args, "--summary"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            default_verify = subprocess.run(
                default_verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(triage_verify.returncode, 0)
        self.assertEqual(triage_verify_summary.returncode, 0)
        self.assertEqual(default_verify.returncode, 1)

        self.assertEqual(emit_result.stderr, "")
        self.assertEqual(triage_verify.stderr, "")
        self.assertEqual(triage_verify_summary.stderr, "")
        self.assertEqual(default_verify.stderr, "")

        self.assertEqual(
            triage_verify_summary.stdout,
            "status=ok checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=0\n",
        )

        triage_payload = json.loads(triage_verify.stdout)
        self.assertEqual(triage_payload["status"], "ok")
        self.assertEqual(
            triage_payload["strict_profile"],
            {
                "expected_mode": "errors-only",
                "expected_layout": "by-status",
            },
        )
        self.assertEqual(triage_payload["strict_profile_mismatches"], [])

        default_payload = json.loads(default_verify.stdout)
        self.assertEqual(default_payload["status"], "error")
        self.assertEqual(
            default_payload["strict_profile_mismatches"],
            [
                {"field": "mode", "expected": "all", "actual": "errors-only"},
                {"field": "layout", "expected": "flat", "actual": "by-status"},
            ],
        )

    def test_fp_022_cli_eval_batch_output_verify_require_run_id_toggle_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]
            strict_verify_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
            ]
            require_run_id_args = [*strict_verify_args, "--batch-output-verify-require-run-id"]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            baseline_verify = subprocess.run(
                strict_verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            require_run_id_verify = subprocess.run(
                require_run_id_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            require_run_id_summary = subprocess.run(
                [*require_run_id_args, "--summary"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(baseline_verify.returncode, 0)
        self.assertEqual(baseline_verify.stderr, "")

        self.assertEqual(require_run_id_verify.returncode, 1)
        self.assertEqual(require_run_id_verify.stderr, "")
        self.assertEqual(require_run_id_summary.returncode, 1)
        self.assertEqual(require_run_id_summary.stderr, "")
        self.assertEqual(
            require_run_id_summary.stdout,
            "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        require_run_id_payload = json.loads(require_run_id_verify.stdout)
        self.assertEqual(require_run_id_payload["status"], "error")
        self.assertEqual(
            require_run_id_payload["strict_profile_mismatches"],
            [{"field": "run.id", "expected": "present", "actual": "<missing>"}],
        )

    def test_fp_023_cli_eval_batch_output_self_verify_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            baseline_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
            ]
            self_verify_args = [
                *baseline_args,
                "--batch-output",
                str(output_dir),
                "--batch-output-self-verify",
            ]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self_verify = subprocess.run(
                self_verify_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verify = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(self_verify.returncode, 0)
        self.assertEqual(verify.returncode, 0)

        self.assertEqual(baseline.stderr, "")
        self.assertEqual(self_verify.stderr, "")
        self.assertEqual(verify.stderr, "")

        self.assertEqual(self_verify.stdout, baseline.stdout)
        self.assertEqual(summary_payload["mode"], "all")
        self.assertEqual(len(summary_payload["event_artifacts"]), 3)
        self.assertEqual(len(summary_payload["artifact_sha256"]), 3)

    def test_fp_024_cli_eval_batch_output_verify_expected_event_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]
            strict_pass_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "3",
            ]
            strict_fail_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-strict",
                "--batch-output-verify-expected-event-count",
                "2",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_pass = subprocess.run(
                strict_pass_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                strict_fail_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [*strict_fail_args, "--summary"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_pass.returncode, 0)
        self.assertEqual(strict_pass.stderr, "")
        strict_pass_payload = json.loads(strict_pass.stdout)
        self.assertEqual(strict_pass_payload["status"], "ok")
        self.assertEqual(
            strict_pass_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_event_count": 3,
            },
        )

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "summary.event_count", "expected": 2, "actual": 3}],
        )

    def test_fp_029_cli_eval_batch_output_verify_expected_verified_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            invalid_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "invalid" in artifact
            )
            (output_dir / invalid_artifact).write_text('{"tampered":true}\n', encoding="utf-8")

            strict_pass = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "*ok*",
                    "--batch-output-verify-expected-verified-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-verified-count",
                    "3",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-verified-count",
                    "3",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_pass.returncode, 0)
        self.assertEqual(strict_pass.stderr, "")
        strict_pass_payload = json.loads(strict_pass.stdout)
        self.assertEqual(strict_pass_payload["status"], "ok")
        self.assertEqual(
            strict_pass_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_verified_count": 1,
            },
        )

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "verified", "expected": 3, "actual": 2}],
        )

    def test_fp_030_cli_eval_batch_output_verify_expected_checked_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            invalid_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "invalid" in artifact
            )
            (output_dir / invalid_artifact).write_text('{"tampered":true}\n', encoding="utf-8")

            strict_pass = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "*ok*",
                    "--batch-output-verify-expected-checked-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "*ok*",
                    "--batch-output-verify-expected-checked-count",
                    "2",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "*ok*",
                    "--batch-output-verify-expected-checked-count",
                    "2",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_pass.returncode, 0)
        self.assertEqual(strict_pass.stderr, "")
        strict_pass_payload = json.loads(strict_pass.stdout)
        self.assertEqual(strict_pass_payload["status"], "ok")
        self.assertEqual(
            strict_pass_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_checked_count": 1,
            },
        )

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=1 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=1 selected_manifest=1 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "checked", "expected": 2, "actual": 1}],
        )

    def test_fp_031_cli_eval_batch_output_verify_expected_missing_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            missing_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "invalid" in artifact
            )
            (output_dir / missing_artifact).unlink()

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-missing-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-missing-count",
                    "0",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-missing-count",
                    "0",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 1)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "error")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_missing_count": 1,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=2 missing=1 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "missing_artifacts.count", "expected": 0, "actual": 1}],
        )

    def test_fp_032_cli_eval_batch_output_verify_expected_mismatched_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            mismatched_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "ok" in artifact
            )
            artifact_path = output_dir / mismatched_artifact
            artifact_path.write_text(
                artifact_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-mismatched-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-mismatched-count",
                    "0",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-mismatched-count",
                    "0",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 1)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "error")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_mismatched_count": 1,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "mismatched_artifacts.count", "expected": 0, "actual": 1}],
        )

    def test_fp_033_cli_eval_batch_output_verify_expected_manifest_missing_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_path = output_dir / "summary.json"
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            missing_manifest_artifact = summary_payload["event_artifacts"][0]
            del summary_payload["artifact_sha256"][missing_manifest_artifact]
            summary_path.write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-manifest-missing-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-manifest-missing-count",
                    "0",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-manifest-missing-count",
                    "0",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 1)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "error")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_manifest_missing_count": 1,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=2 missing=0 manifest_missing=1 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=2 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "missing_manifest_entries.count", "expected": 0, "actual": 1}],
        )

    def test_fp_034_cli_eval_batch_output_verify_expected_invalid_hashes_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_path = output_dir / "summary.json"
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            invalid_hash_artifact = summary_payload["event_artifacts"][0]
            summary_payload["artifact_sha256"][invalid_hash_artifact] = "not-a-sha256"
            summary_path.write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-invalid-hashes-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-invalid-hashes-count",
                    "0",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-invalid-hashes-count",
                    "0",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 1)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "error")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_invalid_hashes_count": 1,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=1 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "invalid_manifest_hashes.count", "expected": 0, "actual": 1}],
        )

    def test_fp_035_cli_eval_batch_output_verify_expected_unexpected_manifest_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]

            emit_result = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_path = output_dir / "summary.json"
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            summary_payload["artifact_sha256"]["unexpected/ghost.envelope.json"] = "0" * 64
            summary_path.write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-unexpected-manifest-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-unexpected-manifest-count",
                    "0",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-unexpected-manifest-count",
                    "0",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 1)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "error")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_unexpected_manifest_count": 1,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=1 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "unexpected_manifest_entries.count", "expected": 0, "actual": 1}],
        )

    def test_fp_036_cli_eval_batch_output_verify_expected_status_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(output_dir),
                    "--batch-output-manifest",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-status",
                    "ok",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-status",
                    "error",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-status",
                    "error",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 0)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "ok")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_status": "ok",
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "status", "expected": "error", "actual": "ok"}],
        )

    def test_fp_037_cli_eval_batch_output_verify_expected_strict_mismatches_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(output_dir),
                    "--batch-output-manifest",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            tampered_artifact_relpath = summary_payload["event_artifacts"][0]
            (output_dir / tampered_artifact_relpath).write_text('{"tampered":true}\n', encoding="utf-8")

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-mismatched-count",
                    "0",
                    "--batch-output-verify-expected-strict-mismatches-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-mismatched-count",
                    "0",
                    "--batch-output-verify-expected-strict-mismatches-count",
                    "0",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-mismatched-count",
                    "0",
                    "--batch-output-verify-expected-strict-mismatches-count",
                    "0",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 1)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "error")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_mismatched_count": 0,
                "expected_strict_mismatches_count": 1,
            },
        )
        self.assertEqual(
            strict_match_payload["strict_profile_mismatches"],
            [{"field": "mismatched_artifacts.count", "expected": 0, "actual": 1}],
        )

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=2\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [
                {"field": "mismatched_artifacts.count", "expected": 0, "actual": 1},
                {
                    "field": "strict_profile_mismatches.count",
                    "expected": 0,
                    "actual": 1,
                },
            ],
        )

    def test_fp_038_cli_eval_batch_output_verify_expected_event_artifact_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(output_dir),
                    "--batch-output-manifest",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-event-artifact-count",
                    "3",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-event-artifact-count",
                    "2",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-event-artifact-count",
                    "2",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 0)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "ok")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_event_artifact_count": 3,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "event_artifacts.count", "expected": 2, "actual": 3}],
        )

    def test_fp_039_cli_eval_batch_output_verify_expected_manifest_entry_count_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(output_dir),
                    "--batch-output-manifest",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-manifest-entry-count",
                    "3",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-manifest-entry-count",
                    "2",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-expected-manifest-entry-count",
                    "2",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 0)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "ok")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_manifest_entry_count": 3,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "artifact_sha256.count", "expected": 2, "actual": 3}],
        )

    def test_fp_040_cli_eval_batch_output_verify_expected_selected_artifact_count_contract(
        self,
    ) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(output_dir),
                    "--batch-output-manifest",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "01-*",
                    "--batch-output-verify-expected-selected-artifact-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "01-*",
                    "--batch-output-verify-expected-selected-artifact-count",
                    "2",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "01-*",
                    "--batch-output-verify-expected-selected-artifact-count",
                    "2",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 0)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "ok")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_selected_artifact_count": 1,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=1 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=1 selected_manifest=1 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "selected_artifacts.count", "expected": 2, "actual": 1}],
        )

    def test_fp_041_cli_eval_batch_output_verify_expected_manifest_selected_entry_count_contract(
        self,
    ) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            emit_result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(output_dir),
                    "--batch-output-manifest",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            strict_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "0*-*.envelope.json",
                    "--batch-output-verify-expected-manifest-selected-entry-count",
                    "3",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            manifest_payload = summary_payload["artifact_sha256"]
            manifest_payload.pop("02-no-action.envelope.json")
            (output_dir / "summary.json").write_text(
                f"{json.dumps(summary_payload, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            strict_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "0*-*.envelope.json",
                    "--batch-output-verify-expected-manifest-selected-entry-count",
                    "3",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-strict",
                    "--batch-output-verify-include",
                    "0*-*.envelope.json",
                    "--batch-output-verify-expected-manifest-selected-entry-count",
                    "3",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_result.returncode, 0)
        self.assertEqual(emit_result.stderr, "")

        self.assertEqual(strict_match.returncode, 0)
        self.assertEqual(strict_match.stderr, "")
        strict_match_payload = json.loads(strict_match.stdout)
        self.assertEqual(strict_match_payload["status"], "ok")
        self.assertEqual(
            strict_match_payload["strict_profile"],
            {
                "expected_mode": "all",
                "expected_manifest_selected_entry_count": 3,
            },
        )
        self.assertEqual(strict_match_payload["strict_profile_mismatches"], [])

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stderr, "")
        self.assertEqual(strict_fail_summary.returncode, 1)
        self.assertEqual(strict_fail_summary.stderr, "")
        self.assertEqual(
            strict_fail_summary.stdout,
            "status=error checked=3 verified=2 missing=0 manifest_missing=1 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=2 strict_mismatches=1\n",
        )

        strict_fail_payload = json.loads(strict_fail.stdout)
        self.assertEqual(strict_fail_payload["status"], "error")
        self.assertEqual(
            strict_fail_payload["strict_profile_mismatches"],
            [{"field": "selected_manifest_entries.count", "expected": 3, "actual": 2}],
        )

    def test_fp_025_cli_eval_batch_output_self_verify_strict_handoff_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            pass_output_dir = Path(tmp_dir) / "batch-output-pass"
            fail_output_dir = Path(tmp_dir) / "batch-output-fail"
            pass_summary_file = Path(tmp_dir) / "self-verify-pass.summary.txt"
            pass_json_file = Path(tmp_dir) / "self-verify-pass.json"
            fail_summary_file = Path(tmp_dir) / "self-verify-fail.summary.txt"
            fail_json_file = Path(tmp_dir) / "self-verify-fail.json"

            baseline_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--summary",
            ]
            strict_pass_args = [
                *baseline_args,
                "--batch-output",
                str(pass_output_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "ci-run-2026-03-07T11-15-00Z",
                "--batch-output-self-verify",
                "--batch-output-self-verify-strict",
                "--batch-output-self-verify-summary-file",
                str(pass_summary_file),
                "--batch-output-self-verify-json-file",
                str(pass_json_file),
                "--batch-output-verify-profile",
                "triage-by-status",
                "--batch-output-verify-expected-run-id-pattern",
                "^ci-run-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$",
                "--batch-output-verify-expected-event-count",
                "3",
            ]
            strict_fail_args = [
                *baseline_args,
                "--batch-output",
                str(fail_output_dir),
                "--batch-output-errors-only",
                "--batch-output-self-verify",
                "--batch-output-self-verify-strict",
                "--batch-output-self-verify-summary-file",
                str(fail_summary_file),
                "--batch-output-self-verify-json-file",
                str(fail_json_file),
            ]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_pass = subprocess.run(
                strict_pass_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_fail = subprocess.run(
                strict_fail_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((pass_output_dir / "summary.json").read_text(encoding="utf-8"))
            pass_summary_output = pass_summary_file.read_text(encoding="utf-8")
            pass_payload = json.loads(pass_json_file.read_text(encoding="utf-8"))
            fail_summary_output = fail_summary_file.read_text(encoding="utf-8")
            fail_payload = json.loads(fail_json_file.read_text(encoding="utf-8"))

        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(baseline.stderr, "")

        self.assertEqual(strict_pass.returncode, 0)
        self.assertEqual(strict_pass.stderr, "")
        self.assertEqual(strict_pass.stdout, baseline.stdout)
        self.assertEqual(summary_payload["mode"], "errors-only")
        self.assertEqual(summary_payload["layout"], "by-status")
        self.assertEqual(summary_payload["run"], {"id": "ci-run-2026-03-07T11-15-00Z"})
        self.assertEqual(len(summary_payload["event_artifacts"]), 2)
        self.assertEqual(len(summary_payload["artifact_sha256"]), 2)
        self.assertEqual(
            pass_summary_output,
            "status=ok checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=0\n",
        )
        self.assertEqual(pass_payload["status"], "ok")
        self.assertEqual(pass_payload["strict_profile_mismatches"], [])
        self.assertEqual(pass_payload["strict_profile"]["expected_mode"], "errors-only")
        self.assertEqual(pass_payload["strict_profile"]["expected_layout"], "by-status")

        self.assertEqual(strict_fail.returncode, 1)
        self.assertEqual(strict_fail.stdout, "")
        self.assertEqual(
            strict_fail.stderr,
            "error: --batch-output-self-verify-strict failed: status=error checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=1\n",
        )
        self.assertEqual(
            fail_summary_output,
            "status=error checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2 strict_mismatches=1\n",
        )
        self.assertEqual(fail_payload["status"], "error")
        self.assertEqual(
            fail_payload["strict_profile_mismatches"],
            [{"field": "mode", "expected": "all", "actual": "errors-only"}],
        )

    def test_fp_068_cli_eval_batch_output_self_compare_handoff_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            strict_candidate_dir = Path(tmp_dir) / "candidate-strict"
            fail_candidate_dir = Path(tmp_dir) / "candidate-fail"
            strict_compare_file = Path(tmp_dir) / "self-compare-strict.json"
            fail_compare_file = Path(tmp_dir) / "self-compare-fail.json"

            baseline_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(baseline_dir),
                "--batch-output-run-id",
                "baseline-001",
            ]
            strict_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(strict_candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-run-id",
                "candidate-expected-002",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-self-compare-strict",
                "--batch-output-compare-profile",
                "expected-asymmetric-drift",
                "--batch-output-compare-expected-compared-count",
                "2",
                "--batch-output-compare-expected-matched-count",
                "2",
                "--batch-output-compare-expected-baseline-only-count",
                "1",
                "--batch-output-compare-expected-candidate-only-count",
                "0",
                "--batch-output-compare-expected-missing-baseline-count",
                "0",
                "--batch-output-compare-expected-missing-candidate-count",
                "0",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "2",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-summary-file",
                str(strict_compare_file),
            ]
            fail_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(fail_candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-run-id",
                "candidate-fail-003",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-compare-summary-file",
                str(fail_compare_file),
            ]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_pass = subprocess.run(
                strict_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            strict_payload = json.loads(strict_compare_file.read_text(encoding="utf-8"))
            fail_run = subprocess.run(
                fail_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            fail_payload = json.loads(fail_compare_file.read_text(encoding="utf-8"))

        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(baseline.stderr, "")

        self.assertEqual(strict_pass.returncode, 0)
        self.assertEqual(strict_pass.stderr, "")
        self.assertEqual(strict_pass.stdout, baseline.stdout)
        self.assertEqual(strict_payload["status"], "ok")
        self.assertEqual(strict_payload["compare_status"], "error")
        self.assertEqual(strict_payload["compared"], 2)
        self.assertEqual(strict_payload["matched"], 2)
        self.assertEqual(strict_payload["selected_baseline_artifacts_count"], 3)
        self.assertEqual(strict_payload["selected_candidate_artifacts_count"], 2)
        self.assertEqual(strict_payload["strict_profile_mismatches"], [])

        self.assertEqual(fail_run.returncode, 1)
        self.assertEqual(fail_run.stdout, "")
        self.assertEqual(
            fail_run.stderr,
            "error: --batch-output-self-compare-against failed: status=error compared=2 matched=2 changed=0 baseline_only=1 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=2 selected_baseline=3 selected_candidate=2\n",
        )
        self.assertEqual(fail_payload["status"], "error")
        self.assertEqual(fail_payload["compared"], 2)
        self.assertEqual(fail_payload["matched"], 2)
        self.assertEqual(fail_payload["selected_baseline_artifacts_count"], 3)
        self.assertEqual(fail_payload["selected_candidate_artifacts_count"], 2)
        self.assertEqual(len(fail_payload["baseline_only_artifacts"]), 1)
        self.assertEqual(len(fail_payload["metadata_mismatches"]), 2)

    def test_fp_069_070_threshold_handoff_self_compare_snapshot_and_manifest_policy(
        self,
    ) -> None:
        threshold_handoff = EVAL_FIXTURES / "threshold-handoff"
        batch_dir = threshold_handoff / "batch"
        baseline_dir = threshold_handoff / "baseline"
        expected_clean_bundle = json.loads(
            (
                threshold_handoff
                / "candidate-clean-vs-baseline.handoff-bundle.expected.json"
            ).read_text(encoding="utf-8")
        )
        expected_triage_bundle = json.loads(
            (
                threshold_handoff
                / "triage-by-status-vs-baseline.handoff-bundle.expected.json"
            ).read_text(encoding="utf-8")
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            clean_candidate_dir = Path(tmp_dir) / "candidate-clean"
            triage_candidate_dir = Path(tmp_dir) / "candidate-triage"
            clean_bundle_file = Path(tmp_dir) / "self-compare-clean-bundle.json"
            triage_bundle_file = Path(tmp_dir) / "self-compare-triage-bundle.json"

            clean_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program-thresholds.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(clean_candidate_dir),
                "--batch-output-run-id",
                "threshold-ci-candidate-clean-001",
                "--batch-output-manifest",
                "--summary",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-handoff-bundle-file",
                str(clean_bundle_file),
            ]
            triage_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program-thresholds.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(triage_candidate_dir),
                "--batch-output-errors-only",
                "--batch-output-layout",
                "by-status",
                "--batch-output-run-id",
                "threshold-ci-triage-001",
                "--batch-output-manifest",
                "--summary",
                "--batch-output-self-compare-against",
                str(baseline_dir),
                "--batch-output-self-compare-strict",
                "--batch-output-compare-profile",
                "expected-asymmetric-drift",
                "--batch-output-compare-expected-baseline-only-count",
                "3",
                "--batch-output-compare-expected-candidate-only-count",
                "2",
                "--batch-output-compare-expected-selected-baseline-count",
                "3",
                "--batch-output-compare-expected-selected-candidate-count",
                "2",
                "--batch-output-compare-expected-metadata-mismatches-count",
                "4",
                "--batch-output-handoff-bundle-file",
                str(triage_bundle_file),
            ]

            clean_run = subprocess.run(
                clean_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            triage_run = subprocess.run(
                triage_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            clean_bundle = json.loads(clean_bundle_file.read_text(encoding="utf-8"))
            triage_bundle = json.loads(triage_bundle_file.read_text(encoding="utf-8"))
            clean_summary = json.loads(
                (clean_candidate_dir / "summary.json").read_text(encoding="utf-8")
            )
            triage_summary = json.loads(
                (triage_candidate_dir / "summary.json").read_text(encoding="utf-8")
            )

        self.assertEqual(clean_run.returncode, 0)
        self.assertEqual(clean_run.stderr, "")
        self.assertEqual(clean_bundle, expected_clean_bundle)
        self.assertIsNone(clean_bundle["self_verify"])
        self.assertEqual(clean_bundle["batch_output_summary"], clean_summary)
        self.assertEqual(clean_bundle["self_compare"]["details"]["status"], "ok")
        self.assertEqual(
            list(clean_summary.keys()),
            ["mode", "run", "event_artifacts", "artifact_sha256", "summary"],
        )
        self.assertEqual(clean_summary["run"]["id"], "threshold-ci-candidate-clean-001")
        self.assertEqual(len(clean_summary["artifact_sha256"]), 3)

        self.assertEqual(triage_run.returncode, 0)
        self.assertEqual(triage_run.stderr, "")
        self.assertEqual(triage_bundle, expected_triage_bundle)
        self.assertIsNone(triage_bundle["self_verify"])
        self.assertEqual(triage_bundle["batch_output_summary"], triage_summary)
        self.assertEqual(triage_bundle["self_compare"]["details"]["status"], "ok")
        self.assertEqual(
            triage_bundle["self_compare"]["details"]["compare_status"], "error"
        )
        self.assertEqual(
            list(triage_summary.keys()),
            ["mode", "layout", "run", "event_artifacts", "artifact_sha256", "summary"],
        )
        self.assertEqual(triage_summary["layout"], "by-status")
        self.assertEqual(triage_summary["run"]["id"], "threshold-ci-triage-001")
        self.assertEqual(len(triage_summary["artifact_sha256"]), 2)

    def test_fp_070_cli_eval_batch_output_self_compare_manifest_baseline_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_auto_dir = Path(tmp_dir) / "candidate-auto"
            candidate_explicit_dir = Path(tmp_dir) / "candidate-explicit"
            auto_compare_file = Path(tmp_dir) / "self-compare-auto.json"
            explicit_compare_file = Path(tmp_dir) / "self-compare-explicit.json"

            baseline = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(baseline_dir),
                    "--batch-output-manifest",
                    "--batch-output-run-id",
                    "baseline-001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            auto_manifest = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(candidate_auto_dir),
                    "--batch-output-run-id",
                    "candidate-auto-002",
                    "--batch-output-self-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-summary-file",
                    str(auto_compare_file),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            explicit_manifest = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(candidate_explicit_dir),
                    "--batch-output-manifest",
                    "--batch-output-run-id",
                    "candidate-explicit-003",
                    "--batch-output-self-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-summary-file",
                    str(explicit_compare_file),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            auto_summary = json.loads((candidate_auto_dir / "summary.json").read_text(encoding="utf-8"))
            explicit_summary = json.loads(
                (candidate_explicit_dir / "summary.json").read_text(encoding="utf-8")
            )
            auto_payload = json.loads(auto_compare_file.read_text(encoding="utf-8"))
            explicit_payload = json.loads(explicit_compare_file.read_text(encoding="utf-8"))

        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(baseline.stderr, "")
        self.assertEqual(auto_manifest.returncode, 0)
        self.assertEqual(auto_manifest.stderr, "")
        self.assertEqual(explicit_manifest.returncode, 0)
        self.assertEqual(explicit_manifest.stderr, "")
        self.assertEqual(auto_manifest.stdout, baseline.stdout)
        self.assertEqual(explicit_manifest.stdout, baseline.stdout)

        self.assertEqual(auto_summary["artifact_sha256"], baseline_summary["artifact_sha256"])
        self.assertEqual(explicit_summary["artifact_sha256"], baseline_summary["artifact_sha256"])
        self.assertEqual(auto_payload["status"], "ok")
        self.assertEqual(explicit_payload["status"], "ok")
        self.assertEqual(auto_payload["baseline_run_id"], "baseline-001")
        self.assertEqual(explicit_payload["baseline_run_id"], "baseline-001")
        self.assertEqual(auto_payload["candidate_run_id"], "candidate-auto-002")
        self.assertEqual(explicit_payload["candidate_run_id"], "candidate-explicit-003")
        self.assertEqual(auto_payload["metadata_mismatches"], [])
        self.assertEqual(explicit_payload["metadata_mismatches"], [])
        auto_payload_without_run = dict(auto_payload)
        explicit_payload_without_run = dict(explicit_payload)
        auto_payload_without_run.pop("candidate_run_id")
        explicit_payload_without_run.pop("candidate_run_id")
        self.assertEqual(auto_payload_without_run, explicit_payload_without_run)
        self.assertEqual(auto_summary["run"]["id"], "candidate-auto-002")
        self.assertEqual(explicit_summary["run"]["id"], "candidate-explicit-003")

    def test_fp_026_cli_eval_batch_output_summary_file_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            summary_file = Path(tmp_dir) / "batch-aggregate.json"

            baseline_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
            ]
            summary_file_args = [
                *baseline_args,
                "--batch-output-summary-file",
                str(summary_file),
            ]

            baseline = subprocess.run(
                baseline_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first = subprocess.run(
                summary_file_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            first_file = summary_file.read_text(encoding="utf-8")

            second = subprocess.run(
                summary_file_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second_file = summary_file.read_text(encoding="utf-8")

        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(baseline.stderr, "")

        self.assertEqual(first.returncode, 0)
        self.assertEqual(first.stderr, "")
        self.assertEqual(first.stdout, baseline.stdout)
        self.assertEqual(first_file, first.stdout)

        self.assertEqual(second.returncode, 0)
        self.assertEqual(second.stderr, "")
        self.assertEqual(second.stdout, baseline.stdout)
        self.assertEqual(second_file, second.stdout)

        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first_file, second_file)

    def test_fp_044_cli_eval_batch_output_compare_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(baseline_dir),
                    "--batch-output-run-id",
                    "baseline-001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            emit_candidate = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(candidate_dir),
                    "--batch-output-run-id",
                    "candidate-002",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_pass = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_pass_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            self.assertEqual(baseline_summary["run"]["id"], "baseline-001")
            self.assertEqual(candidate_summary["run"]["id"], "candidate-002")
            self.assertNotIn("artifact_sha256", baseline_summary)
            self.assertNotIn("artifact_sha256", candidate_summary)

            candidate_artifact = candidate_dir / candidate_summary["event_artifacts"][0]
            candidate_artifact.write_text(
                '{"event":"01-ok.json","actions":[{"kind":"notify","params":{"channel":"drift"}}],"trace":[]}\n',
                encoding="utf-8",
            )
            baseline_trace_count = baseline_summary["summary"]["trace_count"]
            candidate_summary["summary"]["trace_count"] = baseline_trace_count + 1
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            expected_changed_artifact = {
                "artifact": candidate_artifact.name,
                "baseline": hashlib.sha256((baseline_dir / candidate_artifact.name).read_bytes()).hexdigest(),
                "candidate": hashlib.sha256(candidate_artifact.read_bytes()).hexdigest(),
            }

            compare_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_candidate.returncode, 0)
        self.assertEqual(emit_candidate.stderr, "")

        self.assertEqual(compare_pass.returncode, 0)
        self.assertEqual(compare_pass.stderr, "")
        self.assertEqual(compare_pass_summary.returncode, 0)
        self.assertEqual(compare_pass_summary.stderr, "")
        self.assertEqual(
            compare_pass_summary.stdout,
            "status=ok compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=3 selected_candidate=3\n",
        )
        compare_pass_payload = json.loads(compare_pass.stdout)
        self.assertEqual(compare_pass_payload["status"], "ok")
        self.assertEqual(compare_pass_payload["compared"], 3)
        self.assertEqual(compare_pass_payload["matched"], 3)
        self.assertEqual(compare_pass_payload["metadata_mismatches"], [])
        self.assertEqual(compare_pass_payload["selected_baseline_artifacts_count"], 3)
        self.assertEqual(compare_pass_payload["selected_candidate_artifacts_count"], 3)

        self.assertEqual(compare_fail.returncode, 1)
        self.assertEqual(compare_fail.stderr, "")
        self.assertEqual(compare_fail_summary.returncode, 1)
        self.assertEqual(compare_fail_summary.stderr, "")
        self.assertEqual(
            compare_fail_summary.stdout,
            "status=error compared=3 matched=2 changed=1 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=3 selected_candidate=3\n",
        )
        compare_fail_payload = json.loads(compare_fail.stdout)
        self.assertEqual(compare_fail_payload["status"], "error")
        self.assertEqual(compare_fail_payload["selected_baseline_artifacts_count"], 3)
        self.assertEqual(compare_fail_payload["selected_candidate_artifacts_count"], 3)
        self.assertEqual(compare_fail_payload["changed_artifacts"], [expected_changed_artifact])
        self.assertEqual(
            compare_fail_payload["metadata_mismatches"],
            [
                {
                    "field": "summary.trace_count",
                    "baseline": baseline_trace_count,
                    "candidate": baseline_trace_count + 1,
                }
            ],
        )

    def test_fp_045_cli_eval_batch_output_compare_manifest_drift_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(baseline_dir),
                    "--batch-output-manifest",
                    "--batch-output-run-id",
                    "baseline-001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            emit_candidate = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(candidate_dir),
                    "--batch-output-manifest",
                    "--batch-output-run-id",
                    "candidate-002",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            manifest_artifact = sorted(candidate_summary["artifact_sha256"])[0]
            candidate_summary["artifact_sha256"][manifest_artifact] = "0" * 64
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_json = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_candidate.returncode, 0)
        self.assertEqual(emit_candidate.stderr, "")

        self.assertEqual(compare_json.returncode, 1)
        self.assertEqual(compare_json.stderr, "")
        self.assertEqual(compare_summary.returncode, 1)
        self.assertEqual(compare_summary.stderr, "")
        self.assertEqual(
            compare_summary.stdout,
            "status=error compared=3 matched=3 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=3 selected_candidate=3\n",
        )

        compare_payload = json.loads(compare_json.stdout)
        self.assertEqual(compare_payload["status"], "error")
        self.assertEqual(compare_payload["selected_baseline_artifacts_count"], 3)
        self.assertEqual(compare_payload["selected_candidate_artifacts_count"], 3)
        self.assertEqual(compare_payload["changed_artifacts"], [])
        self.assertEqual(
            compare_payload["metadata_mismatches"],
            [
                {
                    "field": "artifact_sha256",
                    "baseline": baseline_summary["artifact_sha256"],
                    "candidate": {
                        artifact: candidate_summary["artifact_sha256"][artifact]
                        for artifact in sorted(candidate_summary["artifact_sha256"])
                    },
                }
            ],
        )

    def test_fp_046_cli_eval_batch_output_compare_empty_artifact_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_dir = Path(tmp_dir) / "batch"
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"
            batch_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(EVAL_FIXTURES / "event-ok.json", batch_dir / "01-ok.json")

            emit_baseline = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(baseline_dir),
                    "--batch-output-errors-only",
                    "--batch-output-manifest",
                    "--batch-output-run-id",
                    "baseline-empty-001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            emit_candidate = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(candidate_dir),
                    "--batch-output-errors-only",
                    "--batch-output-manifest",
                    "--batch-output-run-id",
                    "candidate-empty-002",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_pass = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_pass_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            candidate_summary["summary"]["action_count"] = baseline_summary["summary"]["action_count"] + 1
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_fail_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_candidate.returncode, 0)
        self.assertEqual(emit_candidate.stderr, "")

        self.assertEqual(baseline_summary["event_artifacts"], [])
        self.assertEqual(baseline_summary["artifact_sha256"], {})
        self.assertEqual(compare_pass.returncode, 0)
        self.assertEqual(compare_pass.stderr, "")
        self.assertEqual(compare_pass_summary.returncode, 0)
        self.assertEqual(compare_pass_summary.stderr, "")
        self.assertEqual(
            compare_pass_summary.stdout,
            "status=ok compared=0 matched=0 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=0 selected_candidate=0\n",
        )
        compare_pass_payload = json.loads(compare_pass.stdout)
        self.assertEqual(compare_pass_payload["metadata_mismatches"], [])
        self.assertEqual(compare_pass_payload["selected_baseline_artifacts_count"], 0)
        self.assertEqual(compare_pass_payload["selected_candidate_artifacts_count"], 0)

        self.assertEqual(compare_fail.returncode, 1)
        self.assertEqual(compare_fail.stderr, "")
        self.assertEqual(compare_fail_summary.returncode, 1)
        self.assertEqual(compare_fail_summary.stderr, "")
        self.assertEqual(
            compare_fail_summary.stdout,
            "status=error compared=0 matched=0 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=0 selected_candidate=0\n",
        )
        self.assertEqual(
            json.loads(compare_fail.stdout)["metadata_mismatches"],
            [
                {
                    "field": "summary.action_count",
                    "baseline": baseline_summary["summary"]["action_count"],
                    "candidate": baseline_summary["summary"]["action_count"] + 1,
                }
            ],
        )

    def test_fp_047_cli_eval_batch_output_compare_scoped_selectors(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(baseline_dir),
                    "--batch-output-manifest",
                    "--batch-output-run-id",
                    "baseline-001",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            emit_candidate = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(candidate_dir),
                    "--batch-output-manifest",
                    "--batch-output-run-id",
                    "candidate-002",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            tampered_artifact = candidate_dir / "02-no-action.envelope.json"
            tampered_artifact.write_text(
                '{"event":"02-no-action.json","actions":[{"kind":"notify","params":{"channel":"drift"}}],"trace":[]}\n',
                encoding="utf-8",
            )
            candidate_summary["artifact_sha256"]["02-no-action.envelope.json"] = "0" * 64
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            full_compare = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            scoped_pass = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-include",
                    "01-ok.envelope.json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            scoped_pass_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-include",
                    "01-ok.envelope.json",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            scoped_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-include",
                    "02-no-action.envelope.json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            scoped_no_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-include",
                    "*does-not-exist*",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
            expected_scoped_fail_payload = {
                "status": "error",
                "baseline_run_id": "baseline-001",
                "candidate_run_id": "candidate-002",
                "compared": 1,
                "matched": 0,
                "baseline_only_artifacts": [],
                "candidate_only_artifacts": [],
                "missing_baseline_artifacts": [],
                "missing_candidate_artifacts": [],
                "selected_baseline_artifacts_count": 1,
                "selected_candidate_artifacts_count": 1,
                "changed_artifacts": [
                    {
                        "artifact": "02-no-action.envelope.json",
                        "baseline": hashlib.sha256(
                            (baseline_dir / "02-no-action.envelope.json").read_bytes()
                        ).hexdigest(),
                        "candidate": hashlib.sha256(tampered_artifact.read_bytes()).hexdigest(),
                    }
                ],
                "metadata_mismatches": [
                    {
                        "field": "artifact_sha256",
                        "baseline": {
                            "02-no-action.envelope.json": baseline_summary["artifact_sha256"][
                                "02-no-action.envelope.json"
                            ]
                        },
                        "candidate": {"02-no-action.envelope.json": "0" * 64},
                    }
                ],
            }

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_candidate.returncode, 0)
        self.assertEqual(emit_candidate.stderr, "")

        self.assertEqual(full_compare.returncode, 1)
        self.assertEqual(full_compare.stderr, "")
        self.assertEqual(
            full_compare.stdout,
            "status=error compared=3 matched=2 changed=1 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=1 selected_baseline=3 selected_candidate=3\n",
        )

        self.assertEqual(scoped_pass.returncode, 0)
        self.assertEqual(scoped_pass.stderr, "")
        self.assertEqual(scoped_pass_summary.returncode, 0)
        self.assertEqual(scoped_pass_summary.stderr, "")
        self.assertEqual(
            scoped_pass_summary.stdout,
            "status=ok compared=1 matched=1 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=1 selected_candidate=1\n",
        )
        scoped_pass_payload = json.loads(scoped_pass.stdout)
        self.assertEqual(scoped_pass_payload["baseline_run_id"], "baseline-001")
        self.assertEqual(scoped_pass_payload["candidate_run_id"], "candidate-002")
        self.assertEqual(scoped_pass_payload["metadata_mismatches"], [])
        self.assertEqual(scoped_pass_payload["selected_baseline_artifacts_count"], 1)
        self.assertEqual(scoped_pass_payload["selected_candidate_artifacts_count"], 1)

        self.assertEqual(scoped_fail.returncode, 1)
        self.assertEqual(scoped_fail.stderr, "")
        self.assertEqual(json.loads(scoped_fail.stdout), expected_scoped_fail_payload)

        self.assertEqual(scoped_no_match.returncode, 1)
        self.assertEqual(scoped_no_match.stdout, "")
        self.assertEqual(
            scoped_no_match.stderr,
            "error: --batch-output-compare selectors matched no artifacts (include='*does-not-exist*', exclude='<none>')\n",
        )

    def test_fp_053_cli_eval_batch_output_compare_strict_extended_drift_selectors(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(baseline_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            emit_candidate = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(candidate_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            baseline_summary_path = baseline_dir / "summary.json"
            baseline_summary = json.loads(baseline_summary_path.read_text(encoding="utf-8"))
            baseline_summary["event_artifacts"].append("ghost-baseline.envelope.json")
            baseline_summary_path.write_text(
                f"{json.dumps(baseline_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            candidate_summary["event_artifacts"].append("ghost-candidate.envelope.json")
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_json = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-strict",
                    "--batch-output-compare-expected-status",
                    "error",
                    "--batch-output-compare-expected-compared-count",
                    "3",
                    "--batch-output-compare-expected-matched-count",
                    "3",
                    "--batch-output-compare-expected-changed-count",
                    "0",
                    "--batch-output-compare-expected-baseline-only-count",
                    "1",
                    "--batch-output-compare-expected-candidate-only-count",
                    "1",
                    "--batch-output-compare-expected-missing-baseline-count",
                    "1",
                    "--batch-output-compare-expected-missing-candidate-count",
                    "1",
                    "--batch-output-compare-expected-metadata-mismatches-count",
                    "1",
                    "--batch-output-compare-expected-selected-baseline-count",
                    "4",
                    "--batch-output-compare-expected-selected-candidate-count",
                    "4",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-strict",
                    "--batch-output-compare-expected-status",
                    "error",
                    "--batch-output-compare-expected-compared-count",
                    "3",
                    "--batch-output-compare-expected-matched-count",
                    "3",
                    "--batch-output-compare-expected-changed-count",
                    "0",
                    "--batch-output-compare-expected-baseline-only-count",
                    "1",
                    "--batch-output-compare-expected-candidate-only-count",
                    "1",
                    "--batch-output-compare-expected-missing-baseline-count",
                    "1",
                    "--batch-output-compare-expected-missing-candidate-count",
                    "1",
                    "--batch-output-compare-expected-metadata-mismatches-count",
                    "1",
                    "--batch-output-compare-expected-selected-baseline-count",
                    "4",
                    "--batch-output-compare-expected-selected-candidate-count",
                    "4",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_candidate.returncode, 0)
        self.assertEqual(emit_candidate.stderr, "")

        self.assertEqual(compare_json.returncode, 0)
        self.assertEqual(compare_json.stderr, "")
        self.assertEqual(compare_summary.returncode, 0)
        self.assertEqual(compare_summary.stderr, "")
        self.assertEqual(
            compare_summary.stdout,
            "status=ok compare_status=error compared=3 matched=3 changed=0 baseline_only=1 candidate_only=1 missing_baseline=1 missing_candidate=1 metadata_mismatches=1 selected_baseline=4 selected_candidate=4 strict_mismatches=0\n",
        )

        self.assertEqual(
            json.loads(compare_json.stdout),
            {
                "status": "ok",
                "compare_status": "error",
                "compared": 3,
                "matched": 3,
                "baseline_only_artifacts": ["ghost-baseline.envelope.json"],
                "candidate_only_artifacts": ["ghost-candidate.envelope.json"],
                "missing_baseline_artifacts": ["ghost-baseline.envelope.json"],
                "missing_candidate_artifacts": ["ghost-candidate.envelope.json"],
                "changed_artifacts": [],
                "metadata_mismatches": [
                    {
                        "field": "event_artifacts",
                        "baseline": baseline_summary["event_artifacts"],
                        "candidate": candidate_summary["event_artifacts"],
                    }
                ],
                "selected_baseline_artifacts_count": 4,
                "selected_candidate_artifacts_count": 4,
                "strict_profile": {
                    "expected_status": "error",
                    "expected_compared_count": 3,
                    "expected_matched_count": 3,
                    "expected_changed_count": 0,
                    "expected_baseline_only_count": 1,
                    "expected_candidate_only_count": 1,
                    "expected_missing_baseline_count": 1,
                    "expected_missing_candidate_count": 1,
                    "expected_metadata_mismatches_count": 1,
                    "expected_selected_baseline_count": 4,
                    "expected_selected_candidate_count": 4,
                },
                "strict_profile_mismatches": [],
            },
        )

    def test_fp_053a_cli_eval_batch_output_compare_strict_action_plan_and_resolved_ref_counts(
        self,
    ) -> None:
        batch_dir = EVAL_FIXTURES / "batch-index.json"

        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--exclude",
                    "*invalid*.json",
                    "--action-plan",
                    "--batch-output",
                    str(baseline_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            emit_candidate = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--exclude",
                    "*invalid*.json",
                    "--action-plan",
                    "--batch-output",
                    str(candidate_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_json = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-strict",
                    "--batch-output-compare-expected-status",
                    "ok",
                    "--batch-output-compare-expected-compared-count",
                    "2",
                    "--batch-output-compare-expected-matched-count",
                    "2",
                    "--batch-output-compare-expected-changed-count",
                    "0",
                    "--batch-output-compare-expected-metadata-mismatches-count",
                    "0",
                    "--batch-output-compare-expected-selected-baseline-count",
                    "2",
                    "--batch-output-compare-expected-selected-candidate-count",
                    "2",
                    "--batch-output-compare-expected-baseline-action-plan-count",
                    "1",
                    "--batch-output-compare-expected-candidate-action-plan-count",
                    "1",
                    "--batch-output-compare-expected-baseline-resolved-refs-count",
                    "1",
                    "--batch-output-compare-expected-candidate-resolved-refs-count",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-strict",
                    "--batch-output-compare-expected-status",
                    "ok",
                    "--batch-output-compare-expected-compared-count",
                    "2",
                    "--batch-output-compare-expected-matched-count",
                    "2",
                    "--batch-output-compare-expected-changed-count",
                    "0",
                    "--batch-output-compare-expected-metadata-mismatches-count",
                    "0",
                    "--batch-output-compare-expected-selected-baseline-count",
                    "2",
                    "--batch-output-compare-expected-selected-candidate-count",
                    "2",
                    "--batch-output-compare-expected-baseline-action-plan-count",
                    "1",
                    "--batch-output-compare-expected-candidate-action-plan-count",
                    "1",
                    "--batch-output-compare-expected-baseline-resolved-refs-count",
                    "1",
                    "--batch-output-compare-expected-candidate-resolved-refs-count",
                    "1",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_candidate.returncode, 0)
        self.assertEqual(emit_candidate.stderr, "")
        self.assertEqual(compare_json.returncode, 0)
        self.assertEqual(compare_json.stderr, "")
        self.assertEqual(compare_summary.returncode, 0)
        self.assertEqual(compare_summary.stderr, "")
        self.assertEqual(
            compare_summary.stdout,
            "status=ok compare_status=ok compared=2 matched=2 changed=0 baseline_only=0 candidate_only=0 missing_baseline=0 missing_candidate=0 metadata_mismatches=0 selected_baseline=2 selected_candidate=2 baseline_plan=1 candidate_plan=1 baseline_resolved_refs=1 candidate_resolved_refs=1 strict_mismatches=0\n",
        )
        self.assertEqual(
            json.loads(compare_json.stdout),
            {
                "status": "ok",
                "compare_status": "ok",
                "compared": 2,
                "matched": 2,
                "baseline_only_artifacts": [],
                "candidate_only_artifacts": [],
                "missing_baseline_artifacts": [],
                "missing_candidate_artifacts": [],
                "changed_artifacts": [],
                "metadata_mismatches": [],
                "selected_baseline_artifacts_count": 2,
                "selected_candidate_artifacts_count": 2,
                "baseline_action_plan_count": 1,
                "candidate_action_plan_count": 1,
                "baseline_resolved_ref_count": 1,
                "candidate_resolved_ref_count": 1,
                "strict_profile": {
                    "expected_status": "ok",
                    "expected_compared_count": 2,
                    "expected_matched_count": 2,
                    "expected_changed_count": 0,
                    "expected_metadata_mismatches_count": 0,
                    "expected_baseline_action_plan_count": 1,
                    "expected_candidate_action_plan_count": 1,
                    "expected_baseline_resolved_refs_count": 1,
                    "expected_candidate_resolved_refs_count": 1,
                    "expected_selected_baseline_count": 2,
                    "expected_selected_candidate_count": 2,
                },
                "strict_profile_mismatches": [],
            },
        )

    def test_fp_054_cli_eval_batch_output_compare_strict_profile_expected_asymmetric_drift(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_dir = Path(tmp_dir) / "baseline"
            candidate_dir = Path(tmp_dir) / "candidate"

            emit_baseline = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(baseline_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            emit_candidate = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(candidate_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            baseline_summary_path = baseline_dir / "summary.json"
            baseline_summary = json.loads(baseline_summary_path.read_text(encoding="utf-8"))
            baseline_summary["event_artifacts"].append("ghost-baseline.envelope.json")
            baseline_summary_path.write_text(
                f"{json.dumps(baseline_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            candidate_summary_path = candidate_dir / "summary.json"
            candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
            candidate_summary["event_artifacts"].append("ghost-candidate.envelope.json")
            candidate_summary_path.write_text(
                f"{json.dumps(candidate_summary, separators=(',', ':'), ensure_ascii=False)}\n",
                encoding="utf-8",
            )

            compare_json = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-strict",
                    "--batch-output-compare-profile",
                    "expected-asymmetric-drift",
                    "--batch-output-compare-expected-compared-count",
                    "3",
                    "--batch-output-compare-expected-matched-count",
                    "3",
                    "--batch-output-compare-expected-baseline-only-count",
                    "1",
                    "--batch-output-compare-expected-candidate-only-count",
                    "1",
                    "--batch-output-compare-expected-missing-baseline-count",
                    "1",
                    "--batch-output-compare-expected-missing-candidate-count",
                    "1",
                    "--batch-output-compare-expected-metadata-mismatches-count",
                    "1",
                    "--batch-output-compare-expected-selected-baseline-count",
                    "4",
                    "--batch-output-compare-expected-selected-candidate-count",
                    "4",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            compare_summary = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-compare",
                    str(candidate_dir),
                    "--batch-output-compare-against",
                    str(baseline_dir),
                    "--batch-output-compare-strict",
                    "--batch-output-compare-profile",
                    "expected-asymmetric-drift",
                    "--batch-output-compare-expected-compared-count",
                    "3",
                    "--batch-output-compare-expected-matched-count",
                    "3",
                    "--batch-output-compare-expected-baseline-only-count",
                    "1",
                    "--batch-output-compare-expected-candidate-only-count",
                    "1",
                    "--batch-output-compare-expected-missing-baseline-count",
                    "1",
                    "--batch-output-compare-expected-missing-candidate-count",
                    "1",
                    "--batch-output-compare-expected-metadata-mismatches-count",
                    "1",
                    "--batch-output-compare-expected-selected-baseline-count",
                    "4",
                    "--batch-output-compare-expected-selected-candidate-count",
                    "4",
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit_baseline.returncode, 0)
        self.assertEqual(emit_baseline.stderr, "")
        self.assertEqual(emit_candidate.returncode, 0)
        self.assertEqual(emit_candidate.stderr, "")

        self.assertEqual(compare_json.returncode, 0)
        self.assertEqual(compare_json.stderr, "")
        self.assertEqual(compare_summary.returncode, 0)
        self.assertEqual(compare_summary.stderr, "")
        self.assertEqual(
            compare_summary.stdout,
            "status=ok compare_status=error compared=3 matched=3 changed=0 baseline_only=1 candidate_only=1 missing_baseline=1 missing_candidate=1 metadata_mismatches=1 selected_baseline=4 selected_candidate=4 strict_mismatches=0\n",
        )

        self.assertEqual(
            json.loads(compare_json.stdout),
            {
                "status": "ok",
                "compare_status": "error",
                "compared": 3,
                "matched": 3,
                "baseline_only_artifacts": ["ghost-baseline.envelope.json"],
                "candidate_only_artifacts": ["ghost-candidate.envelope.json"],
                "missing_baseline_artifacts": ["ghost-baseline.envelope.json"],
                "missing_candidate_artifacts": ["ghost-candidate.envelope.json"],
                "changed_artifacts": [],
                "metadata_mismatches": [
                    {
                        "field": "event_artifacts",
                        "baseline": baseline_summary["event_artifacts"],
                        "candidate": candidate_summary["event_artifacts"],
                    }
                ],
                "selected_baseline_artifacts_count": 4,
                "selected_candidate_artifacts_count": 4,
                "strict_profile": {
                    "expected_status": "error",
                    "expected_changed_count": 0,
                    "expected_compared_count": 3,
                    "expected_matched_count": 3,
                    "expected_baseline_only_count": 1,
                    "expected_candidate_only_count": 1,
                    "expected_missing_baseline_count": 1,
                    "expected_missing_candidate_count": 1,
                    "expected_metadata_mismatches_count": 1,
                    "expected_selected_baseline_count": 4,
                    "expected_selected_candidate_count": 4,
                },
                "strict_profile_mismatches": [],
            },
        )

    def test_fp_027_cli_eval_batch_output_verify_summary_file_contract(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"
            verify_json_file = Path(tmp_dir) / "verify-pass.json"
            verify_summary_file = Path(tmp_dir) / "verify-pass-summary.txt"
            verify_fail_file = Path(tmp_dir) / "verify-fail-summary.txt"

            emit_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                str(EVAL_FIXTURES / "program.erz"),
                "--batch",
                str(batch_dir),
                "--batch-output",
                str(output_dir),
                "--batch-output-manifest",
            ]
            verify_json_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--batch-output-verify-summary-file",
                str(verify_json_file),
            ]
            verify_summary_args = [
                "python3",
                "-m",
                "cli.main",
                "eval",
                "--batch-output-verify",
                str(output_dir),
                "--summary",
                "--batch-output-verify-summary-file",
                str(verify_summary_file),
            ]

            emit = subprocess.run(
                emit_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verify_json = subprocess.run(
                verify_json_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verify_summary = subprocess.run(
                verify_summary_args,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            tampered_artifact = output_dir / summary_payload["event_artifacts"][0]
            tampered_artifact.write_text('{"tampered":true}\n', encoding="utf-8")

            verify_fail = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--summary",
                    "--batch-output-verify-summary-file",
                    str(verify_fail_file),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            verify_json_file_contents = verify_json_file.read_text(encoding="utf-8")
            verify_summary_file_contents = verify_summary_file.read_text(encoding="utf-8")
            verify_fail_file_contents = verify_fail_file.read_text(encoding="utf-8")

        self.assertEqual(emit.returncode, 0)
        self.assertEqual(emit.stderr, "")

        self.assertEqual(verify_json.returncode, 0)
        self.assertEqual(verify_json.stderr, "")
        self.assertEqual(verify_json_file_contents, verify_json.stdout)

        self.assertEqual(verify_summary.returncode, 0)
        self.assertEqual(verify_summary.stderr, "")
        self.assertEqual(
            verify_summary.stdout,
            "status=ok checked=3 verified=3 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=3 selected_manifest=3\n",
        )
        self.assertEqual(verify_summary_file_contents, verify_summary.stdout)

        self.assertEqual(verify_fail.returncode, 1)
        self.assertEqual(verify_fail.stderr, "")
        self.assertIn("status=error", verify_fail.stdout)
        self.assertEqual(verify_fail_file_contents, verify_fail.stdout)

    def test_fp_028_cli_eval_batch_output_verify_subset_selectors(self) -> None:
        batch_dir = EVAL_FIXTURES / "batch"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "batch-output"

            emit = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    str(EVAL_FIXTURES / "program.erz"),
                    "--batch",
                    str(batch_dir),
                    "--batch-output",
                    str(output_dir),
                    "--batch-output-manifest",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            invalid_artifact = next(
                artifact for artifact in summary_payload["event_artifacts"] if "invalid" in artifact
            )
            (output_dir / invalid_artifact).write_text('{"tampered":true}\n', encoding="utf-8")

            verify_subset_ok = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--summary",
                    "--batch-output-verify-include",
                    "*ok*",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verify_subset_excluding_invalid = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--summary",
                    "--batch-output-verify-include",
                    "*.envelope.json",
                    "--batch-output-verify-exclude",
                    "*invalid*",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verify_full = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--summary",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verify_no_match = subprocess.run(
                [
                    "python3",
                    "-m",
                    "cli.main",
                    "eval",
                    "--batch-output-verify",
                    str(output_dir),
                    "--batch-output-verify-include",
                    "*does-not-exist*",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(emit.returncode, 0)
        self.assertEqual(emit.stderr, "")

        self.assertEqual(verify_subset_ok.returncode, 0)
        self.assertEqual(verify_subset_ok.stderr, "")
        self.assertEqual(
            verify_subset_ok.stdout,
            "status=ok checked=1 verified=1 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=1 selected_manifest=1\n",
        )

        self.assertEqual(verify_subset_excluding_invalid.returncode, 0)
        self.assertEqual(verify_subset_excluding_invalid.stderr, "")
        self.assertEqual(
            verify_subset_excluding_invalid.stdout,
            "status=ok checked=2 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=0 unexpected_manifest=0 selected=2 selected_manifest=2\n",
        )

        self.assertEqual(verify_full.returncode, 1)
        self.assertEqual(verify_full.stderr, "")
        self.assertEqual(
            verify_full.stdout,
            "status=error checked=3 verified=2 missing=0 manifest_missing=0 invalid_hashes=0 mismatched=1 unexpected_manifest=0 selected=3 selected_manifest=3\n",
        )

        self.assertEqual(verify_no_match.returncode, 1)
        self.assertEqual(verify_no_match.stdout, "")
        self.assertEqual(
            verify_no_match.stderr,
            "error: --batch-output-verify selectors matched no artifacts (include='*does-not-exist*', exclude='<none>')\n",
        )

    def _extract_section_lines(self, *, text: str, heading: str, doc_name: str) -> list[str]:
        lines = text.splitlines()
        self.assertEqual(
            lines.count(heading),
            1,
            f"{doc_name}: expected exactly one heading: {heading}",
        )

        section_start = lines.index(heading) + 1
        section_end = len(lines)
        for index in range(section_start, len(lines)):
            if lines[index].startswith("## ") or lines[index].startswith("### "):
                section_end = index
                break

        return lines[section_start:section_end]

    def _read_error_snapshot(self, name: str) -> str:
        return (ERROR_FIXTURES / name).read_text(encoding="utf-8")

    def _assert_error_snapshot(
        self,
        *,
        envelope: dict[str, object],
        snapshot_name: str,
        expect_span_position: int | None,
    ) -> None:
        self.assertEqual(list(envelope.keys()), list(ERROR_ENVELOPE_FIELD_ORDER))
        self.assertEqual(list(envelope["details"].keys()), ["error_type", "command"])

        if expect_span_position is None:
            self.assertIsNone(envelope["span"])
        else:
            self.assertIsInstance(envelope["span"], dict)
            self.assertEqual(list(envelope["span"].keys()), ["position"])
            self.assertEqual(envelope["span"]["position"], expect_span_position)

        rendered = render_error_envelope_json(envelope) + "\n"
        self.assertEqual(rendered, self._read_error_snapshot(snapshot_name))

    def _parse_anchor_tokens(self, *, text: str, prefix: str, doc_name: str) -> list[str]:
        for line in text.splitlines():
            if line.startswith(prefix):
                tokens = re.findall(r"`([^`]+)`", line)
                self.assertTrue(tokens, f"{doc_name}: anchor line has no backticked tokens: {prefix}")
                return tokens

        self.fail(f"{doc_name}: missing required anchor line: {prefix}")


if __name__ == "__main__":
    unittest.main()
