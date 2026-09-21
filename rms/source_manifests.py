"""Deterministic evidence manifests for accepted synthetic Source versions."""

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from .source_versions import SourceVersion


SOURCE_MANIFEST_SCHEMA_VERSION = 1

_MANIFEST_KEYS = frozenset(("schema_version", "versions"))
_ENTRY_KEYS = frozenset(
    (
        "byte_length",
        "content_sha256",
        "corrects_version",
        "source_id",
        "synthetic",
        "version",
    )
)


class SourceManifestError(ValueError):
    """Base error for Source evidence manifest operations."""


class SourceManifestVerificationError(SourceManifestError):
    """Raised when a Source evidence manifest fails closed."""


def generate_source_manifest(versions: Iterable[SourceVersion]) -> bytes:
    """Return canonical UTF-8 JSON bytes for one Source's accepted versions."""
    accepted_versions = tuple(versions)
    _validate_accepted_versions(accepted_versions)
    manifest = {
        "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
        "versions": [_entry_for_version(version) for version in accepted_versions],
    }
    return _canonical_json_bytes(manifest)


def source_manifest_digest(manifest_bytes: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 of exact manifest bytes."""
    if type(manifest_bytes) is not bytes:
        raise SourceManifestError("manifest must be bytes")
    return hashlib.sha256(manifest_bytes).hexdigest()


def verify_source_manifest(
    manifest_bytes: bytes,
    manifest_digest: str,
    accepted_versions: Iterable[SourceVersion],
) -> None:
    """Verify exact manifest bytes and digest against accepted Source versions."""
    if type(manifest_bytes) is not bytes:
        raise SourceManifestVerificationError("manifest must be bytes")
    if (
        not isinstance(manifest_digest, str)
        or manifest_digest != source_manifest_digest(manifest_bytes)
    ):
        raise SourceManifestVerificationError("manifest digest mismatch")

    manifest = _decode_manifest(manifest_bytes)
    _validate_manifest_schema(manifest)
    if _canonical_json_bytes(manifest) != manifest_bytes:
        raise SourceManifestVerificationError("manifest is not canonical JSON")

    try:
        expected_manifest = generate_source_manifest(tuple(accepted_versions))
    except SourceManifestError as error:
        raise SourceManifestVerificationError(
            "supplied accepted Source versions are invalid"
        ) from error

    if manifest_bytes != expected_manifest:
        raise SourceManifestVerificationError(
            "manifest does not match accepted Source versions"
        )


def _entry_for_version(version: SourceVersion) -> dict[str, object]:
    return {
        "source_id": version.source_id,
        "version": version.version,
        "corrects_version": version.corrects_version,
        "synthetic": version.synthetic,
        "byte_length": len(version.content),
        "content_sha256": hashlib.sha256(version.content).hexdigest(),
    }


def _validate_accepted_versions(versions: tuple[SourceVersion, ...]) -> None:
    if not versions:
        raise SourceManifestError("at least one Source version is required")

    source_id: str | None = None
    for index, version in enumerate(versions, start=1):
        if not isinstance(version, SourceVersion):
            raise SourceManifestError("every accepted version must be a SourceVersion")
        if not isinstance(version.source_id, str) or not version.source_id:
            raise SourceManifestError("source_id must be a non-empty string")
        if source_id is None:
            source_id = version.source_id
        elif version.source_id != source_id:
            raise SourceManifestError("all versions must use one stable source_id")
        if type(version.version) is not int or version.version != index:
            raise SourceManifestError("versions must be ordered, unique, and contiguous")
        expected_correction = None if index == 1 else index - 1
        if version.corrects_version != expected_correction:
            raise SourceManifestError("correction links must reference the prior version")
        if version.synthetic is not True:
            raise SourceManifestError("all versions must be explicitly synthetic")
        if type(version.content) is not bytes:
            raise SourceManifestError("Source content must be bytes")


def _decode_manifest(manifest_bytes: bytes) -> Any:
    try:
        return json.loads(
            manifest_bytes.decode("utf-8"), object_pairs_hook=_unique_json_object
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceManifestVerificationError("manifest is not valid UTF-8 JSON") from error


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SourceManifestVerificationError(
                f"manifest contains duplicate JSON key {key!r}"
            )
        result[key] = value
    return result


def _validate_manifest_schema(manifest: Any) -> None:
    if not isinstance(manifest, dict) or frozenset(manifest) != _MANIFEST_KEYS:
        raise SourceManifestVerificationError("manifest has malformed top-level schema")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise SourceManifestVerificationError("unsupported manifest schema version")

    entries = manifest["versions"]
    if not isinstance(entries, list) or not entries:
        raise SourceManifestVerificationError("manifest versions must be a non-empty list")

    source_id: str | None = None
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or frozenset(entry) != _ENTRY_KEYS:
            raise SourceManifestVerificationError("manifest version entry is malformed")
        if not isinstance(entry["source_id"], str) or not entry["source_id"]:
            raise SourceManifestVerificationError("manifest source_id is malformed")
        if source_id is None:
            source_id = entry["source_id"]
        elif entry["source_id"] != source_id:
            raise SourceManifestVerificationError("manifest source identity changed")
        if type(entry["version"]) is not int or entry["version"] != index:
            raise SourceManifestVerificationError(
                "manifest versions are missing, reordered, or duplicated"
            )
        expected_correction = None if index == 1 else index - 1
        if entry["corrects_version"] != expected_correction:
            raise SourceManifestVerificationError(
                "manifest correction link does not reference the prior version"
            )
        if entry["synthetic"] is not True:
            raise SourceManifestVerificationError("manifest version is not synthetic")
        if type(entry["byte_length"]) is not int or entry["byte_length"] < 0:
            raise SourceManifestVerificationError("manifest byte length is malformed")
        content_sha256 = entry["content_sha256"]
        if (
            not isinstance(content_sha256, str)
            or len(content_sha256) != 64
            or any(character not in "0123456789abcdef" for character in content_sha256)
        ):
            raise SourceManifestVerificationError("manifest content digest is malformed")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

