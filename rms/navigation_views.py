"""Repository-only navigation preparation; no record or API queries."""

from django.template.response import TemplateResponse

from .views import RmsPage


NAVIGATION = (
    ("home", "Home", "/"),
    ("sources", "Sources", "/sources"),
    ("ideas", "Ideas", "/ideas"),
    ("hypotheses", "Hypotheses", "/hypotheses"),
    ("context", "Research context", "/research-context"),
)


def navigation_context(*, section="home", role=None, build=None):
    return {
        "navigation": [
            {"key": key, "label": label, "url": url, "current": key == section}
            for key, label, url in NAVIGATION
        ],
        "role_label": {"editor": "Editor", "founder_viewer": "Viewer (read-only)"}.get(
            role, "Not supplied"
        ),
        "can_edit": role == "editor",
        "build_label": build or "Not supplied — not a deployed release",
        "repository_preview": True,
    }


class NavigationPage(RmsPage):
    section = "home"

    def get(self, request):
        self._require_reader(request)
        role = "editor" if self._has_role(request, "editor") else "founder_viewer"
        context = navigation_context(section=self.section, role=role)
        context["heading"] = dict(
            (key, label) for key, label, url in NAVIGATION
        )[self.section]
        return TemplateResponse(request._request, "rms/navigation.html", context)
