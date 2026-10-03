"""Repository-only navigation preparation; no record or API queries."""

from copy import deepcopy

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


def draft_presentation(groups, *, submitted=None, issues=(), conflict=False):
    bound_groups = deepcopy(groups)
    submitted = submitted if submitted is not None else {}
    controls = {}
    for group in bound_groups:
        for control in group["controls"]:
            path = control["path"]
            control["value"] = submitted.get(path, control.get("value", ""))
            control["errors"] = []
            control["submitted_choice"] = bool(
                control.get("kind") == "select"
                and control["value"]
                and control["value"] not in [choice[0] for choice in control["choices"]]
            )
            controls[path] = control
    errors = []
    for issue in issues:
        control = controls.get(issue.get("path"))
        message = issue["message"]
        if control is not None:
            control["errors"].append(message)
        errors.append({"target": control["id"] if control else None, "message": message})
    return {"field_groups": bound_groups, "errors": errors, "conflict": conflict}


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
