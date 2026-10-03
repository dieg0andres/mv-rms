"""Prepared browser routes; Director owns registration in the project URLconf."""

from django.urls import path

from .navigation_views import (
    HypothesisDraftPreviewPage, NavigationPage, RecordDetailPage,
    RecordEditorPage, RecordHistoryPage, ClassificationLookupPage, RESOURCES,
)


urlpatterns = [
    path("", NavigationPage.as_view(section="home"), name="rms-home"),
    path("sources", NavigationPage.as_view(section="sources"), name="rms-sources"),
    path("ideas", NavigationPage.as_view(section="ideas"), name="rms-ideas"),
    path("hypotheses", NavigationPage.as_view(section="hypotheses"), name="rms-hypotheses"),
    path("hypotheses/draft-preview", HypothesisDraftPreviewPage.as_view(), name="rms-hypothesis-draft-preview"),
    path("research-context", NavigationPage.as_view(section="context"), name="rms-context"),
    path("idea-family-associations", ClassificationLookupPage.as_view(), name="rms-classification-lookup"),
]

for kind in ("hypothesis", "family", "case", "classification"):
    route = RESOURCES[kind]["route"]
    urlpatterns += [
        path(f"{route}/<str:record_id>/revise", RecordEditorPage.as_view(kind=kind), name=f"rms-{kind}-revise"),
        path(f"{route}/<str:record_id>/history", RecordHistoryPage.as_view(kind=kind), name=f"rms-{kind}-history"),
        path(f"{route}/<str:record_id>/versions/<int:version>", RecordDetailPage.as_view(kind=kind), name=f"rms-{kind}-version"),
        path(f"{route}/<str:record_id>", RecordDetailPage.as_view(kind=kind), name=f"rms-{kind}-detail"),
    ]
    if kind != "classification":
        urlpatterns.insert(0, path(f"{route}/new", RecordEditorPage.as_view(kind=kind), name=f"rms-{kind}-create"))

urlpatterns.append(path(
    "prior-research-assessments/<str:record_id>/versions/<int:version>",
    RecordDetailPage.as_view(kind="assessment"), name="rms-assessment-version",
))
