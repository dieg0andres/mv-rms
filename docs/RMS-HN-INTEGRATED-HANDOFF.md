# Integrated Hypothesis/navigation source handoff

October 3, 2026. Director receiving run
`bc892640-8cf3-45de-b497-ffea777ce56c`,
[MAU-140](/MAU/issues/MAU-140).
Authority: [Director integration release](/MAU/issues/MAU-140#comment-090eb825-7226-401a-88d1-5e03f008ab99).
This source handoff supersedes the prior parent F1 integration block; it does
not rewrite the original review/failure evidence or assert release acceptance.

## One source candidate

The application in this Director workspace is the candidate. It was composed
from a local Git archive of reviewed Backend
`aab6d6dfde13fe03f184292f197ed3a56ce00b9d`, overlaid only with the 33 paths in
Frontend `fb9766f25cc723463ce15ae78feed282ab6163fc`'s final manifest. Every overlay
blob was obtained from that exact Git object and checked for bytes/SHA-256.
Frontend manifest SHA-256:
`38b73ce2ae85534628044ea9f2e2867eb0abd4a88bf0494a108660cc143bca8d`.
All source differences from that composition are declared in
`RMS-HN-INTEGRATED-SOURCE-MANIFEST.json`; the manifest binds the complete
application source and retained Backend evidence. Existing Director evidence,
canaries and shared worktrees were preserved.

Accepted contract remains byte-identical under its original filename:
`RMS_HYPOTHESIS_DESIGN_CONTRACT_V1_0.md`, SHA-256
`f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9`.
API 1.2 remains the sole shared schema: SHA-256
`8a2ee1204b3d54647010254939bee3fabf49d5c2a1edae25a7e6be010726aaea`.
Backend's R4/R5 and earlier four-fix approvals remain recorded inputs; their
unchanged review suites were not repeated.

Director root URLs now mount `rms.hypothesis_api_urls` and
`rms.navigation_urls`, retaining every existing Source/Idea route and name.
The exact Frontend branch by itself remains insufficient to run the application.

## Corrections and failure preservation

F1 is corrected in the integrated source: Idea detail uses the shared browser
failure handler, preserving 401/403/404 with Home navigation and suppressing
partial Idea metadata on denial/not-found. Database/schema unavailability keeps
the authorized Idea visible with linked counts explicitly unknown. Generic
service conflicts render the existing safe browser failure page. Authentication
failures retain the challenge header. New regressions exercise both reader roles,
actual root route resolution, response status, Home, diagnostic suppression,
input-independent role denial and source/runtime release labeling.

The previous frontend schema test asserted that navigation was unmounted during
its preparation phase. That assertion now checks actual integrated registration;
the error, lineage, input and permission assertions were retained. The initial
98/99 passing result and its obsolete-phase failure are preserved in
`verification/RMS-HN-INTEGRATED-SOURCE-first-check.log`.

An initial native composition placed two small hunks at repeated contexts in
`rms/models.py` and `rms/services.py`, causing setup to fail with
`IndentationError` at models.py:272. Both files were replaced with the exact
Backend blobs, then the entire composition was byte-checked. This failed setup
was retained in the receiving-run transcript; it was not a database test.

## Reproduction and evidence

Use the existing absolute task `.venv/bin/python`, `login=false`; never invoke
the provisioning wrapper or Django's lifecycle test runner.

```bash
ABSOLUTE_TASK_VENV_PYTHON -B scripts/check-rms-hn-source.py --output NEW_RUN_OWNED_OUTPUT_DIRECTORY
node --test tests/django_hypothesis_frontend_draft.test.js tests/django_hypothesis_frontend_record_form.test.js
```

The Python command verifies every pinned file, denies every Django database
connection during setup/import/execution and refuses an existing output
directory. Its suite includes the integrated browser/API checks and pure
staging-target/package guards. The committed frontend runner separately produced
seven invented HTML renders. Actual final counts, exits and hashes are in
`verification/rms-hn-integrated-bc892640-final/summary.json` and its adjacent log;
render evidence is separately retained in `verification/rms-hn-renders-bc892640`.
Node checks use VM fixtures, not an actual browser. No H-case is counted from
these Director checks. Failed and earlier results remain separate.

## Existing facility reconciliation and concrete preserving procedure

The older `rms_synthetic` software-test facility is not the founder-required
staging target. The existing repository compose recipe names project
`mv-rms-staging`, SQL database `rms_staging`, and its `db` service corresponds to
the instructed `mv-rms-staging-db-1`. This is source configuration evidence,
not an observed live binding, ordinary-role entitlement or installed-schema
claim. Operations must provide observed existing app/database container IDs,
volume identity, secure private-route reference, effective host/port/database,
ordinary-role identity, distinct active editor/viewer IDs, and coordinated slot.
Reuse existing bindings; this handoff creates/grants nothing.

New `rms/hypothesis_staging_preflight.py` supplies a concrete conditional guard:

```bash
ABSOLUTE_TASK_VENV_PYTHON -B -m rms.hypothesis_staging_preflight --packet "$RMS_HN_REVIEWED_PACKET"
```

This CLI performs local packet/source review only, never a DB connection. The
packet contains references/identities and source-manifest hash, no secret values.
Its executable `execute_read_only_preflight` requires the existing approved
runtime to inject an independently authenticated release verifier and an
already-approved connection adapter. No import path, DSN, connection or grant
is supplied/discovered from user metadata. Packet consistency or
`execution_authorized=true` does not grant execution. The verifier must bind
exact packet/source/target digests and the read-only scope; source is rechecked
after verification and the effective address/SQL identity are checked.

Intended preflight writes: **no data, schema, account, sequence, migration or
fixture writes**. SQL is a repeatable-read/read-only transaction, two local
timeouts and SELECT of live DB/session/role flags, ownership, installed additive
migration names and the two existing principal memberships. Always rollback and
close, including rejection/error. Reject schema owner, superuser/CREATEDB/
CREATEROLE/replication/BYPASSRLS, SET ROLE identity mismatch, autocommit, missing
0004/0005 and a viewer also holding editor. This guard was tested with fake
sessions; no staging or software-test DB was contacted.

The old preserving runner/manifest remains an explicitly historical source-only
proposal with an old target/schema pin. It is not the command for this candidate.
Its append-only scenario, full physical baseline comparison, durable restricted
sink, reviewed effect-plan and separate-session observations remain requirements
for later write/concurrency acceptance. Read-only preflight does not replace
them or certify H14/H18. Operations/Test must review the actual binding and
trusted adapter/verifier before any DB invocation. The precise remaining
capability is the authenticated installed staging transport/release packet for
this source; no unavailable entitlement is invented.

Later reviewed data effects must enumerate, before execution: additive
migrations 0004/0005 if absent; newly namespaced invented Source/Idea/family/
manual assessment/case/Hypothesis identities and immutable versions; exact
classification/context/origin associations; correction/impact/idempotency facts;
identity-watermark effects only through reviewed append triggers; sequence
effects under the actual existing role. Existing fixture loader has fixed
fictional identities and is not adopted as an unrestricted concurrency runner.
Never flush/recreate/drop/truncate or delete cleanup. Retain failures and every
permitted addition. Migrations/fixtures/write tests need their separate exact
review and release; none was run here.

## Normal release preparation, without deployment

The old staging adapter intercepted `/` and served only the old forms script.
The source now supports an explicit v2 package: real Home is delegated to the
application, all four required JS/CSS assets are allowlisted and hash checked,
the safe version endpoint is retained, and the validated commit labels the
navigation. The trusted CSRF origin is the existing exact private HTTPS host,
so adapter rewriting to localhost does not reject valid browser saves; other
origins and missing tokens remain denied. Legacy metadata still requires its original commit/tree/static pin
and retains its old Home behavior. Authentication/private origin policy is
unchanged. No live adapter was changed.

After a normal reviewed Git checkpoint supplies exact commit AND tree, the
repository-only package command is:

```bash
ABSOLUTE_TASK_VENV_PYTHON -B staging/build-hn-package.py NEW_PACKAGE_DIRECTORY REVIEWED_FULL_COMMIT REVIEWED_FULL_TREE
```

It archives the exact Git object, verifies its tree and integrated manifest,
copies every adapter/recipe byte from that same object, refuses an existing
output directory and records complete product file hashes. The v2 Dockerfile
uses the unchanged compose recipe/resources. Pure invented-archive tests prove
pins, reproducibility, no moving refs and preserved output. No real package,
image build, Docker operation, migration, account creation or staging update
was performed. Operator records image digests, installed source/adapter/static
identity, preservation proof and private editor/viewer browser outcomes only
under the separate review/merge/deployment authorization.

## Requirements and receiving owners

| Contract sections | Delivered source/evidence | Remaining acceptance |
| --- | --- | --- |
| 1-4 outcome/semantics/dictionary | Exact contract, API 1.2, complete fields/forms/validation | Independent H01-H07 and browser |
| 5 context | Family/case/manual assessment and first-class associations | Actual saved bindings, H13/H19/H20 |
| 6 history | Immutable models/migrations/corrections and exact links | Installed ordinary-role/persistence H08-H14/H20 |
| 7 API | Mounted shared services; role-scoped paginated collections | Actual account/concurrency/persistence assertions |
| 8 navigation | Real root shell, screens, error navigation, preserved input | Independent H15/H16 browser/keyboard/narrow-layout |
| 9 fictional example | Existing idempotent fixture source retained | Exact approved preserving load/identity evidence |
| 10 acceptance | Independent mapping remains Test-owned | All H01-H20 on this exact candidate |
| 11 delivery | Manifest, DB-denied runner, conditional target guard, v2 package recipe | Safe installed binding/procedure, Git/review receipts |
| 12 completion | Explicit acceptance/release boundaries | Normal review/merge/staging records and founder browser outcome |

Next: independent Test on [MAU-144](/MAU/issues/MAU-144) reviews this pinned
source and guard evidence; Operations on [MAU-141](/MAU/issues/MAU-141)
supplies/reviews the existing staging binding/transport and preserving effect
packet; Director retains integration fixes and final source/release identity.
Operator checkpoints/publishes through the existing authorized route if Git
metadata/reporting prevents the Director handoff. Do not recreate the parent
blocked-by-Test scheduling cycle; no new issue or readiness table is needed.

Recommendation: independently review this source and conditional preserving
procedure before released DB/browser execution. Alternatives retaining the
unmounted branch, substituting rms_synthetic, using a schema owner, or running
default Django lifecycle fail the accepted requirements. Assumptions about live
bindings/schema/role are explicitly unverified. Prior Frontend dissent/failures
are retained with the Director correction; independent Test/Risk remain unedited.
No new founder scope approval is requested. Merge/deployment/DB release remain
separate recorded decisions. PR-wide Test INCONCLUSIVE, Risk INCONCLUSIVE /
NOT ACCEPTED (HIGH), 34 unexecuted Stage 1 cases and the restricted OPEN incident
remain unchanged. This increment is not DONE or a qualified strategy.
