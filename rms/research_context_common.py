"""Shared rights, audit, serialization and atomic request handling for HN."""

import hashlib
import json
import re
from uuid import UUID
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from .hypothesis_models import AUTHORITY_REFERENCE, ResearchVersion
from .hypothesis_validation import HypothesisValidationError, validate_request
from .models import IdempotencyRecord, IdeaVersion, SourceVersion
from .permissions import has_rms_read_access, has_rms_write_access
from .services import (
    IdempotencyConflict, ResourceNotFound, ServiceError, StoredResponse,
    _lock_idempotency_key, _replay_or_conflict, canonical_json_bytes,
)


class Forbidden(ServiceError):
    code = "forbidden"
    safe_message = "This operation is not permitted."
    http_status = 403


class AuthenticationRequired(Forbidden):
    code = "authentication_required"
    safe_message = "Authentication is required."
    http_status = 401


class StaleVersion(ServiceError):
    code = "stale_version"
    safe_message = "The correction is based on a stale version."
    http_status = 409


def require_actor(actor, *, write=False):
    if not getattr(actor, "is_authenticated", False):
        raise AuthenticationRequired
    predicate = has_rms_write_access if write else has_rms_read_access
    if not predicate(actor):
        raise Forbidden


def visible(model):
    """Synthetic slice is shared by RMS readers; callers authorize before fetch."""
    if issubclass(model, ResearchVersion):
        return model.objects.filter(classification="synthetic", authority_reference=AUTHORITY_REFERENCE)
    return model.objects.filter(synthetic=True)


def resolve(model, public_id):
    key = "idea_version_id" if model is IdeaVersion else "source_version_id" if model is SourceVersion else "public_id"
    try:
        return visible(model).get(**{key: public_id})
    except model.DoesNotExist as error:
        raise ResourceNotFound from error


def field_error(path, code="inconsistent_context"):
    raise HypothesisValidationError([{"path": path, "code": code, "message": "Select an authorized exact version compatible with this context."}])


def lock_lineage():
    # Shared with existing upstream correction services. One lock avoids the
    # Source-correction/Hypothesis-create race without mutable history or workers.
    _lock_idempotency_key("rms-hn-lineage-v1")


def wire(value):
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    return value


def append(model, *, actor, record, predecessor=None, changed_fields=(), **values):
    now = timezone.now()
    item = model(
        record=record, version=1 if predecessor is None else predecessor.version + 1,
        created_by=actor.get_username(), created_at=now, recorded_at=now,
        corrects_version=None if predecessor is None else predecessor.version,
        changed_fields=list(changed_fields), **values,
    )
    content = {field.attname: wire(getattr(item, field.attname)) for field in item._meta.concrete_fields if field.name != "row_digest"}
    item.row_digest = hashlib.sha256(canonical_json_bytes(content)).hexdigest()
    item.save(force_insert=True)
    record.refresh_from_db(fields=["latest_version"])
    return item


def envelope(item):
    predecessor_id = None
    if item.corrects_version is not None:
        predecessor_id = type(item).objects.get(record=item.record, version=item.corrects_version).public_id
    return {
        "stable_id": item.record.public_id, "version_id": item.public_id,
        "version": item.version, "schema_version": item.schema_version,
        "created_at": wire(item.created_at), "created_by": item.created_by,
        "recorded_at": wire(item.recorded_at), "classification": item.classification,
        "authority_reference": item.authority_reference, "state": item.state,
        "row_digest": item.row_digest, "impact_status": item.impact_status,
        "corrects_version": item.corrects_version, "correction_reason": item.correction_reason,
        "changed_fields": item.changed_fields, "supersedes_version_id": predecessor_id,
        "effective_at": None,
    }


def endpoint(item):
    if isinstance(item, IdeaVersion):
        return {"stable_id": item.idea.idea_id, "version_id": item.idea_version_id, "version": item.version}
    if isinstance(item, SourceVersion):
        return {"stable_id": item.source.source_id, "version_id": item.source_version_id, "version": item.version}
    return {"stable_id": item.record.public_id, "version_id": item.public_id, "version": item.version}


def latest(model, public_id, *, version=None, lock=False):
    qs = visible(model)
    if lock:
        qs = qs.select_for_update()
    version_model = model._meta.get_field("versions").related_model
    if version is not None and (type(version) is not int or version < 1):
        raise ResourceNotFound
    try:
        record = qs.get(public_id=public_id)
        return record, record.versions.get(version=record.latest_version if version is None else version)
    except (model.DoesNotExist, version_model.DoesNotExist) as error:
        raise ResourceNotFound from error


def check_expected(record, payload):
    if record.latest_version != payload["expected_latest_version"]:
        raise StaleVersion


def execute_write(*, actor, idempotency_key, payload, request_name, path, operation):
    require_actor(actor, write=True)
    if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key):
        field_error("/Idempotency-Key", "invalid_format")
    normalized = validate_request(request_name, payload)
    # Actor scopes the storage key; actor/method/route/canonical original payload
    # bind reuse. Replays preserve the exact originally serialized bytes/status.
    actor_id = str(actor.pk)
    key = "HN:" + hashlib.sha256(canonical_json_bytes([actor_id, idempotency_key])).hexdigest()
    digest = hashlib.sha256(canonical_json_bytes({"actor": actor_id, "method": "POST", "path": path, "payload": payload})).hexdigest()
    with transaction.atomic():
        lock_lineage()
        _lock_idempotency_key(key)
        replay = _replay_or_conflict(key, digest)
        if replay is not None:
            return replay
        status, representation = operation(normalized)
        body = canonical_json_bytes(representation)
        IdempotencyRecord.objects.create(
            key=key, request_method="POST", request_path=path, request_sha256=digest,
            response_status=status, response_identity=representation["stable_id"], response_bytes=body,
        )
        return StoredResponse(status, body)


def change_paths(before, after, prefix=""):
    return sorted(prefix + key for key in before.keys() | after.keys() if before.get(key) != after.get(key))


def record_links(route, item):
    path = f"/api/v1/{route}/{item.record.public_id}"
    return {"self": path + f"/versions/{item.version}", "latest": path, "history": path + "/history"}


def paginated(*, actor, model, query, route, render, filter_queryset=None):
    require_actor(actor)
    query = validate_request("ListQuery", query)
    if route != "hypotheses" and "originating_idea_id" in query:
        field_error("/originating_idea_id", "unknown_field")
    qs = visible(model).order_by("-created_at", "public_id")
    if filter_queryset:
        qs = filter_queryset(qs, query)
    count = qs.count()
    start = (query["page"] - 1) * query["page_size"]
    selected = [] if start >= count else qs[start:start + query["page_size"]]
    results = [render(record.versions.get(version=record.latest_version)) for record in selected]
    def page_link(page):
        from urllib.parse import urlencode
        return f"/api/v1/{route}?" + urlencode({**query, "page": page})
    return {"page": query["page"], "page_size": query["page_size"], "count": count,
            "next": page_link(query["page"] + 1) if start + query["page_size"] < count else None,
            "previous": page_link(query["page"] - 1) if query["page"] > 1 else None, "results": results}
