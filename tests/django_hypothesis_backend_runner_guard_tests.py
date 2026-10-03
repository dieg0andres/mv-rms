import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import unittest

from rms.hypothesis_preserving_runner import (
    FORBIDDEN,
    MANIFEST,
    assess_prerequisites,
)


NOW = datetime(2026, 10, 3, 8, tzinfo=timezone.utc)


class PreservingGuardTests(unittest.TestCase):
    def codes(self, receipts=None, manifest=MANIFEST):
        report = assess_prerequisites(receipts, now=NOW, manifest=manifest)
        self.assertEqual(report.disposition, "HOLD")
        self.assertIs(report.db_access_permitted, False)
        self.assertTrue(all(finding.owner and finding.action for finding in report.findings))
        return {finding.code for finding in report.findings}

    def invented_identity(self):
        return {
            **deepcopy(MANIFEST["lifecycle_policy"]),
            "synthetic": True,
            "evidence_ref": "invented-negative-only",
            "proposal_id": MANIFEST["proposal_id"],
            "revision": MANIFEST["revision"],
            "candidate_commit": "1" * 40,
            "file_sha256": {
                path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                for path in (
                    "rms/hypothesis_runner_manifest.json",
                    "rms/hypothesis_preserving_runner.py",
                    "docs/RMS-HN-BACKEND-RUNNER.md",
                )
            },
        }

    def test_missing_and_nonobject_manifests_return_owned_hold(self):
        for manifest in (None, [], "invented", 3, False):
            with self.subTest(manifest=manifest):
                self.assertIn("invalid_manifest", self.codes(manifest=manifest))
        codes = self.codes(manifest={})
        self.assertIn("invalid_receipts", codes)
        self.assertIn("invalid_target", codes)
        self.assertIn("source_only_execution_hold", codes)

    def test_missing_and_nonobject_required_receipts_return_owned_hold(self):
        for value in (None, [], "invented", 3):
            manifest = deepcopy(MANIFEST)
            manifest["required_receipts"] = value
            with self.subTest(value=value):
                self.assertIn("invalid_receipts", self.codes(manifest=manifest))
        manifest.pop("required_receipts")
        self.assertIn("invalid_receipts", self.codes(manifest=manifest))

    def test_missing_and_nonobject_targets_return_owned_hold(self):
        for value in (None, [], "invented", 3, False):
            manifest = deepcopy(MANIFEST)
            manifest["target"] = value
            with self.subTest(value=value):
                codes = self.codes(manifest=manifest)
                self.assertIn("invalid_target", codes)
                self.assertIn("target_mismatch", codes)
        manifest.pop("target")
        self.assertIn("invalid_target", self.codes(manifest=manifest))

    def test_missing_nonobject_or_changed_policies_return_owned_hold(self):
        for name in ("fixture_policy", "sequence_policy", "coordination_policy", "lifecycle_policy", "source_identity", "stop_policy"):
            for value in (None, [], "invented", 3, {}):
                manifest = deepcopy(MANIFEST)
                manifest[name] = value
                with self.subTest(name=name, value=value):
                    code = f"{name}_mismatch" if isinstance(value, dict) else f"{name}_invalid"
                    self.assertIn(code, self.codes(manifest=manifest))
            manifest.pop(name)
            self.assertIn(f"{name}_invalid", self.codes(manifest=manifest))

    def test_unhashable_or_nonlist_prohibition_metadata_is_held(self):
        for value in (None, "cleanup", {}, [[], {}], [None], [True]):
            manifest = deepcopy(MANIFEST)
            manifest["prohibited_operations"] = value
            with self.subTest(value=value):
                self.assertIn("preservation_policy_mismatch", self.codes(manifest=manifest))

    def test_malformed_assessment_times_return_owned_hold(self):
        for value in ([], {}, "2026-10-03T08:00:00Z", 3, False, datetime(2026, 10, 3, 8)):
            with self.subTest(value=value):
                report = assess_prerequisites(now=value)
                self.assertEqual(report.disposition, "HOLD")
                self.assertIs(report.db_access_permitted, False)
                self.assertTrue(all(finding.owner and finding.action for finding in report.findings))
                self.assertIn("invalid_time_metadata", {finding.code for finding in report.findings})

    def test_malformed_authority_times_return_owned_hold(self):
        for value in (None, [], {}, 3, False, "", "99999-10-03T08:00:00Z", "2026-10-03T09:00:00"):
            with self.subTest(value=value):
                self.assertIn("authority_expired_or_unknown", self.codes({"authority": {"expires_at": value}}))

    def test_changed_environment_and_invented_binding_are_held(self):
        for name, value, code in (
            ("environment_id", "invented-other-environment", "target_mismatch"),
            ("binding", "invented-substitute-binding", "target_binding_mismatch"),
            ("binding", [], "target_binding_missing"),
        ):
            manifest = deepcopy(MANIFEST)
            manifest["target"][name] = value
            self.assertIn(code, self.codes(manifest=manifest))

    def test_stale_candidate_revision_or_file_hashes_are_held(self):
        for name, value in (("revision", "1.0"), ("candidate_commit", None), ("candidate_commit", []), ("file_sha256", {"invented": "stale"})):
            identity = self.invented_identity()
            identity[name] = value
            self.assertIn("source_identity_unavailable", self.codes({"runtime_identity": identity}))
        manifest = deepcopy(MANIFEST)
        manifest["revision"] = "1.0"
        self.assertIn("proposal_identity_mismatch", self.codes(manifest=manifest))

    def test_indirect_lifecycle_import_settings_and_routing_are_held(self):
        prohibited = {
            "execution_command": "python manage.py test --keepdb",
            "settings_binding": "rms_project.hypothesis_source_settings",
            "aliases": ["invented-secondary"],
            "routers": ["invented.router"],
            "connections": [{"target": "invented-other"}],
            "requested_operations": ["flush"],
            "imports": ["django.test.runner", "psycopg"],
            "setup": ["create_database"],
            "teardown": ["cleanup"],
            "callbacks": ["on_commit:fixture_loader"],
        }
        for name, value in prohibited.items():
            identity = self.invented_identity()
            identity[name] = value
            with self.subTest(name=name):
                self.assertIn(f"routing_or_lifecycle_{name}_unreviewed", self.codes({"runtime_identity": identity}))
            manifest = deepcopy(MANIFEST)
            manifest["lifecycle_policy"][name] = value
            self.assertIn("lifecycle_policy_mismatch", self.codes(manifest=manifest))

    def test_exact_local_source_metadata_still_cannot_release_execution(self):
        codes = self.codes({"runtime_identity": self.invented_identity()})
        self.assertNotIn("source_identity_unavailable", codes)
        self.assertIn("runtime_identity_unverified", codes)
        self.assertIn("source_only_execution_hold", codes)

    def test_manifest_inventories_are_proposals_not_executed_evidence(self):
        for section in ("effect_inventory", "denial_matrix", "preservation_inventory", "stop_policy", "concurrency_scenario"):
            self.assertTrue(MANIFEST[section])
        for effect in MANIFEST["effect_inventory"]:
            self.assertTrue(all(effect[key] for key in ("id", "owner", "action", "accounting", "hold", "fail")))
        association_kinds = {"IdeaFamily", "InvestigationFamily", "PriorResearchInvestigation", "HypothesisInvestigation", "IdeaHypothesis", "AssessmentRecord"}
        for kind in association_kinds:
            self.assertTrue(any(kind in item for item in MANIFEST["denial_matrix"]["introduced_immutable"]))
        self.assertIn("NOT RUN", MANIFEST["concurrency_scenario"]["status"])
        self.assertIsNone(MANIFEST["source_identity"]["execution_command"])
        self.assertIsNone(MANIFEST["source_identity"]["installed_settings_binding"])
        self.assertTrue(all(value is None for value in MANIFEST["required_receipts"].values()))

    def test_actual_manifest_stays_hold_for_every_unavailable_prerequisite(self):
        codes = self.codes()
        for code in (
            "target_binding_missing", "execution_authority_missing", "schema_unavailable",
            "ordinary_application_role_unavailable", "editor_viewer_bindings_unavailable",
            "sequence_effects_unresolved", "coordinated_use_unavailable",
            "preservation_procedure_unavailable", "committed_separate_session_proof_unavailable",
            "operations_review_unadopted", "independent_test_review_unadopted",
            "director_adoption_unadopted", "source_only_execution_hold",
        ):
            self.assertIn(code, codes)
        self.assertTrue(all(value is None for value in MANIFEST["required_receipts"].values()))

    def test_schema_and_target_mismatches_fail_closed(self):
        manifest = deepcopy(MANIFEST)
        manifest["schema_sha256"] = "invented-wrong-hash"
        manifest["target"]["database"] = "invented-other-target"
        codes = self.codes(manifest=manifest)
        self.assertIn("schema_pin_mismatch", codes)
        self.assertIn("target_mismatch", codes)

    def test_owner_superuser_or_unknown_role_is_not_h14_proof(self):
        for owner, superuser in ((True, False), (False, True), (None, None)):
            receipts = {"ordinary_role": {"synthetic": True, "evidence_ref": "invented-negative-test", "authorized": True, "is_owner": owner, "is_superuser": superuser, "binding_ref": "invented-binding"}}
            codes = self.codes(receipts)
            self.assertIn("ordinary_application_role_unavailable", codes)
            self.assertIn("ordinary_role_unverified", codes)

    def test_missing_or_reused_principals_do_not_grant_access(self):
        receipts = {"principals": {"synthetic": True, "editor_ref": "invented-same", "viewer_ref": "invented-same", "authorized": True}}
        self.assertIn("editor_viewer_bindings_unavailable", self.codes(receipts))

    def test_expired_revoked_stale_or_source_only_authority_is_held(self):
        for changes in (
            {"expires_at": "2026-10-03T07:00:00Z"}, {"expires_at": "invalid"},
            {"expires_at": "2026-10-03T09:00:00"}, {"revoked": True},
            {"scope": "source_only"}, {"schema_sha256": "invented-stale"},
        ):
            authority = {"synthetic": True, "evidence_ref": "invented-negative-test", "scope": "preserving_db_execution", "status": "accepted", "revoked": False, "target": "rms_synthetic", "schema_sha256": MANIFEST["schema_sha256"], "expires_at": "2026-10-03T09:00:00Z"}
            authority.update(changes)
            codes = self.codes({"authority": authority})
            self.assertTrue({"execution_authority_missing", "authority_expired_or_unknown", "authority_target_or_schema_mismatch"} & codes)
            self.assertIn("authority_unverified", codes)

    def test_rollback_or_single_session_does_not_emulate_concurrency(self):
        for sessions, committed in (([], True), (["invented-one"], True), (["invented-same", "invented-same"], True), (["invented-one", "invented-two"], False), ([[], {}], True)):
            receipts = {"concurrency": {"synthetic": True, "session_refs": sessions, "committed": committed, "coordinated": True}}
            self.assertIn("committed_separate_session_proof_unavailable", self.codes(receipts))

    def test_sequence_rollback_and_uncoordinated_use_stay_held(self):
        receipts = {"sequence": {"synthetic": True, "policy": "rollback"}, "coordination": {"synthetic": True, "exclusive": False}}
        codes = self.codes(receipts)
        self.assertIn("sequence_effects_unresolved", codes)
        self.assertIn("coordinated_use_unavailable", codes)

    def test_lifecycle_permissions_cannot_be_removed(self):
        self.assertEqual(set(MANIFEST["prohibited_operations"]), FORBIDDEN)
        for operation in FORBIDDEN:
            manifest = deepcopy(MANIFEST)
            manifest["prohibited_operations"].remove(operation)
            self.assertIn("preservation_policy_mismatch", self.codes(manifest=manifest))
        manifest["source_only"] = False
        self.assertIn("manifest_not_source_only", self.codes(manifest=manifest))

    def test_metadata_is_not_mutated_and_report_has_no_pass_state(self):
        receipts = {"authority": {"synthetic": True, "evidence_ref": "invented-only"}}
        original = deepcopy(receipts)
        report = assess_prerequisites(receipts, now=NOW)
        self.assertEqual(receipts, original)
        self.assertEqual(report.disposition, "HOLD")
        self.assertTrue(all(finding.action and finding.owner for finding in report.findings))
        self.assertIn("invalid_receipts", self.codes(receipts=[]))

    def test_source_is_inert_and_tests_never_invoke_runner(self):
        source = ast.parse(Path("rms/hypothesis_preserving_runner.py").read_text())
        imports = [node.module for node in ast.walk(source) if isinstance(node, ast.ImportFrom)]
        imports.extend(alias.name for node in ast.walk(source) if isinstance(node, ast.Import) for alias in node.names)
        self.assertFalse(any(name.startswith(("django", "psycopg", "subprocess", "socket")) for name in imports))
        runner = next(node for node in ast.walk(source) if isinstance(node, ast.ClassDef) and node.name == "PreservingRunner")
        run = next(node for node in runner.body if isinstance(node, ast.FunctionDef) and node.name == "run")
        self.assertEqual(len(run.body), 1)
        self.assertIsInstance(run.body[0], ast.Raise)


if __name__ == "__main__":
    unittest.main()
