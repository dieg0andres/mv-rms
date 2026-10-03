"""Local source observations, not authentication of installed target evidence."""

import ast
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_MODELS = (
    "Hypothesis", "HypothesisVersion", "ResearchFamily", "ResearchFamilyVersion",
    "Investigation", "InvestigationVersion", "PriorResearchAssessment",
    "PriorResearchAssessmentVersion", "IdeaFamily", "InvestigationFamily",
    "PriorResearchInvestigation", "HypothesisInvestigation", "IdeaHypothesis",
    "AssessmentRecord", "CorrectionImpact",
)
REQUIRED_SERVICES = (
    "create_hypothesis", "correct_hypothesis", "get_hypothesis",
    "get_hypothesis_history", "create_research_family", "correct_research_family",
    "create_investigation", "correct_investigation", "correct_idea_family_association",
)
SOURCE_PATHS = (
    "requirements.lock", "rms/models.py", "rms/services.py", "rms/permissions.py",
    "rms/hypothesis_schema.json", "rms/hypothesis_validation.py",
    "rms/hypothesis_source_identity.py", "rms/hypothesis_preserving_runner.py",
    "rms/hypothesis_preserving_harness.py", "rms/hypothesis_runner_manifest.json",
    "docs/RMS-HN-API-1.md", "docs/RMS-HN-BACKEND-RUNNER.md",
    "tests/django_hypothesis_backend_runner_guard_tests.py",
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def valid_hex(value, length):
    return isinstance(value, str) and len(value) == length and all(character in "0123456789abcdef" for character in value)


def _git(*arguments):
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), *arguments], check=True, capture_output=True,
            text=True, timeout=5,
        ).stdout.strip()
    except subprocess.SubprocessError as error:
        raise ValueError("local_git_identity_unavailable") from error


def observe_source():
    migrations = sorted((ROOT / "rms/migrations").glob("[0-9]*.py"))
    paths = (*SOURCE_PATHS, *(str(path.relative_to(ROOT)) for path in migrations))
    files = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}
    model_names = {node.name for node in ast.parse((ROOT / "rms/models.py").read_text()).body if isinstance(node, ast.ClassDef)}
    service_names = {node.name for node in ast.parse((ROOT / "rms/services.py").read_text()).body if isinstance(node, ast.FunctionDef)}
    missing = [f"model:{name}" for name in REQUIRED_MODELS if name not in model_names]
    missing.extend(f"service:{name}" for name in REQUIRED_SERVICES if name not in service_names)
    schema = {
        "api_schema_sha256": files["rms/hypothesis_schema.json"],
        "migration_sha256": {str(path.relative_to(ROOT)): files[str(path.relative_to(ROOT))] for path in migrations},
        "models_sha256": files["rms/models.py"],
        "services_sha256": files["rms/services.py"],
        "required_models": list(REQUIRED_MODELS),
        "required_services": list(REQUIRED_SERVICES),
    }
    lock = (ROOT / "requirements.lock").read_bytes()
    return {
        "candidate_commit": _git("rev-parse", "HEAD"),
        "candidate_tree": _git("rev-parse", "HEAD^{tree}"),
        "tracked_changes": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "file_sha256": files,
        "schema": schema,
        "schema_signature": digest(schema),
        "additive_capabilities_missing": missing,
        "requirements_sha256": hashlib.sha256(lock).hexdigest(),
        "requirements_bytes": len(lock),
    }


def compare_source_evidence(receipts, actual):
    """Compare external claims to observed bytes; matching claims grant no authority."""
    codes = []
    if not isinstance(receipts, dict):
        codes.append("invalid_receipts")
        receipts = {}
    runtime = receipts.get("runtime_identity")
    if not isinstance(runtime, dict):
        codes.append("runtime_candidate_missing")
        runtime = {}
    for key in ("candidate_commit", "runtime_candidate_commit"):
        value = runtime.get(key)
        if not valid_hex(value, 40):
            codes.append(f"{key}_invalid")
        elif value != actual["candidate_commit"]:
            codes.append(f"{key}_mismatch")
    if runtime.get("candidate_tree") != actual["candidate_tree"]:
        codes.append("candidate_tree_mismatch")
    if runtime.get("file_sha256") != actual["file_sha256"]:
        codes.append("executable_source_mismatch")
    if actual["tracked_changes"]:
        codes.append("executable_source_dirty")

    schema = receipts.get("schema")
    if not isinstance(schema, dict):
        codes.append("installed_schema_missing")
        schema = {}
    if not valid_hex(schema.get("candidate_commit"), 40):
        codes.append("installed_schema_candidate_invalid")
    elif schema["candidate_commit"] != actual["candidate_commit"]:
        codes.append("installed_schema_candidate_mismatch")
    if schema.get("installed") is not True:
        codes.append("installed_schema_unobserved")
    if not valid_hex(schema.get("schema_signature"), 64):
        codes.append("installed_schema_signature_invalid")
    elif schema["schema_signature"] != actual["schema_signature"]:
        codes.append("installed_schema_signature_mismatch")
    if schema.get("required_schema") != actual["schema"]:
        codes.append("candidate_required_schema_mismatch")
    if schema.get("migration_sha256") != actual["schema"]["migration_sha256"]:
        codes.append("installed_migration_signature_mismatch")
    if actual["additive_capabilities_missing"]:
        codes.append("candidate_additive_schema_unavailable")

    dependency = receipts.get("dependency")
    if not isinstance(dependency, dict):
        codes.append("dependency_evidence_missing")
        dependency = {}
    for key in ("approved_lock_sha256", "runtime_lock_sha256"):
        value = dependency.get(key)
        if not valid_hex(value, 64):
            codes.append(f"{key}_invalid")
        elif value != actual["requirements_sha256"]:
            codes.append(f"{key}_mismatch")
    if dependency.get("candidate_commit") != actual["candidate_commit"]:
        codes.append("dependency_candidate_mismatch")
    size = dependency.get("requirements_bytes")
    if type(size) is not int or size != actual["requirements_bytes"]:
        codes.append("dependency_lock_size_mismatch")
    return tuple(codes)
