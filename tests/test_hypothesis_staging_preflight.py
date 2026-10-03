"""Adversarial staging-binding and read-only-session checks; fake transport only."""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock

from rms.hypothesis_staging_preflight import (
    CONTRACT_SHA256, MANIFEST_PATH, PreflightRejected,
    execute_read_only_preflight, review_packet,
)


class StagingPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("PAPERCLIP_RUN_SCRATCH_DIR"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "invented-source.txt"
        source.write_bytes(b"Invented source\n")
        manifest = self.root / MANIFEST_PATH
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"contract_sha256": CONTRACT_SHA256, "files": [{"path": source.name, "bytes": source.stat().st_size, "sha256": sha256(source.read_bytes()).hexdigest()}]}))
        self.packet = {
            "target": {"project": "mv-rms-staging", "database_container": "mv-rms-staging-db-1", "database": "rms_staging", "app_container_id": "Invented app", "database_container_id": "Invented db", "volume_id": "Invented existing volume", "private_route_ref": "Invented private reference", "ordinary_role": "invented_application", "host": "invented-existing-db", "port": 5432, "observation_ref": "Invented observation"},
            "principals": {"editor_id": 11, "viewer_id": 12},
            "operations_review_ref": "Invented Operations review", "test_review_ref": "Invented Test review", "coordination_slot_ref": "Invented slot",
            "source_manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
        }
        self.authorize = Mock(side_effect=lambda **binding: {**binding, "verified": True})
        self.session = Mock(autocommit=False)
        self.session.info = SimpleNamespace(host="invented-existing-db", port=5432)
        self.cursor = MagicMock()
        self.session.cursor.return_value = self.cursor
        self.cursor.__enter__.return_value = self.cursor
        self.cursor.fetchone.side_effect = [("rms_staging", "invented_application", "invented_application", "on"), (False,) * 5, (False,)]
        self.cursor.fetchall.side_effect = [[("0004_hypothesis_records",), ("0005_hypothesis_history_guards",)], [(11, True, "editor"), (12, True, "founder_viewer")]]
        self.connect = Mock(return_value=self.session)

    def execute(self):
        return execute_read_only_preflight(self.packet, root=self.root, authorize=self.authorize, connect=self.connect)

    def test_former_software_test_target_is_rejected_before_authorization_or_connection(self):
        self.packet["target"]["database"] = "rms_synthetic"
        with self.assertRaisesRegex(PreflightRejected, "staging_database_mismatch"):
            self.execute()
        self.authorize.assert_not_called()
        self.connect.assert_not_called()

    def test_same_database_name_does_not_replace_container_volume_and_route_bindings(self):
        for key in ("database_container", "volume_id", "private_route_ref", "observation_ref"):
            packet = deepcopy(self.packet)
            packet["target"][key] = None
            with self.subTest(key=key), self.assertRaises(PreflightRejected):
                review_packet(packet, root=self.root)

    def test_caller_release_flags_cannot_replace_authenticated_verifier(self):
        self.packet["execution_authorized"] = True
        self.authorize.return_value = False
        self.authorize.side_effect = None
        with self.assertRaisesRegex(PreflightRejected, "release_verification_failed"):
            self.execute()
        self.connect.assert_not_called()

    def test_verified_release_for_different_packet_or_scope_is_rejected(self):
        self.authorize.side_effect = lambda **binding: {**binding, "scope": "unrelated", "verified": True}
        with self.assertRaisesRegex(PreflightRejected, "release_verification_failed"):
            self.execute()
        self.connect.assert_not_called()

    def test_changed_source_fails_before_connection_even_if_manifest_pin_matches(self):
        (self.root / "invented-source.txt").write_text("Invented changed source")
        with self.assertRaisesRegex(PreflightRejected, "source_file_mismatch"):
            self.execute()
        self.connect.assert_not_called()

    def test_source_change_during_authorization_is_rechecked(self):
        def change(**binding):
            (self.root / "invented-source.txt").write_text("Invented change during review")
            return {**binding, "verified": True}
        self.authorize.side_effect = change
        with self.assertRaisesRegex(PreflightRejected, "source_file_mismatch"):
            self.execute()
        self.connect.assert_not_called()

    def test_effective_address_and_observed_database_role_must_match(self):
        self.session.info.host = "invented-other-target"
        with self.assertRaisesRegex(PreflightRejected, "effective_target_address_mismatch"):
            self.execute()
        self.session.cursor.assert_not_called()
        self.session.rollback.assert_called_once()
        self.session.close.assert_called_once()

    def test_privileged_or_schema_owner_role_is_rejected_and_session_rolled_back(self):
        for flags, owner in (((True, False, False, False, False), False), ((False,) * 5, True)):
            self.session.reset_mock()
            self.cursor.fetchone.side_effect = [("rms_staging", "invented_application", "invented_application", "on"), flags, (owner,)]
            with self.subTest(flags=flags, owner=owner), self.assertRaises(PreflightRejected):
                self.execute()
            self.session.rollback.assert_called_once()
            self.session.close.assert_called_once()

    def test_missing_migrations_and_viewer_editor_overlap_are_rejected(self):
        self.cursor.fetchall.side_effect = [[("0004_hypothesis_records",)]]
        with self.assertRaisesRegex(PreflightRejected, "installed_additive_schema_missing"):
            self.execute()
        self.session.rollback.assert_called_once()
        self.session.close.assert_called_once()

    def test_viewer_with_editor_membership_is_rejected(self):
        self.cursor.fetchall.side_effect = [[("0004_hypothesis_records",), ("0005_hypothesis_history_guards",)], [(11, True, "editor"), (12, True, "founder_viewer"), (12, True, "editor")]]
        with self.assertRaisesRegex(PreflightRejected, "observed_principals_invalid"):
            self.execute()

    def test_success_is_read_only_rollback_and_not_preservation_acceptance(self):
        result = self.execute()
        self.assertEqual(result["result"], "READ_ONLY_PREFLIGHT_PASS")
        self.assertEqual(result["writes"], [])
        self.assertIn("No H01-H20", result["acceptance"])
        statements = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertTrue(all(sql.startswith(("SET TRANSACTION", "SET LOCAL", "SELECT")) for sql in statements))
        self.assertIn("READ ONLY", statements[0])
        self.session.rollback.assert_called_once()
        self.session.close.assert_called_once()
        self.session.commit.assert_not_called()

    def test_rollback_failure_still_closes_without_commit(self):
        self.session.rollback.side_effect = RuntimeError("Invented rollback failure")
        with self.assertRaisesRegex(RuntimeError, "rollback failure"):
            self.execute()
        self.session.close.assert_called_once()
        self.session.commit.assert_not_called()

    def test_autocommit_and_inline_secrets_are_rejected(self):
        self.session.autocommit = True
        with self.assertRaisesRegex(PreflightRejected, "autocommit_connection_forbidden"):
            self.execute()
        self.session.cursor.assert_not_called()
        self.packet["target"]["password"] = "Invented forbidden value"
        with self.assertRaisesRegex(PreflightRejected, "inline_secret_forbidden"):
            review_packet(self.packet, root=self.root)

    def test_duplicate_principals_or_missing_reviews_are_rejected(self):
        self.packet["principals"]["viewer_id"] = 11
        with self.assertRaisesRegex(PreflightRejected, "principal_bindings_not_distinct"):
            review_packet(self.packet, root=self.root)
        self.packet["principals"]["viewer_id"] = 12
        self.packet["operations_review_ref"] = None
        with self.assertRaisesRegex(PreflightRejected, "review_or_slot_missing"):
            review_packet(self.packet, root=self.root)
