"""DB-free prerequisite assessment and gated preserving-harness entry point."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from rms.hypothesis_validation import SCHEMA_SHA256
from rms.hypothesis_source_identity import compare_source_evidence, observe_source


MANIFEST_PATH = Path(__file__).with_name("hypothesis_runner_manifest.json")
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
MANIFEST_SHA256 = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
_DEFAULT_MANIFEST = object()
FORBIDDEN = frozenset({
    "create_database", "drop_database", "reset", "flush", "truncate",
    "delete_existing", "update_existing", "cleanup", "role_create",
    "role_grant", "migration", "fixture_loader",
})


@dataclass(frozen=True)
class GuardFinding:
    code: str
    owner: str
    action: str


@dataclass(frozen=True)
class GuardReport:
    disposition: str
    db_access_permitted: bool
    findings: tuple[GuardFinding, ...]


class RunnerHeld(RuntimeError):
    pass


def assess_prerequisites(receipts=None, *, now=None, manifest=_DEFAULT_MANIFEST):
    """Inspect supplied metadata only, never attest facts or release execution."""
    findings = []

    def hold(code, owner, action):
        findings.append(GuardFinding(code, owner, action))

    manifest = MANIFEST if manifest is _DEFAULT_MANIFEST else manifest
    if not isinstance(manifest, dict):
        hold("invalid_manifest", "Backend", "Supply the exact reviewed object manifest; do not execute it.")
        manifest = {}
    receipts = manifest.get("required_receipts") if receipts is None else receipts
    now = datetime.now(timezone.utc) if now is None else now
    time_valid = isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None
    if not time_valid:
        hold("invalid_time_metadata", "Director", "Supply a timezone-aware assessment time; no authority is inferred.")
    if not isinstance(receipts, dict):
        receipts = {}
        hold("invalid_receipts", "Director", "Supply reviewed metadata receipts, never credentials.")
    if manifest.get("source_only") is not True or manifest.get("disposition") != "HOLD":
        hold("manifest_not_source_only", "Director", "Retain the accepted source-only boundary.")
    if manifest.get("schema_sha256") != SCHEMA_SHA256:
        hold("schema_pin_mismatch", "Backend", "Reconcile exact schema/proposal identity through Director.")
    operations = manifest.get("prohibited_operations")
    if not isinstance(operations, list) or not all(isinstance(operation, str) for operation in operations) or set(operations) != FORBIDDEN:
        hold("preservation_policy_mismatch", "Director", "Preserve every prohibited lifecycle/mutation operation.")
    for name in ("fixture_policy", "sequence_policy", "coordination_policy", "lifecycle_policy", "source_identity", "stop_policy"):
        policy = manifest.get(name)
        if not isinstance(policy, dict):
            hold(f"{name}_invalid", "Backend", "Supply an object policy from the pinned proposal; missing policy stays HOLD.")
        elif policy != MANIFEST[name]:
            hold(f"{name}_mismatch", "Director", "Review changed limits, imports, lifecycle, routing and identity before adoption.")
    if manifest.get("proposal_id") != MANIFEST["proposal_id"] or manifest.get("revision") != MANIFEST["revision"]:
        hold("proposal_identity_mismatch", "Director", "Reject stale or alternate proposal identity; receipt the exact candidate.")

    expected_target = MANIFEST["target"]
    target = manifest.get("target")
    if not isinstance(target, dict):
        hold("invalid_target", "Operations", "Supply the reviewed target object without credentials; never initialize it.")
        target = {}
    if target.get("database") != expected_target["database"] or target.get("environment_id") != expected_target["environment_id"]:
        hold("target_mismatch", "Operations", "Use only the existing authorized target/environment; no alternate resource.")
    if target.get("binding") != expected_target["binding"]:
        hold("target_binding_mismatch", "Operations", "No installed binding is pinned; separately review any proposed binding before use.")
    if not isinstance(target.get("binding"), str) or not target["binding"].strip():
        hold("target_binding_missing", "Operations", "Report the existing secure target binding by name after authorization.")

    def receipt(name):
        value = receipts.get(name)
        if not isinstance(value, dict):
            hold(f"{name}_missing", "Operations" if name in {"schema", "ordinary_role", "principals", "sequence", "preservation"} else "Director", "Provide actual authorized evidence through the existing task; do not emulate it.")
            return {}
        if value.get("synthetic") is not False or not isinstance(value.get("evidence_ref"), str) or not value["evidence_ref"].strip():
            hold(f"{name}_unverified", "Director", "Replace invented/unknown claims with an exact independently reviewed evidence reference.")
        return value

    identity = receipt("runtime_identity")
    try:
        actual = observe_source()
        comparison_codes = compare_source_evidence(receipts, actual)
    except (OSError, ValueError, RuntimeError, SyntaxError):
        comparison_codes = ("local_source_identity_unavailable",)
    for code in comparison_codes:
        hold(code, "Operations" if code.startswith("installed_") else "Backend", "Reconcile independent reviewed evidence with actual candidate bytes; no target authentication is inferred.")
    if "local_source_identity_unavailable" not in comparison_codes and actual["requirements_sha256"] != MANIFEST["requirements_sha256"]:
        hold("requirements_pin_mismatch", "Backend", "Actual requirements.lock bytes differ from the candidate's pinned dependency contract.")
    candidate = identity.get("candidate_commit")
    runtime_codes = {"local_source_identity_unavailable", "runtime_candidate_missing", "candidate_commit_invalid", "candidate_commit_mismatch", "runtime_candidate_commit_invalid", "runtime_candidate_commit_mismatch", "candidate_tree_mismatch", "executable_source_mismatch", "executable_source_dirty"}
    if runtime_codes.intersection(comparison_codes) or not isinstance(candidate, str) or len(candidate) != 40 or any(character not in "0123456789abcdef" for character in candidate) or identity.get("proposal_id") != MANIFEST["proposal_id"] or identity.get("revision") != MANIFEST["revision"]:
        hold("source_identity_unavailable", "Director", "Match the external exact candidate/path/hash receipt; local bytes are not independent adoption.")
    lifecycle = MANIFEST["lifecycle_policy"]
    for name in ("execution_command", "settings_binding", "aliases", "routers", "connections", "requested_operations", "imports", "setup", "teardown", "callbacks"):
        if name not in identity or identity[name] != lifecycle[name]:
            hold(f"routing_or_lifecycle_{name}_unreviewed", "Operations", "Reject indirect setup, cleanup, imports and unbound connections before any mutation; no transport exists here.")

    authority = receipt("authority")
    if authority.get("scope") != "preserving_db_execution" or authority.get("status") != "accepted" or authority.get("revoked") is not False:
        hold("execution_authority_missing", "Director", "Resolve the separately held exact execution decision through VP; source approval is not DB authority.")
    if authority.get("target") != target.get("database") or authority.get("schema_sha256") != SCHEMA_SHA256:
        hold("authority_target_or_schema_mismatch", "Director", "Bind any later release to this exact reviewed target and schema.")
    try:
        expiry_value = authority.get("expires_at")
        expiry = datetime.fromisoformat(expiry_value) if isinstance(expiry_value, str) else None
        active = time_valid and expiry is not None and expiry.tzinfo is not None and expiry.utcoffset() is not None and expiry > now
    except (TypeError, ValueError, OverflowError):
        active = False
    if not active:
        hold("authority_expired_or_unknown", "Director", "Confirm a current nonrevoked exact authority record; fail closed meanwhile.")

    schema = receipt("schema")
    if schema.get("installed") is not True or schema.get("candidate_commit") is None or not schema.get("migration_versions") or schema.get("schema_sha256") != SCHEMA_SHA256:
        hold("schema_unavailable", "Operations", "Identify an existing reviewed installed schema, candidate and migrations; no migration in this assignment.")
    receipt("dependency")
    ordinary_role = receipt("ordinary_role")
    if ordinary_role.get("authorized") is not True or ordinary_role.get("is_owner") is not False or ordinary_role.get("is_superuser") is not False or not ordinary_role.get("binding_ref"):
        hold("ordinary_application_role_unavailable", "Operations", "Report an existing authorized distinct ordinary application-role binding; never create/grant/borrow owner credentials.")
    principals = receipt("principals")
    if not principals.get("editor_ref") or not principals.get("viewer_ref") or principals.get("editor_ref") == principals.get("viewer_ref") or principals.get("authorized") is not True:
        hold("editor_viewer_bindings_unavailable", "Operations", "Verify existing separate authorized editor/viewer principals without creating accounts or changing roles.")
    sequence = receipt("sequence")
    if sequence.get("policy") != "no_sequence_calls" or sequence.get("defaults_triggers_orm_reviewed") is not True or sequence.get("before_after_accounting") is not True:
        hold("sequence_effects_unresolved", "Operations", "Review every implicit sequence path and before/after accounting; transaction rollback does not restore sequences.")
    coordination = receipt("coordination")
    if not coordination.get("reservation_owner") or coordination.get("exclusive") is not True or not coordination.get("handoff_ref") or not coordination.get("release_boundary"):
        hold("coordinated_use_unavailable", "Director", "Reserve single-owner use with actual handoff/release boundaries; task worktrees do not isolate DB sessions.")
    preservation = receipt("preservation")
    if preservation.get("originals_accounts_roles_watermarks") is not True or preservation.get("retained_append_only_additions") is not True or preservation.get("no_cleanup") is not True:
        hold("preservation_procedure_unavailable", "Operations", "Supply reviewed before/after preservation checks, bounded additions and retention; no reset/flush/cleanup.")
    effect_plan = receipt("effect_plan")
    if effect_plan.get("review_status") != "accepted" or not isinstance(effect_plan.get("review_ref"), str) or not effect_plan.get("review_ref") or not isinstance(effect_plan.get("reference"), str) or not effect_plan.get("reference") or not isinstance(effect_plan.get("plan"), dict):
        hold("reviewed_effect_plan_unavailable", "Director", "Supply a separately reviewed run/candidate/manifest/fixture/physical-mapping-bound exact effect plan; observations never define permitted effects.")
    concurrency = receipt("concurrency")
    sessions = concurrency.get("session_refs", [])
    if not isinstance(sessions, list) or len(sessions) != 2 or not all(isinstance(session, str) and session for session in sessions) or len(set(sessions)) != 2 or concurrency.get("committed") is not True or concurrency.get("coordinated") is not True:
        hold("committed_separate_session_proof_unavailable", "Test", "H10/H11 require actual distinct committed-session evidence, not rollback/single-session/keepdb claims.")
    for name, owner in (("operations_review", "Operations"), ("independent_test_review", "Test"), ("director_adoption", "Director")):
        review = receipt(name)
        if review.get("status") != "accepted" or review.get("manifest_sha256") != MANIFEST_SHA256:
            hold(f"{name}_unadopted", owner, "Inspect this exact pinned proposal on the existing task before any later execution.")
    hold("source_only_execution_hold", "Director", "This module cannot authenticate receipts or execute DB work; a separately reviewed execution implementation and release remain required.")
    return GuardReport("HOLD", False, tuple(findings))


class PreservingRunner:
    """Execution gate precedes every transport or fixture operation."""

    def preflight(self, receipts=None):
        return assess_prerequisites(receipts)

    def run(self, *, receipts=None, verifier=None, transport=None, run_id=None):
        report = self.preflight(receipts)
        if not report.db_access_permitted or verifier is None or transport is None:
            raise RunnerHeld("HOLD: independently authenticated execution release, installed additive schema and reviewed transport unavailable.")
        from rms.hypothesis_preserving_harness import execute_preserving_cases
        return execute_preserving_cases(
            receipts=receipts, verifier=verifier, transport=transport, run_id=run_id,
            actual=observe_source(),
        )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Preserving harness; currently source-only/HOLD.")
    parser.add_argument("--phase", choices=("preflight", "run"), required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        receipts = json.loads(arguments.receipts.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(json.dumps({"disposition": "HOLD", "findings": ["receipts_unreadable"]}))
        return 2
    runner = PreservingRunner()
    if arguments.phase == "run":
        try:
            runner.run(receipts=receipts)
        except RunnerHeld:
            print(json.dumps({"disposition": "HOLD", "findings": ["execution_release_or_transport_unavailable"]}))
            return 2
    else:
        report = runner.preflight(receipts)
        print(json.dumps({"disposition": report.disposition, "findings": [finding.code for finding in report.findings]}))
        return 2 if report.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
