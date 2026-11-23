"""Authenticated browser surface for the synthetic dashboard."""

from django.template.response import TemplateResponse

from .dashboard_projection import dashboard_context
from .navigation_views import navigation_context
from .permissions import IsRmsReader
from .views import RmsPage


class FounderDashboardPage(RmsPage):
    permission_classes = [IsRmsReader]
    http_method_names = ["get", "head"]
    provider = None

    def get(self, request):
        context = dashboard_context(actor=request.user, provider=self.provider)
        context["navigation"] = navigation_context(section="dashboard")["navigation"]
        return TemplateResponse(
            request._request,
            "rms/founder_dashboard.html",
            context,
        )
