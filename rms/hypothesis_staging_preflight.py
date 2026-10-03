"""Preserving staging-target preflight for independent Operations/Test review.

CLI is local packet review only. Database preflight requires an already approved
runtime to inject its authenticated release verifier and existing connection.
No default connection, lifecycle runner, migration or fixture operation exists.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re


MANIFEST_PATH = "docs/RMS-HN-INTEGRATED-SOURCE-MANIFEST.json"
CONTRACT_SHA256 = "f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9"
REQUIRED_MIGRATIONS = {"0004_hypothesis_records", "0005_hypothesis_history_guards"}
FORBIDDEN_SECRET_KEYS = {"password", "token", "secret", "dsn", "connection_string", "api_key"}


class PreflightRejected(ValueError):
    """Only a stable non-sensitive code is emitted to ordinary task output."""


def require(condition, code):
    if not condition:
        raise PreflightRejected(code)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def reject_secrets(value):
    if isinstance(value, dict):
        require(not FORBIDDEN_SECRET_KEYS.intersection(str(k).lower() for k in value), "inline_secret_forbidden")
        for item in value.values():
            reject_secrets(item)
    elif isinstance(value, list):
        for item in value:
            reject_secrets(item)


def verify_source(root, expected_manifest_sha256):
    root = Path(root).resolve(strict=True)
    raw = (root / MANIFEST_PATH).read_bytes()
    require(sha256(raw).hexdigest() == expected_manifest_sha256, "source_manifest_mismatch")
    manifest = json.loads(raw)
    require(manifest.get("contract_sha256") == CONTRACT_SHA256, "contract_mismatch")
    require(isinstance(manifest.get("files"), list) and bool(manifest["files"]), "source_inventory_missing")
    seen = set()
    for item in manifest["files"]:
        require(isinstance(item, dict) and isinstance(item.get("path"), str), "source_path_invalid")
        relative = Path(item["path"])
        require(bool(relative.parts) and not relative.is_absolute() and ".." not in relative.parts and relative.parts[0] != ".git", "source_path_invalid")
        require(item["path"] not in seen, "source_path_duplicate")
        seen.add(item["path"])
        path = (root / relative).resolve(strict=True)
        require(path.is_relative_to(root), "source_path_escape")
        data = path.read_bytes()
        require(len(data) == item["bytes"] and sha256(data).hexdigest() == item["sha256"], "source_file_mismatch")
    return manifest


@dataclass(frozen=True)
class ReviewedPacket:
    body: bytes
    sha256: str

    def contents(self):
        return json.loads(self.body)


def review_packet(packet, *, root):
    require(isinstance(packet, dict), "packet_missing")
    reject_secrets(packet)
    target = packet.get("target")
    require(isinstance(target, dict), "target_missing")
    # The earlier rms_synthetic facility cannot stand in for founder-required reuse.
    require(target.get("project") == "mv-rms-staging", "staging_project_mismatch")
    require(target.get("database_container") == "mv-rms-staging-db-1", "staging_container_mismatch")
    require(target.get("database") == "rms_staging", "staging_database_mismatch")
    for name in ("app_container_id", "database_container_id", "volume_id", "private_route_ref", "ordinary_role", "host", "observation_ref"):
        require(isinstance(target.get(name), str) and bool(target[name].strip()), "observed_target_binding_missing")
    require(type(target.get("port")) is int and 0 < target["port"] <= 65535, "target_port_invalid")
    principals = packet.get("principals")
    require(isinstance(principals, dict), "principal_binding_missing")
    for name in ("editor_id", "viewer_id"):
        require(type(principals.get(name)) is int and principals[name] > 0, "principal_binding_missing")
    require(principals["editor_id"] != principals["viewer_id"], "principal_bindings_not_distinct")
    for name in ("operations_review_ref", "test_review_ref", "coordination_slot_ref"):
        require(isinstance(packet.get(name), str) and bool(packet[name].strip()), "review_or_slot_missing")
    pin = packet.get("source_manifest_sha256")
    require(isinstance(pin, str) and re.fullmatch(r"[0-9a-f]{64}", pin) is not None, "source_pin_missing")
    verify_source(root, pin)
    body = json.dumps(packet, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return ReviewedPacket(body, sha256(body).hexdigest())


def execute_read_only_preflight(packet, *, root, authorize, connect):
    """No caller-supplied metadata is itself execution authorization.

    authorize is the existing runtime's independently authenticated verifier;
    connect is its existing approved target adapter, not a packet import/DSN.
    Neither is discovered, installed or defaulted by this module.
    """
    reviewed = review_packet(packet, root=root)
    require(callable(authorize), "authenticated_release_verifier_missing")
    require(callable(connect), "approved_existing_connection_adapter_missing")
    detached = reviewed.contents()
    proof_binding = {
        "packet_sha256": reviewed.sha256,
        "source_manifest_sha256": detached["source_manifest_sha256"],
        "target_digest": digest(detached["target"]),
        "scope": "staging_read_only_preflight",
    }
    proof = authorize(**proof_binding)
    require(isinstance(proof, dict) and proof == {**proof_binding, "verified": True}, "release_verification_failed")
    # Recheck after authorization to reject a source change during review.
    verify_source(root, detached["source_manifest_sha256"])
    session = connect(target=reviewed.contents()["target"], read_only=True)
    try:
        require(session.autocommit is False, "autocommit_connection_forbidden")
        require(session.info.host == detached["target"]["host"] and session.info.port == detached["target"]["port"], "effective_target_address_mismatch")
        with session.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '3000ms'")
            cursor.execute("SET LOCAL lock_timeout = '1000ms'")
            cursor.execute("SELECT current_database(), session_user, current_user, current_setting('transaction_read_only')")
            database, login, role, read_only = cursor.fetchone()
            require(database == detached["target"]["database"], "observed_database_mismatch")
            require(login == role == detached["target"]["ordinary_role"], "observed_role_mismatch")
            require(read_only == "on", "observed_transaction_not_read_only")
            cursor.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            flags = cursor.fetchone()
            require(flags is not None and not any(flags), "privileged_role_forbidden")
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relname ~ '^(rms_|auth_|django_)' AND c.relowner = (SELECT oid FROM pg_roles WHERE rolname = current_user))")
            require(cursor.fetchone() == (False,), "application_schema_owner_forbidden")
            cursor.execute("SELECT name FROM django_migrations WHERE app = %s AND name IN (%s, %s)", ("rms", *sorted(REQUIRED_MIGRATIONS)))
            require({row[0] for row in cursor.fetchall()} == REQUIRED_MIGRATIONS, "installed_additive_schema_missing")
            cursor.execute("SELECT u.id, u.is_active, g.name FROM auth_user u JOIN auth_user_groups ug ON ug.user_id = u.id JOIN auth_group g ON g.id = ug.group_id WHERE u.id IN (%s, %s)", (detached["principals"]["editor_id"], detached["principals"]["viewer_id"]))
            rows = cursor.fetchall()
            editor = {name for identity, active, name in rows if active and identity == detached["principals"]["editor_id"]}
            viewer = {name for identity, active, name in rows if active and identity == detached["principals"]["viewer_id"]}
            require("editor" in editor and "founder_viewer" in viewer and "editor" not in viewer, "observed_principals_invalid")
        return {"packet_sha256": reviewed.sha256, "result": "READ_ONLY_PREFLIGHT_PASS", "writes": [], "acceptance": "No H01-H20, preservation/concurrency or browser result"}
    finally:
        try:
            session.rollback()
        finally:
            session.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Local staging-bound source/packet review; never connects to a database")
    parser.add_argument("--packet", type=Path, required=True)
    args = parser.parse_args()
    try:
        reviewed = review_packet(json.loads(args.packet.read_text()), root=Path(__file__).resolve().parent.parent)
    except (PreflightRejected, OSError, ValueError, KeyError, TypeError) as error:
        code = str(error) if isinstance(error, PreflightRejected) else "packet_or_source_unavailable"
        print(json.dumps({"result": "PACKET_REVIEW_REJECTED", "code": code, "owner": "Operations/Test", "next_action": "Supply the observed existing staging binding and independently reviewed source packet; no access or DB action was performed"}))
        return 2
    print(json.dumps({"result": "LOCAL_PACKET_CONSISTENT", "packet_sha256": reviewed.sha256, "db_execution_authorized": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
