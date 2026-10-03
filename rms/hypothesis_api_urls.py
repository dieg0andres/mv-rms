"""Director mounts this module at the root URLConf; paths include api/v1."""

from django.urls import path

from .hypothesis_api import ResearchRecordView


urlpatterns = []
for resource in ("hypotheses", "research-families", "investigations"):
    for suffix, action in (
        ("", "collection"), ("/<str:record_id>", "detail"),
        ("/<str:record_id>/versions/<int:version>", "version"),
        ("/<str:record_id>/history", "history"), ("/<str:record_id>/corrections", "correction"),
    ):
        urlpatterns.append(path(f"api/v1/{resource}{suffix}", ResearchRecordView.as_view(resource=resource, action=action), name=f"hn-{resource}-{action}"))

urlpatterns += [
    path("api/v1/prior-research-assessments/<str:record_id>/versions/<int:version>", ResearchRecordView.as_view(resource="prior-research-assessments", action="version"), name="hn-assessment-version"),
    path("api/v1/idea-family-associations/<str:record_id>/corrections", ResearchRecordView.as_view(resource="idea-family-associations", action="correction"), name="hn-idea-family-correction"),
]

for suffix, action in (
    ("", "collection"), ("/<str:record_id>", "detail"),
    ("/<str:record_id>/versions/<int:version>", "version"),
    ("/<str:record_id>/history", "history"),
):
    urlpatterns.append(path(f"api/v1/idea-family-associations{suffix}", ResearchRecordView.as_view(resource="idea-family-associations", action=action), name=f"hn-idea-family-{action}"))
