# RMS-VS-1 frontend contract

## Bounded page

GET /sources/<source_id>/history is the only server-rendered page added by RMS-VS-1. It is authenticated, founder_viewer-only, and read-only. It uses the same get_source, source_detail, source_history, and latest_manifest services as the frozen API; it contains no content bytes, forms, mutation controls, search, approval, dispatch, delegation, administration, or dashboard links.

The page displays the stable Source ID, explicit synthetic/local mode, current version, ordered versions and immediate correction links, exact byte lengths, content SHA-256 values, and manifest SHA-256/length. Its manifest link is the existing authorized GET /api/v1/sources/<source_id>/manifest download route, so its body and X-Manifest-SHA256 header remain API-owned.

Anonymous requests return the same generic HTML 401 for valid and missing Source IDs before lookup. Authenticated non-viewers receive generic 403; a viewer sees generic 404 only after authorization. Missing manifest state produces generic 409 without a data payload.

## Development tests

tests/django_source_history_page_tests.py uses only invented F1 bytes and a local founder-viewer. It asserts page/API metadata parity, absence of raw content, generic anonymous denial, and byte-identical manifest download.

Run in a prepared exact task-local Django/PostgreSQL runtime:

PYTHONDONTWRITEBYTECODE=1 .paperclip-runtime/venv/bin/python manage.py test tests.django_source_history_page_tests -v 2
PYTHONDONTWRITEBYTECODE=1 .paperclip-runtime/venv/bin/python manage.py check

At this handoff the assigned workspace contains no populated .paperclip-runtime/venv; the discoverable CPython 3.13.15 has no Django package. manage.py check therefore exited 1 with ModuleNotFoundError for django. No browser, Django, permission, parity, or manifest-download test is claimed executed here. This is not a Stage 1, deployment, or Risk-acceptance claim.
