"""Settings for the task-scoped PostgreSQL RMS development instance."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("RMS_SECRET_KEY", "local-synthetic-rms-only-not-for-deployment")
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rms.apps.RmsConfig",
]
MIDDLEWARE = []
ROOT_URLCONF = "rms_project.urls"
TEMPLATES = []
WSGI_APPLICATION = "rms_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("RMS_DB_NAME", "rms_vs1"),
        "USER": os.environ.get("RMS_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("RMS_DB_PASSWORD", ""),
        "HOST": os.environ.get("RMS_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("RMS_DB_PORT", "5432"),
        "CONN_MAX_AGE": 0,
    }
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "rms.api.exception_handler",
    "UNAUTHENTICATED_USER": None,
}
