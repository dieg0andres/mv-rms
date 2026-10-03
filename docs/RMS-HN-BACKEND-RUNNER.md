# RMS-HN preserving runner — proposal only, HOLD

MAU-145 permits repository-only source and pure guards, **not invocation**.
`rms/hypothesis_preserving_runner.py` is deliberately inert: its runner entry
raises HOLD unconditionally. There is no database driver, Django runner, shell
execution, connection, migration, fixture loader or cleanup implementation.
`rms/hypothesis_runner_manifest.json` is the pinned preserving proposal. Every
actual prerequisite receipt is null, every phase HOLD. No credential is included.

The pure `assess_prerequisites` helper checks metadata and returns an immutable
HOLD report with named owners/actions; `db_access_permitted` is always false.
It cannot authenticate a Paperclip decision, attest a DB observation or independently
accept evidence. Invented guard inputs remain unit-test fixtures, not live receipts.
Even plausible supplied metadata cannot release execution from this module.
Default Django runner, schema-owner role, rollback or keepdb are not substitutes
for preservation, H14/H18, committed concurrency or authority.

## Bounded future preserving procedure

1. Director coordinates existing MAU-141/144 owners to inspect this pinned source,
   exact schema/candidate and manifest before any later adoption. No new task,
   service, database, role, access or spending is implied.
2. Operations supplies actually available authorized target/schema/ordinary-role
   and separate editor/viewer bindings by secure reference name. Missing schema
   or principals must remain HOLD, never initialized here. The test DB-owner role
   is specifically not ordinary-role proof. No original account/role changes.
3. Review defaults, triggers and ORM paths for every proposed write. This proposal
   allows no sequence calls; any implicit nextval/setval or unresolved sequence
   effect blocks it. Rollback does not reverse sequence effects. If the existing
   schema cannot support this bounded policy, report the concrete capability and
   one remedy to Director → VP, rather than mutate/reset sequences or emulate PASS.
4. Reserve coordinated single-owner target use with an explicit handoff/release
   boundary. Workspace isolation does not isolate the shared database. A reservation
   is not authority to execute; stale/unknown/revoked/mismatched decisions fail closed.
5. Only a later separately reviewed execution implementation may perform authorized
   negative probes, rolling back even unexpected success/error. It must record
   original-record/account/role and DB/evidence watermarks before/after without
   disclosing contents. Do not invoke this proposal to discover target state.
6. H10/H11 require newly invented bounded, run-qualified records and actual distinct
   sessions with committed visibility and coordinated overlapping requests. Retain
   all committed additions/history. Rollback-only or one-session tests prove neither
   cross-session idempotency nor optimistic concurrency. No fixture cleanup.
7. Independent Test assesses safety/evidence; Director alone adopts a demonstrated
   procedure. If any missing capability requires broader permission, use the existing
   escalation route. This source deliverable cannot clear that decision.

Fixture bounds are proposed maximum 100 invented records with run-qualified UUIDs;
there are **zero writes now**. No create/drop/reset/flush/truncate/cleanup, migration,
fixture execution, owner-role test substitution, role creation/grants, merge or deployment.
Unexpected integrity/noninterference changes stop future execution and preserve originals.

## Reproduce pure checks — NOT runner invocation

```bash
BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'python3 -B -m unittest tests.django_hypothesis_backend_validation_tests tests.django_hypothesis_backend_runner_guard_tests -v'
sha256sum rms/hypothesis_schema.json rms/hypothesis_runner_manifest.json rms/hypothesis_preserving_runner.py
```

These tests import only pure helpers. Negative invented metadata exercises missing
schema/role/principals, expired/revoked/stale authority, sequence effects, shared
use and separate-session requirements. The runner method is inspected as syntax,
never invoked. No H-case execution or real preflight is claimed.

Migration/recovery impact: none in this source-only change. Rollback means decline
or revert the reviewed source through normal Director integration; no DB rollback,
reset, cleanup or existing-work removal is needed. Actual later additive migrations
and failure/recovery procedures remain separately reviewed, unexecuted work.
Independent Test INCONCLUSIVE, Risk INCONCLUSIVE / NOT ACCEPTED (HIGH), H01–H20
unexecuted, 34 unexecuted Stage 1 cases and the restricted OPEN incident stay unchanged.
