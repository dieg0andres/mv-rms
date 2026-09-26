#!/bin/sh
set -eu
RMS_DB_PASSWORD=$(cat /run/secrets/db_password)
RMS_SECRET_KEY=$(cat /run/secrets/django_key)
export RMS_DB_PASSWORD RMS_SECRET_KEY
exec "$@"
