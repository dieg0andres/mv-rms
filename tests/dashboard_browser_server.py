"""Loopback-only WSGI harness for the invented dashboard browser journey."""

import argparse
from os import environ
from unittest.mock import patch
from wsgiref.simple_server import make_server

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.test import override_settings
from django.urls import path
from django.views.static import serve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
    application = get_wsgi_application()

    from rms.dashboard_views import FounderDashboardPage
    from rms_project.urls import urlpatterns as routes
    from tests.dashboard_fixtures import InventedDashboardProvider

    global urlpatterns
    urlpatterns = [*routes, path("static/<path:path>", serve, {"document_root": settings.BASE_DIR / "static"})]
    empty_listing = {"count": 0, "results": []}
    with (
        override_settings(ROOT_URLCONF=__name__, AUTHENTICATION_BACKENDS=["tests.dashboard_fixtures.FixtureAuthenticationBackend"]),
        patch.object(FounderDashboardPage, "provider", InventedDashboardProvider()),
        patch("rms.navigation_views.shared_service", return_value=empty_listing),
        patch("rms.test_plan_views.plan_service", return_value=empty_listing),
        make_server("127.0.0.1", args.port, application) as server,
    ):
        print(f"Invented dashboard fixture server: http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
