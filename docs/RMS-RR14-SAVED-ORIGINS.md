# RR14 synthetic saved origins — MAU-179

This is an isolated synthetic candidate patch based on PR #6
`017927f18b0b1150a23bb824e16947aac99beefd` through `0010`. It is not an
activation for the installed app. There is no DDL, SQL ACL change, worker,
service, backfill, deployment, or new credential. RR19's `0011` remains
reserved; its rebase must reconcile shared Runs service and URL edits.

## Read scope and fixture custodian

Set `RMS_RR14_SCOPE_FILE` only on the disposable synthetic instance, to a file
outside Git readable by the RMS process, writable only by the fixture custodian.
The grants are never an API, an RMS role, or a replacement for the existing
assurance mutation policy. Start with no grant. After fixture seeding, the
custodian atomically replaces the file with the following shape (placeholders,
not real data):

```json
{
  "format": "rr14-disposable-synthetic-v1",
  "principals": {
    "<existing fixture user PK>": {
      "username": "<existing fixture username>",
      "cases": ["<invented case stable ID>"],
      "plans": ["<invented Test Plan stable ID>"]
    }
  }
}
```

An active existing `editor` or `founder_viewer` role **and** the matching
PK/username grant are necessary. Cases and Plans are individually scoped. Plan
versions must have an exact, synthetic Hypothesis → Case binding to a scoped
case. A relationship cannot confer a grant to another case or Plan. Exact
versioned children, hypotheses, families and assessments are readable only
through the applicable scoped anchor. An assessment naming an unscoped case
or family is withheld rather than returning partial sealed history. Shared
Stage 1 Source/Idea readers are unchanged. Protected counts, results and
search pagination are computed after filtering. Scoped denials use the normal
not-found response and protected HTTP responses are non-store. Role-only denial
is handled as before. Missing, unreadable, oversized, malformed or ambiguous
scope fails closed. Remove a principal, case or Plan from the file and replace
it atomically to revoke for subsequent requests; an in-flight request retains
its snapshot. Do not recycle fixture usernames/PKs or reuse the grant file for
another database. No authorship or assurance write grant confers a read.

### Synthetic Plan authoring

The JSON endpoints and CSRF-protected browser forms use the same write service.
Existing editor, schema, expected-version, and idempotency requirements still
apply. The write service checks the request's scope before receipt lookup and
checks the saved exact binding before acknowledging an eligible replay. New
receipts store only the internal binding; old receipt rows are not rewritten
and their serialized payload is never returned to a browser or API client.

| JSON POST (under `/api/v1`) | Browser POST | Acknowledgement |
| --- | --- | --- |
| `/test-plans` | `/test-plans/new` | `201 {"saved":true}` or an unpinned confirmation with a link to the Plan list. No generated identity, exact redirect, or automatic read grant. |
| `/test-plans/{plan}/corrections` | `/test-plans/{plan}/revise` | `201` (or `200` for no change) with `plan_id`, `plan_version_id`, `version`, and `no_change` when applicable. Browser redirects to that exact readable version. |
| `/test-plans/{plan}/data-checks` | `/test-plans/{plan}/data-checks/new` | `201 {"saved":true}`; browser redirects to the scoped checks list. No generated check identity. |

The fixture custodian finds new Plans through its isolated fixture channel,
grants named scope, then the editor discovers the Plan through the normal
scoped list. A correct tuple, original author, or signed receipt is not a
grant. Correction needs current Plan and proposed exact Hypothesis scope;
check needs current Plan, pinned Plan version and its exact requirement.
Repeated and changed keys do not bypass these checks. Missing and restricted
targets are indistinguishable. Direct fixture seeding is not an HTTP capability.

**Remaining freeze decision:** the synthetic walkthrough uses custodian-seeded
Hypotheses and cases. The candidate still holds the following existing writes
until Director authorizes a scoped receipt contract or explicitly excludes
them at the synthetic walkthrough boundary:

- JSON `/api/v1/{hypotheses,investigations,research-families}` create and
  `/{id}/corrections`; browser `/{hypotheses,investigations,research-families}/new`
  and `/{id}/revise` under each collection.
- JSON `/api/v1/idea-family-associations/{id}/corrections` and browser
  `/idea-family-associations/{id}/revise`.

Do not activate this candidate on installed users. The existing globally unique
synthetic external-reference conflict remains; use unique fixture references.

## MAU-169 binding

Call `rms.rr14_projection.read_saved_origins(actor=..., plan_id=...,
plan_version_id=...)` in the page adapter, or use
`GET /api/v1/test-plans/<plan_id>/versions/<plan_version_id>/rr14-origins`.
Pass the authenticated request actor, and exact scoped Plan/version from the
already-authorized view. Never fall back to a different version or expose a
requested-but-denied tuple, IDs or numeric deltas. The projection does not
dispatch, calculate broad totals, or duplicate a ledger in storage. Render the
count and links from `activity_trials.origins` and `early_closures.origins`.
`observed_at` is the completion time of this bounded read, not a historical
watermark; take before/after snapshots at quiescent fixture checkpoints. A
scoped empty version returns empty arrays and 0 synthetic activity/closures;
a denied version has no projection. Integrity failures are unavailable, not
zero. `real_totals` are all null: render “Unavailable,” not zero; the separate
`real_credit_from_these_records` reports zero real full-validation/qualification
credit for these synthetic records, not real ledger totals.

The origin grain is canonical `RunAttempt` ID (failed, completed or otherwise)
and once-only original `close_rejected` on the original exact result. Closure
requires verified bytes/manifest, result, criteria and a usable original
decision's exact review edge; decisions written after supersession don't
manufacture a new original. Retry edges/events supply provenance, not extra
attempts. Replay, correction, lessons, invalid/inconclusive reviews and
return-for-revision are not credited. This is not a general closure lifecycle.

## Verification and recovery

On a separately provisioned invented-only PostgreSQL 17 target with `pgcrypto`
and the pinned toolchain, run `manage.py test --noinput tests.django_rr14_scope_tests
tests.django_run_attempt_registration_tests tests.django_run_frontend_template_tests
tests.django_test_plan_frontend_render_tests`. Django creates and drops its own
test database. The tests use `rr14-eng-<unique suffix>` identities and a private
temporary scope file. Do not point them at Test's reserved target. The default
is deny, so other read-dependent legacy fixtures require explicit custodian
grants before those suites can serve as scoped regression evidence.

No new DB permission or migration is needed; ordinary runtime needs only the
existing reads of canonical parents, relationships, attempts, events, results,
reviews and decisions. An SQL dump is not a grant backup. Restore into an
isolated target with scope disabled, verify saved rows, exact identities and
DB/evidence watermarks, and have the fixture custodian reissue only currently
approved scope. Do not copy revoked/stale grants from an old snapshot. To stop
exposure, remove the fixture file and disable the projection binding; do not
reverse populated migrations, clear history, or fall back to unrestricted
reads. No populated upgrade or restore execution is claimed here.
