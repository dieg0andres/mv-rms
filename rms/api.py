"""Frozen DRF API for local synthetic Source history."""

import base64
import binascii
import re
import uuid

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse
from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsEditor
from .services import (
    IdempotencyConflict,
    SourceConflict,
    SourceNotFound,
    canonical_json_bytes,
    correct_source,
    create_source,
    get_source,
    latest_manifest,
    source_detail,
    source_history,
)


SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


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
        (exceptions.NotAuthenticated, "authentication_required", "Authentication is required.", 401),
        (exceptions.AuthenticationFailed, "authentication_required", "Authentication is required.", 401),
        (exceptions.PermissionDenied, "forbidden", "This operation is not permitted.", 403),
        (exceptions.NotFound, "not_found", "Source not found.", 404),
        (exceptions.MethodNotAllowed, "method_not_allowed", "Method not allowed.", 405),
    )
    for exception_type, code, message, http_status in mapping:
        if isinstance(exc, exception_type):
            return error_response(code, message, http_status)
    return error_response("validation_error", "The request is invalid.", 400)


class SourceCreateView(APIView):
    permission_classes = [IsAuthenticated, IsEditor]

    def post(self, request):
        parsed = _parse_payload(
            request.data,
            expected_fields={"source_id", "synthetic", "content_base64"},
            include_source_id=True,
        )
        if isinstance(parsed, Response):
            return parsed
        key = _idempotency_key(request)
        if isinstance(key, Response):
            return key
        try:
            stored = create_source(
                source_id=parsed["source_id"],
                content=parsed["content"],
                idempotency_key=key,
                request_path=request.path,
            )
        except IdempotencyConflict as error:
            return error_response(error.code, error.safe_message, status.HTTP_409_CONFLICT)
        except SourceConflict as error:
            return error_response(error.code, error.safe_message, status.HTTP_409_CONFLICT)
        return HttpResponse(
            stored.body, status=stored.status, content_type="application/json; charset=utf-8"
        )


class SourceCorrectionView(APIView):
    permission_classes = [IsAuthenticated, IsEditor]

    def post(self, request, source_id: str):
        if not SOURCE_ID_RE.fullmatch(source_id):
            return error_response("validation_error", "The request is invalid.", 400)
        parsed = _parse_payload(
            request.data,
            expected_fields={"synthetic", "expected_latest_version", "content_base64"},
            include_expected_version=True,
        )
        if isinstance(parsed, Response):
            return parsed
        key = _idempotency_key(request)
        if isinstance(key, Response):
            return key
        try:
            stored = correct_source(
                source_id=source_id,
                content=parsed["content"],
                expected_latest_version=parsed["expected_latest_version"],
                idempotency_key=key,
                request_path=request.path,
            )
        except SourceNotFound as error:
            return error_response(error.code, error.safe_message, 404)
        except IdempotencyConflict as error:
            return error_response(error.code, error.safe_message, 409)
        except SourceConflict as error:
            return error_response(error.code, error.safe_message, 409)
        return HttpResponse(
            stored.body, status=stored.status, content_type="application/json; charset=utf-8"
        )


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
        try:
            manifest = latest_manifest(source)
        except SourceConflict as error:
            return error_response(error.code, error.safe_message, 409)
        response = HttpResponse(
            bytes(manifest.manifest_bytes),
            content_type="application/json; charset=utf-8",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{source.source_id}-manifest-v{source.latest_version}.json"'
        )
        response["X-Manifest-SHA256"] = manifest.manifest_sha256
        return response


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


def _parse_payload(
    payload,
    *,
    expected_fields: set[str],
    include_source_id: bool = False,
    include_expected_version: bool = False,
):
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        return error_response("validation_error", "The request is invalid.", 400)
    if payload.get("synthetic") is not True:
        return error_response("validation_error", "The request is invalid.", 400)
    if include_source_id and (
        not isinstance(payload.get("source_id"), str)
        or not SOURCE_ID_RE.fullmatch(payload["source_id"])
    ):
        return error_response("validation_error", "The request is invalid.", 400)
    if include_expected_version and (
        type(payload.get("expected_latest_version")) is not int
        or payload["expected_latest_version"] < 1
    ):
        return error_response("validation_error", "The request is invalid.", 400)
    encoded = payload.get("content_base64")
    if not isinstance(encoded, str):
        return error_response("validation_error", "The request is invalid.", 400)
    try:
        ascii_bytes = encoded.encode("ascii")
        content = base64.b64decode(ascii_bytes, validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        return error_response("validation_error", "The request is invalid.", 400)
    if base64.b64encode(content) != ascii_bytes:
        return error_response("validation_error", "The request is invalid.", 400)
    result = {"content": content}
    if include_source_id:
        result["source_id"] = payload["source_id"]
    if include_expected_version:
        result["expected_latest_version"] = payload["expected_latest_version"]
    return result


def _idempotency_key(request):
    key = request.headers.get("Idempotency-Key")
    if not isinstance(key, str) or not IDEMPOTENCY_KEY_RE.fullmatch(key):
        return error_response("validation_error", "The request is invalid.", 400)
    return key


def _source_or_response(source_id: str):
    if not SOURCE_ID_RE.fullmatch(source_id):
        return error_response("not_found", "Source not found.", 404)
    try:
        return get_source(source_id)
    except SourceNotFound as error:
        return error_response(error.code, error.safe_message, 404)
