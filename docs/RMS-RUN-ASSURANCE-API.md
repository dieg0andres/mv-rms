# Exact-result assurance (MAU-166, synthetic only)

This slice implements the MAU-159 exact-result review interface. It never dispatches, changes eligibility, allocates a cycle or produces a qualification. Existing editor and founder-viewer read access still applies. No backend write capability is enabled by default, and no real authority is created or delegated here.

## Shared signatures and browser integration

In `rms.run_assurance_services`, `scope` below stands for the **keyword-only** `actor, plan_id, version_id, run_id, result_version_id`; the actor comes from the authenticated request, not form data. The API prefix is `/api/v1/test-plans/{plan_id}/versions/{version_id}/runs/{run_id}/results/{result_version_id}`. The `version_id` path component is rendered as `plan_version_id`.

| Service signature | API call | Payload / result |
| --- | --- | --- |
| `read_assurance(*, scope)` | `GET /assurance` | Exact scope and digests; `result_head_id`, `review_head_id`, `decision_head_id`, `lesson_head_id`, `available_actions` |
| `list_assurance(*, scope, kind, offset='0')` | `GET /{kind}?offset=0` | `{records, next_offset}` in append order; at most 50 per page |
| `read_assurance_record(*, scope, kind, record_id)` | `GET /{kind}/{record_id}` | Canonical original row plus historical links and current status |
| `publish_review(*, scope, idempotency_key, payload)` | `POST /reviews` | `expected_review_id, artifact_manifest_digest, outcome, rationale, limitations, correction_reason` |
| `record_decision(*, scope, idempotency_key, payload)` | `POST /decisions` | `review_id, expected_decision_id, disposition, rationale, correction_reason` |
| `record_lesson(*, scope, idempotency_key, payload)` | `POST /lessons` | `review_id, decision_id, expected_lesson_id, claim, limitations, uncertainty, applicability, implication, correction_reason` |

`kind` is one of `reviews`, `decisions`, `lessons`. Capabilities use singular names: `review`, `decision`, `lesson`. Missing/empty hints mean deny; hints are advisory, not authority. Posts require `Idempotency-Key`; the shared service returns `StoredResponse` with a canonical JSON 201 response. Absent heads and initial `expected_*_id`/`correction_reason` are `null`. To correct, send the exact prior row for that kind plus a non-blank reason. Reject unknown fields, including any attribution field. The manifest field is **`artifact.manifest_digest`**, not the artifact byte `sha256` or the result `row_digest`.

The stable record fields include the full exact subject scope, `result_digest`, `artifact_manifest_digest`, the applicable `review_id` / `decision_id` / `lesson_id`, `supersedes_<kind>_id` (singular), sequence, authenticated `actor_id`, `recorded_by`, `recorded_at`, `row_digest` and the substantive assessment/decision/lesson fields. A GET additionally includes `current`, `superseded_by_id`, `result_head_id` and `impact` (`decisions` and/or `lessons` lists of IDs where applicable). `current` tracks the currently bound history, not institutional approval. For example, a current `inconclusive` review cannot support a disposition. When a review is superseded, its older dispositions and their lessons remain visible with their original references, but are not current. Initial or corrective dispositions accept only `close_rejected` and `return_for_revision`. `pass` requires every applicable mandatory criterion to pass. `inconclusive` and `invalid` cannot support new downstream reliance.

Requests do not fall forward to a newer result or use review/disposition IDs from another subject. Use a fresh `read_assurance` after a 409 and display history using exact IDs. Canonical replay returns the existing receipt, not a fresh append, only after reauthorizing the requested capability and reverifying evidence. Reads and responses are private and not cacheable. Expect 400 for invalid shape/key; 401 unauthenticated; 403 for denied readers or effective capabilities; 404 for absent or out-of-scope records; 409 for stale state, conflicting replay, unusable reliance or unverifiable evidence. The controller checks client-provided versions and authority again inside the same Run row lock used by result corrections. The lock, pinned criterion re-evaluation and byte verification are not replaceable with a frontend preflight.

## Invented fixture only

`editor` and `founder_viewer` are Django groups that admit reads; neither grants an assurance action. Membership in `founder_viewer` denies all assurance writes and receipt replay, even with a matching grant or simultaneous `editor` membership. These application controls do not provision a PostgreSQL role or grant any SQL privilege.

| Invented fixture account | Read admission | Effective action for the exact result | Planned UI label |
| --- | --- | --- | --- |
| Founder viewer | `founder_viewer` | None, even with a matching grant | View result and history |
| Unrelated editor | `editor` | None | View result and history |
| Independent reviewer | `editor` | `review`, expires one hour after fixture issuance | Publish review |
| Disposition author | `editor` | `decision`, expires one hour after fixture issuance | Record disposition |
| Lesson author | `editor` | `lesson`, expires one hour after fixture issuance | Record lesson |

Only an authorized, disposable synthetic test setup supplies `RMS_SYNTHETIC_ASSURANCE_GRANTS` and `RMS_SYNTHETIC_ASSURANCE_PROVENANCE` via trusted settings; both are absent by default. No app API, browser form, migration or group provisions them. Map `grant_key(actor, result, action)` to an explicit timezone-aware `datetime` expiry. This key binds the authenticated account's stable ID, exact result UUID, verified row digest and single action. Missing, unrelated or malformed grants deny; at or after expiry (or on removal) both new writes and receipt replay deny. Grants never follow corrections. Read access to original history is unaffected. The three synthetic write actors are separate accounts in `tests/django_run_assurance_tests.py`; keep any test credentials inside the disposable environment. These are planned UI labels; Frontend verifies rendered copy after integration and mounts only actions returned by the exact-result backend.

Map `provenance_key(record)` to the known synthetic creator ID from authenticated creation and seed provenance. Never resolve `created_by` to a user by name alone; omit uncertain bindings. The backend checks exact plan/design/link authors and recorded registration, lifecycle, retry and result/evidence actors, including retry ancestry. A contributor cannot review even with a review grant. An actor cannot record a disposition on their own review even with a disposition grant. The separate lesson account requires an explicit lesson grant. Leave this mechanism unconfigured on installed or shared environments.

## Migration, grants and recovery handoff

`0010_run_assurance` is atomic and additive over `0009_run_results`. It creates UUID-keyed `rms_runreview`, `rms_rundecision`, and `rms_runlesson` (zero new sequences), with protected exact result and downstream FKs, unique predecessor/sequence rules and three triggers per table: `ra_binding` (insert), `ra_no_edit` (update/delete) and `ra_no_truncate` (truncate). The invoker-rights insert function locks the existing Run, checks active exact references/digests/byte hash, disallows pass on a non-passing result, and checks decision distinctness. Application policy still owns the trusted synthetic actor grants/provenance and stricter evidence validation; SQL is not a replacement for that policy.

**Proposed to Operations for exact-candidate rehearsal, not provisioned here:** `SELECT, INSERT` only on the three new tables for the ordinary runtime. No new table update/delete/truncate, sequence, schema-create, function-create or global/default privileges. Keep existing `SELECT` on prior RMS context tables and `UPDATE (id)` on `rms_runattempt` for the shared `FOR UPDATE`, plus the already required pgcrypto `public.digest(bytea, text)` execute grant. The migrator owns/creates and attaches `rms_assurance_check_binding()` and existing append-only function guards. Check the installed trigger/function owners, execution ACLs and behavior on a clean restore; grant the ordinary role no DDL or direct elevated trigger function access. Verify with the actual runtime identity: inserts and SQL denials, exact prior rows and actor/edge/digest comparisons, migration leaf, and all three table/trigger inventories. No access or ACL changes to an installed or shared database were performed.

Rollback a failed atomic migration transaction and inspect the migration leaf and schema before retry. Once rows exist, reverse migration refuses to discard them. Prefer rolling back only the application image after schema/read compatibility is verified with Operations, or recovering via the authorized restore path (including bytes/digests and history). Do not drop the tables or remove their guards to recover service.

## Reproduce engineering checks

Use the approved engineering PostgreSQL binding (`postgres-test-env.sh`) and a run-unique Django `DATABASES['default']['TEST']['NAME'] = 'test_mau166_<unique-run-id>'` via an ephemeral test settings module; confirm that target is unused before the first run. Do not use the installed preview, base database for writes, reserved independent Test slot, or restore database. Run:

```sh
python manage.py test tests.django_run_assurance_tests -v 2 --noinput
python manage.py test tests.django_run_result_tests \
  tests.django_run_attempt_registration_tests tests.django_run_frontend_page_tests \
  tests.django_run_frontend_template_tests -v 2 --noinput
```

Run the commands separately: both suites' real-commit concurrency tests deliberately retain append-only rows until Django drops the disposable database and cannot share one fixture lifecycle. The fixture creates only invented authenticated principals and observations via the existing hypothesis/Test Plan/Run lifecycle fixture. The test owner temporarily introduces one corrupt byte payload inside a rolled-back test savepoint; no saved fixture or original row is repaired. Engineering's results do not substitute for named Director review, independent Test/Risk acceptance, an ordinary-runtime rehearsal, browser verification or restore.
