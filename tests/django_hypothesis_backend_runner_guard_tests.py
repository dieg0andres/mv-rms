import ast
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import unittest

from rms.hypothesis_preserving_runner import (
    FORBIDDEN,
    MANIFEST,
    assess_prerequisites,
)


NOW = datetime(2026, 10, 3, 8, tzinfo=timezone.utc)


class PreservingGuardTests(unittest.TestCase):
    def codes(self, receipts=None, manifest=None):
        report = assess_prerequisites(receipts, now=NOW, manifest=manifest)
        self.assertEqual(report.disposition, "HOLD")
        self.assertIs(report.db_access_permitted, False)
        return {finding.code for finding in report.findings}

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
