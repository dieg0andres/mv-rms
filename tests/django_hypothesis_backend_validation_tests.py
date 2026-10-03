from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from rms.hypothesis_validation import (
    HypothesisValidationError,
    SCHEMA,
    SCHEMA_PATH,
    SCHEMA_SHA256,
    draft_completeness,
    validate_request,
)


UUID = "00000000-0000-4000-8000-000000000145"


def create_payload():
    return {
        "originating_idea_version_id": f"IDEV-{UUID}",
        "origin_rationale": "Invented origin, not research evidence.",
        "investigation_version_id": f"INVV-{UUID}",
        "idea_family_binding": {"mode": "existing", "association_version_id": f"IFAV-{UUID}"},
        "fields": {"title": "Invented draft"},
    }


def complete_fields():
    fields = {name: "Invented description only." for name in SCHEMA["$defs"]["HypothesisFields"]["properties"]}
    fields.update({
        "claim_basis": "gross_return", "market": "etfs", "direction": "long",
        "sizing_method": "equity_fraction",
        "effect_horizon": {"kind": "fixed", "quantity": "1", "unit": "trading_sessions", "start_anchor": "Invented open", "counting_convention": "Entry session counts", "calendar": "Invented calendar"},
        "maximum_holding_period": {"kind": "fixed", "quantity": "2.5", "unit": "hours", "start_anchor": "Invented fill", "counting_convention": "Elapsed hours"},
    })
    return fields


def assessment():
    return {
        "query_scope": "Invented records, none available in bounded scope.",
        "query_time": "2026-10-03T07:00:00Z",
        "policy_version": SCHEMA["$defs"]["AssessmentFields"]["properties"]["policy_version"]["const"],
        "result_watermark": "Invented empty review boundary.",
        "finding": "no_relevant_work_found", "rationale": "Invented rationale.",
        "limitations": "No real research reviewed.", "record_links": [],
    }


def case_payload():
    return {
        "family_version_id": f"RFAMV-{UUID}",
        "fields": {"title": "Invented case", "owner_role": "Research", "priority": "normal", "next_action": "Review invented draft"},
        "prior_research_assessment": assessment(),
    }


class SchemaContractTests(unittest.TestCase):
    def test_schema_identity_and_all_local_refs_resolve(self):
        self.assertEqual(SCHEMA_SHA256, hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest())
        self.assertEqual(SCHEMA["x-schema-version"], "1.0")
        self.assertEqual(SCHEMA["x-interface-version"], "1.2")
        self.assertEqual(len(SCHEMA["x-endpoints"]), 26)

        def walk(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    self.assertIn(value["$ref"].removeprefix("#/$defs/"), SCHEMA["$defs"])
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(SCHEMA)
        for endpoint in SCHEMA["x-endpoints"]:
            for key in ("request", "response", "query"):
                if key in endpoint:
                    self.assertIn(endpoint[key], SCHEMA["$defs"])

    def test_full_snapshot_has_every_named_field(self):
        required = SCHEMA["$defs"]["FullHypothesisFields"]["allOf"][1]["required"]
        self.assertEqual(set(required), set(SCHEMA["$defs"]["HypothesisFields"]["properties"]))
        self.assertNotIn("horizon", required)
        self.assertNotIn("sizing", required)

    def test_pure_module_does_not_import_django_or_database_drivers(self):
        import ast

        tree = ast.parse(Path("rms/hypothesis_validation.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        self.assertFalse(any(name.startswith(("django", "psycopg", "rms.services", "rms.models")) for name in imports))


class ValidationAssertions(unittest.TestCase):
    def assert_invalid(self, payload, path, name="HypothesisCreate"):
        original = deepcopy(payload)
        with self.assertRaises(HypothesisValidationError) as raised:
            validate_request(name, payload)
        self.assertIn(path, [issue["path"] for issue in raised.exception.issues])
        self.assertEqual(payload, original)
        self.assertEqual(raised.exception.code, "validation_error")


class HypothesisValidationTests(ValidationAssertions):
    def test_incomplete_create_expands_nulls_without_mutating_input(self):
        payload = create_payload()
        original = deepcopy(payload)
        normalized = validate_request("HypothesisCreate", payload)
        self.assertEqual(payload, original)
        self.assertIsNone(normalized["fields"]["direction"])
        result = draft_completeness(normalized["fields"])
        self.assertEqual(result["draft_completeness"], "incomplete")
        self.assertEqual(result["missing_fields"][0]["path"], "/fields/claim")
        self.assertNotIn("status", result)

    def test_complete_is_not_workflow_or_research_approval(self):
        fields = complete_fields()
        original = deepcopy(fields)
        result = draft_completeness(fields)
        self.assertEqual(result, {"schema_version": "1.0", "draft_completeness": "complete", "missing_fields": []})
        self.assertEqual(fields, original)

    def test_each_enum_invalid_even_in_incomplete_draft(self):
        for key in ("market", "direction", "claim_basis", "sizing_method"):
            with self.subTest(key=key):
                payload = create_payload()
                payload["fields"][key] = "invented-invalid-choice"
                self.assert_invalid(payload, f"/fields/{key}")

    def test_server_owned_or_unknown_fields_cannot_be_forged(self):
        for key in ("status", "classification", "created_by", "row_digest", "authority_reference"):
            payload = create_payload()
            payload[key] = "forged"
            self.assert_invalid(payload, f"/{key}")
        payload = create_payload()
        payload["fields"]["unknown/~"] = "invented"
        self.assert_invalid(payload, "/fields/unknown~1~0")

    def test_required_text_blank_and_lengths(self):
        for value in (None, "", " \n ", "x" * 501):
            payload = create_payload()
            payload["fields"]["title"] = value
            self.assert_invalid(payload, "/fields/title")
        payload = create_payload()
        payload["fields"].update({"title": "  Invented  ", "claim": " \n "})
        result = validate_request("HypothesisCreate", payload)
        self.assertEqual(result["fields"]["title"], "Invented")
        self.assertIsNone(result["fields"]["claim"])
        for name, size in (("claim", 4000), ("decision_schedule", 2000), ("intended_benchmark_name", 500)):
            payload = create_payload()
            payload["fields"][name] = "x" * (size + 1)
            self.assert_invalid(payload, f"/fields/{name}")

    def test_duration_decimal_wrong_type_nonfinite_or_nonpositive(self):
        for value in (0, 1.5, True, "0", "-1", "0.00", "NaN", "Infinity", "1e3", "1\n", "", [], {}):
            with self.subTest(value=value):
                payload = create_payload()
                payload["fields"]["effect_horizon"] = {"kind": "fixed", "quantity": value}
                self.assert_invalid(payload, "/fields/effect_horizon/quantity")
        for value in (".1", "0.25", "2", "001.50"):
            payload = create_payload()
            payload["fields"]["effect_horizon"] = {"kind": "fixed", "quantity": value}
            self.assertEqual(validate_request("HypothesisCreate", payload)["fields"]["effect_horizon"]["quantity"], value)

    def test_incompatible_duration_fields_require_explicit_clear(self):
        payload = create_payload()
        payload["fields"]["effect_horizon"] = {"kind": "event_based", "quantity": "1", "event_condition": "Invented event"}
        self.assert_invalid(payload, "/fields/effect_horizon/quantity")
        payload["fields"]["effect_horizon"]["quantity"] = None
        validate_request("HypothesisCreate", payload)
        payload["fields"]["effect_horizon"] = {"quantity": "1", "event_condition": "Invented event"}
        self.assert_invalid(payload, "/fields/effect_horizon/quantity")

    def test_duration_missing_paths_and_partial_calendar(self):
        fields = complete_fields()
        del fields["effect_horizon"]["calendar"]
        self.assertEqual(draft_completeness(fields)["missing_fields"][0]["path"], "/fields/effect_horizon/calendar")
        fields["effect_horizon"] = {"kind": "fixed", "calendar": "Invented calendar"}
        paths = [issue["path"] for issue in draft_completeness(fields)["missing_fields"]]
        self.assertIn("/fields/effect_horizon/unit", paths)
        fields["effect_horizon"]["unit"] = "bars"
        with self.assertRaises(HypothesisValidationError):
            draft_completeness(fields)

    def test_no_limit_and_event_nonoccurrence_are_explicit(self):
        fields = complete_fields()
        fields["maximum_holding_period"] = {"kind": "no_fixed_time_limit"}
        self.assertEqual(draft_completeness(fields)["missing_fields"][0]["path"], "/fields/maximum_holding_period/rationale")
        fields["maximum_holding_period"]["rationale"] = "Invented open-ended risk acknowledgement"
        self.assertEqual(draft_completeness(fields)["draft_completeness"], "complete")
        fields["maximum_holding_period"] = {"kind": "event_based", "event_condition": "Invented event", "start_anchor": "Invented fill"}
        self.assertEqual(draft_completeness(fields)["missing_fields"][0]["path"], "/fields/maximum_holding_period/if_event_never_occurs")

    def test_malformed_json_shapes_fail_without_crashing(self):
        for value in (None, [], "text", True, 1):
            with self.assertRaises(HypothesisValidationError):
                validate_request("HypothesisCreate", value)
        for value in ([], {}, 1, True, "unknown"):
            payload = create_payload()
            payload["fields"]["effect_horizon"] = {"kind": value}
            self.assert_invalid(payload, "/fields/effect_horizon/kind")

    def test_origin_binding_is_explicit_and_references_are_only_shape_checked(self):
        payload = create_payload()
        payload["idea_family_binding"] = {"mode": "create", "family_version_id": f"RFAMV-{UUID}", "rationale": "Invented grouping confirmation"}
        validate_request("HypothesisCreate", payload)
        payload["idea_family_binding"]["rationale"] = " "
        self.assert_invalid(payload, "/idea_family_binding/rationale")
        for value in ("IDE-latest", f"IDEV-{UUID}\n", f"INVV-{UUID}"):
            payload = create_payload()
            payload["originating_idea_version_id"] = value
            self.assert_invalid(payload, "/originating_idea_version_id")

    def test_correction_is_full_snapshot_reason_and_expected_version(self):
        payload = create_payload()
        payload.update({"expected_latest_version": 1, "correction_reason": "Invented correction"})
        self.assert_invalid(payload, "/fields/claim", "HypothesisCorrection")
        payload["fields"] = validate_request("HypothesisCreate", create_payload())["fields"]
        validate_request("HypothesisCorrection", payload)
        for value in (True, 0, -1, "1"):
            payload["expected_latest_version"] = value
            self.assert_invalid(payload, "/expected_latest_version", "HypothesisCorrection")

    def test_pagination_bounded_and_error_values_not_echoed(self):
        self.assertEqual(validate_request("ListQuery", {}), {"page": 1, "page_size": 25})
        for value in (0, 101, True, "25"):
            self.assert_invalid({"page_size": value}, "/page_size", "ListQuery")
        payload = create_payload()
        payload["fields"]["direction"] = "invented-sensitive-marker"
        with self.assertRaises(HypothesisValidationError) as raised:
            validate_request("HypothesisCreate", payload)
        self.assertNotIn("invented-sensitive-marker", json.dumps(raised.exception.issues))


class ContextValidationTests(ValidationAssertions):
    def test_case_requires_truthful_explicit_assessment(self):
        payload = case_payload()
        validate_request("InvestigationCreate", payload)
        for key in assessment():
            changed = deepcopy(payload)
            del changed["prior_research_assessment"][key]
            self.assert_invalid(changed, f"/prior_research_assessment/{key}", "InvestigationCreate")
        for value in ("2026-02-30T07:00:00Z", "2026-10-03T07:00:00", "2026-10-03T07:00:00+01:00"):
            payload["prior_research_assessment"]["query_time"] = value
            self.assert_invalid(payload, "/prior_research_assessment/query_time", "InvestigationCreate")

    def test_context_corrections_keep_assessment_binding_explicit(self):
        payload = case_payload()
        payload.update({"expected_latest_version": 1, "correction_reason": "Invented case correction"})
        payload["fields"]["blocker_text"] = None
        payload["prior_research_assessment"] = {"mode": "existing", "assessment_version_id": f"PRAV-{UUID}"}
        validate_request("InvestigationCorrection", payload)
        payload["prior_research_assessment"] = {"mode": "correct", "corrects_assessment_version_id": f"PRAV-{UUID}", "expected_latest_assessment_version": 1, "correction_reason": "Invented assessment correction", "fields": assessment()}
        validate_request("InvestigationCorrection", payload)

    def test_links_cannot_fabricate_future_types_or_mismatch_endpoint_kind(self):
        payload = case_payload()
        payload["prior_research_assessment"]["record_links"] = [{"kind": "idea", "version_id": f"SRCV-{UUID}"}]
        self.assert_invalid(payload, "/prior_research_assessment/record_links/0/version_id", "InvestigationCreate")
        payload["prior_research_assessment"]["record_links"] = [{"kind": "test_plan", "version_id": f"TPV-{UUID}"}]
        with self.assertRaises(HypothesisValidationError):
            validate_request("InvestigationCreate", payload)

    def test_family_and_association_corrections_require_expected_versions(self):
        family = {"fields": {"name": "Invented family", "mechanism_boundary": "Invented mechanism", "distinctness_rule": "Invented boundary"}}
        validate_request("FamilyCreate", family)
        family.update({"expected_latest_version": 1, "correction_reason": "Invented reason"})
        self.assert_invalid(family, "/fields/risk_review_reference", "FamilyCorrection")
        family["fields"]["risk_review_reference"] = None
        validate_request("FamilyCorrection", family)
        binding = {"prior_association_version_id": f"IFAV-{UUID}", "family_version_id": f"RFAMV-{UUID}", "rationale": "Invented reclassification", "expected_latest_version": 1, "correction_reason": "Invented reason"}
        validate_request("IdeaFamilyCorrection", binding)


if __name__ == "__main__":
    unittest.main()
