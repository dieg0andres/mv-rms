"""Executable preserving test-source; no connections, fixture loaders or test DB lifecycle."""

from concurrent.futures import Future
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from threading import Event, RLock, Thread
from time import monotonic
from uuid import UUID, uuid5


class HarnessFailure(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise HarnessFailure(code)


def fixture_ids(run_id):
    namespace = UUID(run_id)
    prefixes = {
        "source": "SRC", "source-v1": "SRCV", "idea": "IDE", "idea-v1": "IDEV",
        "family": "RFAM", "family-v1": "RFAMV", "case": "INV", "case-v1": "INVV",
        "assessment": "PRA", "assessment-v1": "PRAV", "idea-family": "IFA",
        "idea-family-v1": "IFAV", "hypothesis": "HYP", "hypothesis-v1": "HYPV",
        "hypothesis-v2": "HYPV",
    }
    return {name: f"{prefix}-{uuid5(namespace, name)}" for name, prefix in prefixes.items()}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def inventory_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class FrozenEffectPlan:
    reference: str
    sha256: str
    body: bytes

    def contents(self):
        return json.loads(self.body)


def freeze_effect_plan(receipt, *, binding, record_limit):
    require(isinstance(receipt, dict), "effect_plan_missing")
    require(receipt.get("review_status") == "accepted" and isinstance(receipt.get("review_ref"), str) and bool(receipt["review_ref"]), "effect_plan_unreviewed")
    require(isinstance(receipt.get("reference"), str) and bool(receipt["reference"]), "effect_plan_reference_missing")
    plan = receipt.get("plan")
    require(isinstance(plan, dict) and plan.get("binding") == binding, "effect_plan_binding_mismatch")
    require(isinstance(binding.get("physical_mappings_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", binding["physical_mappings_sha256"]), "effect_plan_mappings_missing")
    additions = plan.get("additions")
    require(isinstance(additions, dict) and set(additions) == {"rows", "associations", "foreign_keys"}, "effect_plan_inventory_missing")
    require(all(isinstance(value, dict) for value in additions.values()) and isinstance(plan.get("projections"), dict), "effect_plan_inventory_missing")
    require(type(record_limit) is int and record_limit > 0 and type(plan.get("record_limit")) is int and 0 < plan["record_limit"] <= record_limit, "effect_plan_budget_invalid")
    require(len(additions["rows"]) <= plan["record_limit"], "record_limit_exceeded")
    body = canonical_bytes(plan)
    sha256 = hashlib.sha256(body).hexdigest()
    require(receipt.get("sha256") == sha256, "effect_plan_digest_mismatch")
    return FrozenEffectPlan(receipt["reference"], sha256, body)


def require_durable_ack(acknowledgement, *, sha256, binding, code):
    require(isinstance(acknowledgement, dict), code)
    require(acknowledgement.get("durable") is True and acknowledgement.get("restricted") is True, code)
    require(isinstance(acknowledgement.get("reference"), str) and bool(acknowledgement["reference"]), code)
    require(acknowledgement.get("sha256") == sha256 and acknowledgement.get("binding") == binding, code)
    return deepcopy(acknowledgement)


class BoundedSupervisor:
    """A deadline bounds observation, never proves that a timed-out call stopped."""

    def __init__(self, deadline, *, session_refs=()):
        self.deadline = deadline
        self.stop = Event()
        self.lock = RLock()
        self.work = {}
        self.sessions = {reference: {"state": "unknown"} for reference in session_refs}

    def bind_session(self, reference, binding):
        with self.lock:
            require(reference in self.sessions, "unreviewed_owned_session")
            self.sessions[reference] = {"state": "unknown", "binding": {name: binding.get(name) for name in ("backend_pid", "transaction_id", "session_ref")}}

    def submit(self, name, action, *, control=False):
        require(control or not self.stop.is_set(), "dispatch_stopped")
        require(control or monotonic() < self.deadline, "supervision_deadline_exceeded")
        future = Future()
        with self.lock:
            identity = f"{name}:{len(self.work)}"
            self.work[identity] = future

        def worker():
            try:
                require(control or not self.stop.is_set(), "dispatch_stopped")
                future.set_result(action())
            except BaseException as error:
                future.set_exception(error)

        Thread(target=worker, name=identity, daemon=True).start()
        return future

    def await_result(self, future, *, deadline=None):
        boundary = self.deadline if deadline is None else deadline
        remaining = boundary - monotonic()
        require(remaining > 0, "supervision_deadline_exceeded")
        try:
            return future.result(timeout=remaining)
        except BaseException:
            self.stop.set()
            raise

    def call(self, name, action, *, control=False, deadline=None):
        require(monotonic() < (self.deadline if deadline is None else deadline), "supervision_deadline_exceeded")
        return self.await_result(self.submit(name, action, control=control), deadline=deadline)

    def state(self):
        with self.lock:
            return {
                "outstanding_work": [name for name, future in self.work.items() if not future.done()],
                "owned_sessions": deepcopy(self.sessions),
                "reservation": "retain_pending_operations_reconciliation",
            }


def error_identity(error):
    return {"type": type(error).__name__, "code": str(error) if isinstance(error, HarnessFailure) else "restricted_error_details_not_emitted"}


def preserving_failure_handoff(primary, *, supervisor, transport, context, seconds=2):
    supervisor.stop.set()
    started = monotonic()
    deadline = started + seconds
    receipt = {
        **deepcopy(context), "primary_failure": error_identity(primary), "secondary_failures": [],
        "disposition": "FAIL_OR_UNKNOWN_RETAIN_ALL_ADDITIONS", "effects": "retained_or_unknown_no_cleanup",
        "reconciliation_owner": "Operations", "delivery": "not_acknowledged",
    }
    try:
        cancellation_deadline = started + seconds / 3
        owned_sessions = tuple(supervisor.state()["owned_sessions"])
        cancellation = supervisor.call("cancel_owned", lambda: transport.cancel_owned_sessions_only(session_refs=owned_sessions, deadline=cancellation_deadline), control=True, deadline=cancellation_deadline)
        receipt["cancellation"] = {name: deepcopy(cancellation.get(name)) for name in ("server_verified", "session_outcomes")} if isinstance(cancellation, dict) else {"state": "unknown"}
        state = supervisor.state()
        expected_sessions = set(state["owned_sessions"])
        outcomes = cancellation.get("session_outcomes", {}) if isinstance(cancellation, dict) else {}
        receipt["quiescence"] = bool(expected_sessions) and not state["outstanding_work"] and isinstance(cancellation, dict) and cancellation.get("server_verified") is True and set(outcomes) == expected_sessions and all(value == "quiescent" for value in outcomes.values())
    except BaseException as error:
        receipt["secondary_failures"].append({"phase": "cancellation", **error_identity(error)})
        receipt["quiescence"] = False
    for name, boundary in (("append_receipt", started + seconds * 2 / 3), ("retain_reconciliation_receipt", deadline)):
        receipt["session_state"] = supervisor.state()
        document = deepcopy(receipt)
        sha256 = inventory_digest(document)
        try:
            acknowledgement = supervisor.call(name, lambda name=name, document=document: getattr(transport, name)(document), control=True, deadline=boundary)
            receipt["delivery_ack"] = require_durable_ack(acknowledgement, sha256=sha256, binding=context["binding"], code="failure_handoff_not_durable")
            receipt["delivery"] = "acknowledged"
            receipt["acknowledged_document_sha256"] = sha256
            break
        except BaseException as error:
            receipt["secondary_failures"].append({"phase": name, **error_identity(error)})
    receipt["session_state"] = supervisor.state()
    receipt["quiescence"] = receipt.get("quiescence", False) and not receipt["session_state"]["outstanding_work"]
    primary.failure_receipt = deepcopy(receipt)
    return receipt


def assert_preservation(before, after, expected_additions, expected_projections):
    for name in ("accounts", "roles", "sequences", "volume", "private_route", "evidence_watermarks"):
        require(name in before and before[name] is not None and before[name] == after.get(name), f"preservation_{name}_changed_or_missing")
    for name in ("rows", "associations", "foreign_keys"):
        require(isinstance(before.get(name), dict) and isinstance(after.get(name), dict), f"preservation_{name}_inventory_missing")
        require(all(after[name].get(key) == value for key, value in before[name].items()), f"preservation_original_{name}_changed")
        appended = {key: value for key, value in after[name].items() if key not in before[name]}
        require(appended == expected_additions[name], f"preservation_unexpected_{name}_effects")
    require(isinstance(before.get("projections"), dict) and isinstance(expected_projections, dict), "projection_inventory_missing")
    require(after.get("projections") == expected_projections, "unreviewed_projection_effect")
    require(len(expected_additions["rows"]) <= 100, "record_limit_exceeded")


@dataclass(frozen=True)
class FrozenPreservationBaseline:
    sha256: str
    body: bytes

    def contents(self):
        return json.loads(self.body)


def freeze_preservation_baseline(inventory):
    require(isinstance(inventory, dict), "baseline_inventory_missing")
    body = canonical_bytes(inventory)
    baseline = FrozenPreservationBaseline(hashlib.sha256(body).hexdigest(), body)
    detached = baseline.contents()
    assert_preservation(detached, detached, {name: {} for name in ("rows", "associations", "foreign_keys")}, detached.get("projections"))
    return baseline


def _identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-z_][a-z0-9_]*", value) is not None, "unreviewed_sql_identifier")
    return f'"{value}"'


def snapshot_tables(connection, inventory, *, maximum_rows):
    """Hash every authorized mapped row, not a count/sample; caller owns the reviewed session."""
    require(type(maximum_rows) is int and maximum_rows > 0, "baseline_capacity_unavailable")
    result = {}
    remaining = maximum_rows
    with connection.cursor() as cursor:
        for table in inventory:
            name = _identifier(table["table"])
            key = _identifier(table["key"])
            columns = ", ".join(_identifier(column) for column in table["columns"])
            cursor.execute(f"SELECT {key}, {columns} FROM {name} ORDER BY {key}")
            rows = cursor.fetchmany(remaining + 1)
            require(len(rows) <= remaining, "baseline_capacity_exceeded_no_sampling")
            remaining -= len(rows)
            for row in rows:
                serialized = json.dumps(row[1:], default=str, separators=(",", ":")).encode()
                identity = f"{table['table']}:{row[0]}"
                require(identity not in result, "duplicate_baseline_identity")
                result[identity] = hashlib.sha256(serialized).hexdigest()
    return result


def probe_immutable_row(connection, mapping, row_id):
    """A successful forbidden statement fails even after savepoint rollback."""
    table = _identifier(mapping["table"])
    key = _identifier(mapping["key"])
    column = _identifier(mapping["immutable_column"])
    outcomes = []
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {key} FROM {table} WHERE {key} = %s", (row_id,))
        require(cursor.fetchone() is not None, "denial_probe_row_missing")
        for operation, statement in (
            ("update", f"UPDATE {table} SET {column} = {column} WHERE {key} = %s"),
            ("delete", f"DELETE FROM {table} WHERE {key} = %s"),
        ):
            cursor.execute("SAVEPOINT hn_denial_probe")
            rejected = False
            try:
                cursor.execute(statement, (row_id,))
            except Exception as error:
                rejected = getattr(error, "sqlstate", None) in {"23000", "42501"}
            finally:
                cursor.execute("ROLLBACK TO SAVEPOINT hn_denial_probe")
                cursor.execute("RELEASE SAVEPOINT hn_denial_probe")
            require(rejected, f"forbidden_{operation}_not_demonstrably_denied")
            outcomes.append(operation)
    return tuple(outcomes)


def coordinated_requests(transport, first, second, checkpoint, supervisor, session_refs):
    """Two bound sessions; A cannot commit until a server-observed B lock wait."""
    first_locked = Event()
    abort = Event()
    observation = {}

    def worker(label, request):
        checkpoint(f"overlap_{label}_open")
        with transport.session(label, principal="editor") as session:
            binding = session.binding()
            require(binding["ordinary_role"] is True and binding["owner"] is False and binding["superuser"] is False, "overlap_privileged_session")
            require(binding.get("session_ref") == session_refs[label], "overlap_session_binding_mismatch")
            supervisor.bind_session(session_refs[label], binding)
            transport.append_receipt({"phase": "session_open", "label": label, "binding": binding})
            if label == "B":
                require(first_locked.wait(0.5) and not abort.is_set(), "overlap_A_lock_unavailable")
            started = monotonic()

            def before_commit():
                checkpoint(f"overlap_{label}_before_commit")
                if label == "A":
                    first_locked.set()
                    evidence = session.observe_waiter("B", timeout_seconds=0.5)
                    require(evidence["server_observed"] is True and evidence["blocked_on_this_transaction"] is True, "overlap_not_server_observed")
                    require(evidence["backend_pid"] != binding["backend_pid"], "overlap_same_backend")
                    observation.update(evidence)
                    transport.append_receipt({"phase": "overlap_observed", "evidence": evidence})

            try:
                outcome = session.request(request, before_commit=before_commit)
                require(outcome["durable"] is True, "overlap_outcome_not_durable")
                visible = session.read_committed(outcome["hypothesis_id"])
                transport.append_receipt({"phase": "request_finished", "label": label, "request": request, "outcome": outcome})
                return {"binding": binding, "started": started, "finished": monotonic(), "outcome": outcome, "visible": visible}
            except BaseException:
                abort.set()
                first_locked.set()
                raise

    deadline = min(supervisor.deadline, monotonic() + 10)
    first_future = supervisor.submit("overlap_A", lambda: worker("A", first))
    second_future = supervisor.submit("overlap_B", lambda: worker("B", second))
    try:
        results = (supervisor.await_result(first_future, deadline=deadline), supervisor.await_result(second_future, deadline=deadline))
    except BaseException:
        supervisor.stop.set()
        abort.set()
        first_locked.set()
        raise
    require(bool(observation), "overlap_receipt_missing")
    require(results[0]["binding"]["backend_pid"] != results[1]["binding"]["backend_pid"], "overlap_same_session")
    require(results[0]["binding"]["transaction_id"] != results[1]["binding"]["transaction_id"], "overlap_same_transaction")
    require(results[1]["started"] < results[0]["finished"], "serial_requests_not_overlap")
    require(results[0]["visible"] == results[1]["visible"], "committed_cross_session_visibility_mismatch")
    return results


def execute_preserving_cases(*, receipts, verifier, transport, run_id, actual):
    """Real assertions/orchestration; authenticated verifier and installed adapter are absent now."""
    from rms.hypothesis_preserving_runner import MANIFEST, MANIFEST_SHA256, RunnerHeld, assess_prerequisites
    from rms.hypothesis_source_identity import observe_source
    report = assess_prerequisites(receipts)
    if not report.db_access_permitted:
        raise RunnerHeld("HOLD: metadata comparison is not authenticated execution approval.")
    started = monotonic()
    session_refs = dict(zip(("A", "B"), receipts["concurrency"]["session_refs"]))
    supervisor = BoundedSupervisor(started + MANIFEST["stop_policy"]["wall_seconds"] - 2, session_refs=session_refs.values())
    phase = "preflight"

    def checkpoint(current_phase):
        nonlocal phase
        phase = current_phase
        require(not supervisor.stop.is_set(), "dispatch_stopped")
        require(monotonic() - started < MANIFEST["stop_policy"]["wall_seconds"], "wall_limit_stop")
        require(observe_source() == actual, "source_changed_during_run")
        supervisor.call("authority", lambda: verifier.require_active(
            receipts=receipts, candidate=actual, manifest_sha256=MANIFEST_SHA256,
            scope="preserving_db_execution", run_id=run_id, phase=phase,
        ))
        supervisor.call("target_binding", lambda: transport.require_bound_ordinary_target(receipts, phase=phase))
        supervisor.call("limits", lambda: transport.require_limits_and_durable_sink(MANIFEST["stop_policy"]))

    def operation(name, action):
        checkpoint(name)
        return supervisor.call(name, action)

    ids = fixture_ids(run_id)
    binding = {
        "candidate": actual, "manifest_sha256": MANIFEST_SHA256, "run_id": run_id,
        "fixture_ids": ids, "physical_mappings_sha256": receipts["schema"].get("physical_mappings_sha256"),
    }
    baseline_ack = None
    baseline_sha256 = None
    plan = None
    try:
        checkpoint("preflight")
        require(isinstance(receipts["coordination"].get("handoff_ref"), str) and bool(receipts["coordination"]["handoff_ref"]), "reconciliation_reference_missing")
        supervisor.call("physical_mappings", lambda: verifier.require_physical_mappings(binding=binding, receipts=receipts))
        plan = freeze_effect_plan(receipts.get("effect_plan"), binding=binding, record_limit=MANIFEST["stop_policy"]["record_limit"])
        supervisor.call("effect_plan_review", lambda: verifier.require_reviewed_effect_plan(reference=plan.reference, sha256=plan.sha256, binding=binding, receipts=receipts))
        baseline = freeze_preservation_baseline(operation("baseline_snapshot", transport.snapshot_full_preservation_inventory))
        baseline_sha256 = baseline.sha256
        baseline_ack = require_durable_ack(
            operation("baseline_persist", lambda: transport.persist_restricted_baseline(baseline.contents(), sha256=baseline_sha256, binding=binding)),
            sha256=baseline_sha256, binding=binding, code="baseline_not_durable",
        )
        supervisor.call("baseline_ack_verification", lambda: verifier.require_durable_baseline(acknowledgement=baseline_ack, binding=binding, receipts=receipts))
        checkpoint("invented_context")
        context = supervisor.call("invented_context", lambda: transport.create_invented_context_through_shared_services(ids, key_prefix=f"{run_id}:fixture"))
        require(context["ids"] == ids, "fixture_ids_or_sequence_free_factory_unavailable")
        require(context["assessment_truthful_manual"] is True and context["case_state"] == "proposed", "fabricated_or_approved_context")
        payload = {
            "originating_idea_version_id": ids["idea-v1"],
            "origin_rationale": "Invented overlap scenario, not research evidence.",
            "investigation_version_id": ids["case-v1"],
            "idea_family_binding": {"mode": "existing", "association_version_id": ids["idea-family-v1"]},
            "fields": {"title": "Invented overlap draft"},
        }
        create = {"operation": "create_hypothesis", "key": f"{run_id}:P06:create", "payload": payload}
        created = coordinated_requests(transport, create, deepcopy(create), checkpoint, supervisor, session_refs)
        require(created[0]["outcome"]["status"] == created[1]["outcome"]["status"] == 201, "create_not_original_201_replay")
        require(created[0]["outcome"]["response_bytes"] == created[1]["outcome"]["response_bytes"], "idempotent_replay_response_changed")
        require(created[0]["outcome"]["hypothesis_id"] == ids["hypothesis"], "hypothesis_fixture_identity_mismatch")
        hypothesis_id = ids["hypothesis"]
        checkpoint("conflicting_key")
        conflicting = deepcopy(create)
        conflicting["payload"]["fields"]["title"] = "Invented conflicting reuse"
        conflict = operation("conflicting_request", lambda: transport.request_as("editor", conflicting))
        require(conflict["status"] == 409 and conflict["error_code"] == "idempotency_conflict", "changed_key_payload_not_rejected")
        require(conflict["research_additions"] == [], "conflicting_key_partial_write")

        corrections = []
        fields = {name: None for name in operation("schema_fields", transport.reviewed_schema_field_names)}
        for label in ("A", "B"):
            correction = deepcopy(payload)
            correction.update(expected_latest_version=1, correction_reason=f"Invented {label} change")
            correction["fields"] = {**fields, "title": f"Invented correction {label}"}
            corrections.append({"operation": "correct_hypothesis", "hypothesis_id": hypothesis_id, "key": f"{run_id}:P06:correct:{label}", "payload": correction})
        corrected = coordinated_requests(transport, *corrections, checkpoint, supervisor, session_refs)
        require(corrected[0]["outcome"]["status"] == 201, "correction_A_not_saved")
        require(corrected[1]["outcome"]["status"] == 409 and corrected[1]["outcome"]["error_code"] == "stale_version", "correction_B_not_stale")
        require(corrected[1]["outcome"]["research_additions"] == [], "stale_correction_partial_write")
        no_change = deepcopy(corrections[0])
        no_change["key"] = f"{run_id}:P06:nochange"
        no_change["payload"]["expected_latest_version"] = 2
        checkpoint("no_change")
        unchanged = operation("no_change_request", lambda: transport.request_as("editor", no_change))
        require(unchanged["status"] == 200 and unchanged["research_additions"] == [], "no_change_created_version")

        checkpoint("rights_and_history")
        for request in (create, corrections[0]):
            denied = operation("viewer_request", lambda: transport.request_as("viewer", request))
            require(denied["status"] == 403 and denied["research_additions"] == [], "viewer_write_or_partial_effect")
        history = operation("history", lambda: transport.exact_hypothesis_history_as("viewer", hypothesis_id))
        require(history["version_ids"] == [ids["hypothesis-v1"], ids["hypothesis-v2"]], "history_not_exact_two_versions")
        require(history["original_endpoint_ids"] == [ids["idea-v1"], ids["case-v1"]], "history_endpoint_retargeted")
        require(history["workflow_states"] == ["draft", "draft"], "research_state_escalated")
        require(history["original_version_digest"] == created[0]["visible"]["version_digest"], "original_version_rewritten")
        operation("immutable_denials", lambda: transport.assert_every_mapped_immutable_denial(probe_immutable_row))
        checkpoint("preservation")
        effects = operation("effect_observations", transport.actual_service_effect_inventory)
        require(effects["contract_assertions"] == {"single_origin": True, "exact_context_fks": True, "no_orphans": True, "one_hypothesis": True, "two_versions": True, "no_unapproved_effects": True}, "association_or_write_inventory_incomplete")
        expected = plan.contents()
        assert_preservation(baseline.contents(), operation("final_snapshot", transport.snapshot_full_preservation_inventory), expected["additions"], expected["projections"])
        operation("finished_receipt", lambda: transport.append_receipt({"phase": "finished", "run_id": run_id, "disposition": "observations_require_independent_review", "baseline_ack": baseline_ack, "effect_plan_ref": plan.reference, "session_state": supervisor.state()}))
        return {"disposition": "observations_require_independent_review", "run_id": run_id}
    except BaseException as primary:
        preserving_failure_handoff(primary, supervisor=supervisor, transport=transport, context={
            "phase": phase, "run_id": run_id, "binding": binding, "baseline_ack": baseline_ack,
            "baseline_sha256": baseline_sha256, "effect_plan_ref": plan.reference if plan else None,
            "effect_plan_sha256": plan.sha256 if plan else None,
            "request_keys": [f"{run_id}:fixture", f"{run_id}:P06:create", f"{run_id}:P06:correct:A", f"{run_id}:P06:correct:B", f"{run_id}:P06:nochange"],
            "reconciliation_ref": receipts.get("coordination", {}).get("handoff_ref"),
        })
        raise
