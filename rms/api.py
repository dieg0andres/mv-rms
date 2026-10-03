"""RMS-SI-1.0 DRF API for synthetic Source and Idea history."""

import base64
import binascii
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse
from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ELIGIBLE_MARKETS, SOURCE_TYPES, WORKFLOW_STATUSES
from .permissions import IsEditor
from .services import (
    IdeaNotFound,
    ResourceNotFound,
    ServiceError,
    SourceNotFound,
    correct_idea,
    correct_source,
    create_idea,
    create_source,
    get_idea,
    get_source,
    idea_detail,
    idea_history,
    manifest_for_version,
    source_detail,
    source_history,
)


SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
PUBLIC_ID_RE = re.compile(
    r"^(?:IDE|IDEV|SRCV|SIE)-[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SOURCE_FIELDS = {
    "title",
    "source_type",
    "citation",
    "observed_available_at",
    "authors",
    "publisher",
    "published_at",
    "canonical_url",
    "rights_note",
}
IDEA_FIELDS = {
    "title",
    "mechanism",
    "testable_claim",
    "falsification",
    "eligible_market",
    "workflow_status",
    "rejection_reason",
    "contributions",
}


def error_response(code: str, message: str, http_status: int) -> Response:
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "request_id": uuid.uuid4().hex,
            }
        },
        status=http_status,
    )


def exception_handler(exc, context):
    mapping = (
        (
            exceptions.NotAuthenticated,
            "authentication_required",
            "Authentication is required.",
            401,
        ),
        (
            exceptions.AuthenticationFailed,
            "authentication_required",
            "Authentication is required.",
            401,
        ),
        (exceptions.PermissionDenied, "forbidden", "This operation is not permitted.", 403),
        (exceptions.NotFound, "not_found", "Resource not found.", 404),
        (exceptions.MethodNotAllowed, "method_not_allowed", "Method not allowed.", 405),
    )
    for exception_type, code, message, http_status in mapping:
        if isinstance(exc, exception_type):
            return error_response(code, message, http_status)
    return error_response("validation_error", "The request is invalid.", 400)


class SourceCreateView(APIView):
    permission_classes = [IsAuthenticated, IsEditor]

    def post(self, request):
        if request.content_type != "application/json":
            return _invalid()
        parsed = _parse_source_payload(request.data, create=True)
        if isinstance(parsed, Response):
            return parsed
        key = _idempotency_key(request)
        if isinstance(key, Response):
            return key
        try:
            stored = create_source(
                source_id=parsed["source_id"],
                content=parsed["content"],
                fields=parsed["fields"],
                actor=request.user.get_username(),
                idempotency_key=key,
                request_path=request.path,
            )
        except ServiceError as error:
            return _service_error_response(error)
        return _stored_response(stored)


class SourceCorrectionView(APIView):
    permission_classes = [IsAuthenticated, IsEditor]

    def post(self, request, source_id: str):
        if request.content_type != "application/json":
            return _invalid()
        if not SOURCE_ID_RE.fullmatch(source_id):
            return error_response("not_found", "Resource not found.", 404)
        parsed = _parse_source_payload(request.data, create=False)
        if isinstance(parsed, Response):
            return parsed
        key = _idempotency_key(request)
        if isinstance(key, Response):
            return key
        try:
            stored = correct_source(
                source_id=source_id,
                content=parsed["content"],
                fields=parsed["fields"],
                actor=request.user.get_username(),
                expected_latest_version=parsed["expected_latest_version"],
                correction_reason=parsed["correction_reason"],
                idempotency_key=key,
                request_path=request.path,
            )
        except ServiceError as error:
            return _service_error_response(error)
        return _stored_response(stored)


class SourceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, source_id: str):
        source = _source_or_response(source_id)
        if isinstance(source, Response):
            return source
        return Response(source_detail(source))


class SourceHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, source_id: str):
        source = _source_or_response(source_id)
        if isinstance(source, Response):
            return source
        return Response(source_history(source))


class SourceManifestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, source_id: str):
        source = _source_or_response(source_id)
        if isinstance(source, Response):
            return source
        if set(request.query_params) - {"through_version"}:
            return _invalid()
        through_version = None
        if "through_version" in request.query_params:
            value = request.query_params.get("through_version")
            try:
                through_version = int(value)
            except (TypeError, ValueError):
                return _invalid()
            if through_version < 1 or str(through_version) != value:
                return _invalid()
        try:
            manifest = manifest_for_version(source, through_version)
        except ServiceError as error:
            return _service_error_response(error)
        response = HttpResponse(
            bytes(manifest.manifest_bytes),
            content_type="application/json; charset=utf-8",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{source.source_id}-manifest-v{manifest.through_version}.json"'
        )
        response["X-Manifest-SHA256"] = manifest.manifest_sha256
        return response


class IdeaCreateView(APIView):
    permission_classes = [IsAuthenticated, IsEditor]

    def post(self, request):
        if request.content_type != "application/json":
            return _invalid()
        parsed = _parse_idea_payload(request.data, create=True)
        if isinstance(parsed, Response):
            return parsed
        key = _idempotency_key(request)
        if isinstance(key, Response):
            return key
        try:
            stored = create_idea(
                fields=parsed["fields"],
                contributions=parsed["contributions"],
                actor=request.user.get_username(),
                idempotency_key=key,
                request_path=request.path,
            )
        except ServiceError as error:
            return _service_error_response(error)
        return _stored_response(stored)


class IdeaCorrectionView(APIView):
    permission_classes = [IsAuthenticated, IsEditor]

    def post(self, request, idea_id: str):
        if request.content_type != "application/json":
            return _invalid()
        if not _public_id(idea_id, "IDE"):
            return error_response("not_found", "Resource not found.", 404)
        parsed = _parse_idea_payload(request.data, create=False)
        if isinstance(parsed, Response):
            return parsed
        key = _idempotency_key(request)
        if isinstance(key, Response):
            return key
        try:
            stored = correct_idea(
                idea_id=idea_id,
                fields=parsed["fields"],
                contributions=parsed["contributions"],
                actor=request.user.get_username(),
                expected_latest_version=parsed["expected_latest_version"],
                correction_reason=parsed["correction_reason"],
                idempotency_key=key,
                request_path=request.path,
            )
        except ServiceError as error:
            return _service_error_response(error)
        return _stored_response(stored)


class IdeaDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, idea_id: str):
        idea = _idea_or_response(idea_id)
        if isinstance(idea, Response):
            return idea
        return Response(idea_detail(idea))


class IdeaHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, idea_id: str):
        idea = _idea_or_response(idea_id)
        if isinstance(idea, Response):
            return idea
        return Response(idea_history(idea))


class ReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                raise RuntimeError("pending migrations")
        except Exception:
            return error_response("not_ready", "The local test service is not ready.", 503)
        return Response({"status": "ready"})


def _parse_source_payload(payload, *, create: bool):
    expected = SOURCE_FIELDS | {"synthetic", "content_base64"}
    if create:
        expected.add("source_id")
    else:
        expected |= {"expected_latest_version", "correction_reason"}
    if not isinstance(payload, dict) or set(payload) != expected:
        return _invalid()
    if payload.get("synthetic") is not True:
        return _invalid()
    if create and (
        not isinstance(payload.get("source_id"), str)
        or not SOURCE_ID_RE.fullmatch(payload["source_id"])
    ):
        return _invalid()
    if not create and not _positive_integer(payload.get("expected_latest_version")):
        return _invalid()
    if not create and not _valid_text(payload.get("correction_reason"), 1, 1000):
        return _invalid()

    fields = {
        "title": payload.get("title"),
        "source_type": payload.get("source_type"),
        "citation": payload.get("citation"),
        "observed_available_at": _parse_timestamp(payload.get("observed_available_at")),
        "authors": payload.get("authors"),
        "publisher": payload.get("publisher"),
        "published_at": _parse_timestamp(payload.get("published_at"), nullable=True),
        "canonical_url": payload.get("canonical_url"),
        "rights_note": payload.get("rights_note"),
    }
    if not _valid_text(fields["title"], 1, 500):
        return _invalid()
    if fields["source_type"] not in SOURCE_TYPES:
        return _invalid()
    if not _valid_text(fields["citation"], 1, 2000):
        return _invalid()
    if fields["observed_available_at"] is _INVALID:
        return _invalid()
    if not _valid_authors(fields["authors"]):
        return _invalid()
    if not _nullable_text(fields["publisher"], 1, 500):
        return _invalid()
    if fields["published_at"] is _INVALID:
        return _invalid()
    if not _valid_url(fields["canonical_url"]):
        return _invalid()
    if not _nullable_text(fields["rights_note"], 1, 4000):
        return _invalid()

    content = _parse_base64(payload.get("content_base64"), nullable=not create)
    if content is _INVALID:
        return _invalid()
    result = {"fields": fields, "content": content}
    if create:
        result["source_id"] = payload["source_id"]
    else:
        result["expected_latest_version"] = payload["expected_latest_version"]
        result["correction_reason"] = payload["correction_reason"]
    return result


def _parse_idea_payload(payload, *, create: bool):
    expected = IDEA_FIELDS | {"synthetic"}
    if not create:
        expected |= {"expected_latest_version", "correction_reason"}
    if not isinstance(payload, dict) or set(payload) != expected:
        return _invalid()
    if payload.get("synthetic") is not True:
        return _invalid()
    if not create and not _positive_integer(payload.get("expected_latest_version")):
        return _invalid()
    if not create and not _valid_text(payload.get("correction_reason"), 1, 1000):
        return _invalid()

    fields = {name: payload.get(name) for name in IDEA_FIELDS - {"contributions"}}
    for name in ("title", "mechanism", "testable_claim", "falsification"):
        maximum = 500 if name == "title" else 4000
        if not _valid_text(fields[name], 1, maximum):
            return _invalid()
    if fields["eligible_market"] not in ELIGIBLE_MARKETS:
        return _invalid()
    if fields["workflow_status"] not in WORKFLOW_STATUSES:
        return _invalid()
    if fields["workflow_status"] == "rejected":
        if not _valid_text(fields["rejection_reason"], 1, 2000):
            return _invalid()
    elif fields["rejection_reason"] is not None:
        return _invalid()

    contributions = payload.get("contributions")
    if not isinstance(contributions, list) or not 1 <= len(contributions) <= 100:
        return _invalid()
    canonical_contributions = []
    seen = set()
    for item in contributions:
        if not isinstance(item, dict) or set(item) != {"source_version_id", "contribution"}:
            return _invalid()
        source_version_id = item.get("source_version_id")
        contribution = item.get("contribution")
        if not _public_id(source_version_id, "SRCV") or not _valid_text(
            contribution, 1, 4000
        ):
            return _invalid()
        pair = (source_version_id, contribution)
        if pair in seen:
            return _invalid()
        seen.add(pair)
        canonical_contributions.append(
            {"source_version_id": source_version_id, "contribution": contribution}
        )

    result = {"fields": fields, "contributions": canonical_contributions}
    if not create:
        result["expected_latest_version"] = payload["expected_latest_version"]
        result["correction_reason"] = payload["correction_reason"]
    return result


class _InvalidValue:
    pass


_INVALID = _InvalidValue()


def _parse_base64(value, *, nullable: bool):
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        return _INVALID
    try:
        ascii_bytes = value.encode("ascii")
        content = base64.b64decode(ascii_bytes, validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        return _INVALID
    if base64.b64encode(content) != ascii_bytes:
        return _INVALID
    return content


def _parse_timestamp(value, *, nullable: bool = False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not TIMESTAMP_RE.fullmatch(value):
        return _INVALID
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return _INVALID
    if parsed.tzinfo is None:
        return _INVALID
    return parsed.astimezone(UTC)


def _valid_text(value, minimum: int, maximum: int) -> bool:
    return bool(
        isinstance(value, str)
        and minimum <= len(value) <= maximum
        and value == value.strip()
        and any(not char.isspace() for char in value)
        and all(char in "\t\n" or not (ord(char) < 32 or ord(char) == 127) for char in value)
    )


def _nullable_text(value, minimum: int, maximum: int) -> bool:
    return value is None or _valid_text(value, minimum, maximum)


def _valid_authors(value) -> bool:
    return value is None or (
        isinstance(value, list)
        and 1 <= len(value) <= 100
        and all(_valid_text(author, 1, 300) for author in value)
        and len(set(value)) == len(value)
    )


def _valid_url(value) -> bool:
    if value is None:
        return True
    if not _valid_text(value, 1, 2048):
        return False
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.netloc
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
    )


def _positive_integer(value) -> bool:
    return type(value) is int and value >= 1


def _public_id(value, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(f"{prefix}-") and bool(
        PUBLIC_ID_RE.fullmatch(value)
    )


def _idempotency_key(request):
    key = request.headers.get("Idempotency-Key")
    if not isinstance(key, str) or not IDEMPOTENCY_KEY_RE.fullmatch(key):
        return _invalid()
    return key


def _source_or_response(source_id: str):
    if not SOURCE_ID_RE.fullmatch(source_id):
        return error_response("not_found", "Resource not found.", 404)
    try:
        return get_source(source_id)
    except SourceNotFound as error:
        return _service_error_response(error)


def _idea_or_response(idea_id: str):
    if not _public_id(idea_id, "IDE"):
        return error_response("not_found", "Resource not found.", 404)
    try:
        return get_idea(idea_id)
    except IdeaNotFound as error:
        return _service_error_response(error)


def _stored_response(stored):
    return HttpResponse(
        stored.body,
        status=stored.status,
        content_type="application/json; charset=utf-8",
    )


def _service_error_response(error: ServiceError) -> Response:
    if isinstance(error, ResourceNotFound):
        http_status = 404
    else:
        http_status = 409
    return error_response(error.code, error.safe_message, http_status)


def _invalid() -> Response:
    return error_response("validation_error", "The request is invalid.", 400)
