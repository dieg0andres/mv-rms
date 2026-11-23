# Founder dashboard: synthetic software slice

Base: `0358987d313abe0f5f654aa27ad9e80cfda76469` (confirmed GitHub `master`).
Scope: [MAU-169](/MAU/issues/MAU-169) under [MAU-33](/MAU/issues/MAU-33),
[MAU-25 revision 3](/MAU/issues/MAU-25#document-plan) and the
[November 22, 2026 synthetic release direction](/MAU/issues/MAU-159#comment-823664a6-3c9a-42d9-848d-6f08715f9346).
This is not an installed release, a Stage 2 verdict, or real-use authority.

## Behavior and provider boundary

- Authorized users follow **Home → Founder dashboard**. `GET /founder-dashboard`
  uses the existing `IsRmsReader` permission (`editor` and `founder_viewer`),
  negotiates the existing deny page for unknown/denied principals, and returns
  `private, no-store` with `Vary: Authorization, Cookie` via `RmsPage`.
  No new API, query scope controls, browser-side data requests or mutation route.
- There is no provider in application configuration. Until independently sourced
  projections are reviewed and wired, the dashboard shows pipeline and ledger
  sources as unavailable. The invented provider is only injected by tests.
- Proposed adapter: `pipeline(actor=...)` consumes Codex's shared authorized case
  projection, not a second store. Map saved owner, blocker and next action without
  deriving them; use `None` for unknown and distinguish an explicit no-blocker
  value supplied by the source. Stage, health, exceptions and reported authority
  mode are also source facts. `last_changed_at` is a timezone-aware datetime or
  `None`; age is relative to the projection's `as_of`, not a live clock. Only
  authorized metadata may be returned, including watermarks. The adapter must
  reject unauthorized scope before projection; query-string input cannot select
  the actor or scope. Confirm exact source fields, visibility predicate, timestamp
  semantics, staleness policy and safe exact-version reference with Codex and the
  Director before binding. There are no record links or duplicate saved fields in
  this slice. When the contract lands, verify parity with the source search/API for
  the same authorized and denied actors, including version references.
- `activity`, `early_closures`, `full_validation`, and `qualifications` supply four
  independent scoped snapshots. Each origin applies authorization before counting
  and only returns safe source/version/policy metadata. Empty current scope can
  return `0`; missing or failed source returns `None` or raises
  `DashboardSourceUnavailable`. Stale or unknown-freshness ledger counts are not
  presented as current; stale case rows are marked historical. Availability must
  not vary based on the presence of records hidden from the caller. Never infer
  one ledger from another, the pipeline, or a raw search result count.
- The fixture-only projection has **no input for real credit**; a known current
  synthetic snapshot shows zero real credit from its examples, even for purported
  passing fixtures, variants, reruns, failed and inconclusive evidence. It makes
  no claim about real totals. Any later real-credit eligibility policy belongs to
  Backend and requires independent Risk review and separate authority.

## Verification and handoff

Local configuration: Python 3.13.15, Django 5.2.17, DRF 3.18.1, Node 24.20.0.
No DB, live routes, evidence stores or release Test/restore resources were used.

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py test tests.django_dashboard_tests tests.django_hypothesis_frontend_navigation_tests
node --check tests/browser/test-founder-dashboard.mjs
```

The 26 request/navigation tests passed, including denied/no-provider-call,
cache headers, query-scope spoofing, withheld rows, four independently scoped
counts, stale and failed origins, escaped values and viewer/editor read-only
behavior. Local loopback WSGI HTTP smoke inspected rendered HTML: authorized
Home and viewer/editor dashboard `200`, unassigned dashboard `403`, CSS `200`,
expected case visibility and no scope escalation from query parameters.
This does not establish PostgreSQL or production object-scope behavior.

On an already authorized isolated machine with the project's Playwright and
Chromium available (not the release's Test/restore resources), run these in
separate terminals:

```sh
.venv/bin/python -m tests.dashboard_browser_server
node tests/browser/test-founder-dashboard.mjs
```

The fixture WSGI harness binds only to `127.0.0.1`, uses invented Basic Auth
principals and serves existing local CSS. Record the verified candidate SHA and
actual keyboard focus/360px/role results. **Browser not run here:** Node could not
resolve `playwright` and no local Chromium was available. No browser dependency
was obtained externally. For bounded Research review, evaluate whether the founder
can find the page, tell unavailable from a scoped zero, and identify who acts next
on a blocked invented case. Do not use real data or interpret results as credit.

## Migration, backup and rollback

No schema changes, migrations, data population, persistent fixture state, app
configuration changes or evidence objects. No new backup/restore work is required
for this source-only slice; existing recovery policy stays unchanged. Reverting
the source change removes the link and route without touching database/evidence
history. Any later saved-provider or persistence change needs its own review.
