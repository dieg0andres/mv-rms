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
