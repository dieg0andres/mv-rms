"""The six frozen RMS-VS-1 API routes."""

from django.urls import path

from rms import api


urlpatterns = [
    path("api/v1/sources", api.SourceCreateView.as_view(), name="source-create"),
    path(
        "api/v1/sources/<str:source_id>/corrections",
        api.SourceCorrectionView.as_view(),
        name="source-correction",
    ),
    path(
        "api/v1/sources/<str:source_id>",
        api.SourceDetailView.as_view(),
        name="source-detail",
    ),
    path(
        "api/v1/sources/<str:source_id>/versions",
        api.SourceHistoryView.as_view(),
        name="source-history",
    ),
    path(
        "api/v1/sources/<str:source_id>/manifest",
        api.SourceManifestView.as_view(),
        name="source-manifest",
    ),
    path("api/v1/readiness", api.ReadinessView.as_view(), name="readiness"),
]
