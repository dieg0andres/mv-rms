# Independent receiving evaluation: ordinary-DML guard probe

**Verdict: SCOPED PASS for 22 sampled UPDATE/DELETE denials across 11 populated tables.** One empty table is **NOT EXECUTED**. This is a bounded development-gate result, not full H14 or H01–H20 acceptance.

Test Engineer receiving run `5851e91e-afde-4059-8054-9c1a51542899`, evaluated at `2026-10-03T20:56:26.177Z`. Test independently evaluated existing operator output offline using Node, filesystem reads and SHA-256. Test performed no browser, database, Docker or probe invocation, and authored no product fix. Operator execution remains attributed to Codex's founder-posted actual handoff.

## Baseline and provenance

- Product `aead8ff52128859fbae8b0f3d8ed2de67aff5131`; tree `5880845c045af75e19c686cb5840b736a414abfa`; PR #4. Earlier installed-release identity remains `mv-rms-staging-app-1`, image `mv-rms-staging-preview:aead8ff`, image ID `sha256:a8fbb6afaf0e1c48bea4f37b918bdc60a0e4b4b8229889fa118247270e52cf96`. This receiving evaluation did not reobserve the image.
- [Accepted contract](/MAU/issues/MAU-140#document-contract), revision `3982eccc-e180-4ac9-bc70-9c4e16aa47f1`, independently rehashed body `f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9`; sections 6/7/8 and H14 distinguish historical protection, derived pointers and browser conflicts.
- [Exact pre-execution probe review](/MAU/issues/MAU-140#document-history-guard-probe-review), revision `681b31a4-e26b-46bb-ba16-8bb31fd7dee5`. Actual probe SHA `923f08ea3789876f8f5cf39fe39c2035a2c92c67448bf4075f836e6744d419c4` matches accepted bytes.
- Receipt: `2026-10-03T20:53:32.473726+00:00` to `2026-10-03T20:53:33.608240+00:00`, exit 0, empty stderr. Actual argv: `docker exec -i mv-rms-staging-app-1 /srv/adapter/entrypoint.sh /usr/local/bin/python - --run`, exact source on stdin. The receipt omits the reviewed example's `-B`; no product/database change is implied by that difference, and the omitted flag is preserved here.
- Result SHA `6da5772002f89691ed3ea823cc020286f3c3bf7b95c4171679d4970a8e343748`; receipt SHA `be78ce7827dadbdfec41b4f4cd579fcf486dea6f6cdbce4310fcab043b55e6db`. All five manifest entries match actual byte lengths and digests, and receipt source/stdout hashes match.
- Effective database/current user/session user are reported as `rms_staging`/`rms_staging`/`rms_staging`. All four reported privilege flags (superuser, createdb, createrole, bypassrls) are true. **This is a privileged application binding.**
- Exact source asserts the release metadata and RMS migrations 0001–0005 before probing. Interpreter version and dependency versions are not emitted in this receipt; no new observation of those versions is claimed.

## Expected behavior and actual mapping

The accepted specification predates execution. Each case uses one existing invented row chosen deterministically by UUID and synthetic classification, shared-locked; paired operations target the same row. UPDATE changes its primary key; DELETE targets it directly. Each operation uses a rollback savepoint within an outer rollback transaction, with local lock/statement/idle timeouts. No fixture insertion, DDL, role/grant/trigger/replication or authentication change is present.

Expected identity UPDATE: SQLSTATE `P0001`, exact message `Only append triggers may advance research watermarks`; DELETE: `P0001`, `Research identities are retained`. Expected immutable-row UPDATE/DELETE: `23000`, exact `<table> rows are append-only`. Source diagnostics were compared with migrations 0002 and 0005 at the exact product Git object. Generic permission/FK/timeout failures or successful DML cannot pass.

| Table / mandatory sampled case | Expected SQLSTATE | Actual UPDATE / DELETE |
| --- | --- | --- |
| rms_researchfamily | P0001 | PASS / PASS |
| rms_investigation | P0001 | PASS / PASS |
| rms_priorresearchassessment | P0001 | PASS / PASS |
| rms_hypothesis | P0001 | PASS / PASS |
| rms_researchassociationidentity | P0001 | PASS / PASS |
| rms_researchfamilyversion | 23000 | PASS / PASS |
| rms_investigationversion | 23000 | PASS / PASS |
| rms_priorresearchassessmentversion | 23000 | PASS / PASS |
| rms_hypothesisversion | 23000 | PASS / PASS |
| rms_researchassociation | 23000 | PASS / PASS |
| rms_assessmentexternalreference | 23000 | NOT EXECUTED: no existing synthetic row |
| rms_hypothesiscorrectionimpact | 23000 | PASS / PASS |

`evaluation.json` records fixture UUIDs, paired operations, expected states, receipt and original artifact digests. Every executed entry has the expected SQLSTATE, `guard_message_matches=true`, and no successful row count. The exact probe compares full sampled historical rows, excluding only derived identity `latest_version`; it reports equality after each denial and after the outer atomic block exits. Savepoint exception unwinding and unconditional outer rollback are present in the accepted source. Result reports unchanged sampled rows and zero committed writes.

Those equality/rollback conclusions are receiving evaluations of the hash-verified probe's assertions and control flow. Raw before/after fingerprint values are not emitted, so Test cannot independently recompute row equality from this package or certify whole-database/auth/pointer equality. No full-table preservation, TRUNCATE, administrator bypass resistance or least privilege was tested. Legal append/watermark advancement remains for the browser flow. The empty-table entry is excluded from passes.

The operator note preserves an earlier launcher SyntaxError before probe execution/mutation. One corrected invocation of unchanged accepted probe bytes produced this receipt; no failing product case was retried or removed.

## Remaining handoff

The [single browser executable is already published](/MAU/issues/MAU-140#comment-a4e45ab7-d7f9-46c9-8a73-9267be578d16); package SHA `ceaa6d7965fa3d4fd9c5cf87dddadb87c5d2e462b57d545096bfe58ffbadd288`, script SHA `de61910ae49f207467b057fd8d13208ab35f3b0a30c3c0a1687f249aeb789be5`. Its offline preparation checks are separate from live browser outcomes. Its predicted stale-409 request-key change remains a source concern, not an executed browser failure. Preserve the delivered assertion and Director/product-owner disposition against confirmed rejection versus unknown response semantics; this receiving review does not waive it or edit the test.

Director owns exact browser receiving review and concern disposition, then coordinates Codex's one host execution. Test independently evaluates actual output on existing [MAU-144](/MAU/issues/MAU-144). Checkout of that task in this heartbeat returned 409 with active execution run `78cd2c6b-ad4d-4c50-b7d6-49ef63aa9e04`; it was not retried and no second browser flow was created. This report is a parent receiving response, not takeover of that checkout.

Full original amended acceptance remains INCOMPLETE / INCONCLUSIVE. Viewer checks stay WAIVED BY FOUNDER / NOT EXECUTED. Deeper DB overlap, broader permutations, Risk/Stage 1 findings and incident history remain as previously recorded. Director retains the bounded development verdict; this report grants no merge, Stage 1, research or Risk acceptance.
