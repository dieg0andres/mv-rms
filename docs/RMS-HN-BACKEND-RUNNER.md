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
   negative probes, rolling back even unexpected success/error. Successful
   forbidden DML is FAIL despite rollback; unchanged rows are not denial proof.
   It must record
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

## Director-requested preservation packet revision 1.1

This append-only specification supersedes the incomplete 1.0 packet at candidate
`a324f60173b9d7c259fc4f858dfb2831ada66e02`. It does not supersede the adopted
RMS-HN-API-1 / 1.0 schema, API signatures or pure validation. All P01–P06 and
H01–H20 execution remains NOT RUN. The following are reviewable **proposals**,
not authenticated observations, installed migrations or runnable fixtures.
The manifest carries their machine-readable inventories. Operations on MAU-141
and independent Test on MAU-144 must inspect the exact candidate before any later
adoption; their review alone cannot release DB execution.

### P01 Complete effect and nontransactional accounting

Each manifest `effect_inventory` entry names an owner, bounded action, preservation
accounting, HOLD condition and FAIL rule. Inventory covers transitive imports;
test setup/teardown/context managers/finalizers/atexit; app-ready and pre/post
init/save/delete/m2m signals; on-commit, deferred/background and error/rollback
callbacks; migration RunSQL/RunPython and pre/post-migrate; fixture loaders/save
signals; ORM bulk/direct operations; defaults/generated columns/identity/serial,
trigger functions and direct/indirect SQL; cache/session invalidation; local files,
logs and evidence bytes/watermarks; aliases, routers, pools and reconnections;
resources, locks, failures and interruptions. Every unresolved/deferred or untested
path stays HOLD, not implicitly harmless. No worker or connector is proposed.

Current imports read only the pinned local runner/manifest/validator/schema and
procedure bytes and use stdlib. There is no Django initialization or execution
transport. DB-free checks use `-B` to avoid bytecode writes. Current effect allowance
does not authorize future test lifecycle, callbacks, DB/filesystem/cache writes.
Future restricted durable session/failure receipts require an already authorized
append-only sink, limits and rights; that sink is unknown/HOLD, not fabricated.

Sequence review covers every existing sequence and every implicit or explicit
nextval/setval path, including rejected, conflicting and rolled-back INSERTs.
The proposed UUID-only additions must avoid all such paths. Any unknown dependency
is HOLD; any unexpected advance/change is FAIL and stops the procedure. Retain
the observed changed value and discrepancy; never reset a sequence. Transaction
rollback is necessary for negative probes but cannot prove complete noninterference,
repair sequence/cache/filesystem effects or restore independent evidence custody.

### P02 Exact identity and indirect routing guards

The exact resubmission commit plus each changed-file SHA-256 is published in the
MAU-145 receipt/work product. Resolve every runner/manifest/procedure/test path at
that one immutable candidate; keep schema/signature/validator pins at their unchanged
hashes. The manifest itself cannot embed its own final hash/commit: these are
external in the verified receiving receipt, not guessed or circular placeholders.
`source_identity` pins the pure command, paths, superseded candidate and existing
requirements hash. `runtime_identity` metadata must match local proposal ID/revision
and runner/manifest/procedure hashes; local matches never authenticate an adoption.

Exact permitted focused command from the existing approved toolchain:

```bash
BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'python3 -B -m unittest tests.django_hypothesis_backend_runner_guard_tests -v'
```

The execution command and installed settings/binding are **null/absent, HOLD**.
Previously reported `rms_project/hypothesis_source_settings.py` remains absent;
this assignment neither creates it nor pretends it is installed. No runner command
exists, even for testing rejection. Current allowed alias/router/connection/setup/
teardown/callback lists are empty. A default Django runner, management command,
keepdb cleanup, signal/import hook, guessed settings, secondary alias/router or
changed target/environment/binding is rejected by the pure metadata guards.

Before any later mutation, a separately adopted executable implementation must
pin its exact command, runner/settings/import graph and all effective connections,
secure target references and ordinary-role identities. Validate each primary,
secondary, pooled or reconnected session before use; a reviewed initial connection
cannot authorize indirect routing. Unknown/stale/changed pins stop execution.
No connection or installed binding is discovered by these pure checks.

Malformed supplied manifests, targets, required receipts, object policies,
prohibition lists and assessment/authority time metadata produce owned HOLD findings,
not unstructured indexing/get/set/time exceptions. Assessment time must be aware;
authority expiry must be a valid aware ISO time later than assessment time. The
report remains HOLD with DB access false even for structurally plausible metadata.

### P03 Complete immutable/projection denial matrix

Apply both UPDATE and DELETE denial cases to every row/version/association below.
Logical names describe the adopted contract, not newly installed table names:

| Scope | Immutable contents and endpoint/version records |
| --- | --- |
| Existing preserved records | Source original identity, SourceVersion, SourceManifest, Idea original identity, IdeaVersion, IdeaContribution, IdempotencyRecord canonical request/result bytes |
| New entities | Hypothesis, ResearchFamily, Investigation, PriorResearchAssessment original identities and every immutable version/common envelope |
| New associations | IdeaFamily, InvestigationFamily, PriorResearchInvestigation (including case-to-assessment binding), HypothesisInvestigation, IdeaHypothesis, AssessmentRecord: each logical identity/envelope, exact endpoint versions, rationale and correction history |
| Assessment references | AssessmentRecord links to Source/Idea/family/case versions and labeled external-document references; no fabricated unavailable entity |
| Corrections and impacts | CorrectionImpact identity and immutable impact versions, supersession/correction/changed-field audit facts, direct Idea and transitive Source→Idea→Hypothesis impact links, and each new writer idempotency result |

Only specifically mapped server-derived latest-version pointer columns and authorized
display/completeness/upstream-notice projections may update. Original identity,
audit/classification/state/digest, relationship endpoints and history are not
projections; permissions must not grant blanket row UPDATE. Effective ordinary-role
privileges and exact column/trigger/table mappings remain unknown and HOLD.
No ownership/superuser substitute, new accounts, role creation or grants.

For each introduced/preserved type, later Test records actual ordinary application-role
identity and rejected DML with SQLSTATE/statement outcome and complete no-partial-write
accounting. A successful forbidden UPDATE/DELETE is **FAIL even if the probe rolls
back**; final row equality alone cannot prove denial. Browser/API editor overwrite/
delete/metadata-forgery, viewer writes and anonymous reads/writes are separate
unexecuted subcases. Authorized viewer history/read and permitted projection updates
must also be tested without allowing restricted metadata leakage. Each unmapped
type/channel/case is HOLD/NOT RUN, not covered by a sampled representative.

### P04 Additive inventory, preservation and compatibility

There are no new migration/model/fixture-loader files in this candidate. Future
schema inventory consists of the four entity identity/version pairs, all six
adopted association kinds and exact endpoints, CorrectionImpact versions and path
links, explicit immutable protections/constraints and separately mapped projections.
Reuse existing Source/Idea/idempotency/auth mechanisms, not competing tables/ledgers.
Exact physical mapping, DDL, dependencies, default/generated/trigger behavior,
additive migration hooks and installed-schema/old-app compatibility are unknown/HOLD.

Before a separately authorized migration/fixture, Operations must inventory **all**
original logical IDs, rows, versions, association endpoints/envelopes, correction/
impact/history/idempotency bytes, original accounts/effective privileges/roles,
all sequences, manifests and evidence bytes/digests/rights/sealing state, and DB/
evidence watermarks, preserving existing application/database/volume. Authorized
before/after restricted inventories compare exact per-record digests/endpoints and
the complete addition set; counts or sampled sentinels do not close H18. Do not
publish original/restricted evidence or baseline data in Git/logs.

Permitted future additions are only explicitly selected run-qualified invented
Source/Idea/context/Hypothesis rows, immutable versions/associations/impact/audit
facts, new idempotency results and bounded retained receipts needed for P06.
The 100-record limit includes all expanded relational/audit additions, not merely
four top-level entities. Use a later authorized run UUID namespace and canonical
fixture digest. Exact fixture replay yields the same IDs/bytes with zero additional
research rows; changed payload under the same key conflicts. Never overwrite an
existing fixture, auto-create empty parents, backfill prior records or clean up.

Migration failure or an unknown partial state stops all further mutations. Operations
records the exact applied/failed boundary, reconciles complete before/after plus
retained committed additions and supplies a reviewed recovery plan before any retry.
No migration recovery is executed now. Future old-app rollback must leave additions
in place and demonstrate Source/Idea/auth/API/browser and original app/database/volume
compatibility, including new constraints/hooks; absent demonstration stays HOLD.
Destructive down-migrations or deleting fixtures are not a rollback plan.

### P05 Bounded stop, cancellation and interrupted handoff

Proposed maxima: one reserved slot, two owned sessions, 300 seconds total/slot,
60 CPU seconds, 512 MiB memory, 1 MiB sanitized receipt bytes, 100 total appended
records, 5-second statement timeout, 500-ms lock wait and 10-second transaction.
These are proposed review limits, not allocated capacity, authenticated measurements
or a promise. Actual capacity, enforceable stop transport and durable receipt sink
are unknown/HOLD. The reserved A/B pair is the only coordinated overlap; all other
target use must be excluded or explicitly reconciled, never terminated by this runner.

Stop dispatch on expiry/revocation/lost slot, changed target/role/command/settings,
pause/cancel/interruption, disappeared session, time/resource/lock limit, any unknown
effect, forbidden DML success or preservation mismatch. A later reviewed transport
may cancel only the owned pair and roll back only their open transactions. Retain
every committed addition and original, including failed/losing request inputs.
No unrelated session termination, reset/cleanup or automatic retry-until-green.

Durable restricted append-only failure receipts must retain run/candidate/proposal,
phase, request/key/payload digest, owned session/transaction IDs, observed outcome,
commit/rollback uncertainty, stop/error/timing/limit and retained-addition references,
without credentials/restricted research contents. An abrupt kill may leave an
outcome unknown; missing durable evidence is HOLD, never presumed rollback/success.
Operations reconciles owned sessions/transactions, full baseline/additions and DB/
evidence watermarks and records the explicit reservation disposition/handoff before
any subsequent invocation. Director coordinates the separate release; no slot is
reserved/released here and no interruption is claimed observed.

### P06 Deterministic durable overlapping-session proposal

The manifest specifies exact request/key/version relationships using illustrative
`{run:name}` UUIDv5 placeholders, not live bindings/records. Resolve them only under
a later authorized run and installed schema. Preserve existing v1 Source/Idea and
truthful invented family/manual assessment/proposed case with explicit compatible
IdeaFamily context before the scenario; every required addition remains retained.

1. Sessions A/B use the same authorized editor but distinct actually bound ordinary
   application-role connections. Both enter shared POST create with the identical
   manifest payload and key `{run}:P06:create`. A/B barrier proves live separate
   transactions; A claims the key, B attempts before A commits, then A commits.
   Retain both session/transaction IDs and start/barrier/claim/wait/commit times.
2. Exactly one Hypothesis/v1 and its atomic associations/idempotency result commit.
   B returns the same original 201/status/body/identity, and both sessions separately
   observe that committed result. Changed title with the same actor/method/route/key
   gives 409 idempotency_conflict, no overwrite/version/addition; keep losing input.
3. Both corrections target that original ID, expected version 1, exact same origin/
   context bindings, complete fields with explicit nulls, and nonblank distinct reasons.
   A uses key `{run}:P06:correct:A`, title Invented correction A; B uses distinct key
   `{run}:P06:correct:B`, title Invented correction B. Barrier captures both live
   expected-v1 transactions and B attempting while A holds the reviewed version lock.
   A commits v2; B yields 409 stale_version without a research row. Both then observe
   durable v2 and unchanged v1/endpoints, retaining B input and both error/commit receipts.
4. New key `{run}:P06:nochange` submits the v2 full snapshot and expected version 2
   with reason: 200 no-change, no v3; retain its new idempotency receipt. Record complete
   before/after outcome/addition inventory and stop on discrepancy or lock budget.

Deterministic A-first coordination does not mean serial execution: independent
receipts must prove B attempted before A commit and actual committed cross-session
visibility. Mocks, rollback-only observations, a repeated session, serial calls or
retry-until-green cannot close P06/H10/H11. Failure/unknown outcome uses P05; all
committed facts stay. Real browser double submission and losing form/context-input
preservation require separate later independent observations and remain NOT RUN.

Migration/recovery impact: none in this source-only change. Rollback means decline
or revert the reviewed source through normal Director integration; no DB rollback,
reset, cleanup or existing-work removal is needed. Actual later additive migrations
and failure/recovery procedures remain separately reviewed, unexecuted work.
Independent Test INCONCLUSIVE, Risk INCONCLUSIVE / NOT ACCEPTED (HIGH), H01–H20
unexecuted, 34 unexecuted Stage 1 cases and the restricted OPEN incident stay unchanged.

## October 3 executable-test source successor — revision 1.2

This appendix supersedes only the inert-source stopping point above. Preserve the
accepted predecessor `1a306f24b030da1e3ee2df7d6e439849959ca616`, native APPROVED
decision `29b2a559-56aa-4f4f-8fa1-6c5a3189e20b`, packet
`392d302d-1dc4-46cc-8c48-21bc14d7ca3d` and addendum
`ae2ceaba-2bc5-4565-bd51-0a5fe0f527a5`. Human delegation MAU-140 comment
`506673c1-71c4-4ed4-8962-4451a445bdb0`, and continuation revision
`7484c1e9-e359-4b38-8286-312ab9ec9635`, authorize source and focused DB-free tests,
not harness invocation or database access. No original finding is independently
closed by this successor. Target remains the historical proposal, not a live
binding: Operations MAU-141 must reconcile `rms_synthetic` with instructed reuse
of `mv-rms-staging` / `mv-rms-staging-db-1`, existing volume and private route.

### P02 implemented comparisons and trusted boundary

`rms/hypothesis_source_identity.py` observes Git HEAD/tree, dirty tracked source,
actual allowlisted executable/validator/schema/model/service/migration bytes and
actual `requirements.lock` bytes/length. Git commands are fixed local read-only
`rev-parse` and `status` operations with a five-second timeout; no fetch or DB
probe is part of assessment. Missing local evidence produces an owned HOLD.

External receipt object shapes (no credentials or research contents):

- `runtime_identity`: independent reviewed `candidate_commit`, observed installed
  `runtime_candidate_commit`, `candidate_tree`, complete `file_sha256` map from
  the observer, proposal ID/revision and the existing exact lifecycle fields.
  Both commits must equal actual local HEAD, and all executable byte hashes must
  equal actual files. A matching manifest/revision alone cannot mask a stale
  non-null candidate. Dirty tracked source stays HOLD.
- `schema`: independently observed `installed=true`, `candidate_commit`,
  `schema_signature`, `required_schema` descriptor, exact `migration_sha256`,
  API `schema_sha256` and `migration_versions`. The descriptor contains actual
  API, migration, model/service hashes and required additive model/service names;
  its signature is canonical sorted compact JSON SHA-256. Installed migration
  hashes and descriptor/signature must match actual source. A matching API JSON
  hash is not proof that additive tables or enforcement exist. Missing required
  symbols separately reports `candidate_additive_schema_unavailable`.
- `dependency`: independently approved `approved_lock_sha256`, independently
  observed `runtime_lock_sha256`, exact `candidate_commit`, `requirements_bytes`.
  Each digest and byte count is compared to actual candidate lock bytes; a stale
  static manifest pair cannot pass. Null/nonhex/non-object/divergent evidence
  gets distinct missing/invalid/mismatch findings. The manifest's dependency
  pin is also checked against actual bytes.

These inputs are **claims**, including `synthetic=false`/evidence references.
Caller-provided text, local Git identity, synthetic matching examples and checksum
equality do not authenticate a deployed target, receipt signer, reviewer, rights
or current execution authority. Assessment always yields HOLD/DB-access-false in
this source-only candidate. There is no secret binding, installed-target reader,
authenticated authority verifier or adopted execution adapter here. Do not turn
any invented test dictionary into dispatch. No `PASS` is emitted for P02/H cases.

### Inspectable executable portions and phases

`rms/hypothesis_preserving_harness.py` supplies actual assertion and orchestration
source, rather than descriptive HOLD lists alone:

1. Preflight checks source stability, exact release scope/candidate/manifest/run,
   effective ordinary target binding, capacity/limits and durable receipt sink
   before transport use. The entry point and the harness both refuse current
   source-only assessment. A later execution-capable candidate/manifest, exact
   independent review, authenticated verifier and transport binding are required;
   there is no CLI switch or metadata flag to bypass this.
2. A run UUID determines invented fixture identities through UUIDv5; names and
   prefixes are in `fixture_ids`. These are proposed server-side sequence-free
   fixture-factory identities, **not** client-writable API metadata. A reviewed
   deterministic factory does not exist now. No fixture loader is used or called.
   Source/Idea, family, truthful manual assessment, proposed case and explicit
   Idea-family context are required before the Hypothesis scenario.
3. `snapshot_tables` executes full authorized mapped-row SELECT/hash accounting
   with an explicit row-capacity refusal, not counts/sampling. Original rows,
   history, associations, FK inventories, accounts, roles, sequences, volume,
   private route and evidence watermarks must remain identical; only exact
   inventoried append-only additions and reviewed derived projections may differ.
   SQL identifiers are restricted to reviewed simple identifiers. Actual physical
   mappings, authorized baseline capacity and external volume/route evidence are
   unavailable; no names, target credentials or evidence contents are invented.
4. `probe_immutable_row` attempts real UPDATE and DELETE in an owned savepoint.
   Only actual `23000` immutable-trigger or `42501` permission rejection counts
   as the proposed expected outcome. Missing rows, unrelated FK/SQL errors or
   successful forbidden statements fail, even after savepoint rollback. All
   immutable row kinds must be mapped, including original identity columns and
   introduced associations; no owner/superuser test or final checksum substitutes.
5. `coordinated_requests` uses two independently bound physical sessions and
   separate transactions. A's before-commit hook requires server-observed B
   blocking on **this** transaction before A commits. Distinct backend/transaction
   IDs, timing, committed outcomes and cross-session visibility are asserted.
   Waiting/blocked hooks and cancellation must be implemented by an independently
   reviewed adapter; a repeated connection, serialized mock or local event alone
   cannot satisfy the assertion. Thread/session deadlines do not prove host CPU/
   memory enforcement; the bound adapter must provide those enforceable limits.
6. Shared-service scenarios assert exact create replay bytes/status, changed-key
   409 with no research additions, A-v2/B-stale correction with losing input
   retained in restricted receipts, no-change 200/no-v3, viewer write denial,
   exact v1/v2 history, unchanged original endpoints/digest, draft states, and
   exact FK/association/addition accounting. Failure cancels only the owned pair,
   retains every committed addition and records FAIL/unknown; never cleanup/retry.

Current concrete capabilities still absent: additive models/migrations and shared
Hypothesis/context writers (MAU-142 remains blocked), installed ordinary-role and
editor/viewer bindings, sequence-free fixtures (existing identity/auth paths may
consume sequences), full mapping/projection/trigger/FK inventories, two-session
transaction hooks/server lock observations, authenticated live authority/reviews,
enforceable resource/cancel transport and durable restricted receipt destination.
Baseline/account/volume/private-route and per-session bindings come from observed
Operations evidence, not this source. Permission and preservation probes and
H14/H18 remain NOT RUN; no migration behavior is claimed tested. No new service,
role, privilege, access, schema migration or target default is proposed.

### Exact command proposal — not invoked or adopted

After independently pinning the successor, Operations supplies the existing tool
root and an approved external receipt-file path, without changing settings or
binding secrets. Proposed commands, from the unchanged receiving branch:

```bash
BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'python3 -B -m rms.hypothesis_preserving_runner --phase preflight --receipts "$RMS_HN_REVIEWED_RECEIPTS"'
BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'python3 -B -m rms.hypothesis_preserving_runner --phase run --receipts "$RMS_HN_REVIEWED_RECEIPTS"'
```

Both currently refuse with exit 2 before DB/fixture transport. The receipt path
variable is a proposed input, not an observed installed binding. This assignment
invokes neither command nor `PreservingRunner.run`. No default Django runner,
`--keepdb`, provisioner loop, migration, `loaddata`, reset, create/drop, flush,
cleanup, role change or browser/API integration is embedded in the commands.
Independent Test MAU-144 reviews these exact command bytes and executable source
after native Director review; MAU-140 owns any subsequent concrete execution
proposal using Operations prerequisites. This is not an execution-adoption packet.

Expected later effects are explicitly bounded to the invented fixture bundle,
one Hypothesis with two immutable versions and versioned associations, original
create/A-correction/no-change idempotency receipts, allowed latest projections,
and append-only restricted test receipts. Replay, changed-key, stale and viewer
attempts create no research rows. No existing original/account/role/sequence,
evidence watermark, volume or private route changes are allowed. At most 100
appended records; exact physical counts and full schema are unavailable and must
be independently reviewed rather than fabricated. An unexpected effect, forbidden
DML success or unknown commit stops the invocation and remains independently open.

### Defect and requirements map

| Item | Executable source / builder negatives | Unexecuted or missing capability |
| --- | --- | --- |
| P02-CAND runtime | actual HEAD/tree/files vs both independent candidate claims; stale/non-object/dirty diagnostics | installed-target authentication, independent SE-HN-G01 retest |
| P02-CAND schema | actual migration/model/service/API descriptor + signature vs installed evidence; mismatch diagnostics | additive source/schema absent, no migration/schema inspection |
| P02-DEP | actual lock bytes/length vs approved and runtime lock evidence; malformed/divergent negatives | authenticated runtime evidence, independent retest |
| SE-HN-G01 original failure shapes | missing/non-object manifests/receipts; null/invalid targets and fields preserved in focused guard tests | original MEDIUM/open finding not closed by builder results |
| P01/P03/P04, H08/H13/H14/H18 | full snapshot/account/sequence/FK/association assertions; real denial-probe source | actual target, physical mapping, rights, migration/recovery and external preservation proof unavailable |
| P05 | bounded checkpoints, exact owned-pair cancellation/retention and receipt calls | enforceable resources/cancel/receipt sink and interrupted-run observations unavailable |
| P06, H10/H11 | two-session overlap and replay/stale/no-change assertions | committed real separate-session evidence and browser losing-input proof unavailable |
| H02/H08/H12/H19/H20 portions | exact context/history endpoints, draft state and viewer-denial assertions | installed shared services, actual permission principals and full context corrections unavailable |
| H01/H03–H07/H09/H12 remaining/H15–H17/H18 release | frozen validation/schema retained; no integration claims | browser/navigation/accessibility, full fields, impacts, metadata-forgery/anonymous channels, regressions, staging/rollback NOT RUN |

Builder guard results are pure invented comparisons; they are not independent
Test retests, observed P01–P06/H01–H20 passes, preservation certification or Risk
acceptance. Review may reject this executable candidate/command without changing
the earlier APPROVED source-only decision. Repository rollback is decline/revert
through Director review only; no database rollback/reset or cleanup is involved.

## Revision 1.3 — G02/G03/G04 corrective source contract

October 3, 2026. This appendix supersedes revision 1.2 implementation descriptions
for effect expectations, supervision and interrupted evidence; it does not erase
that candidate, its tests or either attributable Director source decision.
Independent findings remain open pending review/retest. All commands above remain
proposals, not invoked or adopted. The target mismatch remains unresolved; no
retarget, actual binding, settings, ordinary role, principal or sink is invented.

### G02: fixed independent pre-write effect plan

`effect_plan` is now a required receipt. Its `reference`, `review_ref`, accepted
review status and canonical JSON SHA-256 bind the complete `plan` before writes.
The plan binding contains actual executable candidate identity, manifest digest,
run ID, deterministic fixture IDs and independently supplied schema evidence
`physical_mappings_sha256`. The authenticated installed verifier must validate
both actual mappings and the separate review/reference/digest/binding. Pure
metadata validation is not authority or installed-schema proof.

The plan contains exact `additions.rows`, `additions.associations`,
`additions.foreign_keys`, final allowed `projections`, and a positive integer
`record_limit` no greater than 100. Rows must include every physical append,
including history, impact and idempotency records; physical mapping/values remain
unavailable, not guessed. Freeze canonical bytes before mutation; decoding
returns a fresh object. The final independently observed snapshot is compared to
this frozen plan, never to `actual_service_effect_inventory` expectations. Extra
Y beyond planned X, FK/association effects, projection drift, missing mappings,
unreviewed/mismatched plans and budget overruns fail. Original rows/relationship
endpoints/history, accounts, roles, sequences, volume/private route and evidence
watermarks remain unchanged. Missing full baseline/projection inventory fails.

### G03: bounded supervision is not stopped-session proof

`BoundedSupervisor` tracks named owned callbacks, the two externally reviewed
session references and observed backend/transaction identities. One monotonic
run deadline reserves two seconds of the existing 300-second budget for cleanup
handoff. Both overlap futures share one deadline of at most ten seconds, not two
fresh ten-second waits. Daemon helper threads avoid implicit executor-context
joins. Checkpoints refuse dispatch after stop. Every blocking external call is
supervised, including authority/target/sink checks and the two overlap workers.

On failure, stop new dispatch and bound cancellation of the exact owned session
references, primary receipt sink and fallback under one two-second deadline,
allocating one third to each. Never submit a callback after its deadline. Report
unfinished work and unknown sessions explicitly. A timeout, callback completion,
nonwaiting shutdown or successful cancellation request does not prove stopped DB
work. Quiescence requires server-verified outcomes for every reviewed session
and zero outstanding callbacks; reservation state always remains
`retain_pending_operations_reconciliation`, even when that evidence exists.

Daemon threads cannot terminate a running driver/server operation. Actual
statement/session stop capabilities, resource enforcement, process containment
and reconciliation remain Operations prerequisites and independent-adoption
gates. The source neither releases a reservation nor claims target reuse safe.
Unresponsive-worker tests exist only in isolated subprocesses under a hard
three-second external timeout; no indefinitely blocked worker is started in the
shared workspace process, and no session/DB transport is invoked by these tests.

### G04: acknowledged baseline and resilient failure evidence

Before the fixture writer, validate the complete inventory and hash canonical
bytes, call `persist_restricted_baseline` with the full inventory/digest/binding,
and require an acknowledgement with `durable=true`, `restricted=true`, nonempty
artifact reference and exact digest/binding. The independent verifier must
authenticate that acknowledgement. Missing, malformed, unavailable or mismatched
acknowledgements stop before writes. Metadata/hash claims do not validate actual
storage, independent custody or crash recovery.

Failure handoff retains the original raised exception and its primary error
identity, separately records cancellation and sink errors, and attempts both
primary append-only and separately restricted fallback sinks within the shared
deadline. The receipt includes phase/run/candidate/fixture/request identities,
baseline and frozen-plan references/digests, owned sessions/outstanding callbacks,
retained-or-unknown additions and the existing Operations reconciliation ref.
No exception messages from external adapters, raw rows or credentials are emitted.
Only an exact restricted durable acknowledgement earns `delivery=acknowledged`.
The acknowledged document digest is explicit; later local state/errors are not
falsely attributed to that earlier durable document. If both sinks fail, the
original exception carries `failure_receipt` with delivery `not_acknowledged`;
this in-memory fallback is NOT durable delivery or process-crash recovery proof.
The already acknowledged restricted baseline remains the recovery prerequisite.

### Reproduce builder helpers only

```bash
BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'python3 -B -m unittest tests.django_hypothesis_backend_preservation_helper_tests tests.django_hypothesis_backend_runner_guard_tests -v'
git diff --check
```

Use the existing pinned toolchain only. These tests exercise pure helpers and
invented callbacks; they never call `PreservingRunner.run`,
`execute_preserving_cases`, either CLI phase, a fixture/service writer, SQL probe
or any DB/session transport. The proposed preflight/run commands remain exactly
as in revision 1.2, both structurally HOLD with no authenticated adapter supplied.

| Finding | Corrective builder evidence | Remaining independent requirement |
| --- | --- | --- |
| G01 MEDIUM/open | original malformed manifest/receipt/null-target and real candidate/schema/lock comparison negatives retained | independent retest NOT RUN |
| G02 MEDIUM/open STATIC | frozen-plan missing/review/digest/binding/mapping/budget and unexpected rows/FKs/associations/projections negatives | independent source review; actual full physical mappings and preservation proof NOT RUN |
| G03 MEDIUM/open STATIC | externally deadline-isolated blocked/delayed/ineffective-cancel helpers; explicit outstanding work and no reservation release | actual stop/containment/session reconciliation and independent retest NOT RUN |
| G04 MEDIUM/open STATIC | missing/mismatched durable-baseline ack and primary+cancellation+both-sink failure/fallback negatives; AST pre-write ordering check | actual restricted baseline/sink durability/recovery and independent retest NOT RUN |

No migration/API/browser contract changes. Decline/revert source through Director
review only; no DB cleanup/rollback is performed. Director re-reviews the exact
successor via this issue while the retained native Test stage remains the actual
resubmission path; MAU-144 retains independent command adoption. MAU-140/144 stay
blocked. H01-H20/P01-P06 NOT RUN, Test INCONCLUSIVE/NOT ADOPTABLE, Risk
INCONCLUSIVE/NOT ACCEPTED (HIGH), 34 Stage 1 cases and the restricted OPEN incident
remain unchanged. No merge, deployment, resources, access, spend or research credit.

## Revision 1.4: G05 independently owned original baseline

The original G04 implementation retained a mutable adapter-returned inventory.
Independent Test revision `d2d0e8e6-0662-4b54-a3b0-66eaa8fc92c0` identified that
a retained persistence callback or reused snapshot could rewrite the final oracle
after its original digest was acknowledged. Those predecessor results and the
changes-requested decision remain preserved; this appendix supersedes only that
source boundary, not any execution restriction or historical review.

Immediately after the original snapshot returns, `freeze_preservation_baseline`
serializes the entire inventory into independently owned canonical immutable bytes,
then validates a decoded detached inventory. The original digest derives from those
same bytes. `persist_restricted_baseline` receives a fresh decoded view; neither
its retained references nor a reused adapter snapshot can alter the frozen bytes.
The final preservation comparison decodes the original frozen bytes again, never
uses the callback's object or re-observes an original baseline. The acknowledgement
must still match the frozen digest/binding and be independently authenticated.
Dishonest durability claims are not repaired or authenticated by local hashing.

Nine additional DB-free builder regressions exercise retained callback mutation,
in-callback mutation, rewritten-byte acknowledgement refusal, reused snapshots,
full-inventory freezing, independent callback views, valid additions, malformed
baselines and AST wiring/order. They do not invoke any harness/runner entrypoint,
DB/session adapter, writer or SQL. Reproduction commands and measured builder
results are in `docs/RMS-HN-BACKEND-G05-RECEIPT.md`.

G05 MEDIUM/open remains pending independent review/retest. G01-G04 now have
independent DB-free helper PASS evidence on the preserved predecessor, not blanket
operational closure. The manifest and historical proposed command/target bindings
are unchanged: this successor does not reinterpret `rms_synthetic`/null pins as
authorization for the observed `rms_staging` target. Commands remain NOT ADOPTABLE;
MAU-141 supplies actual target/schema/ordinary-role/sequence/session/stop/sink proof,
and MAU-140 owns any later concrete execution approval. All H/P, Stage 1, Risk,
restricted-incident and release holds remain unchanged.
