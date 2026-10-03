# Hypothesis/backend source handoff

The October 3 source implementation release is MAU-142 comment
`f44b4a69-5572-44eb-acbe-08a96e41cedc`. Receiving run:
`c5b4b07b-ef27-4af1-852c-0e033930e082`. Base HEAD is
`4a1858f76777aa2f5e172b705b184fb8610237ea`; branch remains
`MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api`.

Before editing, the exact local Git contract at
`de6b971b8b1ef8b5ab6d230641aaec0daeb7e374` was read in full and verified:
58,395 bytes, SHA-256
`f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9`.
The input API-1 receipt hash was
`10f0b286eb290fba60ed4c63e8d2af10f6febd579cd6d7a1899c1dc048bce4c7`.
The approved contract was added from that exact Git object; it was absent from
the input worktree. The machine-readable schema was preserved byte-for-byte.
API-1 prose now describes the authored persistence source rather than its former
implementation hold. No dependency, runtime, service, account or grant was changed.

## Integration contract

The sole machine-readable interface remains `rms/hypothesis_schema.json`.
Browser callers use the signatures in API-1 with a Django user as `actor`,
an `Idempotency-Key` string and the full request envelope. Raw username strings
are not accepted by the new public services. Duration objects replace whole
values; optional field omission on creation expands to null. Corrections require
full snapshots, reasons and the positive expected latest version.

Director integration adds `include("rms.hypothesis_api_urls")` at the root URLConf.
The module contains `api/v1/...` paths without trailing slashes, matching the
schema. Root URLs, `rms/views.py`, templates and static files were not edited.
Hypothesis services live in `rms/hypothesis_services.py`; context services live
in `rms/research_context_services.py`. The new DRF adapter calls these exact
services and returns stored response bytes/status for writes.

The existing synthetic slice has shared authenticated read access and editor
group write access. New services additionally reject inactive principals and
scope retrieval before counts/serialization to synthetic records. New records
bind the exact accepted software contract reference; this reference neither
approves a Hypothesis nor creates a live Paperclip authority workflow.
Hidden/nonexistent references use uniform 404; field inconsistencies are 400;
stale expected versions and conflicting request-key reuse are 409. Role denial
occurs before validation, reference retrieval and mutation, including direct
browser-service calls. This increments no research ledger or credit.

## Storage and lineage

`rms/hypothesis_models.py` supplies separate stable identities and immutable
versions for Hypothesis, ResearchFamily, Investigation and PriorResearchAssessment.
Named scalar fields are stored in each version's `fields` JSON object and remain
independently addressable through the public field dictionary. Scalar JSON is
never used to store authoritative relationships. `effect_horizon` implements
baseline `horizon`; the separate sizing fields implement baseline `sizing`.

All six association kinds share constrained `ResearchAssociationIdentity` and
`ResearchAssociation` tables: IdeaFamily, InvestigationFamily,
PriorResearchInvestigation, HypothesisInvestigation, IdeaHypothesis and
AssessmentRecord. Each association has its own identity, version/audit envelope
and typed foreign-key endpoints. Partial unique indexes enforce one origin/case
per Hypothesis version and one family/assessment per case version. An exact Idea
version has one logical classification identity. Its explicit corrections append
association versions; older Hypotheses retain the selected classification version.
Choosing an exact historical classification is permitted when its family identity
matches the selected case; supersession is shown separately, never silently adopted.

Assessment record links become versioned association rows. Labeled external
references become separate immutable `AssessmentExternalReference` rows.
Positions preserve mixed internal/external link ordering through round trips.
Creation validates all reference existence/context before saving. Case and separate
assessment, or Hypothesis and explicit first Idea-family assignment, commit together.
An assessment correction must name the case's current assessment record/version;
no other case's assessment is silently adopted or rewritten.

`HypothesisCorrectionImpact` rows pin exact old/new endpoint versions. Existing
Source and Idea corrections now record direct and transitive impacts in the same
transaction, including Hypotheses reached through pinned Idea contributions.
Family/case/assessment/classification corrections also record impacts. A newly
created/revised Hypothesis using older explicit context records initial notices.
Historical fields and lineage remain intact; completeness and upstream review-needed
notices remain distinct. Source/Idea create/manifest/response semantics are preserved.

HN writes and upstream Source/Idea corrections take one transaction-scoped
PostgreSQL advisory lineage lock before other write locks. This deliberately
serializes this bounded synthetic slice to prevent missed create/correction impacts
and lock-order races. No workers or mutable evidence projections are introduced.
Identity row locks and append triggers retain the expected-version checks.
Idempotency keys are scoped to actor identity; actor/method/route/canonical original
payload bind reuse. A replay returns original bytes/status; a new-key identical
snapshot returns 200 and writes only its idempotency result, not a research version.

## Migration and rollback behavior

`0004_hypothesis_records` creates only additive tables, indexes and constraints;
it neither backfills nor alters existing Source/Idea rows. `0005_hypothesis_history_guards`
adds only new-table PostgreSQL triggers/functions, reusing the existing append-only
row-change function. Versions must append sequentially with immediate-predecessor
FKs; only append triggers advance identity watermarks. UPDATE/DELETE/TRUNCATE of
new historical rows is rejected. Deferred graph checks require complete compatible
origin/case/family/assessment bindings at transaction commit. A failed migration
rolls back its own atomic transaction; a failed write leaves no committed partial
record, relation, impact or idempotency result.

These are authored guards, not verified database protection. The ordinary app role
must have no table-owner, superuser, DDL or trigger-disable authority; its actual
rights and the guard denials require independent verification on the separately
authorized facility. No grants or database operations were run here.

Apply both migrations before routing new APIs or running source with new correction
hooks. Rolling application code back retains all additive data/tables/guards and is
compatible with old Source/Idea code. Migration 0005 is deliberately irreversible:
automatic downgrade must not strip history protection. Do not reverse 0004 or delete
new records to roll back. Operations owns installation/recovery under a separate
authorization, with existing saved data/volume/accounts preserved.
Schema compatibility alone does not preserve correction-impact recording: older
Source/Idea code lacks the new hooks. A rollback must retain those hooks or freeze
upstream correction writes until they are restored, under Operations' separately
authorized recovery procedure. Reads may continue; do not silently create an
unrecorded impact gap while retaining Hypothesis history.

## Invented fixture and verification

`load_rms_hn_fixture` is authored management source only; it was not executed.
Fixture identity is `RMS-HN-F1-20261003`. It uses an existing named editor and an
explicit fictional review UTC time, creates its own invented Source/Idea/family/
assessment/case, a Hypothesis v1, a sibling and an explicit Idea-v2/Hypothesis-v2
adoption. It uses actual saved IDs, explicit family assignment and limitations;
it creates no account, hidden parent, exception, research approval or empirical result.
The recipe's assessment is labeled as an invented manual-review example.
A retained fixture receipt makes reruns with the same actor/time idempotent;
conflicting identities stop without rewriting existing records. The command is
not a substitute for the approved preserving harness or its target/role receipts.

DB-free verification uses the approved `.venv/bin/python` and non-login exec:

```text
.venv/bin/python -m unittest tests.django_hypothesis_backend_validation_tests tests.django_hypothesis_backend_source_tests tests.django_research_context_backend_source_tests -v
```

The broader focused regression command also includes
`tests.test_source_versions`, `tests.test_source_manifests`,
`tests.django_hypothesis_backend_preservation_helper_tests`, and
`tests.django_hypothesis_backend_runner_guard_tests`. It was run through
`unittest.defaultTestLoader.loadTestsFromNames` with the default Django
connection's `ensure_connection` patched to raise before any DB access.

Observed results in this run: the first 38 checks passed; a broader 119-check
run had one legacy assertion that still expected missing persistence source.
That assertion was updated to recognize the implemented source while retaining
the unauthenticated-installation HOLD; a separate missing-capability failure
test was added. The final 120-check run passed with zero failures/errors,
4.804 seconds of unittest time and 4.905 seconds of measured check wall time.
`git diff --check`, Python AST parsing, Django checks with `databases=[]`,
and in-memory migration autodetection also passed. No DB connection was opened.

Machine-readable schema SHA-256 remains
`ef2fe7d0e71d644ca978d7a3878f9ced4338212969cb6cdbc34a46550b73c5bc`.
Both editor fixtures retained their original exact bytes and remain untracked;
`.paperclip` and prior recovery-report evidence were untouched.

## Publication and review receipt

The single normal staging attempt failed, exit 128, because Git's worktree
`index.lock` is on a read-only filesystem. No commit or publication was attempted
after that denial; no Git metadata permissions were changed. Exact command:

```text
git add -- docs/RMS-HN-API-1.md docs/RMS-HN-API-1-IMPLEMENTATION.md docs/RMS_HYPOTHESIS_DESIGN_CONTRACT_V1_0.md rms/models.py rms/services.py rms/hypothesis_models.py rms/hypothesis_services.py rms/hypothesis_api.py rms/hypothesis_api_urls.py rms/hypothesis_fixture.py rms/hypothesis_source_identity.py rms/research_context_common.py rms/research_context_services.py rms/management/commands/load_rms_hn_fixture.py rms/migrations/0004_hypothesis_records.py rms/migrations/0005_hypothesis_history_guards.py tests/django_hypothesis_backend_source_tests.py tests/django_research_context_backend_source_tests.py tests/django_hypothesis_backend_runner_guard_tests.py
```

The failure was `Unable to create .../mv-rms/.git/worktrees/MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api/index.lock: Read-only file system`.
All 19 requested product/document paths remain in the assigned worktree for the
separately authorized handoff. The accompanying
`docs/RMS-HN-API-1-source.diff` captures those paths against base HEAD, including
new files and the exact approved contract. Recovery evidence is excluded.

Named reviewer and integration owner: Director of Engineering, Diego Galindo.
Next action: review this source/diff, arrange the permitted commit handoff and
mount the API module in the integrated candidate. Test Engineering then requires
separate authority for its preserving DB checks against that named candidate.
The task final response is the operator-requested durable receipt; the operator
relays review/status through the signed-in UI. No control-plane call was made in
this source implementation run, and no task completion or recorded review status
is claimed here.

New tests prohibit Django connections. They cover request validation and
completeness, independent duration semantics, adapter anonymous/viewer denials,
safe field errors, server-owned metadata, browser-service role checks, canonical
actor-scoped request binding/replay status, context mismatches, exact historical
serialization, endpoint routing, Django model checks and migration-state agreement.

Real persistence, concurrency, SQL syntax/trigger execution, ordinary-role denials,
the fixture, complete Source/Idea database regressions and browser behavior remain
unexecuted. H01-H20 require the integrated named candidate and independent Test
Engineering. Director of Engineering owns review/integration and the next release;
Operations owns separately authorized DB setup/migration execution. No merge,
deployment or independent Risk acceptance is implied by source checks.

## Follow-up receiving run and named source candidate

Receiving run `eedbe575-46e6-4ed5-a203-42cbc4416af3`, October 3, 2026, used
the updated instruction to verify the original API document at
`4a1858f76777aa2f5e172b705b184fb8610237ea:docs/RMS-HN-API-1.md`.
Its 7,584 bytes match the approved input hash
`10f0b286eb290fba60ed4c63e8d2af10f6febd579cd6d7a1899c1dc048bce4c7`.
The full 58,395-byte contract at the pinned `de6b971b` object was read and its
approved hash verified again. The earlier working-copy hash gate is resolved;
the implementation update to API-1 does not replace its original receiving input.

The operator created the source checkpoint
`f633d6faba574603b929d3521b7f46c3990502dd` on the assigned branch. This run
observed that commit and verified its exact 19 changed paths against base
`4a1858f76777aa2f5e172b705b184fb8610237ea`. Before these receipt additions,
every one of those working files matched its committed bytes. The existing
`docs/RMS-HN-API-1-source.diff` reconstructs every candidate file exactly;
diff ordering/header formatting differs from a single Git diff invocation.
Its SHA256 is `57608bc7cae5b33fb8ae8694883e16555688f93dbc07b915562ea069ff455e8a`.
The original machine-readable schema remains byte-for-byte unchanged, with
SHA256 `ef2fe7d0e71d644ca978d7a3878f9ced4338212969cb6cdbc34a46550b73c5bc`.

Focused verification executed with `.venv/bin/python` and `login=false`:

```python
import os, unittest
from unittest.mock import patch
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
from django.db.backends.base.base import BaseDatabaseWrapper
modules = [
    "tests.django_hypothesis_backend_validation_tests",
    "tests.django_hypothesis_backend_source_tests",
    "tests.django_research_context_backend_source_tests",
    "tests.test_source_versions",
    "tests.test_source_manifests",
    "tests.django_hypothesis_backend_preservation_helper_tests",
    "tests.django_hypothesis_backend_runner_guard_tests",
]
with patch.object(BaseDatabaseWrapper, "ensure_connection",
                  side_effect=AssertionError("DB connections forbidden")):
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
```

Observed: **120 tests passed**, zero failures/errors/skips. Unittest time was
4.706 seconds; measured check wall time 5.061 seconds; process CPU time 3.054
seconds; peak RSS 68,612 KiB. Python AST checks, Django DB-free checks and in-memory
migration-state agreement passed; `git diff --check` also passed. No database
connection was allowed. Existing Source/Idea DB-free regressions passed; their
database regressions remain unexecuted.

Both canary files still hash to
`3c5bea7c1d370f88c1b520e1a754ded40c2fb3f1ebe10a8bdfd36e1a7a4d3adb` and
remain untracked. This run changed only this handoff receipt and appended the
resolution to the prior hash-gate receipt; it did not alter product code or the
operator fixtures. These receipt updates are outside the named source checkpoint.
The source checkpoint does not claim a push, merge, deployment, DB migration or
independent H01-H20 verification.

Named review owner: **Diego Galindo, Director of Engineering**. Review the
checkpoint/diff and mount `rms.hypothesis_api_urls` through Director-owned root
URL integration. Test Engineering subsequently needs the integrated candidate
and separate authorization for preserving database checks. These receipt-only
changes do not broaden the verified product source. The final response reports
whether the requested Paperclip review disposition could actually be recorded.

Disposition outcome in this follow-up: both bounded authenticated HTTPS
`PATCH /api/issues/$PAPERCLIP_TASK_ID` requests for `status=in_review` failed
before transmission with `gaierror: [Errno -3] Temporary failure in name
resolution`. Both included `X-Paperclip-Run-Id`; no credentials were exposed.
No further attempts were made after the two consecutive write failures. No
recorded review status or readback is claimed. The supplied issue state is still
`in_progress`; the adapter/runtime final receipt is the sanctioned fallback.
The named review action above remains with Diego, and the operator can relay
this concrete source/checkpoint receipt through the signed-in UI as already
specified by the task. This is a coordination failure, not a new source hash
blocker or evidence of implementation/test acceptance.

## Director corrections received and implemented

The operator's October 3 comment `651f6838-1212-4ad7-a18c-6f28ccce8083`
returned the four Director corrections to Backend run
`008a5ef0-d15e-4ab6-a54d-3ddbf91420cc`. They are implemented in source with
135 focused DB-free checks passing. Current/exact/history classification
readers and exact-Idea discovery are published in API interface 1.1, preserving
record schema version 1.0. Assessments now commit their complete ordered link
set through immutable count/digest columns and deferred guard source.

The current correction/migration/read-contract handoff is
`docs/RMS-HN-API-1-CORRECTIONS-008a5ef0.md`, which distinguishes source checks
from unexecuted SQL and records the initial-migration compatibility limit.
The earlier receipts above remain historical evidence for `f633d6f`; they do
not claim verification of these subsequent changes. Director reviews the
corrected candidate. No network retry, DB execution, merge or deployment is
authorized by or claimed in this correction receipt.
