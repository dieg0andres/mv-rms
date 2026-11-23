# Synthetic lifecycle and result API (MAU-164)

This extends the registration contract from MAU-159. Source: MAU-25 plan revision 3,
§§4, 7–9. An attempt reports an invented external observation; RMS does not dispatch
work. A completed attempt is not a research pass, qualification, or cycle credit.

## Routes and preconditions

Paths below are relative to `/api/v1/test-plans/{plan_id}/versions/{version_id}/runs/{run_id}`.
The exact plan and version must match the attempt. Editors can write; editors and
founder viewers can read authorized synthetic records. All responses are private
and non-cacheable. Denials do not create records or consume idempotency keys.

| Method and suffix | Behavior |
| --- | --- |
| `GET` (empty suffix) | Attempt identity, state, `current_event_id`, ordered events, retry links, exact applicable `criteria`, and writer-only action hints (below). |
| `GET /events` | Ordered append-only lifecycle, including the current event ID; an empty chain means `registered`. |
| `POST /events` | `{expected_event_id, state, reason}`. Use `null` before any event. Recorded transitions: `registered → running/failed/cancelled`; `running → completed/failed/cancelled`. Terminal events are never overwritten. |
| `POST /retry` | `{expected_event_id, external_reference, reason}`. Only on a failed or cancelled terminal event with no existing successor; new synthetic reference and run ID, identical exact configuration and reported identities. Register changed inputs separately. |
| `GET /results` | Latest-first revision metadata; optional `offset`, up to 50 per page, with `next_offset`. |
| `POST /results` | Publish an initial revision or full correction, only on the exact completed event. See payload below. |
| `GET /results/{result_version_id}` | One immutable version (`RESV-…`), exact criterion assessments and artifact manifest. |
| `GET /results/{result_version_id}/artifact` | Verified manifest and exact `content_base64`; bytes are not rendered inline as a document. For custody plans, the same current rights and receipt checks as custody export apply. |

`read_run` and `GET` on the attempt detail omit both `available_actions` and
`allowed_event_states` for readers without write access. Writers receive
`available_actions: []` when no action is eligible. `event` is accompanied by
`allowed_event_states` from the lifecycle transition table. `retry` disappears
when a successor exists. `result` allows initial publication or correction on a
completed execution and makes no claim about criteria passing. Clients should
render only advertised actions and event states. Hints are a snapshot, not
authorization; POST still checks permissions, state and expected heads.

Every POST requires `Idempotency-Key`. Actor, method, path and original payload bind
the committed response. Repeating the exact request returns the original 201 and
response bytes. Conflicting reuse, stale expected IDs, or invalid state transitions
return 409; invalid shapes return 400; out-of-scope object paths return 404 only
after role authorization. Writes serialize on the attempt row. On any conflict,
retrieve the exact record before forming a new intent with a fresh key.

## Result payload and interpretation

- `completed_event_id`, `expected_result_version_id`, `correction_reason`, `summary`,
  `assessments`, `artifact`. Use null expectation and reason for the first version.
  A correction supplies the observed current `result_version_id`, nonblank reason,
  and a full replacement payload. The `run_id` is the stable logical result anchor;
  every `result_version_id` is immutable and names its immediate predecessor.
- Each assessment has `criterion_edge_id`, `criterion_version_id`, `sample_satisfied`,
  `observed_value`, `reported_outcome`, and `explanation`. Cover each applicable
  edge exactly once. Baseline-only edges do not apply to variations. Numeric rules
  compare precise decimal strings to the frozen thresholds; `reported_outcome`
  must be null. Objective rules take an explained reported outcome (`passed`,
  `failed`, `inconclusive`), with `observed_value` null. Inadequate samples cannot
  pass. This does not validate the truth of the reporter's sample assertion.
- Any mandatory failure yields `mandatory_fail`; if there are no applicable
  mandatory criteria or any mandatory outcome is inconclusive, the result is
  `inconclusive` unless another mandatory criterion failed. All applicable
  mandatory criteria passing yields `criteria_pass`, not independent acceptance.
- `artifact` has canonical `content_base64` (1–8192 decoded bytes), `sha256`,
  and `synthetic_confirmed: true`. The server stages and decodes in memory,
  computes and compares the digest, then seals in the same PostgreSQL transaction
  as the result. The manifest binds bytes to provenance, exact plan/run/config,
  completed event, assessment digest and exact result watermark. A mismatch
  rejects publication; unexpected stored inconsistencies fail closed on read
  without rewriting stored originals. This local synthetic seal does not prove
  external provenance, independent custody, rights or disaster recovery.

Independent review consumers must use `get_result_version` in
`rms/run_result_services.py` (or equivalent authorized exact binding) and store
the concrete `RunResultVersion` and `row_digest`, never resolve the newest result
implicitly. A correction does not update existing review, decision or lesson links.

## Migration and test handoff

`0009_run_results` depends on `0008_run_attempts`; creates three record tables and
installs PostgreSQL guards for append-only rows, exact predecessor bindings and
artifact byte length/digest. Existing plans and attempts are not rewritten. The
migration is atomic; on failure inspect the transaction/error before retrying.
Roll back application routes, not history. Reverse migration refuses if any new
table has records. Do not disable guards or drop populated tables to roll back.

Run on a disposable PostgreSQL test target with the pinned environment:

```sh
python manage.py test tests.django_run_result_tests tests.django_run_attempt_registration_tests tests.test_test_plan_backend_validation --noinput
```

Fixtures: invented `RMS-HN-F1-20261003` context plus `complete_fixture()` Test Plan
and invented attempt and artifact labels in `tests/django_run_result_tests.py`.
The concurrency test commits in two sessions and the Django runner drops its
disposable database; do not use `--keepdb` for that suite. No staging or live
database, external execution, real evidence or role changes are needed.
