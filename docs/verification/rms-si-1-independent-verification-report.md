# RMS-SI-1.0 independent software verification report

**Issue:** [MAU-95](/MAU/issues/MAU-95)  
**Authority:** [MAU-44 plan revision 4](/MAU/issues/MAU-44#document-plan), revision `3603fbc1-87fe-4701-9592-c870d526b20b`  
**Contract:** [RMS-SI-1.0](/MAU/issues/MAU-93#document-contract), revision `13eb82e2-9762-4d96-83cc-30e6aa8b6f3e`  
**Checklist:** `docs/verification/rms-si-1-predeclared-checklist.md`, version 1.0  
**Product candidate:** `0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0`  
**Candidate tree:** `c1219ad5bd24bbb43b11f74938c7b2b4c8e08f77`  
**Delivered regression baseline:** `107504a78eb8bb8b27465d4d726c6c447bab9ca5`  
**Execution:** 2026-09-22, completed 15:44 UTC  
**Owner:** Test Engineer, Research Systems

## Verdict

**INCONCLUSIVE — RMS-SI-1.0 SOFTWARE INCREMENT**

The exact product candidate passed every executed Backend, Frontend page/template, migration, database-integrity, permission, correction, linkage, idempotency, concurrency, manifest, rollback, route-inventory, public regression, and system case. No product defect was observed. The positive label is withheld because mandatory `UI-01` was not executed in a real browser: independent evidence covers server-rendered DOM, JavaScript syntax/binding inspection, and route-level pages, but not an actual browser form create/correct submission. Under the frozen checklist, missing evidence is not a pass.

This verdict is software verification only. It is not Risk acceptance, Stage 1 acceptance, deployment readiness, protected-data isolation, research validity, strategy qualification, or trading approval.

### Totals

| Status | Mandatory cases |
|---|---:|
| PASS | 48 |
| FAIL | 0 |
| INCONCLUSIVE | 1 (`UI-01`) |
| BLOCKED / NOT RUN | 0 |

No product repair or product-code change was made by Test. Test authored only `tests/django_rms_si_independent_tests.py` and this report after pinning the candidate. The first three Test-owned executions exposed Test-harness mistakes; all are retained in the evidence archive and do not count as product failures.

## Candidate and environment identity

- Branch: `MAU-44-rms-stage-1-founder-dashboard-and-frontend`; candidate was local `HEAD` at execution start and the worktree was clean.
- Ancestry: the delivered baseline is the candidate merge-base. Builder handoffs `5d22886170c3dac95dac37d5e7aa2d12f45fb5ae` and `5bd23cfc64627ff7e72c6ac4788c55544b573adb` are in the recorded lineage.
- Remote state: no local remote-tracking ref contains the candidate; `origin/master` is 14 commits behind. Identity is therefore the exact local SHA and [MAU-97](/MAU/issues/MAU-97) commit work product, not branch-name equality.
- Baseline-to-candidate binary diff SHA-256: `ab11ea63ee02c539affad536b4884b2cf968f50fbd718b65a24cdb4ac7656f96`.
- Runtime: Linux x86_64, CPython 3.13.15, Django 5.2.17, DRF 3.18.1, psycopg/psycopg-binary 3.3.6, PostgreSQL 17.11.
- Lock digests: `requirements.lock` `d21ca3b1acbcd2bbd60637b3870b5498307084173e070a9f78834dc4b4341ea4`; `stack.lock` `937dfe5d48c71f14a092e9196a2e38ea22a4dbb33e89d6a58b1c5bf4668eeb00`.
- Migration digests: `0001` `f108abe2…`, `0002` `6ce06b0e…`, `0003` `bc39af63…` (full values in the evidence archive).
- Fresh isolated cluster: run-owned scratch directory, PostgreSQL 17.11, database owner `node`, `read committed`; application `TIME_ZONE=UTC`, `USE_TZ=true`, locale `C`. The cluster was never shared or exposed beyond loopback.
- The handoff-relative `.paperclip-runtime/venv` did not exist in this worktree. Test used the unchanged pinned Python/PostgreSQL artifacts in the approved VS1 execution workspace; exact absolute paths and versions are retained in command evidence.
- Redacted configuration digest: `d473022dc2a76e9dcf2ca25a51e0d56e83586c4028f726d3c764222d1b8642e7`.

## Executed evidence

| Evidence | Result |
|---|---|
| Fresh migration through `rms.0003`, then repeat migrate | PASS; second run reported no migrations to apply |
| Baseline-shaped `rms.0002` rows migrated to `0003` | PASS; two raw byte sequences, two content digests, and two historical manifest byte/digest pairs unchanged; deterministic `SRCV-*` IDs assigned |
| Public `python -m unittest discover -v` | PASS, 20/20, 0 skip/retry |
| Focused Backend Django suite | PASS, 23/23, 0 skip/retry |
| Focused Frontend Django suite | PASS, 7/7, 0 skip/retry |
| Test-owned independent Django suite | Final PASS, 10/10, 0 skip/retry |
| Workspace diagnostics | PASS, 2/2 |
| `makemigrations --check --dry-run` | PASS, no changes detected |
| `manage.py check` | PASS, no issues |
| `node --check static/rms/rms_forms.js` | PASS |
| Schema/trigger inventory | PASS; ten append/watermark/manifest/idempotency triggers plus expected unique/check/FK constraints retained |
| `manage.py check --deploy` exploratory | Four expected local-only warnings: missing security/clickjacking/CSRF middleware and development secret. Not a mandatory failure because deployment is expressly excluded. |

The Test-owned suite used only fictional data and independently exercised all Source enums and nulls; max-length/array boundaries; invalid text/timestamp/URL/Base64/shape cases; all Idea market/status combinations and the rejection matrix; 100/101 contribution edges; exact-version binding; authorization-before-lookup; failure-key reuse; offset-equivalent idempotent replay; three historical manifests; database history mutation/cross-record reassignment denial; injected Source/Idea rollback points; intake/rejection UI labels; raw-byte absence; and exact route/exclusion inventory.

## Requirement-to-case actuals

| Cases | Actual | Evidence |
|---|---|---|
| `GATE-01` | PASS | Exact SHA/tree/ancestry/status, runtime/package/lock/config/database identities, diff and evidence digests captured |
| `MIG-01`–`MIG-03` | PASS | Fresh/repeat migrations, baseline migration preservation, schema/trigger inventory, builder and Test-owned database negatives |
| `SRC-01`–`SRC-06` | PASS | Backend focused suite plus Test-owned enum/null/boundary/three-version cases |
| `VAL-01`–`VAL-05` | PASS | Test-owned boundary matrices plus Backend frozen-contract validation and generic error cases |
| `IDEA-01`–`IDEA-05` | PASS | Backend Source/Idea suite, Test-owned status/contribution/UI cases, row/API comparisons |
| `LINK-01`–`LINK-03` | PASS | Exact v1 binding across Source v2/v3, raw/Base64 absence in JSON/pages/manifests, atomic bad-reference denial |
| `MAN-01`–`MAN-04` | PASS | Three-version manifest test and independent pre/post-`0003` byte/digest preservation |
| `PERM-01`–`PERM-05` | PASS | Editor/viewer/other/anonymous API and page matrix; before-lookup denials and unchanged row counts |
| `IDEM-01`–`IDEM-04` | PASS | Byte-exact replay, cross-endpoint conflict, canonical-time equivalence, validation/not-found/stale/authorization rollback/no reservation |
| `ATOM-01`–`ATOM-03` | PASS | Source/Idea stale checks, real two-session one-winner races, injected pre-commit failures with full rollback and unchanged watermarks |
| `UI-01` | **INCONCLUSIVE** | Templates, page contexts, correction prefill, JS syntax and request-construction inspection passed; no independent real-browser create/correct submission |
| `UI-02`–`UI-05` | PASS | Exact `source_version_id` selector/prefill, page/API values and denials, intake/rejection wording, raw-byte absence |
| `REG-01`–`REG-04` | PASS | 20 public + 23 Backend + 7 Frontend + system/migration checks; no skips or retries |
| `SYS-01` | PASS | Exact 17-route inventory; excluded search/import/hypothesis/approval/dashboard/connector routes return 404 |

## Preserved Test-harness failures

These failures were authored and diagnosed by Test; product code was unchanged throughout.

1. Initial Test-owned run: 9/9 errors because a helper named `client` collided with Django's built-in fixture. No product assertion ran.
2. First corrected run: 7/9 pass, two invalid Test assertions (empty-string leak search and a negative setup that accidentally created a valid same-record v2).
3. First rollback run: 9/10 pass; Test expected injected exceptions to escape, while the frozen DRF handler correctly returned the generic error envelope. Row-state assertions were then retained and the response expectation corrected.
4. Final run: 10/10 pass.

No retry conceals an initial product failure; there was no observed product failure.

## Defects, limits, and next action

- Product defects: none observed.
- Mandatory evidence gap: `UI-01` real-browser form submission. Owner: Director of Engineering/Test environment owner. Next action: provide an approved ephemeral browser-capable loopback environment for this exact SHA (or a replacement exact candidate if product changes), then Test executes Source create/correct and Idea create/correct through the actual forms and publishes a supplemental verdict. This report must not be relabeled PASS without that evidence.
- Remote reproducibility limit: candidate is not present on a local remote-tracking ref. The exact commit exists in the authorized execution worktree and [MAU-97](/MAU/issues/MAU-97) work product; preservation beyond that workspace is an Engineering handoff concern.
- Deployment/security warnings were observed only under the optional `--deploy` check. This increment expressly excludes deployment and Basic authentication is loopback-development-only.
- Synthetic local PostgreSQL tests do not prove protected-data isolation, independent evidence custody, backup/restore, off-VPS recovery, production security, or research validity.

Evidence archive SHA-256: `82e4bfdc4098696177d2db85cb6f3bcaf65789a05bd6058305f13cbf7f73d5b0`.
