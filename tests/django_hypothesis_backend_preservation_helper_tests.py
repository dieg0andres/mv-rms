import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic
from types import SimpleNamespace
import unittest

from rms.hypothesis_preserving_harness import (
    BoundedSupervisor,
    HarnessFailure,
    assert_preservation,
    fixture_ids,
    freeze_effect_plan,
    freeze_preservation_baseline,
    inventory_digest,
    preserving_failure_handoff,
    require_durable_ack,
)


class FrozenEffectPlanTests(unittest.TestCase):
    def setUp(self):
        self.binding = {
            "candidate": {"candidate_commit": "invented-not-installed"},
            "manifest_sha256": "a" * 64,
            "run_id": "a4641c8b-24e1-4016-b603-71e15d2b8460",
            "fixture_ids": fixture_ids("a4641c8b-24e1-4016-b603-71e15d2b8460"),
            "physical_mappings_sha256": "b" * 64,
        }
        self.plan = {
            "binding": self.binding, "record_limit": 100,
            "additions": {"rows": {"planned-X": "invented-digest"}, "associations": {}, "foreign_keys": {}},
            "projections": {"invented-latest": "planned-X"},
        }
        self.receipt = {
            "reference": "invented-plan-ref", "review_ref": "invented-review-not-authority",
            "review_status": "accepted", "plan": self.plan, "sha256": inventory_digest(self.plan),
        }
        self.before = {name: {"invented-original": "original-digest"} for name in ("rows", "associations", "foreign_keys", "accounts", "roles", "sequences", "volume", "private_route", "evidence_watermarks")}
        self.before["projections"] = {"invented-latest": "invented-original"}

    def freeze(self, receipt=None):
        return freeze_effect_plan(self.receipt if receipt is None else receipt, binding=self.binding, record_limit=100)

    def after(self):
        after = deepcopy(self.before)
        for name, additions in self.plan["additions"].items():
            after[name].update(additions)
        after["projections"] = deepcopy(self.plan["projections"])
        return after

    def test_fixed_plan_accepts_only_exact_invented_effects(self):
        frozen = self.freeze().contents()
        assert_preservation(self.before, self.after(), frozen["additions"], frozen["projections"])

    def test_unexpected_rows_associations_and_foreign_keys_are_rejected(self):
        frozen = self.freeze().contents()
        for name in ("rows", "associations", "foreign_keys"):
            with self.subTest(name=name):
                after = self.after()
                after[name]["unapproved-Y"] = "unexpected-digest"
                with self.assertRaisesRegex(HarnessFailure, f"preservation_unexpected_{name}_effects"):
                    assert_preservation(self.before, after, frozen["additions"], frozen["projections"])

    def test_observed_projection_cannot_define_approved_projection(self):
        frozen = self.freeze().contents()
        after = self.after()
        after["projections"]["unapproved"] = "Y"
        with self.assertRaisesRegex(HarnessFailure, "unreviewed_projection_effect"):
            assert_preservation(self.before, after, frozen["additions"], frozen["projections"])

    def test_original_history_accounts_sequences_and_mappings_stay_fixed(self):
        frozen = self.freeze().contents()
        for name in self.before:
            if name == "projections":
                continue
            with self.subTest(name=name):
                after = self.after()
                after[name]["invented-original"] = "rewritten-history-or-binding"
                with self.assertRaises(HarnessFailure):
                    assert_preservation(self.before, after, frozen["additions"], frozen["projections"])

    def test_missing_nonobject_unreviewed_and_mismatched_plans_fail(self):
        for missing in (None, [], "invented"):
            with self.assertRaisesRegex(HarnessFailure, "effect_plan_missing"):
                freeze_effect_plan(missing, binding=self.binding, record_limit=100)
        for changes, expected in (({"review_status": "pending"}, "unreviewed"), ({"reference": None}, "reference_missing"), ({"sha256": "c" * 64}, "digest_mismatch")):
            receipt = {**self.receipt, **changes}
            with self.assertRaisesRegex(HarnessFailure, expected):
                self.freeze(receipt)
        receipt = deepcopy(self.receipt)
        receipt["plan"]["binding"]["run_id"] = "invented-wrong-run"
        receipt["sha256"] = inventory_digest(receipt["plan"])
        with self.assertRaisesRegex(HarnessFailure, "binding_mismatch"):
            self.freeze(receipt)

    def test_mapping_and_inventory_and_budget_missing_or_exceeded_fail(self):
        binding = {**self.binding, "physical_mappings_sha256": None}
        receipt = deepcopy(self.receipt)
        receipt["plan"]["binding"] = binding
        with self.assertRaisesRegex(HarnessFailure, "mappings_missing"):
            freeze_effect_plan(receipt, binding=binding, record_limit=100)
        for change, expected in (({"additions": {}}, "inventory_missing"), ({"record_limit": True}, "budget_invalid"), ({"record_limit": 101}, "budget_invalid"), ({"additions": {"rows": {f"invented-{index}": "digest" for index in range(101)}, "associations": {}, "foreign_keys": {}}}, "record_limit_exceeded")):
            receipt = deepcopy(self.receipt)
            receipt["plan"].update(change)
            with self.assertRaisesRegex(HarnessFailure, expected):
                self.freeze(receipt)

    def test_plan_is_immutable_and_caller_mutation_cannot_expand_effects(self):
        frozen = self.freeze()
        self.plan["additions"]["rows"]["Y"] = "unapproved"
        returned = frozen.contents()
        returned["additions"]["rows"]["Z"] = "unapproved"
        self.assertEqual(frozen.contents()["additions"]["rows"], {"planned-X": "invented-digest"})


class FrozenPreservationBaselineTests(unittest.TestCase):
    def setUp(self):
        self.inventory = {name: {"invented-original": {"digest": "original-digest"}} for name in ("rows", "associations", "foreign_keys", "accounts", "roles", "sequences", "volume", "private_route", "evidence_watermarks")}
        self.inventory["projections"] = {"invented-latest": "invented-original"}
        self.inventory["inventory_receipt"] = {"invented-extra": ["full-inventory"]}
        self.additions = {name: {} for name in ("rows", "associations", "foreign_keys")}
        self.binding = {"run_id": "invented-run"}

    def assert_preserved(self, baseline, after):
        assert_preservation(baseline.contents(), after, self.additions, baseline.contents()["projections"])

    def test_full_inventory_is_frozen_as_owned_canonical_bytes(self):
        original = deepcopy(self.inventory)
        baseline = freeze_preservation_baseline(self.inventory)
        self.assertIsInstance(baseline.body, bytes)
        self.assertEqual(baseline.sha256, inventory_digest(original))
        for value in self.inventory.values():
            value.clear()
        self.assertEqual(baseline.contents(), original)
        self.assertEqual(inventory_digest(baseline.contents()), baseline.sha256)

    def test_each_callback_view_is_independently_owned(self):
        baseline = freeze_preservation_baseline(self.inventory)
        first = baseline.contents()
        second = baseline.contents()
        first["rows"]["invented-original"]["digest"] = "rewritten"
        first["inventory_receipt"]["invented-extra"].append("rewritten")
        self.assertEqual(second, self.inventory)
        self.assertEqual(baseline.contents(), self.inventory)

    def test_retained_persistence_callback_cannot_conceal_original_drift(self):
        for name in ("rows", "associations", "foreign_keys", "accounts", "roles", "sequences", "volume", "private_route", "evidence_watermarks"):
            with self.subTest(inventory=name):
                baseline = freeze_preservation_baseline(self.inventory)
                retained = []
                durable = []

                def persist(document, *, sha256, binding):
                    self.assertEqual(inventory_digest(document), sha256)
                    retained.append(document)
                    durable.append(deepcopy(document))
                    return {"durable": True, "restricted": True, "reference": "invented-sink-not-authority", "sha256": sha256, "binding": binding}

                ack = require_durable_ack(persist(baseline.contents(), sha256=baseline.sha256, binding=self.binding), sha256=baseline.sha256, binding=self.binding, code="baseline_not_durable")
                retained[0][name]["invented-original"]["digest"] = "rewritten"
                self.assertEqual(inventory_digest(durable[0]), ack["sha256"])
                self.assertNotEqual(inventory_digest(retained[0]), ack["sha256"])
                with self.assertRaisesRegex(HarnessFailure, f"preservation_.*{name}"):
                    self.assert_preserved(baseline, retained[0])

    def test_in_callback_mutation_cannot_replace_frozen_acknowledged_oracle(self):
        baseline = freeze_preservation_baseline(self.inventory)
        observed = []

        def persist(document, *, sha256, binding):
            document["rows"]["invented-original"]["digest"] = "rewritten-in-callback"
            observed.append(document)
            return {"durable": True, "restricted": True, "reference": "invented-claim-not-authority", "sha256": sha256, "binding": binding}

        ack = require_durable_ack(persist(baseline.contents(), sha256=baseline.sha256, binding=self.binding), sha256=baseline.sha256, binding=self.binding, code="baseline_not_durable")
        self.assertEqual(baseline.sha256, ack["sha256"])
        self.assertEqual(baseline.contents(), self.inventory)
        with self.assertRaisesRegex(HarnessFailure, "preservation_original_rows_changed"):
            self.assert_preserved(baseline, observed[0])

    def test_ack_for_callback_mutated_bytes_is_rejected(self):
        baseline = freeze_preservation_baseline(self.inventory)
        document = baseline.contents()
        document["rows"]["invented-original"]["digest"] = "rewritten"
        ack = {"durable": True, "restricted": True, "reference": "invented-sink", "sha256": inventory_digest(document), "binding": self.binding}
        with self.assertRaisesRegex(HarnessFailure, "baseline_not_durable"):
            require_durable_ack(ack, sha256=baseline.sha256, binding=self.binding, code="baseline_not_durable")

    def test_reused_adapter_snapshot_cannot_rewrite_original_oracle(self):
        def snapshot():
            return self.inventory

        baseline = freeze_preservation_baseline(snapshot())
        original_digest = baseline.sha256
        snapshot()["rows"]["invented-original"]["digest"] = "rewritten-between-snapshots"
        final = snapshot()
        self.assertIs(final, self.inventory)
        self.assertEqual(inventory_digest(baseline.contents()), original_digest)
        with self.assertRaisesRegex(HarnessFailure, "preservation_original_rows_changed"):
            self.assert_preserved(baseline, final)

    def test_unchanged_reused_snapshot_and_exact_additions_are_allowed(self):
        baseline = freeze_preservation_baseline(self.inventory)
        self.assert_preserved(baseline, self.inventory)
        self.inventory["rows"]["invented-approved-new"] = {"digest": "planned-digest"}
        self.additions["rows"]["invented-approved-new"] = {"digest": "planned-digest"}
        self.assert_preserved(baseline, self.inventory)
        self.assertNotIn("invented-approved-new", baseline.contents()["rows"])

    def test_missing_or_incomplete_baseline_is_rejected_before_callbacks(self):
        for inventory in (None, [], {}, {**self.inventory, "rows": None}, {**self.inventory, "accounts": None}, {**self.inventory, "projections": None}):
            with self.subTest(inventory=inventory), self.assertRaises(HarnessFailure):
                freeze_preservation_baseline(inventory)

    def test_source_freezes_before_persist_and_uses_detached_final_oracle(self):
        tree = ast.parse(Path("rms/hypothesis_preserving_harness.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "execute_preserving_cases")
        calls = list(node for node in ast.walk(function) if isinstance(node, ast.Call))
        freeze = next(node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "freeze_preservation_baseline")
        persist = next(node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "persist_restricted_baseline")
        final = next(node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "assert_preservation")
        self.assertLess(freeze.lineno, persist.lineno)
        self.assertEqual(ast.unparse(freeze.args[0]), "operation('baseline_snapshot', transport.snapshot_full_preservation_inventory)")
        self.assertEqual(ast.unparse(persist.args[0]), "baseline.contents()")
        self.assertEqual(ast.unparse(final.args[0]), "baseline.contents()")
        self.assertEqual(ast.unparse(final.args[1]), "operation('final_snapshot', transport.snapshot_full_preservation_inventory)")
        assignments = [node for node in ast.walk(function) if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "baseline_sha256" for target in node.targets)]
        self.assertTrue(any(ast.unparse(node.value) == "baseline.sha256" for node in assignments))


class BaselineAndFailureHandoffTests(unittest.TestCase):
    def setUp(self):
        self.binding = {"run_id": "invented-run", "candidate": "invented-candidate"}
        self.context = {
            "phase": "invented_write_failed", "run_id": "invented-run", "binding": self.binding,
            "baseline_ack": {"reference": "invented-restricted-baseline"},
            "baseline_sha256": "a" * 64, "effect_plan_ref": "invented-frozen-plan",
            "reconciliation_ref": "invented-existing-handoff",
        }

    def ack(self, document):
        return {"durable": True, "restricted": True, "reference": "invented-only-not-real-sink", "sha256": inventory_digest(document), "binding": self.binding}

    def test_missing_malformed_unacknowledged_or_wrong_baseline_is_refused(self):
        document = {"invented_inventory": "complete"}
        valid = self.ack(document)
        for ack in (None, [], {}, {**valid, "durable": False}, {**valid, "restricted": False}, {**valid, "reference": None}, {**valid, "sha256": "b" * 64}, {**valid, "binding": {"run_id": "different"}}):
            with self.subTest(ack=ack), self.assertRaisesRegex(HarnessFailure, "baseline_not_durable"):
                require_durable_ack(ack, sha256=inventory_digest(document), binding=self.binding, code="baseline_not_durable")

    def test_baseline_ack_matches_exact_full_inventory_digest(self):
        document = {"invented_inventory": "complete"}
        self.assertEqual(require_durable_ack(self.ack(document), sha256=inventory_digest(document), binding=self.binding, code="baseline_not_durable"), self.ack(document))

    def test_compound_cancellation_and_both_sink_errors_preserve_primary(self):
        def failing(**kwargs):
            raise RuntimeError("invented-sensitive-details-must-not-leak")

        sink = SimpleNamespace(cancel_owned_sessions_only=failing, append_receipt=lambda document: failing(), retain_reconciliation_receipt=lambda document: failing())
        primary = HarnessFailure("invented_primary")
        supervisor = BoundedSupervisor(monotonic() + 1, session_refs=("invented-A", "invented-B"))
        receipt = preserving_failure_handoff(primary, supervisor=supervisor, transport=sink, context=self.context, seconds=0.3)
        self.assertEqual(receipt["primary_failure"]["code"], "invented_primary")
        self.assertEqual([error["phase"] for error in receipt["secondary_failures"]], ["cancellation", "append_receipt", "retain_reconciliation_receipt"])
        self.assertEqual(receipt["delivery"], "not_acknowledged")
        self.assertFalse(receipt["quiescence"])
        self.assertEqual(receipt["session_state"]["reservation"], "retain_pending_operations_reconciliation")
        self.assertEqual(receipt["reconciliation_ref"], self.context["reconciliation_ref"])
        self.assertEqual(primary.failure_receipt, receipt)
        self.assertNotIn("invented-sensitive-details", json.dumps(receipt))

    def test_fallback_retains_failed_primary_sink_without_faking_ack(self):
        observed = []

        def primary_sink(document):
            raise OSError("invented-unavailable")

        def fallback(document):
            observed.append(deepcopy(document))
            return self.ack(document)

        sink = SimpleNamespace(cancel_owned_sessions_only=lambda **kwargs: {"server_verified": False}, append_receipt=primary_sink, retain_reconciliation_receipt=fallback)
        receipt = preserving_failure_handoff(HarnessFailure("primary"), supervisor=BoundedSupervisor(monotonic() + 1), transport=sink, context=self.context, seconds=0.3)
        self.assertEqual(receipt["delivery"], "acknowledged")
        self.assertFalse(receipt["quiescence"])
        self.assertEqual(observed[0]["secondary_failures"][0]["phase"], "append_receipt")
        self.assertEqual(receipt["delivery_ack"]["sha256"], inventory_digest(observed[0]))

    def test_completed_calls_or_unverified_cancellation_do_not_prove_quiescence(self):
        for cancellation in ({}, {"server_verified": True, "session_outcomes": {"invented-A": "quiescent"}}, {"server_verified": False, "session_outcomes": {"invented-A": "quiescent", "invented-B": "quiescent"}}):
            sink = SimpleNamespace(cancel_owned_sessions_only=lambda **kwargs: cancellation, append_receipt=self.ack)
            receipt = preserving_failure_handoff(HarnessFailure("primary"), supervisor=BoundedSupervisor(monotonic() + 1, session_refs=("invented-A", "invented-B")), transport=sink, context=self.context, seconds=0.3)
            self.assertFalse(receipt["quiescence"])
            self.assertEqual(receipt["session_state"]["reservation"], "retain_pending_operations_reconciliation")

    def test_prewrite_source_requires_plan_and_durable_baseline_before_context(self):
        source = Path("rms/hypothesis_preserving_harness.py").read_text()
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "execute_preserving_cases")
        calls = {name: [] for name in ("freeze_effect_plan", "require_reviewed_effect_plan", "require_durable_ack", "require_durable_baseline", "create_invented_context_through_shared_services")}
        for node in ast.walk(function):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
                if name in calls:
                    calls[name].append(node.lineno)
        for name in calls:
            self.assertTrue(calls[name], name)
            if name != "create_invented_context_through_shared_services":
                self.assertLess(min(calls[name]), min(calls["create_invented_context_through_shared_services"]))
        self.assertNotIn("ThreadPoolExecutor", source)
        self.assertNotIn("effects[\"additions\"]", source)
        self.assertNotIn("effects[\"reviewed_projections\"]", source)


class IsolatedSupervisionTests(unittest.TestCase):
    def test_unresponsive_work_cancellation_and_sink_have_hard_external_deadline(self):
        script = """
import json
from threading import Event
from time import monotonic
from types import SimpleNamespace
from rms.hypothesis_preserving_harness import BoundedSupervisor, HarnessFailure, preserving_failure_handoff
blocked = Event()
supervisor = BoundedSupervisor(monotonic() + 0.08, session_refs=("invented-A", "invented-B"))
future = supervisor.submit("invented_unresponsive_worker", blocked.wait)
try:
    supervisor.await_result(future)
except TimeoutError as primary:
    sink = SimpleNamespace(cancel_owned_sessions_only=lambda **kwargs: blocked.wait(), append_receipt=lambda document: blocked.wait(), retain_reconciliation_receipt=lambda document: blocked.wait())
    receipt = preserving_failure_handoff(primary, supervisor=supervisor, transport=sink, context={"phase": "invented-blocked", "binding": {}, "reconciliation_ref": "invented-handoff"}, seconds=0.12)
    assert not receipt["quiescence"]
    assert receipt["delivery"] == "not_acknowledged"
    assert len(receipt["session_state"]["outstanding_work"]) == 4
    assert receipt["session_state"]["reservation"] == "retain_pending_operations_reconciliation"
    assert len(receipt["secondary_failures"]) == 3
    try:
        supervisor.submit("unsafe-new-dispatch", lambda: None)
    except HarnessFailure:
        pass
    else:
        raise AssertionError("dispatch resumed after stop")
    print(json.dumps({"unknown_owned_work": len(receipt["session_state"]["outstanding_work"]), "quiescence": receipt["quiescence"], "delivery": receipt["delivery"]}))
else:
    raise AssertionError("blocked work unexpectedly returned")
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", "import sys; sys.path.insert(0, sys.argv[1]); exec(sys.argv[2])", str(Path.cwd()), script], capture_output=True, text=True, timeout=3, check=True)
        self.assertEqual(json.loads(result.stdout), {"unknown_owned_work": 4, "quiescence": False, "delivery": "not_acknowledged"})

    def test_expired_deadline_cannot_start_any_new_callback(self):
        called = []
        supervisor = BoundedSupervisor(monotonic() - 1)
        with self.assertRaisesRegex(HarnessFailure, "supervision_deadline_exceeded"):
            supervisor.call("expired", lambda: called.append(True))
        self.assertEqual(called, [])
        self.assertEqual(supervisor.state()["outstanding_work"], [])

    def test_acknowledged_cancellation_does_not_hide_outstanding_worker(self):
        script = """
from threading import Event
from time import monotonic
from types import SimpleNamespace
from rms.hypothesis_preserving_harness import BoundedSupervisor, inventory_digest, preserving_failure_handoff
supervisor = BoundedSupervisor(monotonic() + 0.04, session_refs=("invented-A", "invented-B"))
future = supervisor.submit("invented_unresponsive", Event().wait)
try:
    supervisor.await_result(future)
except TimeoutError as primary:
    def cancel(**kwargs):
        assert kwargs["session_refs"] == ("invented-A", "invented-B")
        return {"server_verified": True, "session_outcomes": {"invented-A": "quiescent", "invented-B": "quiescent"}}
    sink = SimpleNamespace(cancel_owned_sessions_only=cancel, append_receipt=lambda document: {"durable": True, "restricted": True, "reference": "invented-only", "sha256": inventory_digest(document), "binding": {}})
    receipt = preserving_failure_handoff(primary, supervisor=supervisor, transport=sink, context={"binding": {}, "reconciliation_ref": "invented"}, seconds=0.15)
    assert not receipt["quiescence"]
    assert receipt["session_state"]["outstanding_work"]
    assert receipt["session_state"]["reservation"] == "retain_pending_operations_reconciliation"
else:
    raise AssertionError("unresponsive work returned")
"""
        subprocess.run([sys.executable, "-I", "-B", "-c", "import sys; sys.path.insert(0, sys.argv[1]); exec(sys.argv[2])", str(Path.cwd()), script], timeout=3, check=True, capture_output=True, text=True)

    def test_late_worker_completion_without_session_proof_remains_unknown(self):
        script = """
from time import monotonic, sleep
from types import SimpleNamespace
from rms.hypothesis_preserving_harness import BoundedSupervisor, inventory_digest, preserving_failure_handoff
supervisor = BoundedSupervisor(monotonic() + 0.04, session_refs=("invented-A", "invented-B"))
future = supervisor.submit("invented_delayed", lambda: sleep(0.08))
try:
    supervisor.await_result(future)
except TimeoutError as primary:
    def cancel(**kwargs):
        sleep(0.06)
        return {"server_verified": False}
    sink = SimpleNamespace(cancel_owned_sessions_only=cancel, append_receipt=lambda document: {"durable": True, "restricted": True, "reference": "invented-only", "sha256": inventory_digest(document), "binding": {}})
    receipt = preserving_failure_handoff(primary, supervisor=supervisor, transport=sink, context={"binding": {}, "reconciliation_ref": "invented"}, seconds=0.3)
    assert future.done()
    assert not receipt["session_state"]["outstanding_work"]
    assert all(session["state"] == "unknown" for session in receipt["session_state"]["owned_sessions"].values())
    assert not receipt["quiescence"]
else:
    raise AssertionError("delayed worker unexpectedly met deadline")
"""
        subprocess.run([sys.executable, "-I", "-B", "-c", "import sys; sys.path.insert(0, sys.argv[1]); exec(sys.argv[2])", str(Path.cwd()), script], timeout=3, check=True, capture_output=True, text=True)
