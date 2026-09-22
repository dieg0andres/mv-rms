"""Shared Source workflow rules used by every RMS-VS-1 API write/read."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from django.db import DatabaseError, connection, transaction

from .models import IdempotencyRecord, Source, SourceManifest
from .models import SourceVersion as StoredSourceVersion
from .source_manifests import generate_source_manifest
from .source_versions import SourceVersion as DomainSourceVersion


class SourceServiceError(Exception):
    code = "conflict"
    safe_message = "The request conflicts with current Source state."


class SourceNotFound(SourceServiceError):
    code = "not_found"
    safe_message = "Source not found."


class SourceConflict(SourceServiceError):
    pass


class IdempotencyConflict(SourceConflict):
    safe_message = "The idempotency key was already used for a different request."


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status: int
    body: bytes


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def create_source(
    *, source_id: str, content: bytes, idempotency_key: str, request_path: str
) -> StoredResponse:
    canonical_request = {
        "content_base64": _canonical_base64(content),
        "source_id": source_id,
        "synthetic": True,
    }
    request_digest = _request_digest("POST", request_path, canonical_request)

    with transaction.atomic():
        _lock_idempotency_key(idempotency_key)
        replay = _replay_or_conflict(idempotency_key, request_digest)
        if replay is not None:
            return replay
        if Source.objects.filter(source_id=source_id).exists():
            raise SourceConflict("Source identity already exists")

        try:
            source = Source.objects.create(source_id=source_id, synthetic=True)
            StoredSourceVersion.objects.create(
                source=source,
                version=1,
                corrects_version=None,
                content=content,
                synthetic=True,
            )
            source.refresh_from_db()
            _create_manifest(source)
        except DatabaseError as error:
            raise SourceConflict("database rejected Source creation") from error

        body = canonical_json_bytes(source_detail(source))
        _store_idempotency(
            key=idempotency_key,
            request_path=request_path,
            request_digest=request_digest,
            response_identity=source_id,
            response_body=body,
        )
        return StoredResponse(201, body)


def correct_source(
    *,
    source_id: str,
    content: bytes,
    expected_latest_version: int,
    idempotency_key: str,
    request_path: str,
) -> StoredResponse:
    canonical_request = {
        "content_base64": _canonical_base64(content),
        "expected_latest_version": expected_latest_version,
        "synthetic": True,
    }
    request_digest = _request_digest("POST", request_path, canonical_request)

    with transaction.atomic():
        _lock_idempotency_key(idempotency_key)
        replay = _replay_or_conflict(idempotency_key, request_digest)
        if replay is not None:
            return replay
        try:
            source = Source.objects.select_for_update().get(source_id=source_id)
        except Source.DoesNotExist as error:
            raise SourceNotFound from error
        if source.latest_version != expected_latest_version:
            raise SourceConflict("stale expected latest version")

        next_version = source.latest_version + 1
        try:
            StoredSourceVersion.objects.create(
                source=source,
                version=next_version,
                corrects_version=source.latest_version,
                content=content,
                synthetic=True,
            )
            source.refresh_from_db()
            _create_manifest(source)
        except DatabaseError as error:
            raise SourceConflict("database rejected Source correction") from error

        body = canonical_json_bytes(source_detail(source))
        _store_idempotency(
            key=idempotency_key,
            request_path=request_path,
            request_digest=request_digest,
            response_identity=source_id,
            response_body=body,
        )
        return StoredResponse(201, body)


def get_source(source_id: str) -> Source:
    try:
        return Source.objects.get(source_id=source_id)
    except Source.DoesNotExist as error:
        raise SourceNotFound from error


def source_detail(source: Source) -> dict[str, Any]:
    latest = source.versions.get(version=source.latest_version)
    return {
        "source_id": source.source_id,
        "synthetic": source.synthetic,
        "latest_version": source.latest_version,
        "created_at": _timestamp(source.created_at),
        "latest": version_representation(latest),
    }


def source_history(source: Source) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "versions": [
            version_representation(version)
            for version in source.versions.order_by("version")
        ],
    }


def version_representation(version: StoredSourceVersion) -> dict[str, Any]:
    return {
        "version": version.version,
        "corrects_version": version.corrects_version,
        "synthetic": version.synthetic,
        "byte_length": version.byte_length,
        "content_sha256": version.content_sha256,
        "created_at": _timestamp(version.created_at),
    }


def latest_manifest(source: Source) -> SourceManifest:
    try:
        return source.manifests.get(through_version=source.latest_version)
    except SourceManifest.DoesNotExist as error:
        raise SourceConflict("manifest is missing for latest Source version") from error


def _create_manifest(source: Source) -> SourceManifest:
    stored_versions = tuple(source.versions.order_by("version"))
    domain_versions = tuple(
        DomainSourceVersion(
            source_id=source.source_id,
            version=version.version,
            content=bytes(version.content),
            synthetic=version.synthetic,
            corrects_version=version.corrects_version,
        )
        for version in stored_versions
    )
    manifest_bytes = generate_source_manifest(domain_versions)
    return SourceManifest.objects.create(
        source=source,
        through_version=source.latest_version,
        schema_version=1,
        version_count=source.latest_version,
        manifest_bytes=manifest_bytes,
    )


def _request_digest(method: str, path: str, request: object) -> str:
    canonical = canonical_json_bytes({"method": method, "path": path, "request": request})
    return hashlib.sha256(canonical).hexdigest()


def _canonical_base64(content: bytes) -> str:
    import base64

    return base64.b64encode(content).decode("ascii")


def _lock_idempotency_key(key: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [key])


def _replay_or_conflict(key: str, request_digest: str) -> StoredResponse | None:
    try:
        record = IdempotencyRecord.objects.get(key=key)
    except IdempotencyRecord.DoesNotExist:
        return None
    if record.request_sha256 != request_digest:
        raise IdempotencyConflict
    return StoredResponse(record.response_status, bytes(record.response_bytes))


def _store_idempotency(
    *,
    key: str,
    request_path: str,
    request_digest: str,
    response_identity: str,
    response_body: bytes,
) -> None:
    IdempotencyRecord.objects.create(
        key=key,
        request_method="POST",
        request_path=request_path,
        request_sha256=request_digest,
        response_status=201,
        response_identity=response_identity,
        response_bytes=response_body,
    )


def _timestamp(value) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
