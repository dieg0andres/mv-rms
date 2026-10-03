"""The frozen RMS-VS-1 API routes and read-only history page."""

from django.urls import path

from rms import api, views


urlpatterns = [
    path("sources/new", views.SourceCreatePage.as_view(), name="source-create-page"),
    path(
        "sources/<str:source_id>/correct",
        views.SourceCorrectionPage.as_view(),
        name="source-correction-page",
    ),
    path("sources/<str:source_id>/history", views.SourceHistoryPage.as_view(), name="source-history-page"),
    path("ideas/new", views.IdeaCreatePage.as_view(), name="idea-create-page"),
    path(
        "ideas/<str:idea_id>/correct",
        views.IdeaCorrectionPage.as_view(),
        name="idea-correction-page",
    ),
    path("ideas/<str:idea_id>", views.IdeaDetailPage.as_view(), name="idea-detail-page"),
    path(
        "ideas/<str:idea_id>/history",
        views.IdeaHistoryPage.as_view(),
        name="idea-history-page",
    ),
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
    path("api/v1/ideas", api.IdeaCreateView.as_view(), name="idea-create"),
    path(
        "api/v1/ideas/<str:idea_id>/corrections",
        api.IdeaCorrectionView.as_view(),
        name="idea-correction",
    ),
    path(
        "api/v1/ideas/<str:idea_id>",
        api.IdeaDetailView.as_view(),
        name="idea-detail",
    ),
    path(
        "api/v1/ideas/<str:idea_id>/versions",
        api.IdeaHistoryView.as_view(),
        name="idea-history",
    ),
    path("api/v1/readiness", api.ReadinessView.as_view(), name="readiness"),
]
