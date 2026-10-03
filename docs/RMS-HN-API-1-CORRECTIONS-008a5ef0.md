# Director correction handoff — October 3, 2026

Receiving Backend run: `008a5ef0-d15e-4ab6-a54d-3ddbf91420cc`.
Authority: operator relay on [MAU-142](/MAU/issues/MAU-142), comment
`651f6838-1212-4ad7-a18c-6f28ccce8083`, recording Director request-changes.
Base candidate: `f633d6faba574603b929d3521b7f46c3990502dd`.
Branch remains `MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api`.
All four requested source corrections are implemented. Director **Diego Galindo**
reviews the corrected candidate; no completion/independent acceptance is claimed.

## Changes and contracts

1. `rms/hypothesis_services.py` derives `origin_idea_history` from the existing
   `idea-history` URL name, resolving to `/api/v1/ideas/{idea_id}/versions`.
   A regression resolves the serializer's actual emitted link.
2. `rms/hypothesis_api.py` uses DRF's JSON parser with media-type parameters.
   Ordinary and `application/json; charset=utf-8` requests reach the same shared
   service. Malformed/unsupported bodies return safe 400 errors; authentication
   and viewer-write denials precede body parsing and service execution.
3. Shared classification lookup/current/exact/history functions are in
   `rms/research_context_services.py`. `rms/hypothesis_api_urls.py` supplies the
   four GET operations declared in the updated schema. Readers enforce active
   authenticated access and endpoint visibility before serialization. Discovery
   pins an exact Idea version; unavailable/unclassified references use uniform
   404. History is ordered by version. No read adopts a new family classification
   into an existing Hypothesis. The original correction writer remains intact.
4. `rms/hypothesis_assessment_links.py` computes an ordered commitment before
   parent insertion. `PriorResearchAssessmentVersion.link_count/link_digest`
   are immutable scalar columns, included by `append` in the parent row digest.
   The authoritative relationships remain typed FK rows and separately labeled
   external references. `assessment_read` verifies count, contiguous unique
   positions and digest before returning reconstructed content; mismatches fail
   closed as 503 `history_integrity_error`, preserving original history.

The complete ordered commitment hashes UTF-8 lines:
`position:kind:token\n`, starting at position one. Internal tokens are exact
public version IDs. External tokens are the SHA256 of the reference's UTF-8
bytes, avoiding delimiter/Unicode ambiguity. The empty set commits SHA256 of
empty bytes. No authoritative relationship array is stored on the parent.

The machine-readable interface is **1.1**; record/completeness schema version
stays **1.0**. The four GETs, `IdeaFamilyQuery`, `IdeaFamilyRead`, and
`AssociationHistory` are documented in `docs/RMS-HN-API-1.md`. There are 24
declared operations and 21 URL patterns. Existing research fields and write
envelopes are unchanged. Original interface 1.0 remains at
`f633d6f:rms/hypothesis_schema.json`; its SHA256 is
`ef2fe7d0e71d644ca978d7a3878f9ced4338212969cb6cdbc34a46550b73c5bc`.

New schema: `rms/hypothesis_schema.json`, 26,669 bytes, SHA256
`ad9042c79467ecf62adb29bde0781ec2cfd434f25233275adda1a80d59643049`.
Shared API handoff: `docs/RMS-HN-API-1.md`, 12,274 bytes, SHA256
`5c088e797544bbd706d4c24d332adb518c043876126749ee9a340c58bceb0b3d`.
Frontend/Test must use this exact schema/service revision with the corrected
candidate, rather than a parallel model reader. The preserving manifest still
binds the original schema and remains HOLD; changed schema/procedure adoption
requires its existing separate review and authorization.

## Migration and recovery limits

The **unexecuted initial migration sources** `0004_hypothesis_records` and
`0005_hypothesis_history_guards` are corrected before first application. 0004
adds required link count/digest columns and the seal-shape constraint to the new
assessment table; it still makes no changes/backfill to Source/Idea records.
0005 adds deferred constraint triggers on the assessment parent and both link
tables. At transaction commit, they reconstruct the ordered typed union and
verify count, positions and digest, including an empty set. Extra/changed links
must fail; an explicit case correction supplies a new assessment version to
change the set. Every new link INSERT is checked, including a late insertion
using another identity. Existing immutability guards protect commitment columns
and child rows from ordinary UPDATE/DELETE/TRUNCATE.

Deferral permits assembling the initial parent and complete set atomically;
it does not permit committing a mismatched set. Any violation rolls back the
transaction, including inserted identities, links and derived watermarks.
The function uses the repository's existing pgcrypto dependency, adding no
extension, service, grant or worker. SQL syntax/execution and ordinary-role
insert denials have **not** been executed or certified in this run.

Operations must check the authorized target's migration state before a later
installation. If the old 0004/0005 have already been applied, these revised
source files will not be reapplied by Django: stop and arrange a separately
reviewed additive remediation. No blind reapplication or reinterpretation of
old records/digests is authorized. No live history was migrated here. Keep
0005 irreversible, preserve tables/data on application rollback, and retain
Source/Idea impact hooks or freeze those correction writes as already documented.

## Focused verification

Command executed using `.venv/bin/python`, `login=false`, with
`BaseDatabaseWrapper.ensure_connection` patched to raise before loading tests:

```python
import os, unittest
from unittest.mock import patch
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
from django.db.backends.base.base import BaseDatabaseWrapper
modules = [
    "tests.django_hypothesis_backend_validation_tests",
    "tests.django_hypothesis_backend_source_tests",
    "tests.django_research_context_backend_source_tests",
    "tests.django_hypothesis_backend_corrections_tests",
    "tests.test_source_versions",
    "tests.test_source_manifests",
    "tests.django_hypothesis_backend_preservation_helper_tests",
    "tests.django_hypothesis_backend_runner_guard_tests",
]
with patch.object(BaseDatabaseWrapper, "ensure_connection",
                  side_effect=AssertionError("DB connections forbidden")):
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromNames(modules))
raise SystemExit(0 if result.wasSuccessful() else 1)
```

Observed **135 checks passed**, zero failures/errors/skips, 5.005 seconds of
unittest time; wall time 5.392 seconds, CPU 3.268 seconds, peak RSS 69,288 KiB.
The source-observation inventory then gained the new regression module. The
affected runner-guard module was rerun: **33 checks passed**, 4.067 seconds;
these overlap the 135 and are not added to that count. Django checks with
`databases=[]`, in-memory migration-state agreement, Python AST and whitespace
checks passed. No database connection was allowed.

Regressions cover actual emitted history routing; normal/parameterized JSON,
malformed/unsupported bodies and retained viewer/anonymous denials; current,
historical and ordered classification reads, exact-Idea discovery, hidden
endpoints and direct browser-service permissions; empty/mixed ordered assessment
sets, internal/external late-addition refusal, duplicate/gapped positions,
commitment-bound parent digests, v2 link changes and unchanged v1/old case context.
Trigger coverage is structural source inspection, **not executed SQL denial**.

## Review and remaining independent checks

Director reviews the bounded diff and this interface revision. Next integration
action is to mount the existing backend URL module in the Director-owned root
URLConf; Backend did not edit root URLs, views, templates or static files.
Test Engineering receives the integrated named candidate and, only after its
separate authorization, verifies database transactions and role protection.

Outstanding: initial empty/mixed link insertion and deferred checks at commit;
late internal/external inserts with new identities; duplicate positions across
tables; incomplete/mismatched sets; concurrent late inserts; attempted parent
seal updates; explicit case/assessment v2 changes preserving old Hypothesis
context; rollback of denied writes; existing Source/Idea database regressions;
the idempotent fixture; independent H01-H20 and browser observations. No DB
execution, migration/fixture execution, merge, deployment, empirical research or
independent Risk verdict occurred. Passing source checks earn no research credit.

All Director/operator receipts and `.paperclip` were preserved. Both canary files
retain SHA256 `3c5bea7c1d370f88c1b520e1a754ded40c2fb3f1ebe10a8bdfd36e1a7a4d3adb`
and remain untracked. The old review diff was not replaced.
The comment explicitly prohibits repeating failed network/API publication; no
control-plane request was made. The supplied issue status is `in_progress`.
Required handoff disposition is Director review on this same task, relayed
through the supported UI/runtime if it cannot be recorded by the task tools.
The final receipt must not imply a remotely confirmed review transition.

## Local publication outcome

The one normal local staging attempt failed, exit 128, before index creation:
`Unable to create .../mv-rms/.git/worktrees/MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api/index.lock: Read-only file system`.
Exact command:

```text
git add -- docs/RMS-HN-API-1.md docs/RMS-HN-API-1-IMPLEMENTATION.md docs/RMS-HN-API-1-CORRECTIONS-008a5ef0.md rms/hypothesis_api.py rms/hypothesis_api_urls.py rms/hypothesis_models.py rms/hypothesis_schema.json rms/hypothesis_services.py rms/hypothesis_source_identity.py rms/research_context_services.py rms/hypothesis_assessment_links.py rms/migrations/0004_hypothesis_records.py rms/migrations/0005_hypothesis_history_guards.py tests/django_hypothesis_backend_validation_tests.py tests/django_research_context_backend_source_tests.py tests/django_hypothesis_backend_corrections_tests.py
```

No staging retry, commit, permission workaround, network publication or API
request followed. The corrected source remains in the assigned worktree; the
old `f633d6f` commit is the base, not a corrected candidate. Director owns the
separately scoped commit handoff and review of the exact correction files.
The correction diff is `docs/RMS-HN-API-1-corrections-008a5ef0.diff`, against
that base, including all 15 changed product/API/implementation-receipt paths.
This final correction receipt is additional handoff evidence outside the diff.
The previous implementation receipt's uncommitted append is retained in that
diff instead of being discarded. Reviewer/operator receipts, the older source
diff, canaries and `.paperclip` are excluded from staging and the correction diff.

Exact uncommitted correction candidate: base
`f633d6faba574603b929d3521b7f46c3990502dd` plus the **58,370-byte** correction
diff, SHA256 `a44c46ce297645eb4dfc6d215393f43d4fbd50357537c09f09936ba76894dbb2`.
Reconstruction of all 15 files from that base/diff was checked against their
working bytes and passed. The staging index is still empty; HEAD is unchanged.
The contract copy still matches its approved hash. This receipt is the 16th
handoff file and does not participate in the diff's digest.

Requested final disposition for the supported operator/runtime relay:
**Director review**, with Diego Galindo as the existing named reviewer and
integration owner. Record the new correction receipt/candidate on this same
task and start its bounded follow-up review. No remote disposition was attempted
or confirmed in this run, following the explicit no-API-retry instruction.
The last supplied `in_progress` state is not claimed as a recorded review state.
