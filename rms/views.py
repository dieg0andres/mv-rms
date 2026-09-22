"""Authenticated server-rendered pages for the bounded RMS-SI-1 slice."""

from django.template.response import TemplateResponse
from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .api import PUBLIC_ID_RE, SOURCE_ID_RE
from .models import ELIGIBLE_MARKETS, SOURCE_TYPES, WORKFLOW_STATUSES, SourceVersion
from .services import (
    IdeaNotFound,
    SourceConflict,
    SourceNotFound,
    get_idea,
    get_source,
    idea_detail,
    idea_history,
    latest_manifest,
    source_detail,
    source_history,
)


def _choices(values, selected=None):
    ordered = ([selected] if selected in values else []) + [
        value for value in values if value != selected
    ]
    return [(value, value.replace("_", " ").title()) for value in ordered]


def _source_fields(version=None):
    version = version or {}
    authors = version.get("authors")
    return [
        {"name": "title", "label": "Title", "required": True, "value": version.get("title", "")},
        {"name": "source_type", "label": "Source type", "required": True, "kind": "select", "choices": _choices(SOURCE_TYPES, version.get("source_type")), "value": version.get("source_type", "")},
        {"name": "citation", "label": "Citation", "required": True, "value": version.get("citation", "")},
        {"name": "observed_available_at", "label": "Observed available at (RFC 3339)", "required": True, "value": version.get("observed_available_at", "")},
        {"name": "authors", "label": "Authors (one per line)", "required": False, "value": "\n".join(authors or [])},
        {"name": "publisher", "label": "Publisher", "required": False, "value": version.get("publisher") or ""},
        {"name": "published_at", "label": "Published at (RFC 3339)", "required": False, "value": version.get("published_at") or ""},
        {"name": "canonical_url", "label": "Canonical URL", "required": False, "value": version.get("canonical_url") or ""},
        {"name": "rights_note", "label": "Rights note", "required": False, "value": version.get("rights_note") or ""},
    ]


def _idea_fields(version=None):
    version = version or {}
    return [
        {"name": "title", "label": "Title", "required": True, "value": version.get("title", "")},
        {"name": "mechanism", "label": "Mechanism", "required": True, "value": version.get("mechanism", "")},
        {"name": "testable_claim", "label": "Testable claim", "required": True, "value": version.get("testable_claim", "")},
        {"name": "falsification", "label": "Falsification", "required": True, "value": version.get("falsification", "")},
        {"name": "eligible_market", "label": "Eligible market", "required": True, "kind": "select", "choices": _choices(ELIGIBLE_MARKETS, version.get("eligible_market")), "value": version.get("eligible_market", "")},
        {"name": "workflow_status", "label": "Workflow status", "required": True, "kind": "select", "choices": _choices(WORKFLOW_STATUSES, version.get("workflow_status")), "value": version.get("workflow_status", "")},
        {"name": "rejection_reason", "label": "Rejection reason", "required": False, "value": version.get("rejection_reason") or ""},
    ]


def _source_version_options():
    return [
        {
            "source_version_id": version.source_version_id,
            "source_id": version.source.source_id,
            "version": version.version,
            "title": version.title,
        }
        for version in SourceVersion.objects.select_related("source").order_by(
            "source__source_id", "version"
        )
    ]


class RmsPage(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
            return TemplateResponse(self.request._request, "rms/denied.html", status=401)
        if isinstance(exc, exceptions.PermissionDenied):
            return TemplateResponse(self.request._request, "rms/denied.html", status=403)
        return super().handle_exception(exc)

    @staticmethod
    def _has_role(request, *roles):
        return request.user.groups.filter(name__in=roles).exists()

    def _require_editor(self, request):
        if not self._has_role(request, "editor"):
            raise exceptions.PermissionDenied

    def _require_reader(self, request):
        if not self._has_role(request, "editor", "founder_viewer"):
            raise exceptions.PermissionDenied

    @staticmethod
    def _not_found(request):
        return TemplateResponse(request._request, "rms/not_found.html", status=404)

    @staticmethod
    def _unavailable(request):
        return TemplateResponse(request._request, "rms/unavailable.html", status=409)


class SourceCreatePage(RmsPage):
    def get(self, request):
        self._require_editor(request)
        return TemplateResponse(
            request._request,
            "rms/source_editor.html",
            {"api_url": "/api/v1/sources", "correction": False, "source_fields": _source_fields()},
        )


class SourceCorrectionPage(RmsPage):
    def get(self, request, source_id: str):
        self._require_editor(request)
        if not SOURCE_ID_RE.fullmatch(source_id):
            return self._not_found(request)
        try:
            detail = source_detail(get_source(source_id))
        except SourceNotFound:
            return self._not_found(request)
        return TemplateResponse(
            request._request,
            "rms/source_editor.html",
            {
                "api_url": f"/api/v1/sources/{source_id}/corrections",
                "correction": True,
                "source_id": source_id,
                "expected_latest_version": detail["latest_version"],
                "source_fields": _source_fields(detail["latest"]),
            },
        )


class SourceHistoryPage(RmsPage):
    def get(self, request, source_id: str):
        self._require_reader(request)
        if not SOURCE_ID_RE.fullmatch(source_id):
            return self._not_found(request)
        try:
            source = get_source(source_id)
            detail = source_detail(source)
            history = source_history(source)["versions"]
            manifest = latest_manifest(source)
        except SourceNotFound:
            return self._not_found(request)
        except SourceConflict:
            return self._unavailable(request)
        for version in history:
            version["manifest_download_url"] = (
                f"/api/v1/sources/{source.source_id}/manifest?through_version={version['version']}"
            )
        return TemplateResponse(
            request._request,
            "rms/source_history.html",
            {
                "detail": detail,
                "history": history,
                "manifest": manifest,
                "manifest_download_url": f"/api/v1/sources/{source.source_id}/manifest",
            },
        )


class IdeaCreatePage(RmsPage):
    def get(self, request):
        self._require_editor(request)
        return TemplateResponse(
            request._request,
            "rms/idea_editor.html",
            {
                "api_url": "/api/v1/ideas",
                "correction": False,
                "idea_fields": _idea_fields(),
                "source_versions": _source_version_options(),
                "contributions": [{}],
            },
        )


class IdeaCorrectionPage(RmsPage):
    def get(self, request, idea_id: str):
        self._require_editor(request)
        if not PUBLIC_ID_RE.fullmatch(idea_id) or not idea_id.startswith("IDE-"):
            return self._not_found(request)
        try:
            detail = idea_detail(get_idea(idea_id))
        except IdeaNotFound:
            return self._not_found(request)
        return TemplateResponse(
            request._request,
            "rms/idea_editor.html",
            {
                "api_url": f"/api/v1/ideas/{idea_id}/corrections",
                "correction": True,
                "idea_id": idea_id,
                "expected_latest_version": detail["latest_version"],
                "idea_fields": _idea_fields(detail["latest"]),
                "source_versions": _source_version_options(),
                "contributions": detail["latest"]["contributions"],
            },
        )


class IdeaDetailPage(RmsPage):
    def get(self, request, idea_id: str):
        self._require_reader(request)
        if not PUBLIC_ID_RE.fullmatch(idea_id) or not idea_id.startswith("IDE-"):
            return self._not_found(request)
        try:
            detail = idea_detail(get_idea(idea_id))
        except IdeaNotFound:
            return self._not_found(request)
        return TemplateResponse(request._request, "rms/idea_detail.html", {"detail": detail})


class IdeaHistoryPage(RmsPage):
    def get(self, request, idea_id: str):
        self._require_reader(request)
        if not PUBLIC_ID_RE.fullmatch(idea_id) or not idea_id.startswith("IDE-"):
            return self._not_found(request)
        try:
            history = idea_history(get_idea(idea_id))
        except IdeaNotFound:
            return self._not_found(request)
        return TemplateResponse(
            request._request,
            "rms/idea_history.html",
            {"idea_id": idea_id, "versions": history["versions"]},
        )
