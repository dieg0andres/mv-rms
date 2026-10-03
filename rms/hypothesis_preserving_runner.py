"""Inert preserving-runner proposal and database-free prerequisite assessment."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from rms.hypothesis_validation import SCHEMA_SHA256


MANIFEST_PATH = Path(__file__).with_name("hypothesis_runner_manifest.json")
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
MANIFEST_SHA256 = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
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


def assess_prerequisites(receipts=None, *, now=None, manifest=None):
    """Inspect supplied metadata only, never attest facts or release execution."""
    manifest = MANIFEST if manifest is None else manifest
    receipts = manifest["required_receipts"] if receipts is None else receipts
    now = datetime.now(timezone.utc) if now is None else now
    findings = []

    def hold(code, owner, action):
        findings.append(GuardFinding(code, owner, action))

    if not isinstance(receipts, dict):
        receipts = {}
        hold("invalid_receipts", "Director", "Supply reviewed metadata receipts, never credentials.")
    if manifest.get("source_only") is not True or manifest.get("disposition") != "HOLD":
        hold("manifest_not_source_only", "Director", "Retain the accepted source-only boundary.")
    if manifest.get("schema_sha256") != SCHEMA_SHA256:
        hold("schema_pin_mismatch", "Backend", "Reconcile exact schema/proposal identity through Director.")
    if set(manifest.get("prohibited_operations", [])) != FORBIDDEN:
        hold("preservation_policy_mismatch", "Director", "Preserve every prohibited lifecycle/mutation operation.")

    expected_target = MANIFEST["target"]
    target = manifest.get("target", {})
    if target.get("database") != expected_target["database"] or target.get("environment_id") != expected_target["environment_id"]:
        hold("target_mismatch", "Operations", "Use only the existing authorized target/environment; no alternate resource.")
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

    authority = receipt("authority")
    if authority.get("scope") != "preserving_db_execution" or authority.get("status") != "accepted" or authority.get("revoked") is not False:
        hold("execution_authority_missing", "Director", "Resolve the separately held exact execution decision through VP; source approval is not DB authority.")
    if authority.get("target") != target.get("database") or authority.get("schema_sha256") != SCHEMA_SHA256:
        hold("authority_target_or_schema_mismatch", "Director", "Bind any later release to this exact reviewed target and schema.")
    try:
        expiry = datetime.fromisoformat(authority.get("expires_at", ""))
        active = expiry.tzinfo is not None and now.tzinfo is not None and expiry > now
    except (TypeError, ValueError):
        active = False
    if not active:
        hold("authority_expired_or_unknown", "Director", "Confirm a current nonrevoked exact authority record; fail closed meanwhile.")

    schema = receipt("schema")
    if schema.get("installed") is not True or schema.get("candidate_commit") is None or not schema.get("migration_versions") or schema.get("schema_sha256") != SCHEMA_SHA256:
        hold("schema_unavailable", "Operations", "Identify an existing reviewed installed schema, candidate and migrations; no migration in this assignment.")
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
    """Proposal only: deliberately no DB lifecycle or execution implementation."""

    def run(self, *args, **kwargs):
        raise RunnerHeld("HOLD: source-only proposal; no runner invocation or DB execution authorized.")
