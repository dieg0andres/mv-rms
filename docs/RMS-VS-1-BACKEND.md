# RMS-SI-1.0 backend development contract

This repository implements the frozen RMS-SI-1.0 synthetic-only Source completion and Source-to-Idea backend. It is not a deployed service, Stage 1 acceptance, independent Risk acceptance, or authority to use real or protected research data.

## Pinned stack

- CPython 3.13.15
- Django 5.2.17 LTS
- Django REST Framework 3.18.1
- psycopg / psycopg-binary 3.3.6
- PostgreSQL 17.11

`requirements.lock` pins every Python artifact by SHA-256. `stack.lock` records the selected CPython, wheel, PostgreSQL, and runtime-library artifacts and hashes. Task-local binaries and database files are excluded from Git.

## Persistence and migration behavior

`rms.0001_initial` and `rms.0002_source_invariants` retain the delivered Source, SourceVersion, SourceManifest, and global IdempotencyRecord schema and append-only database triggers.

`rms.0003_source_idea_contract` is one atomic migration that:

- adds Source descriptive snapshots, correction metadata, actor, and immutable `SRCV-{uuid}` identities;
- temporarily removes only the SourceVersion row-change trigger inside the migration transaction, backfills each existing public version ID deterministically from its immutable internal UUID, preserves all raw content and historical manifest bytes, and restores the trigger before commit;
- makes the required backfilled fields non-null and the public version ID unique;
- creates stable Idea, immutable IdeaVersion, and ordered immutable IdeaContribution tables; and
- adds same-Idea immediate-predecessor, one-step watermark, stable-row guard, and version/edge immutability constraints.

A failure rolls back the complete migration transaction, including trigger changes. Stop the application, preserve the database and command output, diagnose the failed migration, and retry only after review. Do not fake a migration, edit applied migration history, substitute SQLite, or delete evidence rows. The explicit reverse SQL removes the new Idea triggers before Django drops the new tables and Source fields; reversal is a reviewed development rollback only and would discard the new increment's rows.

Apply only to an authorized task-scoped PostgreSQL database:

```console
.paperclip-runtime/venv/bin/python manage.py migrate --noinput
```

## API contract

HTTP Basic authentication remains a loopback development mechanism only. Backend authorization precedes object lookup:

- `editor`: authenticated reads and all Source/Idea writes;
- `founder_viewer`: authenticated Source/Idea reads only;
- other authenticated users: the delivered authenticated-read baseline and no writes; and
- anonymous: generic `401` before retrieval.

RMS-SI-1.0 routes:

```text
POST /api/v1/sources
POST /api/v1/sources/{source_id}/corrections
GET  /api/v1/sources/{source_id}
GET  /api/v1/sources/{source_id}/versions
GET  /api/v1/sources/{source_id}/manifest[?through_version=N]
POST /api/v1/ideas
POST /api/v1/ideas/{idea_id}/corrections
GET  /api/v1/ideas/{idea_id}
GET  /api/v1/ideas/{idea_id}/versions
GET  /api/v1/readiness
```

Writes require JSON and `Idempotency-Key`. Source and Idea corrections require an expected latest integer version, a reason, and a complete snapshot. Source correction accepts `content_base64: null` to carry the predecessor bytes without returning them to the client. Every Idea contribution binds one immutable `source_version_id`; reads expand only the exact immutable Source version's safe summary and never raw content.

The shared services acquire a transaction-scoped advisory lock for the global idempotency key, then a stable Source/Idea row lock for corrections. Stable/version rows, Source manifest snapshots where applicable, Idea contribution edges, exact response bytes, idempotency state, and latest-version watermarks commit together. A stale/concurrent loser writes nothing. A replay of the winning request returns its stored `201` response bytes even after later corrections.

## Deterministic fixture

`RMS-VS-1-F1` still contains only invented bytes. Its existing internal UUIDs, timestamps, content, ordered versions, and manifest bytes are unchanged. Its public Source-version IDs derive from those immutable UUIDs, so loading before or after migration converges on the same fixture identity.

```console
.paperclip-runtime/venv/bin/python manage.py load_rms_vs_1_fixture
.paperclip-runtime/venv/bin/python manage.py export_rms_vs_1_fixture
```

The export contains public history metadata and Base64-encoded canonical manifest bytes; it never contains raw Source content. A mismatch stops with `CommandError` rather than replacing rows.

## Development verification

Set `RMS_DB_*` to an authorized PostgreSQL 17.11 database. Backend verification commands are:

```console
PYTHONDONTWRITEBYTECODE=1 .paperclip-runtime/venv/bin/python -m unittest discover -v
PYTHONDONTWRITEBYTECODE=1 .paperclip-runtime/venv/bin/python manage.py test \
  tests.django_source_api_tests \
  tests.django_source_history_page_tests \
  tests.django_fixture_tests \
  tests.django_contract_tests \
  tests.django_source_idea_tests -v 2
.paperclip-runtime/venv/bin/python manage.py makemigrations --check --dry-run
.paperclip-runtime/venv/bin/python manage.py check
```

The focused suite covers field/null/enum validation, timestamp offset normalization and naive-time rejection, Source correction preservation, historical manifest retrieval, exact Source-version contribution binding, byte non-disclosure, editor/viewer/anonymous denials, global idempotent replay/conflict, stale rollback, and one-winner Source/Idea concurrency. Independent Test Engineering still verifies the exact integrated candidate.

## Boundaries

There is no import, scoring, summary, search, broad dashboard, connector, background worker, real/protected data, research execution, trading, deployment, or broader RMS record flow in this backend increment. `accepted` is workflow intake only and creates no research or trading approval.
