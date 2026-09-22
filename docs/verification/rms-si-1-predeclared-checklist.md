# RMS-SI-1.0 predeclared independent verification checklist

**Checklist version:** 1.0
**Declared:** 2026-09-22 UTC
**Owner:** Test Engineer, Research Systems
**Authority:** founder-accepted [MAU-44 plan revision 4](/MAU/issues/MAU-44#document-plan), revision `3603fbc1-87fe-4701-9592-c870d526b20b`; frozen [RMS-SI-1.0 contract](/MAU/issues/MAU-93#document-contract), revision `13eb82e2-9762-4d96-83cc-30e6aa8b6f3e`.
**Delivered regression baseline:** `107504a78eb8bb8b27465d4d726c6c447bab9ca5`.
**Execution target:** one exact integrated candidate supplied through [MAU-97](/MAU/issues/MAU-97).
**Status:** design frozen; all actual results are `NOT RUN` until that candidate exists.

This checklist is software verification only. It does not issue or substitute for Risk acceptance, Stage 1 acceptance, deployment readiness, protected-data isolation, research validity, strategy qualification, or trading approval. Only invented data is permitted. Missing evidence is not a pass. Criteria are not weakened after results are seen.

## 1. Execution and evidence gate

Before behavioral execution, Test records the following. A missing or mismatched item makes dependent cases `BLOCKED/NOT RUN` or `INCONCLUSIVE`, never `PASS`.

| Gate | Required record |
|---|---|
| Candidate | Full 40-character commit from [MAU-97](/MAU/issues/MAU-97), tree SHA, branch, remote ref/equality, merge-base ancestry from `107504a`, clean/dirty status, submodules, changed-file list, and archived diff |
| Contract | Exact plan and contract revision IDs above; no superseding revision, rejection, or deferral |
| Runtime | UTC start/end, cwd, OS/architecture, CPython/Django/DRF/psycopg/PostgreSQL identities, lockfile SHA-256, installed package list, locale/timezone, transaction isolation, and redacted configuration digest |
| Database | Fresh isolated PostgreSQL identity/version, migration plan/order/digests, schema/constraints/triggers, and per-case pre/post counts; SQLite cannot support a mandatory result |
| Fixture | Checklist version, loader path/commit/digest, exact invented values below, principal/group proof, and post-load count/digest summary |
| Commands | Exact command, exit status, duration, ordered stdout/stderr artifact, selection, skips, retries, and failure preservation |
| HTTP/UI | Safe request/response captures, same-principal proof, DOM/page capture, error body digest, and absence-of-leak assertions |
| Concurrency | Barrier/orchestration, two request IDs/keys, transaction outcomes, and final row/watermark counts; sequential simulation does not pass |
| Report | PASS/FAIL/BLOCKED/INCONCLUSIVE/NOT RUN totals, defects, initial and retest results, artifact references, untested limits, and unchanged package for Risk |

Every executed case record contains: case ID and checklist version; fixture; role; setup; action; expected; actual; artifact; defect/retest state. Developer tests are inputs, not Test's verdict. If Test changes product code, the affected verification requires another reviewer and the authorship is disclosed.

## 2. Fixed invented fixtures and principals

### F0 — empty isolated database

PostgreSQL 17.11 with no RMS application tables before migration. Platform bootstrap state, database identity, and extension state are recorded.

### F1 — described Source history

Stable `source_id`: `fixture.source.increment1`.

| Field | v1 | v2 publication correction | v3 later Source correction |
|---|---|---|---|
| `title` | `Fictional volatility note` | unchanged | `Fictional volatility note — corrected edition` |
| `source_type` | `working_paper` | unchanged | unchanged |
| `citation` | `Example, A. (2026). Fictional volatility note.` | unchanged | unchanged |
| `observed_available_at` | `2026-09-01T14:00:00.000000Z` | unchanged | unchanged |
| `authors` | `["Ada Fiction", "Ben Example"]` | unchanged | unchanged |
| `publisher` | `Invented Research Press` | unchanged | unchanged |
| `published_at` input | `2026-08-31T12:00:00-04:00` | `2026-08-31T12:30:00-04:00` | unchanged |
| emitted `published_at` | `2026-08-31T16:00:00.000000Z` | `2026-08-31T16:30:00.000000Z` | unchanged |
| `canonical_url` | `https://example.invalid/fictional-volatility-note` | unchanged | unchanged |
| `rights_note` | `Synthetic fixture; no external rights claim.` | unchanged | unchanged |
| raw bytes | UTF-8 `invented increment-one source bytes v1` | copied with `content_base64: null` | UTF-8 `invented increment-one source bytes v3` |
| byte length / SHA-256 | `38` / `6bcebae9bec0ca4ca468e6535dea532dedca532e54c781b44152188dfc8eef6e` | same as v1 | `38` / `b9197845d0f37fac4940817e1f1b40d733ed65afe5b6df207210f250db6d063b` |
| correction reason | `null` | `Correct the fictional publication timestamp.` | `Correct the fictional title and synthetic bytes.` |
| expected `changed_fields` | `[]` | `["published_at"]` | `["content_sha256", "title"]` |

All writes use `synthetic: true`, full snapshots, and distinct non-secret keys prefixed `rms-si-1:`. Server IDs and timestamps are captured rather than fixed, then checked for canonical shape, uniqueness, stability, ordering, and exact replay.

### F2 — Idea history bound to F1 v1

Idea v1 fields:

- `title`: `Fictional availability-to-volatility idea`
- `mechanism`: `An invented availability lag may alter a fictional volatility response.`
- `testable_claim`: `The invented response is larger after the stated availability time.`
- `falsification`: `No larger response in the invented comparison falsifies the claim.`
- `eligible_market`: `equities`
- `workflow_status`: `draft`
- `rejection_reason`: `null`
- one contribution: exact F1 v1 `source_version_id` plus `The exact fictional v1 motivates the invented availability mechanism.`

Idea v2 is a full-snapshot correction with reason `Clarify the fictional falsification statement.`, changes only `falsification`, and resubmits the same exact Source-v1 contribution. A separate rejected-Idea variant uses `workflow_status: rejected` and a non-null invented rejection reason. An accepted variant is used only to verify the explicit intake-only label.

### Principals

- `editor`: authenticated member of `editor`; allowed Source/Idea reads and writes.
- `founder_viewer`: authenticated member of `founder_viewer`; reads only.
- `authenticated_other`: authenticated member of neither group; baseline-compatible authenticated reads only, no writes.
- `anonymous`: no session or authorization header; no read or write.

Credential values remain outside Git and evidence. Safe principal IDs and group membership are recorded.

## 3. Requirement-to-case mapping

| Requirement | Mandatory cases |
|---|---|
| Exact candidate/environment and migration | `GATE-01`, `MIG-01`–`MIG-03`, `SYS-01` |
| Source field/null/enum/text/timestamp/URL/Base64 contract | `SRC-01`–`SRC-06`, `VAL-01`–`VAL-05` |
| Source IDs, correction history, originals, manifests | `SRC-02`–`SRC-05`, `MAN-01`–`MAN-04` |
| Idea create/correct/reject/intake semantics | `IDEA-01`–`IDEA-05`, `VAL-01`–`VAL-04` |
| Exact Source-v1 contribution after Source correction | `LINK-01`–`LINK-03` |
| No raw Source bytes in Idea responses/UI | `LINK-03`, `PERM-05`, `UI-03` |
| Editor/viewer/other/anonymous and lookup ordering | `PERM-01`–`PERM-05` |
| Idempotency, stale rollback, concurrency, atomicity | `IDEM-01`–`IDEM-04`, `ATOM-01`–`ATOM-03` |
| Frontend/API parity and history/correction UX | `UI-01`–`UI-05` |
| Focused suites and unchanged VS1 regressions | `REG-01`–`REG-04` |

## 4. Mandatory cases

All `Actual / artifact` values are `NOT RUN / TBD` until the exact candidate handoff.

| ID | Fixture / role | Setup and action | Expected result | Actual / artifact |
|---|---|---|---|---|
| `GATE-01` | no content / Test | Capture every gate in section 1 before behavior tests and verify candidate does not change during the run. | Identities are complete, authorized, mutually consistent, and fixed. | NOT RUN / TBD |
| `MIG-01` | F0 / DB owner | Apply all migrations to a genuinely empty database; inspect graph/schema/constraints; run migrate again. | Ordered success, expected Source/Idea/idempotency/edge structures and constraints, then no-op; no fixture rows. | NOT RUN / TBD |
| `MIG-02` | delivered baseline-shaped rows / DB owner | Load pre-increment Source and SourceVersion/manifests, record bytes/digests, then migrate. | Every existing SourceVersion gets one unique canonical `SRCV-{uuid}`; stable IDs, integer versions, raw bytes, historical manifest bytes, and content digests are unchanged. | NOT RUN / TBD |
| `MIG-03` | migrated F1/F2 variants / DB owner | Attempt duplicate/skipped versions, cross-record or non-immediate predecessors, duplicate public IDs, invalid edge references, and updates/deletes of immutable versions/edges/manifests. | Database constraints/triggers reject each rolled-back attempt; no historical or watermark change. Application validation alone is insufficient. | NOT RUN / TBD |
| `SRC-01` | F0 / editor | Create F1 v1 with every required and representative optional field; read detail/history. | `201`; exact stable shape, normalized UTC timestamp, canonical generated ID, v1 null predecessors/reason, empty changed fields, correct digest/length, no raw bytes. | NOT RUN / TBD |
| `SRC-02` | F1 v1 / editor | Correct to v2 with full snapshot, `content_base64: null`, expected version 1, and reason. | `201`; contiguous v2, immediate predecessor IDs/numbers, copied bytes/digest, only `published_at` changed, originals preserved. | NOT RUN / TBD |
| `SRC-03` | F1 v1/v2 / editor | Correct to v3 with changed title and canonical Base64 bytes; read all versions. | `201`; contiguous v3, immediate v2 predecessor, exact new digest/length, sorted changed fields; v1/v2 remain byte-for-byte stable. | NOT RUN / TBD |
| `SRC-04` | F1 / viewer | Compare detail `latest`, latest pointers, and ascending history with database rows. | Exact identity/version/predecessor/reason/actor/time/field parity; nullable fields are present as explicit `null`. | NOT RUN / TBD |
| `SRC-05` | F1 / Test | Snapshot v1/v2 serialized forms and rows before v3, then compare afterward. | No field, byte, digest, manifest, actor, timestamp, or public ID in v1/v2 changes. | NOT RUN / TBD |
| `SRC-06` | Source enum matrix / editor | Create one valid Source for every `source_type`; test required fields with representative nullable fields explicitly null. | Every listed enum succeeds; explicit null optionals round-trip as null; no unlisted enum succeeds. | NOT RUN / TBD |
| `VAL-01` | Source/Idea boundary variants / editor | For each text field test exact min/max, empty, whitespace-only, untrimmed, max+1, NUL, disallowed control, tab/newline, and valid UTF-8. | Contract boundaries hold; accepted strings are not silently trimmed; each failure is generic `400` with no rows/idempotency record or rejected value leak. | NOT RUN / TBD |
| `VAL-02` | timestamp variants / editor | Submit `Z`, positive/negative offsets, naive, date-only, named zone, leap second, and publication earlier/later than observed availability. | Aware values normalize to UTC; invalid formats fail; no ordering constraint is invented between the two claims. | NOT RUN / TBD |
| `VAL-03` | array/URL/Base64 variants / editor | Exercise authors null/1/100/101, duplicate authors, order, credentials/non-HTTP/overlong URL, canonical/noncanonical Base64, and unknown/missing fields. | Exact contract acceptance/rejection; array order retained; unknown/missing fields and noncanonical Base64 fail generically and atomically. | NOT RUN / TBD |
| `VAL-04` | Idea variants / editor | Exercise all markets/statuses; rejection reason null/non-null matrix; 1/100/101 contributions; duplicate pair and distinct same-source contributions. | Exact enums and conditional rule hold; order retained; duplicate pairs and size violations fail without rows. | NOT RUN / TBD |
| `VAL-05` | malformed/missing IDs / editor+viewer | Read invalid and well-formed missing IDs; write correction against both; send server-controlled fields. | Authenticated reads give indistinguishable generic `404`; editor corrections give generic `404`; server-controlled/unknown fields give `400`; no existence/value leak. | NOT RUN / TBD |
| `IDEA-01` | F1 v1 + F2 v1 / editor | Create F2 and read detail/history. | `201`; canonical stable/version/edge IDs; v1 null predecessor/reason, empty changes, exact fields and Source-v1 summary; one immutable edge. | NOT RUN / TBD |
| `IDEA-02` | F2 v1 / editor | Correct to F2 v2 with full snapshot and reason; read both versions. | `201`; contiguous v2 and immediate predecessor; sorted changed fields; new edges on v2; v1 and its edge remain unchanged/readable. | NOT RUN / TBD |
| `IDEA-03` | rejected variant / editor+viewer | Create/read rejected Idea. | Rejection reason is required, retained, and visible; record remains readable. | NOT RUN / TBD |
| `IDEA-04` | accepted variant / editor+viewer | Create/read accepted Idea in API and UI. | Accepted status is shown only as workflow intake, never validated/qualified/approved/tested/tradable. | NOT RUN / TBD |
| `IDEA-05` | F2 / Test | Compare detail/history/API rows, generated IDs, actors, timestamps, predecessor links, and changes. | Exact parity and immutability; history ascending; all nullable fields present. | NOT RUN / TBD |
| `LINK-01` | F1 v1 + F2 v1 then F1 v2/v3 / editor+viewer | Capture Idea contribution/summary before and after both later Source corrections. | Contribution remains bound to the exact v1 `source_version_id`; source integer version and summary never move or rewrite. | NOT RUN / TBD |
| `LINK-02` | readable/missing Source versions / editor | Create/correct Idea using valid v1, valid v3, missing, malformed, and duplicate contribution references. | Valid exact versions bind; invalid/unreadable references fail atomically with generic safe errors; no orphan Idea/edge/idempotency rows. | NOT RUN / TBD |
| `LINK-03` | distinctive F1 bytes/Base64 / all readers | Recursively inspect every Idea JSON/body, page DOM, embedded data, errors, logs, and cache for raw bytes, Base64, `content_base64`, content body, credentials, or rights evidence. | None appear; only the allowed fixed Source summary and digest-free contribution shape are present. | NOT RUN / TBD |
| `MAN-01` | F1 v1/v2/v3 / viewer | GET manifest through versions 1, 2, and 3; repeat from a fresh connection; hash bodies independently. | Canonical bodies and `X-Manifest-SHA256` agree; each through-version snapshot has exact ordered entries and raw-content digests; no raw content. | NOT RUN / TBD |
| `MAN-02` | retained manifest bodies / Test | Compare saved v1 manifest before/after v2/v3 and saved v2 manifest before/after v3. | Historical bytes and hashes are byte-identical; later snapshots append without rewriting earlier snapshots. | NOT RUN / TBD |
| `MAN-03` | F1 / viewer | Omit `through_version`, request 1/2/3, 0/negative/noninteger, and future version. | Omitted means latest; valid versions return exact stored snapshot; invalid/missing snapshots return contract-safe errors without mutation/leak. | NOT RUN / TBD |
| `MAN-04` | migration fixture / Test | Compare pre-increment baseline manifest bytes/digests with post-migration retrieval. | Adding descriptive fields/public version IDs does not rewrite historical canonical manifest bytes or content digest semantics. | NOT RUN / TBD |
| `PERM-01` | F1/F2 / editor | Exercise every Source/Idea GET/POST and frontend edit/read route. | Contract-allowed operations succeed; no approval, dispatch, administrative, connector, or delete capability appears. | NOT RUN / TBD |
| `PERM-02` | F1/F2 / founder_viewer | Exercise all reads, forge every write/method directly, and inspect UI controls. | Reads succeed; all writes are `403`; no partial rows; editing controls absent but Backend denial is independently proven. | NOT RUN / TBD |
| `PERM-03` | F1/F2 / authenticated_other | Exercise baseline-compatible GETs and every write. | Reads follow recorded baseline policy; writes are always `403` before lookup; no rows or object-existence leak. | NOT RUN / TBD |
| `PERM-04` | existing/missing/malformed objects / anonymous+viewer | Compare all read/write results across identities. | Anonymous always `401` before lookup; authenticated non-editor writes always `403` before lookup; bodies cannot distinguish existence. | NOT RUN / TBD |
| `PERM-05` | denied requests / Test | Compare pre/post rows and inspect errors, logs, caches, pages, exports, snippets, and counts. | Denial writes nothing and leaks no content, values, existence, hidden counts, stack traces, credentials, or secret material. | NOT RUN / TBD |
| `IDEM-01` | F1/F2 creates and corrections / editor | Replay each identical canonical request with its original key after intervening later versions. | Exact committed `201` status and response bytes/IDs replay; exactly one operation and one idempotency record exist. | NOT RUN / TBD |
| `IDEM-02` | successful writes / editor | Reuse each key with changed method, path, body, expected version, or target; also reuse a Source key on Idea. | Global-scope `409 idempotency_conflict`; original outcome preserved; no changed/new row. | NOT RUN / TBD |
| `IDEM-03` | canonical-equivalent writes / editor | Replay timestamp-offset-equivalent and canonical-Base64-equivalent complete bodies. | Canonical-equivalent requests replay the exact response rather than conflict; non-equivalent requests conflict. | NOT RUN / TBD |
| `IDEM-04` | failing writes / editor/viewer/anonymous | Reuse a key after auth, authorization, validation, not-found, stale, and other failed transactions, then submit one valid request. | Failures reserve no key; valid request can commit once; only successful `201` reserves it. | NOT RUN / TBD |
| `ATOM-01` | F1/F2 latest+1 already exists / editor | Submit stale Source and Idea corrections; capture all relevant table counts, histories, manifests, response cache, and watermarks before/after. | Generic `409 stale_correction`; no version, edge, manifest, idempotency, response, or watermark row is added/changed. | NOT RUN / TBD |
| `ATOM-02` | one predecessor / two editor sessions | Barrier two distinct-key Source corrections, then two distinct-key Idea corrections, each based on the same latest version. | Per race exactly one `201` and one `409`; one next version only; loser leaves no partial rows; winner replay remains exact. | NOT RUN / TBD |
| `ATOM-03` | injected rollback points / Test harness | Cause failure after stable/version/edge/manifest/response/idempotency preparation but before commit for Source and Idea writes. | Whole transaction rolls back at every point; historical truth and latest watermarks remain coherent; no silent repair. | NOT RUN / TBD |
| `UI-01` | F1 / editor | Create/correct Source using frontend forms with exact contract names/nulls; use null-content correction. | Requests match API full snapshots; errors are safe; successful pages show IDs, predecessors, reason, actor, time, sorted changes, and preserved history. | NOT RUN / TBD |
| `UI-02` | F1/F2 / editor | Create/correct Idea in frontend, selecting exact Source version; inspect submitted body. | Selector shows integer version and immutable summary and submits `source_version_id`, never `source_id` or latest-only citation. | NOT RUN / TBD |
| `UI-03` | F1/F2 / viewer | Compare page values/links/DOM with API under the same principal/session. | Exact parity for stable/version IDs, histories, corrections, contributions, summaries, statuses, nulls, and denial semantics; no raw bytes/hidden mutation. | NOT RUN / TBD |
| `UI-04` | rejected/accepted F2 variants / viewer | Inspect status presentation and history. | Rejection reason stays visible; accepted shows explicit intake-only language; neither implies approval or research result. | NOT RUN / TBD |
| `UI-05` | existing/missing objects / anonymous+viewer | Compare anonymous, forbidden, malformed, and missing UI pages with API decisions. | Pages do not infer existence beyond Backend responses, expose stack/data, or rely on hidden controls for authorization. | NOT RUN / TBD |
| `REG-01` | candidate / Test | Run focused Backend suite exactly as handed off; inspect discovery, skips, and assertions. | Exit 0 only counts with all intended tests collected and no unexplained skip/retry; failures are preserved. | NOT RUN / TBD |
| `REG-02` | candidate / Test | Run focused Frontend suite exactly as handed off; inspect discovery, skips, snapshots, and assertions. | Same evidentiary standard as `REG-01`; UI hiding alone cannot satisfy permission cases. | NOT RUN / TBD |
| `REG-03` | candidate / Test | Run existing public `python -m unittest discover` plus Django Source API/fixture/history tests and compare accepted files to baseline. | All existing VS1 tests remain active and pass unchanged in intent; removals, skips, weakened assertions, or fixture rewrites are failures. | NOT RUN / TBD |
| `REG-04` | candidate / Test | Run migration check, Django system check, and no-pending-migration/readiness checks. | No pending model changes or migrations, no system-check errors, and authenticated readiness accurately reflects DB/migration state. | NOT RUN / TBD |
| `SYS-01` | candidate / Test | Inventory exposed routes and methods against the frozen contract and exclusions. | Required routes exist; excluded delete/search/import/assessment/hypothesis/approval/dashboard/connector routes and dispatch/approval actions are absent. | NOT RUN / TBD |

## 5. Optional exploratory checks

These cannot compensate for a mandatory failure and are reported separately: randomized valid Unicode; repeated navigation/session renewal; browser accessibility beyond contract labels; larger-but-in-limit contribution mixes; and query-count/performance observation without a performance acceptance claim.

## 6. Verdict rules and current blockers

- A mandatory case is `PASS` only with the expected result and retained evidence on the exact candidate.
- Any behavioral mismatch is `FAIL`; environmental or identity gaps are `BLOCKED/NOT RUN` or `INCONCLUSIVE` as applicable.
- Retries do not erase initial failures. A repair is retested on the exact reviewed repair candidate and both results remain visible.
- The overall positive label, if earned, is `PASS — RMS-SI-1.0 SOFTWARE INCREMENT` and means only the bounded fictional Source completion + Source-to-Idea software slice passed.
- Final execution is blocked until [MAU-97](/MAU/issues/MAU-97) supplies one exact integrated candidate and reproducible Backend/Frontend handoff. The Director of Engineering owns that unblock action.
