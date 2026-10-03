# Strategy Specification and Test Plan integration

Implementation release: founder direction October 3, 2026 on
[MAU-150](/MAU/issues/MAU-150). Predecessors
[MAU-140](/MAU/issues/MAU-140) and [MAU-44](/MAU/issues/MAU-44) remain closed.
VP Data & Engineering is accountable; Director owns the integrated candidate.

Canonical source: `RMS_STRATEGY_SPECIFICATION_AND_TEST_PLAN_DESIGN_CONTRACT_V1_0.md`,
82,585 UTF-8 bytes, SHA-256
`9236d104249fc796d3b5fbe214a5be92c4d4f95812ee17ba0f0fb99d1cb1a240`.
Readable Paperclip revision: `dec62ed2-adab-4ab3-bbfd-8dffbcee897d`.
The full document was read and its exact bytes preserved in this checkout.
Base: merged master `e166539d507cf9b05fcf1d44373f172883ee386b`.

## Disjoint ownership

| Owner | Exclusive files |
| --- | --- |
| Backend | `rms/test_plan_schema.json`, `rms/test_plan_models.py`, `rms/test_plan_validation.py`, `rms/test_plan_services.py`, `rms/test_plan_api.py`, `rms/test_plan_api_urls.py`, new `rms/test_plan_*.py` backend modules, `rms/models.py` import registration, migrations starting `0006`, `docs/RMS-TP-API-1.md`, builder tests prefixed `test_test_plan_backend` or `django_test_plan_backend` |
| Frontend | `rms/test_plan_views.py`, `rms/test_plan_navigation_urls.py`, `rms/navigation_views.py`, `templates/rms/` including existing navigation/detail templates, `static/rms/test_plan*`, builder tests prefixed `test_test_plan_frontend` or `django_test_plan_frontend` |
| Independent Test | `tests/independent_test_plan*`, `docs/verification/rms-tp-*`, `staging/browser/test-plan-*`; no product fixes or editing builder evidence |
| Director | `rms_project/urls.py`, `staging/build*`, `staging/release_identity.py`, `rms/staging_test_reset.py`, source manifests, integration receipts, root routes and final conflict resolution |

No simultaneous edits outside the assigned paths. Coordinate any reassignment
explicitly in the parent. Backend publishes API-1/schema commit and hash first;
Frontend consumes the exact version and uses shared services. Root route names
are `rms.test_plan_api_urls` and `rms.test_plan_navigation_urls`. Backend owns
migration numbering; no second migration series. Director integrates without
waiting for acceptance of the candidate being integrated.

## First usable checkpoint

Existing exact Hypothesis → title-only incomplete plan → explicit save → reopen
→ revise with expected head/reason → unchanged v1 and pinned lineage. Extend
that same flow to the complete contract, including child versions, listed
variations, criteria, data definitions and external check reports. No reduced
final scope is implied.

## Runtime and evidence

Existing task-local `.venv/bin/python` loads CPython 3.13.15, Django 5.2.17,
DRF 3.18.1 and psycopg 3.3.6. The PATH Python launcher tried to open the shared
read-only bootstrap lock and failed; invoking the already-provisioned task-local
interpreter succeeds. Do not rerun the provisioner or alter shared tool settings.

Use existing `mv-rms-staging` / `mv-rms-staging-db-1` / `rms_staging` for database
checks under the approved auth-preserving procedure. No new per-test database,
`rms_synthetic` fallback, whole-database flush/drop or service creation.
Source-only checks are labeled separately from PostgreSQL/browser acceptance.
Every handoff records commit/interface, paths, commands/results, remaining defect
and one next owner/action. Independent TP01–TP24 evidence remains separate.

`staging/build-tp-package.py` extends the existing exact-Git-object packaging
recipe and requires the new integrated source manifest plus contract/interface.
It prepares a package only. Merge, staging application update and research
execution retain their separate authorization boundaries.

## API-1 integration checkpoint, October 3, 2026

Director copied ten Backend-owned files from run
`6b02bb29-16d0-461a-bb58-e9673271ec5a` as an uncommitted source snapshot.
`docs/RMS-TP-API-1-INTEGRATION-RECEIPT.json` preserves every copied hash.
Actual schema hash is
`bcd72eb27e932f8778a7fa09bd47dafb40550364490c459839d5f04a84e23900`;
the first advertised `81b351…` schema hash is historical. Backend is producing
a successor interface note. Frontend received the concrete current source.

Director registered all nine API routes at `/api/v1/`. Database-free reverse
and resolve checks passed for each route; `manage.py check` exited 0. Browser
root registration waits for the matching Frontend source handoff. Persistence
and the first click-through workflow are not yet verified.

The existing staging reset helper now allows exactly the eight additive Test
Plan tables (27 RMS tables total), accepts only the three reviewed schema
levels, and separately verifies/restores `hn_no_truncate` and `tp_no_truncate`
guards. Partial schemas/migrations/guards fail before mutation. Authentication
fingerprints and guard verification remain inside the same atomic transaction;
ordinary version/association triggers remain enabled.
`manage.py test tests.test_staging_test_reset -v 2`: 22/22 PASS, exit 0, unused
database skipped. These are mock boundary/rollback tests, not PostgreSQL proof.
No database connection, migration, reset, fixture or deployment was performed.

Independent preparation on [MAU-153](/MAU/issues/MAU-153) retains 24
NOT EXECUTED acceptance cases and two early validator expectations requiring
Backend correction/retest (decimal equality and missing-path order). Test owns
its unchanged findings. Actual integrated-candidate acceptance is pending.

Director's existing granted GitHub alias was read through the approved secret
API without disclosing or persisting its value. Observed repository write access
and remote master `e166539d507cf9b05fcf1d44373f172883ee386b` permit direct
GitHub object/ref publication on this same execution branch, without shared
Git-metadata permission changes. Local metadata remains read-only.
[MAU-154](/MAU/issues/MAU-154) owns the existing-staging execution route and
any necessary local-metadata reconciliation through its approved operator path.

Next owner/action: Frontend supplies the matching browser slice; Backend supplies
the successor schema/note and defect checks; Director integrates their next
receipts, provides one exact candidate, and allocates the existing-staging slot
after Operations supplies observed project/container/database/SQL-role binding.
Merge and application deployment remain separate decisions.

## Browser/API source integration checkpoint

Backend API-1 candidate revision 1.1 is adopted; schema SHA-256
`17e17d366e89fb0e69c3d992dd06da7b2345bcef6193170015b7b733e26df82e`.
Director captured 12 Backend and 17 Frontend owned files as source snapshots;
`docs/RMS-TP-SLICE-INTEGRATION-RECEIPT.json` preserves their exact bytes/hashes.
All nine browser routes now resolve, alongside all nine API bindings.
The release static allowlist includes the new Test Plan JS/CSS.

Executed integrated-source checks: 45 rendering/backend validation cases pass
with the DB skipped; six JavaScript cases pass; eleven package/static-identity
cases pass after the static allowlist change. Reset boundary tests passed 22/22.
`docs/RMS-TP-SLICE-SOURCE-CHECKS.json` records commands, results and limitations.
`docs/RMS-TP-INTEGRATED-SOURCE-MANIFEST.json` inventories the exact product inputs
for the Test Plan packaging recipe. These checks do not prove database saving
or a browser click-through against an installed build.

[Draft PR #5](https://github.com/dieg0andres/mv-rms/pull/5) was published early
at `beb5d113855873c91559686ce5d86b4df51ab200`; the initial publication receipt
is preserved in `docs/RMS-TP-PUBLICATION-RECEIPT.json`. Later candidate commits
are explicit successors. Ordinary source checks for the two early Backend
validator findings now pass; independent retest remains Test-owned.

Next: Operations supplies the existing-staging route/observed SQL role; Director
allocates Backend's bounded migration/service slot, then Test's independent
slot. Application deployment and merge are still separate release decisions.
