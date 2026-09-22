# RMS-VS-1 predeclared software-verification checklist

**Checklist version:** 1.0  
**Declared:** 2026-09-22 UTC  
**Owner:** Test Engineer, Research Systems  
**Authority:** accepted [MAU-43 RMS-VS-1 plan](/MAU/issues/MAU-43#document-plan), revision `9358d205-9ac6-4a7a-9955-95c7c8fb0e10`; human-only confirmation `5ff26514-2437-4602-8653-db155eb8f99d`, accepted 2026-09-22T00:41:05Z.  
**Baseline:** Director-approved commit `2fc97fb8ccfcc0120b2e1ff3bb79e655fde68a0b`; the accepted 20-test public regression suite and unchanged six-test Source-kernel subset remain mandatory.  
**Status:** design only; every execution result is `NOT RUN`. This document does not accept software or authorize implementation, deployment, merge, real data, or reserved/final-test access.

## 1. Verdict boundary and immutability

This checklist fixes the mandatory software-verification intent before contract freeze/T0. The Director of Engineering may fill in representation details expressly left as contract-freeze fields, but may not remove a case, weaken an expected result, change a fixture after results are known, substitute SQLite, or treat missing evidence as a pass. Any material criterion change after T0 creates a new dated revision and invalidates comparison with results already observed.

The only positive overall label is **`PASS — RMS-VS-1 SOFTWARE INCREMENT`**. It means only that the bounded local synthetic Source create/correct/history/manifest slice passed on the recorded candidate. Stage 1, deployment, production readiness, protected-data controls, independent custody, research validity, and independent Risk acceptance remain inconclusive and are not implied.

Developer tests are inputs, not Test's verdict. Test must independently execute the mandatory cases on the exact candidate and retain its own raw evidence. VP Risk & Research Assurance receives the unchanged package and decides any later independent acceptance; Engineering/Test cannot issue, edit, waive, or substitute that decision. If Test authors a product-code fix, authorship is disclosed and another reviewer must verify the affected cases.

Only public tests and invented inputs are permitted. Reserved/final tests, real research, vendor/licensed content, connectors, empirical backtests, paper trading, and live trading are prohibited.

## 2. T0 contract-freeze and evidence gate

Testing does not begin until the Director records all fields below. A missing or mismatched field is `INCONCLUSIVE`, not a pass.

| Field | Required value/evidence |
|---|---|
| Authority | Plan revision and accepted confirmation IDs above; T0 timestamp and Director identity |
| Repository/lineage | `mv-rms`; base SHA, final 40-character candidate SHA, branch, remote ref, `git merge-base --is-ancestor` result, remote-SHA equality, clean/dirty status, submodule state, and base-to-final changed-file list |
| Candidate immutability | Candidate tree SHA and archived diff; no candidate change during a run or bounded retest |
| Runtime | OS/architecture; CPython `3.13.15`; Django `5.2.17`; DRF `3.18.1`; psycopg `3.3.6`; PostgreSQL `17.11`; executable/image identities and cryptographic digests |
| Dependencies/config | Lockfile and lock digest; installed-package listing; redacted settings/config digest; timezone; locale; relevant database isolation level; no secret values |
| Database | Fresh isolated PostgreSQL database identity; server version; migration names/order/status and digest of every migration file; schema/constraint inventory; pre/post row counts |
| Fixture | Fixture version/path/digest; loader commit; exact synthetic bytes and fixed identities in section 3; post-load count/digest summary |
| Interface freeze | Exact Source-detail page route; authentication method; JSON field names; `Idempotency-Key` handling; `expected_latest_version` field; error schema; manifest content type and digest metadata location; authority-mode label |
| Commands | Exact commands, cwd, start/end UTC, exit status, duration, ordered stdout/stderr artifacts, and test selection; no undisclosed retry |
| Per-case record | Case ID/version; role/principal reference; setup; request/action; relevant request headers and body digest; expected; actual status/body/state; pre/post database counts; artifact references; defect ID; initial/retest verdict |
| Page/API evidence | Raw HTTP captures, rendered-page capture, accessibility/DOM extraction used for parity, and same-principal/session proof |
| Concurrency evidence | Barrier/orchestration description, two request IDs/idempotency keys, transaction timestamps/outcomes, locks/conflicts, and post-race database/history/manifest counts |
| Export evidence | Exact export bytes, byte length, SHA-256, response metadata, producing command, and equality/difference result across clean reloads |
| Security/denial evidence | Response status/schema/body digest, absence of protected fields/counts/snippets, unchanged database state, and redacted application/database log excerpt proving no content/secret leakage |
| Report | Totals by PASS/FAIL/INCONCLUSIVE/NOT RUN, skipped/retried tests, defects and severity, known limitations, actual effort, retest link, Test verdict, and unchanged evidence-package reference for Risk |

No secret, credential, token, or real evidence may appear in an artifact. Hashes supplement retained bytes; a hash alone is not the evidence.

## 3. Fixed synthetic fixtures and principals

### F0 — empty database

An isolated, closed PostgreSQL 17.11 database with only platform-required bootstrap state and no RMS application tables before migration. SQLite is forbidden for every mandatory result.

### F1 — Source history

| Item | Fixed value |
|---|---|
| Fixture label | `RMS-VS-1-F1` |
| Stable Source ID | `11111111-1111-4111-8111-111111111111` |
| Source v1 bytes | UTF-8 bytes for `invented Source version one` |
| v1 byte length / SHA-256 | `27` / `42fff28d6c54902a3c90843c457664df5ce9f803fa8ccb9934d2bb3741481c86` |
| Source v2 bytes | UTF-8 bytes for `invented Source version two correction` |
| v2 byte length / SHA-256 | `38` / `c16ad70788fce3ea9a392d0a9526c92bb9df47626c11c4c3c7f143dac38e4048` |
| Version rules | v1=`1`, no predecessor; v2=`2`, `corrects_version=1`; both `synthetic=true`; same stable ID |
| Idempotency keys | fixed, non-secret keys per operation/case; concurrency uses distinct keys `...:race:a` and `...:race:b` |
| Authority display | exact T0-frozen text must unambiguously state local/synthetic mode and must not imply an effective approval, dispatch, delegation, or research grant |

If database-generated version UUIDs/timestamps are required, the loader must make the export deterministic by freezing them in the fixture or excluding them under the frozen canonical export contract. Silent normalization of content bytes is forbidden.

### Principals

- `editor`: authenticated local synthetic-fixture editor; may create v1, append correction v2, and read.
- `founder_viewer`: authenticated read-only founder principal; may read the page/API/manifest and may not mutate.
- `anonymous`: no session or authorization header; may not read or write the page/API/manifest.

Principal credentials stay outside Git and artifacts. Each run records a safe principal identifier and assigned groups/permissions.

## 4. Requirement-to-case map

| Requirement | Mandatory cases |
|---|---|
| Exact candidate/environment | `GATE-01` |
| Empty PostgreSQL migration and database constraints | `PG-01`, `PG-03` |
| Deterministic fixture and export reproduction | `PG-02`, `PG-04` |
| Accepted Source v1/v2, stable identity, ordered history | `SRC-01`, `SRC-02` |
| Original/version preservation | `SRC-03`, `MAN-02`, `REG-03`, `REG-09` |
| Deterministic manifest, hashes, no raw content | `MAN-01`–`MAN-03`, `REG-09`–`REG-20` |
| Non-synthetic, overwrite/delete, sequence/link, stale, manifest/content denial | `DENY-01`–`DENY-05` |
| Idempotency replay and conflicting reuse | `IDEM-01`–`IDEM-04` |
| Concurrent corrections / no partial write | `CON-01` |
| Editor/viewer/anonymous permissions and non-leakage | `PERM-01`–`PERM-05` |
| Page/API parity | `PAR-01`–`PAR-03` |
| Accepted 20-test public regression | `REG-01`–`REG-20` |

## 5. Mandatory vertical-slice cases

All cases start with `Actual: NOT RUN — predeclaration` and `Artifact: TBD at execution`. Unless stated otherwise, setup uses F0 migrated to the exact candidate and a fresh transactionally clean database.

| ID | Fixture / role | Setup and action | Expected result | Actual / artifact |
|---|---|---|---|---|
| `GATE-01` | No content / Test | Independently capture every section 2 identity, ancestry, version, lock, migration, fixture, configuration, and remote-equality field before behavior tests. | Every identity is complete and matches the accepted stack/base/frozen contract; candidate and configuration remain unchanged through the run. Any missing/mismatch stops dependent cases as INCONCLUSIVE. | NOT RUN / TBD |
| `PG-01` | F0 / Test DB owner | Create a genuinely empty PostgreSQL 17.11 database; apply migrations once; inspect migration state and schema. | Exit 0; exactly the frozen migrations apply in order; required Source, SourceVersion, IdempotencyRecord, auth/permission, and manifest representation exist; second migration invocation is a no-op; no fixture rows exist. | NOT RUN / TBD |
| `PG-02` | F1 / fixture loader | Load the deterministic fixture into the migrated database, record counts/digests, rebuild F0, and load again. | Both loads exit 0 and yield identical stable IDs, version history, bytes, content digests, manifest/export bytes and declared deterministic fields; no non-synthetic row exists. | NOT RUN / TBD |
| `PG-03` | F1 variants / Test DB owner | In separate rolled-back attempts, directly violate `(source_id, version)` uniqueness, insert skipped v3, use a cross-source/non-immediate correction link, and update immutable identity/version/content/digest/predecessor fields. | PostgreSQL constraints/triggers reject each attempt; transaction is rolled back; F1 counts, v1/v2 bytes, history, and manifest remain unchanged. Application-only validation is insufficient for this case. | NOT RUN / TBD |
| `PG-04` | Two clean F1 loads / Test | Export through the frozen manifest/export command and HTTP download after each independent F0→migration→F1 cycle. | Command and HTTP bytes agree; run-1 and run-2 export bytes, lengths, canonical ordering, and SHA-256 are identical; raw Source content is absent; stored/derived digest agrees. | NOT RUN / TBD |
| `SRC-01` | F0 / editor | `POST /api/v1/sources` with v1, `synthetic=true`, and a fresh `Idempotency-Key`; then GET detail/history. | `201`; one stable Source and v1 exist; exact 27 bytes/digest are stored; current/latest=1; history is `[1]`; response/DB identity agree; no v2 or partial duplicate exists. | NOT RUN / TBD |
| `SRC-02` | v1 / editor | `POST /api/v1/sources/{source_id}/corrections` with exact v2 bytes, `expected_latest_version=1`, and a fresh idempotency key; GET detail/history. | `201`; same stable Source; exactly one v2 numbered 2 with immediate correction link to v1; exact 38 bytes/digest; current/latest=2; ordered history is `[1,2]`. | NOT RUN / TBD |
| `SRC-03` | v1 snapshot then v2 / editor+Test | Before correction retain v1 row/serialized bytes/digest/timestamps and v1 manifest entry; append v2; reread v1 directly and through API. | Every v1 identity, byte, digest, created fact, and prior manifest entry is byte-for-byte unchanged and addressable; only append-only v2/current-view state is added. | NOT RUN / TBD |
| `MAN-01` | F1 / editor reader | Generate/get the manifest three times, including a fresh process/connection; independently canonicalize and hash it. | All bodies are byte-identical canonical UTF-8 JSON; SHA-256 metadata equals SHA-256(body); schema/version entries are ordered `[1,2]`; exact IDs, links, `synthetic`, byte lengths, and content digests agree; neither raw content string/bytes nor a `content` field appears. | NOT RUN / TBD |
| `MAN-02` | v1 then F1 / Test | Generate v1-only manifest; append v2; generate v1/v2 manifest and compare v1 entry and stored v1. | Original v1 entry/content is unchanged; v2 is appended; no rewrite or reordering occurs. | NOT RUN / TBD |
| `MAN-03` | Copies of F1 manifest/versions / Test | Separately alter schema, omit/reorder/duplicate a version, break the correction link, alter metadata, alter Source content bytes, and supply a wrong digest to the frozen verifier/reconciliation path. | Every mutation fails closed with the frozen validation/conflict error; no historical/source/manifest row is repaired or changed; dependent export/claim is not reported valid. | NOT RUN / TBD |
| `DENY-01` | F0 and v1 / editor | Attempt create and, where the correction contract carries the marker, correction with `synthetic=false`, missing, null, string, and integer truthy values. | `400` frozen validation error for each; no Source/SourceVersion/IdempotencyRecord/manifest write and no object/count/content leak. Only JSON boolean `true` is accepted. | NOT RUN / TBD |
| `DENY-02` | F1 / editor and founder_viewer | Probe `PUT`, `PATCH`, and `DELETE` against collection/detail/version/correction routes and attempt an overwrite through the service layer. | Routes are absent or `405` under the frozen route table; service/DB rejects overwrite; no row, bytes, digest, history, idempotency outcome, or manifest changes. Viewer remains `403` where authentication precedes method handling. | NOT RUN / TBD |
| `DENY-03` | F1 variants / editor+Test | Attempt skipped v3, explicit reordered/duplicate version, predecessor not immediately prior, and predecessor from another Source through every exposed API/service path and direct DB checks in `PG-03`. | Validation/conflict (`400` for malformed input, `409` for valid-but-conflicting state) and DB constraint rejection; no partial row or history/manifest change. | NOT RUN / TBD |
| `DENY-04` | F1 / editor | Submit a correction with stale `expected_latest_version=1` after latest is 2. | `409` frozen conflict; exactly two versions remain; no idempotency replay is falsely reported; history and manifest are unchanged. | NOT RUN / TBD |
| `DENY-05` | v1 / editor | Omit/blank/oversize/malformed `Idempotency-Key` and omit/malformed `expected_latest_version` on correction; repeat equivalent validation on create where applicable. | `400`; no SourceVersion or orphan IdempotencyRecord; error contains no Source bytes or hidden metadata. | NOT RUN / TBD |
| `IDEM-01` | F0 / editor | Send identical create request twice with the same key. | Second response has the stored original status, response identity, and body; exactly one Source/v1 and one coherent idempotency outcome exist; no duplicate side effect. | NOT RUN / TBD |
| `IDEM-02` | v1 / editor | Send identical correction request twice with the same key. | Same stored outcome on replay; exactly one v2 exists; history `[1,2]`; no duplicate manifest/version side effect. | NOT RUN / TBD |
| `IDEM-03` | F0 / editor | Reuse a create key with any changed payload byte/field. | `409`; original v1/outcome remains; changed request creates no row and does not replace the stored request digest/response. | NOT RUN / TBD |
| `IDEM-04` | v1 / editor | Reuse a correction key with changed content, expected version, Source ID, or synthetic marker. | `409`; original correction outcome remains; no changed or additional version/manifest row. | NOT RUN / TBD |
| `CON-01` | v1 / two editor sessions | Synchronize two correction requests with distinct keys and the same `expected_latest_version=1` so both reach the transaction barrier before either commits. Repeat only as the single declared case run, not as a retry loop. | Exactly one `201` and one `409`; one and only one v2 is committed; loser creates no SourceVersion/manifest partial write or inconsistent idempotency record; latest=2; history `[1,2]`; v1 unchanged. Sequential simulation does not pass. | NOT RUN / TBD |
| `PERM-01` | F0/F1 / editor | Exercise all three GET routes and both POST routes. | Authorized operations succeed with frozen `200/201` status and only the allowed Source fields; editor receives no approval/dispatch/delegation/admin capability. | NOT RUN / TBD |
| `PERM-02` | F1 / founder_viewer | GET Source-detail page, current detail, ordered history, and manifest/download. | `200`; exact allowed metadata is visible; synthetic/local authority label is present; no write controls or mutable form endpoints are exposed. | NOT RUN / TBD |
| `PERM-03` | F0/F1 / founder_viewer | Forge both POSTs and all update/delete methods directly, regardless of hidden controls. | `403` frozen error for every write attempt; database and manifest unchanged; response reveals no content/count beyond the authorized read contract. | NOT RUN / TBD |
| `PERM-04` | F0/F1 / anonymous | GET page and each API route for both existing and random non-existing Source IDs; POST both write routes. | API returns `401` frozen error; page returns the frozen anonymous denial/redirect for both existing and missing IDs; responses do not distinguish object existence or disclose metadata, manifest, snippets, counts, or bytes; no write. | NOT RUN / TBD |
| `PERM-05` | F1 / founder_viewer+anonymous | Inspect redacted application/database logs and any configured cache after denied reads/writes. | Denials are attributable by safe principal/route/status, but logs/cache/errors contain no Source content, credential, token, manifest body, hidden count/snippet, or stack trace. If no cache exists, record configuration proof as not applicable; absence is not assumed. | NOT RUN / TBD |
| `PAR-01` | F1 / founder_viewer | Under the same authenticated principal/session, capture API detail/history/manifest metadata and extract the rendered page values. | Exact parity for stable Source ID, `synthetic`, latest version, ordered versions, immediate correction link, byte lengths, content SHA-256 values, manifest SHA-256, and authority-mode semantics; page has no extra inaccessible object data. | NOT RUN / TBD |
| `PAR-02` | F1 / founder_viewer | Download the manifest from the page link and call the API manifest route in the same session. | Download and API canonical bodies are byte-identical; digest metadata and independently computed SHA-256 agree; filename/content type match the frozen contract; no raw content. | NOT RUN / TBD |
| `PAR-03` | F1 / founder_viewer+anonymous | Compare page/API responses for forged writes, denied reads, missing Source, and malformed identifiers; inspect page links/forms/embedded data. | Both surfaces apply the same service/permission decision; no UI-only bypass, hidden mutation control, object-existence oracle, sensitive embedded JSON, or inconsistent history/manifest result. Protocol-specific status differences must equal the T0-frozen matrix. | NOT RUN / TBD |

## 6. Mandatory 20-test public regression inventory

These are the exact accepted tests at baseline commit `2fc97fb8ccfcc0120b2e1ff3bb79e655fde68a0b`. Test must prove the files remain active: no removal, rename that evades discovery, skip/xfail, weakened assertion, changed fixture, or changed expected exception merely to obtain a pass. `tests/test_source_versions.py` must also be byte-for-byte equal to the baseline and pass separately as 6/6.

For every row: fixture is the test's invented in-memory Source fixture; role is Test; setup is an exact-candidate clean process using the attested CPython; actual is `NOT RUN`; artifact is the complete unittest command/output plus test-file and baseline/current digests.

| ID | Exact accepted test | Action / expected result | Actual / artifact |
|---|---|---|---|
| `REG-01` | `SourceVersionKernelTests.test_creates_invented_source_v1` | Add/retrieve synthetic v1; same object is returned. | NOT RUN / TBD |
| `REG-02` | `SourceVersionKernelTests.test_appends_v2_under_stable_identity_and_exposes_it_as_latest` | Append v2; stable identity and latest version 2. | NOT RUN / TBD |
| `REG-03` | `SourceVersionKernelTests.test_v2_correction_preserves_v1_bytes_and_retrieval` | Append v2; exact v1 bytes/object remain retrievable. | NOT RUN / TBD |
| `REG-04` | `SourceVersionKernelTests.test_rejects_overwrite_of_an_existing_version` | Changed v1 overwrite raises `SourceOverwriteError`; v1 unchanged. | NOT RUN / TBD |
| `REG-05` | `SourceVersionKernelTests.test_rejects_duplicate_version` | Duplicate v1 raises `DuplicateSourceVersionError`; latest unchanged. | NOT RUN / TBD |
| `REG-06` | `SourceVersionKernelTests.test_rejects_source_not_explicitly_marked_synthetic` | `false`, null, and integer truthy markers each raise `NonSyntheticSourceError`. | NOT RUN / TBD |
| `REG-07` | `SourceHistoryTests.test_history_is_ordered_immutable_snapshot` | History is ordered tuple `(v1,v2)`; tuple/item mutation fails. | NOT RUN / TBD |
| `REG-08` | `SourceHistoryTests.test_kernel_rejects_mutable_content` | `bytearray` content raises `ValueError`. | NOT RUN / TBD |
| `REG-09` | `SourceManifestTests.test_manifest_records_exact_metadata_and_hashes_without_raw_content` | Canonical manifest records exact schema/order/links/lengths/hashes and excludes raw content. | NOT RUN / TBD |
| `REG-10` | `SourceManifestTests.test_generation_and_digest_are_byte_for_byte_deterministic` | Repeated bytes/digest are identical and digest equals SHA-256(body). | NOT RUN / TBD |
| `REG-11` | `SourceManifestTests.test_adding_v2_does_not_change_v1_entry_or_content` | v1 entry/content unchanged after v2. | NOT RUN / TBD |
| `REG-12` | `SourceManifestTests.test_verifies_unchanged_manifest` | Unchanged manifest verifies without error. | NOT RUN / TBD |
| `REG-13` | `SourceManifestTests.test_rejects_malformed_schema` | Wrong/missing/extra schema fields raise `SourceManifestVerificationError`. | NOT RUN / TBD |
| `REG-14` | `SourceManifestTests.test_rejects_missing_version` | Missing version raises verification error. | NOT RUN / TBD |
| `REG-15` | `SourceManifestTests.test_rejects_reordered_versions` | Reordered versions raise verification error. | NOT RUN / TBD |
| `REG-16` | `SourceManifestTests.test_rejects_duplicate_version` | Duplicate version raises verification error. | NOT RUN / TBD |
| `REG-17` | `SourceManifestTests.test_rejects_broken_correction_link` | Broken predecessor link raises verification error. | NOT RUN / TBD |
| `REG-18` | `SourceManifestTests.test_rejects_changed_metadata` | Changed byte length/metadata raises verification error. | NOT RUN / TBD |
| `REG-19` | `SourceManifestTests.test_rejects_changed_content_bytes` | Changed Source bytes raise verification error. | NOT RUN / TBD |
| `REG-20` | `SourceManifestTests.test_rejects_digest_mismatch` | Wrong manifest digest raises verification error. | NOT RUN / TBD |

Mandatory commands, with the exact T0 launcher substituted, are:

```text
python -m unittest discover
python -m unittest tests.test_source_versions
```

The full run must report exactly the frozen expected inventory or a Director-approved additive inventory; discovery of fewer than 20, any skip, or failure is not a pass. Additive tests do not replace any row above.

## 7. Case and overall verdict rules

### Per case

- **PASS:** the exact expected result is observed once on the exact candidate/configuration/fixture; all required raw artifacts and pre/post state are present; no undeclared retry, skip, partial write, or leakage exists.
- **FAIL:** any expected result differs, a forbidden write/leak occurs, the case/test fails or skips, the database/export/page/API states disagree, or a mandatory integrity/permission/concurrency invariant is violated. A reproducible product defect is FAIL even if a workaround exists.
- **INCONCLUSIVE:** the exact candidate/environment cannot be established, execution is interrupted or contaminated, required evidence is missing/corrupt, the frozen representation is ambiguous, or an authorized dependency/runtime is unavailable before behavior can be determined. Inconclusive is never pass.
- **NOT RUN:** execution has not started. This is the status of every case in this predeclaration.

Expected denials pass only when the declared denial occurs **and** no write, object-existence oracle, content/count/snippet leak, partial idempotency state, misleading log/cache/export residue, or silent repair is observed.

### Overall

- **PASS — RMS-VS-1 SOFTWARE INCREMENT:** every mandatory vertical-slice case and all 20 regression cases PASS; zero failures, inconclusive, not-run, skipped, or weakened cases; evidence gate complete; no unresolved mandatory defect.
- **FAIL:** any mandatory case FAILS. A later fix does not erase the initial failure; apply the bounded retest rule below.
- **INCONCLUSIVE:** no mandatory failure was observed, but at least one mandatory case is INCONCLUSIVE/NOT RUN or evidence/identity is incomplete. If both a failure and uncertainty exist, report FAIL and separately list the uncertainty.

No pass rate, severity downgrade, retry, developer assertion, or deadline can override a mandatory failure.

## 8. One bounded retest

At most one retest cycle is allowed within the Test Engineer's shared 1.0-person-day RMS-VS-1 cap.

1. Preserve the original candidate, command output, artifacts, case verdicts, and defect report unchanged.
2. The build owner supplies one reviewed fix candidate with a new exact commit/tree, bounded diff, dependency/config identity, and defect-to-change mapping. Test does not silently patch the candidate.
3. Retest every failed/inconclusive case affected by the change, all cases sharing the changed rule/path, `GATE-01`, and the full `REG-01`–`REG-20` suite. Permission, transaction, migration, fixture, or shared-service changes require the corresponding complete case families, not a single spot check.
4. Record initial and retest results separately. If the bounded retest passes, the report may PASS only when every mandatory case is complete and passing. Any remaining/new mandatory failure is final FAIL; remaining environment/evidence uncertainty is INCONCLUSIVE.
5. A second fix, another candidate change, criterion/fixture weakening, cap overrun, or new scope requires a fresh authorized verification cycle; it is not called a retry.

## 9. Defect record minimum

Each defect records: ID; discovered UTC; exact candidate/config/fixture; case ID; severity and user/integrity/security impact; minimal synthetic reproduction; exact command/request; expected versus actual; pre/post state and whether a write/leak occurred; safe artifact references; suspected component clearly labeled as hypothesis; build owner; fix commit; reviewer; retest cases/result; unresolved risk/dissent. Failures and logs remain preserved if the build owner disagrees.

## 10. Known limitations and explicit non-claims

- Local developer-run loopback/task-scoped instance only; no deployment, shared URL, service availability, default-branch merge, release, Operations support, or production/VPS claim.
- Synthetic Source records only. No real/protected/vendor/licensed/candidate/reserved/final-test data, rights effectiveness, connector, empirical test, backtest, paper trade, or live trade.
- Only Source create/correct/history/manifest, one read-only page, narrow permissions, migration, fixture, and export reproduction are assessed. Search, snippets/counts/summaries, broad dashboard, approval/delegation/dispatch, workflows beyond Source, four ledgers, backup/restore, evidence-object custody, off-VPS recovery, monitoring, and the full Stage 1 data contract are outside this increment.
- Hash/digest agreement detects tested changes; it does not prove immutable or independently protected custody, prevent privileged replacement, or establish lawful rights.
- PostgreSQL concurrency results apply only to the recorded version/configuration/isolation and two-request case; they do not establish general load, performance, or distributed exactly-once behavior.
- Page/API parity covers the frozen Source fields and principals only. Accessibility, browser compatibility, operational security hardening, and other roles remain unproven except where separately recorded.
- Public regression tests are known to the build team and are not reserved tests. Passing them does not establish independent Risk acceptance.
- Research accounting remains zero empirical experiments, zero early empirical closures, zero countable full-validation cycles, and zero qualifications.

## 11. Handoff

The Director of Engineering uses this checklist during contract freeze/T0, fills the exact interface/environment fields, and supplies the version-bound candidate package. Build owners may comment on testability but do not change mandatory intent after results are seen. Test executes incrementally when an authorized stable slice exists, publishes the separate exact-build report and unchanged evidence package, and hands it to Risk without claiming Stage 1 acceptance.
