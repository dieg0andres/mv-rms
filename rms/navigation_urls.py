"""Prepared browser routes; Director owns registration in the project URLconf."""

from django.urls import path

from .navigation_views import HypothesisDraftPreviewPage, NavigationPage


urlpatterns = [
    path("", NavigationPage.as_view(section="home"), name="rms-home"),
    path("sources", NavigationPage.as_view(section="sources"), name="rms-sources"),
    path("ideas", NavigationPage.as_view(section="ideas"), name="rms-ideas"),
    path("hypotheses", NavigationPage.as_view(section="hypotheses"), name="rms-hypotheses"),
    path("hypotheses/draft-preview", HypothesisDraftPreviewPage.as_view(), name="rms-hypothesis-draft-preview"),
    path("research-context", NavigationPage.as_view(section="context"), name="rms-context"),
]
