# Synthetic Runs and Results

Source contracts: MAU-25 staged delivery plan, revision 3, §§4, 7–9;
`RMS_STRATEGY_SPECIFICATION_AND_TEST_PLAN_DESIGN_CONTRACT_V1_0.md`;
`RMS-TP-API-1.md`. Initial software scope: MAU-159, November 22, 2026.

## Registration

- JSON and browser collections: `/api/v1/test-plans/{TPL}/versions/{TPLV}/runs`
  and `/test-plans/{TPL}/versions/{TPLV}/runs`. Editors write and read, founder
  viewers read, outsiders cannot resolve records. Both IDs must match an
  authorized synthetic definition. Corrections do not move earlier attempts.
- JSON POST requires `Idempotency-Key` and exactly `configuration_key`,
  `external_reference` (`synthetic:<slug>`), `code_commit` (lowercase full
  40-hex Git identifier), `code_manifest_digest`, `dependency_lock_digest`,
  `dataset_manifest_digest`, `parameter_digest`, `environment_digest`
  (lowercase SHA-256). Parameter digest must match the selected baseline or
  variation. Other digests are reported identities, not verified captures.
  GET accepts an optional numeric `offset`.
- `RunAttempt` records immutable registration with `RUN-…` ID, exact version
  and config, reporter, time and row digest. Repeated key + same editor, path
  and body replays the original 201. Key conflict or duplicate synthetic
  reference is 409. Migration 0008 guards exact configuration and history.
- Registration does not run an experiment, fetch evidence, or assert a
  result, authority, rights, independent review, qualification or cycle count.
  No real data, credentials, or external activity.

## Runs browser API writes (RR01)

- The shared Runs JSON write boundary covers POST for registration, events,
  reconciliations, retries, results (including corrections), and exact-result
  reviews, decisions and lessons. GET/HEAD/OPTIONS, unsupported methods,
  browser forms and other API families retain their existing behavior.
- A Basic-auth browser JSON caller uses the masked `csrfmiddlewaretoken` from
  its authorized same-origin page form (for registration, the Runs collection
  page). Send it as `X-CSRFToken` with the page-issued CSRF cookie and the usual
  `Idempotency-Key` in a same-origin request. Do not log the token. An empty 403
  means no write or replay occurred; reload the form before an intentional
  retry with the same key and unchanged payload. Anonymous requests still
  receive the Basic 401 challenge.
- Origin, Referer, Fetch Metadata or a nonempty Cookie header selects Django's
  CSRF policy, including its Origin and HTTPS Referer checks. Denials and other
  Runs API responses retain `Cache-Control: private, no-store` and vary on
  authorization and cookies. Keep browser request metadata and the external
  scheme intact at ingress; do not enable cross-origin access to these writes.
- Direct non-browser Basic-auth JSON callers without browser headers or cookies
  (such as `scripts/rms-python/runtime-grants-check.py`) retain the existing
  contract where the ingress permits them. Authentication, strict JSON parsing,
  scope, and the required idempotency key still apply. This does not change the
  separate staging ingress policy or add a caller exemption flag.

## Missing controls and release checks

| Surface | Minimum verification | Boundary |
| --- | --- | --- |
| Runs | Append observed events with actor, timestamps and reasons. Preserve concurrency-safe retries, reconciliation and exact configurations. | No external dispatch. |
| Results | Seal results against completed attempts, exact criterion versions and artifacts. Compare failed attempt and completed retry to predefined rules. Preserve correction history. | Completed execution is not a criterion pass or qualification. |
| Evidence | Bound synthetic bytes and verify digest, size, media type, provenance and custody. Demonstrate recovery. | No remote fetching or rights inference. |
| Review, decision, lesson | Authorize reviewer independently and exclude contributors. Bind exact result and evidence; record disposition separately and retain originals. | Attribution alone does not establish independence or founder authority. |
| Dashboard and stage gates | Show synthetic status, owner, blocker, next action and freshness; report cycle and qualification counts separately. | Keep real approval, rights, freeze and release fail-closed. |
| Recovery and rollout | Verify additive migration, ordinary-role protection, private route, users/roles/history, normal browser and 360px/keyboard. Record exact reviewed SHA and restore receipts. | No host operation from this workspace; no off-VPS recovery claim. |
| Automated integration | Inventory Paperclip, GitHub and LEAN connectors, rights, approved owners, exact capture, queue controls and reserved-test isolation. | No real intake/execution, delegation, broker or trading. |

Recommend an independently reviewed synthetic release before requesting live
integration. Mutable/latest-pointer evidence loses lineage; live execution
requires separately observed authority, rights and account controls. Route role
and external access decisions through MAU-159. This is not an independent
acceptance receipt.
