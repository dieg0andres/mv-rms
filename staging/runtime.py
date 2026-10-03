"""Private synthetic staging adapter outside the pinned application tree."""
import base64
import binascii
import hashlib
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path('/srv')
metadata = json.loads((ROOT / 'metadata.json').read_text())
RELEASE = ROOT / 'releases' / metadata['commit']
if metadata['commit'] != '0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0':
    raise RuntimeError('Unexpected application commit')
sys.path.insert(0, str(RELEASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_project.settings')
import django
django.setup()
from django.contrib.auth import authenticate
from django.core.wsgi import get_wsgi_application
from request_policy import unsafe_request_allowed

application = get_wsgi_application()
asset = RELEASE / 'static/rms/rms_forms.js'
if not RELEASE.is_dir() or hashlib.sha256(asset.read_bytes()).hexdigest() != metadata['static_sha256']:
    raise RuntimeError('Staging product/static identity mismatch')


def reply(start_response, status, body, content_type, headers=()):
    start_response(status, [('Content-Type', content_type), ('Content-Length', str(len(body))),
                            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                            *headers])
    return [body]


def staging_app(environ, start_response):
    path = environ.get('PATH_INFO', '')
    if path == '/__staging/health' and environ.get('REMOTE_ADDR') == '127.0.0.1':
        try:
            from django.db import connection
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            return reply(start_response, '200 OK', b'ok\n', 'text/plain')
        except Exception:
            return reply(start_response, '503 Service Unavailable', b'unavailable\n', 'text/plain')
    if environ.get('HTTP_HOST') != os.environ['RMS_STAGING_HOST']:
        return reply(start_response, '400 Bad Request', b'Invalid host.\n', 'text/plain')
    if not unsafe_request_allowed(environ, os.environ['RMS_STAGING_HOST']):
        return reply(start_response, '403 Forbidden', b'Invalid request origin.\n', 'text/plain')
    environ['HTTP_HOST'] = 'localhost'
    header = environ.get('HTTP_AUTHORIZATION', '')
    try:
        scheme, encoded = header.split(' ', 1)
        if scheme.lower() != 'basic':
            raise ValueError
        username, password = base64.b64decode(encoded, validate=True).decode('utf-8').split(':', 1)
        user = authenticate(username=username, password=password)
    except (ValueError, UnicodeError, binascii.Error):
        user = None
    if user is None or not user.is_active:
        return reply(start_response, '401 Unauthorized', b'Authentication required.\n', 'text/plain',
                     [('WWW-Authenticate', 'Basic realm="RMS synthetic staging"')])
    if not user.groups.filter(name__in=('editor', 'founder_viewer')).exists():
        return reply(start_response, '403 Forbidden', b'Forbidden.\n', 'text/plain')
    if path in ('/', '/__staging/version'):
        commit = html.escape(metadata['commit'])
        summary = html.escape(metadata['summary'])
        body = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<title>RMS synthetic staging</title><h1>RMS synthetic staging</h1>'
                '<p>Fictional data only. Not research approval or production.</p>'
                f'<p>Deployed application commit: <code>{commit}</code></p>'
                f'<p>Change summary: {summary}</p>'
                '<p><a href="/sources/new">Source editor</a> (editor only). '
                'History links are available after creating a Source.</p></html>').encode()
        return reply(start_response, '200 OK', body, 'text/html; charset=utf-8')
    if path == '/static/rms/rms_forms.js':
        return reply(start_response, '200 OK', asset.read_bytes(), 'text/javascript; charset=utf-8')
    return application(environ, start_response)
