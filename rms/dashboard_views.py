"""Authenticated browser surface for the synthetic dashboard."""

from django.conf import settings
from django.db import DatabaseError
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware

from .dashboard_projection import dashboard_context
from .navigation_views import navigation_context
from .permissions import IsRmsReader
from .services import ServiceError
from .views import RmsPage


class FounderDashboardPage(RmsPage):
    permission_classes = [IsRmsReader]
    http_method_names = ["get", "head"]
    provider = None

    def get(self, request, plan_id=None, version_id=None):
        scoped = plan_id is not None and version_id is not None
        context = dashboard_context(actor=request.user, provider=None if scoped else self.provider)
        context["navigation"] = navigation_context(section="dashboard")["navigation"]
        if scoped:
            context.update(
                rr14_scoped=True,
                rr14=rr14_context(actor=request.user, plan_id=plan_id, version_id=version_id),
            )
        return TemplateResponse(
            request._request,
            "rms/founder_dashboard.html",
            context,
        )


def read_rr14_projection(*, actor, plan_id, plan_version_id):
    from .rr14_projection import read_saved_origins
    from .run_result_services import ResultIntegrityError

    try:
        return read_saved_origins(actor=actor, plan_id=plan_id, plan_version_id=plan_version_id)
    except ResultIntegrityError:
        return None


def rr14_context(*, actor, plan_id, version_id):
    """Allowlist presentation values from the already scope-checked reader."""
    if not getattr(settings, "RMS_RR14_SCOPE_FILE", ""):
        return None
    try:
        saved = read_rr14_projection(actor=actor, plan_id=plan_id, plan_version_id=version_id)
        if (
            saved is None
            or saved["classification"] != "synthetic"
            or (saved["plan_id"], saved["plan_version_id"]) != (plan_id, version_id)
        ):
            return None
        activity = saved["activity_trials"]["count"]
        closures = saved["early_closures"]["count"]
        credit = saved["real_credit_from_these_records"]
        cycles, qualifications = credit["full_validation_cycles"], credit["qualifications"]
        observed_at = parse_datetime(saved["observed_at"])
        if (
            any(type(value) is not int or value < 0 for value in (activity, closures, cycles, qualifications))
            or (cycles, qualifications) != (0, 0)
            or observed_at is None
            or not is_aware(observed_at)
        ):
            return None
    except (ServiceError, DatabaseError, KeyError, TypeError, ValueError):
        return None
    return {
        "plan_url": reverse("rms-test-plan-version", args=(plan_id, version_id)),
        "activity": activity,
        "closures": closures,
        "cycles": cycles,
        "qualifications": qualifications,
        "observed_at": observed_at,
    }
