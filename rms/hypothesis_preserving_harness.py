"""Executable preserving test-source; no connections, fixture loaders or test DB lifecycle."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import re
from threading import Event
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


def assert_preservation(before, after, expected_additions, expected_projections):
    for name in ("accounts", "roles", "sequences", "volume", "private_route", "evidence_watermarks"):
        require(name in before and before[name] == after.get(name), f"preservation_{name}_changed_or_missing")
    for name in ("rows", "associations", "foreign_keys"):
        require(isinstance(before.get(name), dict) and isinstance(after.get(name), dict), f"preservation_{name}_inventory_missing")
        require(all(after[name].get(key) == value for key, value in before[name].items()), f"preservation_original_{name}_changed")
        appended = {key: value for key, value in after[name].items() if key not in before[name]}
        require(appended == expected_additions[name], f"preservation_unexpected_{name}_effects")
    require(after.get("projections") == expected_projections, "unreviewed_projection_effect")
    require(len(expected_additions["rows"]) <= 100, "record_limit_exceeded")


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


def coordinated_requests(transport, first, second, checkpoint):
    """Two bound sessions; A cannot commit until a server-observed B lock wait."""
    first_locked = Event()
    abort = Event()
    observation = {}

    def worker(label, request):
        checkpoint(f"overlap_{label}_open")
        with transport.session(label, principal="editor") as session:
            binding = session.binding()
            require(binding["ordinary_role"] is True and binding["owner"] is False and binding["superuser"] is False, "overlap_privileged_session")
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

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(worker, "A", first)
        second_future = executor.submit(worker, "B", second)
        try:
            results = (first_future.result(timeout=10), second_future.result(timeout=10))
        except BaseException:
            abort.set()
            first_locked.set()
            transport.cancel_owned_sessions_only()
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

    def checkpoint(phase):
        require(monotonic() - started < MANIFEST["stop_policy"]["wall_seconds"], "wall_limit_stop")
        require(observe_source() == actual, "source_changed_during_run")
        verifier.require_active(
            receipts=receipts, candidate=actual, manifest_sha256=MANIFEST_SHA256,
            scope="preserving_db_execution", run_id=run_id, phase=phase,
        )
        transport.require_bound_ordinary_target(receipts, phase=phase)
        transport.require_limits_and_durable_sink(MANIFEST["stop_policy"])

    checkpoint("preflight")
    ids = fixture_ids(run_id)
    baseline = transport.snapshot_full_preservation_inventory()
    transport.append_receipt({"phase": "baseline", "run_id": run_id, "candidate_commit": actual["candidate_commit"]})
    try:
        checkpoint("invented_context")
        context = transport.create_invented_context_through_shared_services(ids, key_prefix=f"{run_id}:fixture")
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
        created = coordinated_requests(transport, create, deepcopy(create), checkpoint)
        require(created[0]["outcome"]["status"] == created[1]["outcome"]["status"] == 201, "create_not_original_201_replay")
        require(created[0]["outcome"]["response_bytes"] == created[1]["outcome"]["response_bytes"], "idempotent_replay_response_changed")
        require(created[0]["outcome"]["hypothesis_id"] == ids["hypothesis"], "hypothesis_fixture_identity_mismatch")
        hypothesis_id = ids["hypothesis"]
        checkpoint("conflicting_key")
        conflicting = deepcopy(create)
        conflicting["payload"]["fields"]["title"] = "Invented conflicting reuse"
        conflict = transport.request_as("editor", conflicting)
        require(conflict["status"] == 409 and conflict["error_code"] == "idempotency_conflict", "changed_key_payload_not_rejected")
        require(conflict["research_additions"] == [], "conflicting_key_partial_write")

        corrections = []
        fields = {name: None for name in transport.reviewed_schema_field_names()}
        for label in ("A", "B"):
            correction = deepcopy(payload)
            correction.update(expected_latest_version=1, correction_reason=f"Invented {label} change")
            correction["fields"] = {**fields, "title": f"Invented correction {label}"}
            corrections.append({"operation": "correct_hypothesis", "hypothesis_id": hypothesis_id, "key": f"{run_id}:P06:correct:{label}", "payload": correction})
        corrected = coordinated_requests(transport, *corrections, checkpoint)
        require(corrected[0]["outcome"]["status"] == 201, "correction_A_not_saved")
        require(corrected[1]["outcome"]["status"] == 409 and corrected[1]["outcome"]["error_code"] == "stale_version", "correction_B_not_stale")
        require(corrected[1]["outcome"]["research_additions"] == [], "stale_correction_partial_write")
        no_change = deepcopy(corrections[0])
        no_change["key"] = f"{run_id}:P06:nochange"
        no_change["payload"]["expected_latest_version"] = 2
        checkpoint("no_change")
        unchanged = transport.request_as("editor", no_change)
        require(unchanged["status"] == 200 and unchanged["research_additions"] == [], "no_change_created_version")

        checkpoint("rights_and_history")
        for request in (create, corrections[0]):
            denied = transport.request_as("viewer", request)
            require(denied["status"] == 403 and denied["research_additions"] == [], "viewer_write_or_partial_effect")
        history = transport.exact_hypothesis_history_as("viewer", hypothesis_id)
        require(history["version_ids"] == [ids["hypothesis-v1"], ids["hypothesis-v2"]], "history_not_exact_two_versions")
        require(history["original_endpoint_ids"] == [ids["idea-v1"], ids["case-v1"]], "history_endpoint_retargeted")
        require(history["workflow_states"] == ["draft", "draft"], "research_state_escalated")
        require(history["original_version_digest"] == created[0]["visible"]["version_digest"], "original_version_rewritten")
        transport.assert_every_mapped_immutable_denial(probe_immutable_row)
        checkpoint("preservation")
        effects = transport.actual_service_effect_inventory()
        require(effects["contract_assertions"] == {"single_origin": True, "exact_context_fks": True, "no_orphans": True, "one_hypothesis": True, "two_versions": True, "no_unapproved_effects": True}, "association_or_write_inventory_incomplete")
        assert_preservation(baseline, transport.snapshot_full_preservation_inventory(), effects["additions"], effects["reviewed_projections"])
        transport.append_receipt({"phase": "finished", "run_id": run_id, "disposition": "observations_require_independent_review"})
        return {"disposition": "observations_require_independent_review", "run_id": run_id}
    except BaseException:
        transport.cancel_owned_sessions_only()
        transport.append_receipt({"phase": "stopped", "run_id": run_id, "disposition": "FAIL_OR_UNKNOWN_RETAIN_ALL_ADDITIONS"})
        raise
