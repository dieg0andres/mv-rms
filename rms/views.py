"""Server-rendered, read-only RMS-VS-1 Source history page."""
from django.template.response import TemplateResponse
from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .api import SOURCE_ID_RE
from .services import SourceConflict, SourceNotFound, get_source, latest_manifest, source_detail, source_history

class SourceHistoryPage(APIView):
    permission_classes = [IsAuthenticated]
    def handle_exception(self, exc):
        if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
            return TemplateResponse(self.request._request, "rms/denied.html", status=401)
        if isinstance(exc, exceptions.PermissionDenied):
            return TemplateResponse(self.request._request, "rms/denied.html", status=403)
        return super().handle_exception(exc)
    def get(self, request, source_id: str):
        if not request.user.groups.filter(name="founder_viewer").exists():
            raise exceptions.PermissionDenied
        if not SOURCE_ID_RE.fullmatch(source_id): return self._not_found(request)
        try:
            source = get_source(source_id)
            detail, history, manifest = source_detail(source), source_history(source), latest_manifest(source)
        except SourceNotFound: return self._not_found(request)
        except SourceConflict: return TemplateResponse(request._request, "rms/unavailable.html", status=409)
        return TemplateResponse(request._request, "rms/source_history.html", {"detail": detail, "history": history["versions"], "manifest": manifest, "manifest_download_url": f"/api/v1/sources/{source.source_id}/manifest"})
    @staticmethod
    def _not_found(request): return TemplateResponse(request._request, "rms/not_found.html", status=404)
