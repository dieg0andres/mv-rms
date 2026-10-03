"""Shared transactional Source and Idea domain services."""

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from django.db import DatabaseError, connection, transaction

from .models import (
    IdempotencyRecord,
    Idea,
    IdeaContribution,
    IdeaVersion,
    Source,
    SourceManifest,
    SourceVersion,
)
from .source_manifests import generate_source_manifest
from .source_versions import SourceVersion as DomainSourceVersion


SOURCE_FIELD_NAMES = (
    "title",
    "source_type",
    "citation",
    "observed_available_at",
    "authors",
    "publisher",
    "published_at",
    "canonical_url",
    "rights_note",
)
IDEA_FIELD_NAMES = (
    "title",
    "mechanism",
    "testable_claim",
    "falsification",
    "eligible_market",
    "workflow_status",
    "rejection_reason",
)


class ServiceError(Exception):
    code = "conflict"
    safe_message = "The request conflicts with current state."


class ResourceNotFound(ServiceError):
    code = "not_found"
    safe_message = "Resource not found."


class SourceNotFound(ResourceNotFound):
    pass


class IdeaNotFound(ResourceNotFound):
    pass


class SourceConflict(ServiceError):
    pass


class IdeaConflict(ServiceError):
    pass


class StaleCorrection(ServiceError):
    code = "stale_correction"
    safe_message = "The correction is based on a stale version."


class IdempotencyConflict(ServiceError):
    code = "idempotency_conflict"
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
    *,
    source_id: str,
    content: bytes,
    fields: dict[str, Any],
    actor: str,
    idempotency_key: str,
    request_path: str,
) -> StoredResponse:
    canonical_request = {
        "source_id": source_id,
        "synthetic": True,
        "content_base64": _canonical_base64(content),
        **_wire_fields(fields, SOURCE_FIELD_NAMES),
    }
    request_digest = _request_digest("POST", request_path, canonical_request)

    with transaction.atomic():
        _lock_idempotency_key(idempotency_key)
        replay = _replay_or_conflict(idempotency_key, request_digest)
        if replay is not None:
            return replay
        if Source.objects.filter(source_id=source_id).exists():
            raise SourceConflict

        try:
            source = Source.objects.create(source_id=source_id, synthetic=True)
            SourceVersion.objects.create(
                source=source,
                version=1,
                corrects_version=None,
                correction_reason=None,
                changed_fields=[],
                content=content,
                synthetic=True,
                created_by=actor,
                **fields,
            )
            source.refresh_from_db()
            _create_manifest(source)
        except DatabaseError as error:
            raise SourceConflict from error

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
    content: bytes | None,
    fields: dict[str, Any],
    actor: str,
    expected_latest_version: int,
    correction_reason: str,
    idempotency_key: str,
    request_path: str,
) -> StoredResponse:
    canonical_request = {
        "synthetic": True,
        "expected_latest_version": expected_latest_version,
        "correction_reason": correction_reason,
        "content_base64": None if content is None else _canonical_base64(content),
        **_wire_fields(fields, SOURCE_FIELD_NAMES),
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
            raise StaleCorrection

        predecessor = source.versions.get(version=source.latest_version)
        next_content = bytes(predecessor.content) if content is None else content
        changed_fields = _changed_fields(predecessor, fields, SOURCE_FIELD_NAMES)
        if next_content != bytes(predecessor.content):
            changed_fields.append("content_sha256")
        changed_fields.sort()

        try:
            SourceVersion.objects.create(
                source=source,
                version=source.latest_version + 1,
                corrects_version=source.latest_version,
                correction_reason=correction_reason,
                changed_fields=changed_fields,
                content=next_content,
                synthetic=True,
                created_by=actor,
                **fields,
            )
            source.refresh_from_db()
            _create_manifest(source)
        except DatabaseError as error:
            raise SourceConflict from error

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


def get_source_version(source_version_id: str) -> SourceVersion:
    try:
        return SourceVersion.objects.select_related("source").get(
            source_version_id=source_version_id
        )
    except SourceVersion.DoesNotExist as error:
        raise SourceNotFound from error


def source_detail(source: Source) -> dict[str, Any]:
    latest = source.versions.get(version=source.latest_version)
    return {
        "source_id": source.source_id,
        "synthetic": source.synthetic,
        "latest_version": source.latest_version,
        "latest_source_version_id": latest.source_version_id,
        "created_at": _timestamp(source.created_at),
        "latest": source_version_representation(latest),
    }


def source_history(source: Source) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "versions": [
            source_version_representation(version)
            for version in source.versions.order_by("version")
        ],
    }


def source_version_representation(version: SourceVersion) -> dict[str, Any]:
    predecessor_id = None
    if version.corrects_version is not None:
        predecessor_id = version.source.versions.only("source_version_id").get(
            version=version.corrects_version
        ).source_version_id
    return {
        "source_version_id": version.source_version_id,
        "version": version.version,
        "corrects_source_version_id": predecessor_id,
        "corrects_version": version.corrects_version,
        "correction_reason": version.correction_reason,
        "changed_fields": version.changed_fields,
        "title": version.title,
        "source_type": version.source_type,
        "citation": version.citation,
        "observed_available_at": _timestamp(version.observed_available_at),
        "authors": version.authors,
        "publisher": version.publisher,
        "published_at": _timestamp(version.published_at),
        "canonical_url": version.canonical_url,
        "rights_note": version.rights_note,
        "synthetic": version.synthetic,
        "byte_length": version.byte_length,
        "content_sha256": version.content_sha256,
        "created_at": _timestamp(version.created_at),
        "created_by": version.created_by,
    }


def manifest_for_version(source: Source, through_version: int | None = None) -> SourceManifest:
    version = source.latest_version if through_version is None else through_version
    try:
        return source.manifests.get(through_version=version)
    except SourceManifest.DoesNotExist as error:
        if 1 <= version <= source.latest_version:
            raise SourceConflict from error
        raise SourceNotFound from error


def latest_manifest(source: Source) -> SourceManifest:
    return manifest_for_version(source)


def create_idea(
    *,
    fields: dict[str, Any],
    contributions: list[dict[str, str]],
    actor: str,
    idempotency_key: str,
    request_path: str,
) -> StoredResponse:
    canonical_request = {
        "synthetic": True,
        **_wire_fields(fields, IDEA_FIELD_NAMES),
        "contributions": contributions,
    }
    request_digest = _request_digest("POST", request_path, canonical_request)

    with transaction.atomic():
        _lock_idempotency_key(idempotency_key)
        replay = _replay_or_conflict(idempotency_key, request_digest)
        if replay is not None:
            return replay
        resolved = _resolve_contributions(contributions)
        try:
            idea = Idea.objects.create(synthetic=True)
            version = IdeaVersion.objects.create(
                idea=idea,
                version=1,
                corrects_version=None,
                correction_reason=None,
                changed_fields=[],
                synthetic=True,
                created_by=actor,
                **fields,
            )
            _create_contributions(version, resolved)
            idea.refresh_from_db()
        except DatabaseError as error:
            raise IdeaConflict from error

        body = canonical_json_bytes(idea_detail(idea))
        _store_idempotency(
            key=idempotency_key,
            request_path=request_path,
            request_digest=request_digest,
            response_identity=idea.idea_id,
            response_body=body,
        )
        return StoredResponse(201, body)


def correct_idea(
    *,
    idea_id: str,
    fields: dict[str, Any],
    contributions: list[dict[str, str]],
    actor: str,
    expected_latest_version: int,
    correction_reason: str,
    idempotency_key: str,
    request_path: str,
) -> StoredResponse:
    canonical_request = {
        "synthetic": True,
        "expected_latest_version": expected_latest_version,
        "correction_reason": correction_reason,
        **_wire_fields(fields, IDEA_FIELD_NAMES),
        "contributions": contributions,
    }
    request_digest = _request_digest("POST", request_path, canonical_request)

    with transaction.atomic():
        _lock_idempotency_key(idempotency_key)
        replay = _replay_or_conflict(idempotency_key, request_digest)
        if replay is not None:
            return replay
        try:
            idea = Idea.objects.select_for_update().get(idea_id=idea_id)
        except Idea.DoesNotExist as error:
            raise IdeaNotFound from error
        if idea.latest_version != expected_latest_version:
            raise StaleCorrection

        predecessor = idea.versions.get(version=idea.latest_version)
        predecessor_contributions = [
            {
                "source_version_id": edge.source_version.source_version_id,
                "contribution": edge.contribution,
            }
            for edge in predecessor.contributions.select_related("source_version").order_by(
                "position"
            )
        ]
        changed_fields = _changed_fields(predecessor, fields, IDEA_FIELD_NAMES)
        if predecessor_contributions != contributions:
            changed_fields.append("contributions")
        changed_fields.sort()
        resolved = _resolve_contributions(contributions)

        try:
            version = IdeaVersion.objects.create(
                idea=idea,
                version=idea.latest_version + 1,
                corrects_version=idea.latest_version,
                correction_reason=correction_reason,
                changed_fields=changed_fields,
                synthetic=True,
                created_by=actor,
                **fields,
            )
            _create_contributions(version, resolved)
            idea.refresh_from_db()
        except DatabaseError as error:
            raise IdeaConflict from error

        body = canonical_json_bytes(idea_detail(idea))
        _store_idempotency(
            key=idempotency_key,
            request_path=request_path,
            request_digest=request_digest,
            response_identity=idea_id,
            response_body=body,
        )
        return StoredResponse(201, body)


def get_idea(idea_id: str) -> Idea:
    try:
        return Idea.objects.get(idea_id=idea_id)
    except Idea.DoesNotExist as error:
        raise IdeaNotFound from error


def idea_detail(idea: Idea) -> dict[str, Any]:
    latest = idea.versions.get(version=idea.latest_version)
    return {
        "idea_id": idea.idea_id,
        "synthetic": idea.synthetic,
        "latest_version": idea.latest_version,
        "latest_idea_version_id": latest.idea_version_id,
        "created_at": _timestamp(idea.created_at),
        "latest": idea_version_representation(latest),
    }


def idea_history(idea: Idea) -> dict[str, Any]:
    return {
        "idea_id": idea.idea_id,
        "versions": [
            idea_version_representation(version)
            for version in idea.versions.order_by("version")
        ],
    }


def idea_version_representation(version: IdeaVersion) -> dict[str, Any]:
    predecessor_id = None
    if version.corrects_version is not None:
        predecessor_id = version.idea.versions.only("idea_version_id").get(
            version=version.corrects_version
        ).idea_version_id
    return {
        "idea_version_id": version.idea_version_id,
        "version": version.version,
        "corrects_idea_version_id": predecessor_id,
        "corrects_version": version.corrects_version,
        "correction_reason": version.correction_reason,
        "changed_fields": version.changed_fields,
        "title": version.title,
        "mechanism": version.mechanism,
        "testable_claim": version.testable_claim,
        "falsification": version.falsification,
        "eligible_market": version.eligible_market,
        "workflow_status": version.workflow_status,
        "rejection_reason": version.rejection_reason,
        "contributions": [
            contribution_representation(edge)
            for edge in version.contributions.select_related(
                "source_version", "source_version__source"
            ).order_by("position")
        ],
        "created_at": _timestamp(version.created_at),
        "created_by": version.created_by,
    }


def contribution_representation(edge: IdeaContribution) -> dict[str, Any]:
    source_version = edge.source_version
    return {
        "contribution_id": edge.contribution_id,
        "source_version_id": source_version.source_version_id,
        "source_id": source_version.source.source_id,
        "version": source_version.version,
        "contribution": edge.contribution,
        "source_summary": {
            "title": source_version.title,
            "source_type": source_version.source_type,
            "citation": source_version.citation,
            "published_at": _timestamp(source_version.published_at),
            "observed_available_at": _timestamp(source_version.observed_available_at),
            "canonical_url": source_version.canonical_url,
        },
    }


def _resolve_contributions(
    contributions: list[dict[str, str]],
) -> list[tuple[SourceVersion, str]]:
    resolved = []
    for item in contributions:
        try:
            source_version = SourceVersion.objects.select_related("source").get(
                source_version_id=item["source_version_id"]
            )
        except SourceVersion.DoesNotExist as error:
            raise SourceNotFound from error
        resolved.append((source_version, item["contribution"]))
    return resolved


def _create_contributions(
    version: IdeaVersion, resolved: list[tuple[SourceVersion, str]]
) -> None:
    IdeaContribution.objects.bulk_create(
        [
            IdeaContribution(
                idea_version=version,
                source_version=source_version,
                contribution=contribution,
                position=position,
            )
            for position, (source_version, contribution) in enumerate(resolved, start=1)
        ]
    )


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


def _changed_fields(stored, fields: dict[str, Any], names: tuple[str, ...]) -> list[str]:
    return sorted(name for name in names if getattr(stored, name) != fields[name])


def _wire_fields(fields: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    return {
        name: _timestamp(fields[name]) if name.endswith("_at") else fields[name]
        for name in names
    }


def _request_digest(method: str, path: str, request: object) -> str:
    canonical = canonical_json_bytes({"method": method, "path": path, "request": request})
    return hashlib.sha256(canonical).hexdigest()


def _canonical_base64(content: bytes) -> str:
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


def _timestamp(value) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
