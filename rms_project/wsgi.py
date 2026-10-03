"""WSGI entry point for a developer-run loopback instance only."""

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
application = get_wsgi_application()
