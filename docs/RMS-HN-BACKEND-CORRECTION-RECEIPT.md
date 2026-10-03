# MAU-145 G02/G03/G04 corrective successor receipt

October 3, 2026. Builder: Backend Engineer, receiving run
`a4641c8b-24e1-4016-b603-71e15d2b8460`, task
`8134410a-0e03-47c1-8dae-dd76e7bbe78a` (MAU-145). Exact successor commit/tree
and path hashes are recorded in the external issue packet, not a self-reference
in this file. This is builder evidence, not independent closure or acceptance.

## Governing instruction and preserved history

Human delegation `506673c1-71c4-4ed4-8962-4451a445bdb0` at October 3,
09:14:56.033 UTC read back on MAU-140. Director corrective handoff revision
`133de3e4-62e1-43a4-bd06-72b95212f575` and independent Test revision
`7a85dfce-e1fa-4ba9-830d-cac95dbe8565` govern this same-task correction. Latest
Risk receipt `34bfa3df-c4c3-4117-a948-17c5a08a40b4` preserves the HIGH hold.
Accepted predecessor source `1a306f24b030da1e3ee2df7d6e439849959ca616`, approval
`29b2a559-56aa-4f4f-8fa1-6c5a3189e20b`, and separately reviewed successor
`1d0abfcf8e3c242a86166cd15db2228b03843f76` stay attributable and unaltered.
No source-only approval is represented as execution or independent acceptance.

Harness checkout was already held; no repeated checkout. Authenticated current
issue is Backend-owned `in_progress`/`changes_requested`, with matching Backend
return assignee. The completed Director stage and actual next native Test stage
are preserved; no policy, participant or decision-history rewrite. Director
`86f5fae2-e9e7-4c89-8f78-157f4d41b572` re-reviews the corrected pinned source;
Test `a61c51d8-fd54-42db-927c-106e82cde751` retains the actual native stage and
MAU-144 independent command-review path. Review approval is still required.

## Actual receiving workspace and minimal startup

- Injected project workspace `8258fcbb-78e0-44f2-bbf2-59e619b24920` and API task
  execution workspace `749e45e0-42a8-4bb7-a3b8-cb93c3fa220f` match the preserved
  MAU-142 worktree/cwd. `environment_id=c3931944-3432-4b78-ad1d-ff7e39cc78c0`
  remains the approved manifest pin, not authenticated installed DB evidence.
- Run uid 1000; no root/sudo or host changes. Initial branch
  `MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api`, HEAD
  `1d0abfcf8e3c242a86166cd15db2228b03843f76`, tree
  `902ceb1880382e52f58f4c92f28699cd4727d819`; dirty work none. No branch switch,
  rename/repoint, unrelated source edit, reset or cleanup. Remote
  `https://github.com/dieg0andres/mv-rms.git`; locally observed fetched
  `origin/master=bd0e6b82634349ac2cbb75e91989e37dbb925014`, no new fetch.
- Approved source `de6b971b8b1ef8b5ab6d230641aaec0daeb7e374` contract bytes
  rechecked via Git: SHA-256
  `f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9`.
  Full unchanged contract/API receipt reused, not rewritten. Schema, validator,
  API and dependency lock remain unchanged. No migration/model/service,
  Frontend, URL routing or runtime settings changes.
- Existing toolchain reused at the absolute project `toolchains/rms` path;
  provisioner SHA-256
  `fb0bc792212cccbde8f73556b5b17a11678bc741e200627382fd8c4fab341285` matches.
  No provision/install/bootstrap command. Minimal DB-free isolated import check:
  Python 3.13.15 / Django 5.2.17 / DRF 3.18.1 / psycopg 3.3.6, exit 0.
  No DB environment or settings sourced; imports establish dependencies only.
- Namespace sandbox initially failed before command execution, exit 1.
  Approved per-command escalation reused uid 1000 and native Codex apply_patch;
  no namespace/sysctl policy, permissions or access changed.

## Correction contract and verification

Revision 1.3 of `docs/RMS-HN-BACKEND-RUNNER.md` and the manifest defines:

- G02: separately reviewed frozen canonical effect plan/reference/digest bound
  to actual candidate, manifest, run, fixture IDs and independent physical
  mappings. Compare final observations against it, not observed additions.
  Missing/unreviewed/mismatched plans, extra rows/FKs/associations/projections,
  original/history/account/sequence changes and record overrun fail closed.
- G03: one supervision deadline, shared overlap bound and bounded cancellation
  of exact reviewed sessions; explicit outstanding callbacks and unknown
  session identities. No executor context join or automatic reservation release.
  Daemon threads bound observation only; actual driver/server stop, containment
  and reconciliation remain unavailable/HOLD, not simulated acceptance.
- G04: full restricted baseline inventory reference/digest acknowledgement and
  independent verification before fixture writes; bounded primary/fallback
  handoff preserves primary, cancellation and sink failures with phase,
  sessions, retained-or-unknown effects and reconciliation refs. Missing
  acknowledgements remain not_acknowledged; local exception evidence is NOT
  durable delivery or crash-recovery proof.

Actual focused DB-free checks, all builder-attributed:

| Command / stage | Result | Observed resources |
| --- | --- | --- |
| minimal pinned isolated dependency import | exit 0, versions above | not separately timed |
| helper module before additional negatives | 15/15, exit 0; 0.281 test seconds | shell 0.538 s elapsed / 0.212 user / 0.144 system |
| existing guard/comparison module | 32/32, exit 0; 2.736 test seconds | shell 3.023 s elapsed / 1.610 user / 1.494 system |
| final combined helper + guard modules | 49/49 (17 helpers + 32 guards), exit 0; 3.215 test seconds | shell 3.514 s elapsed / 1.701 user / 1.558 system |
| git diff --check and control-character scan | clean / none | not separately timed |

No failing test attempt. No full Django suite or startup loop. Three blocked,
delayed or ineffective-cancellation checks run only in isolated Python child
processes under hard external three-second deadlines. No indefinitely blocked
worker runs in the shared workspace process. CPU/elapsed above are observed;
peak memory, DB/server resources and paid cost were not measured. No new
resource, installation, credential binding, service or spending operation.

Reproduction uses the existing pinned toolchain:

```bash
BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'python3 -B -m unittest tests.django_hypothesis_backend_preservation_helper_tests tests.django_hypothesis_backend_runner_guard_tests -v'
git diff --check
```

The tests exercise only pure helpers, invented callbacks and local source
comparison/AST assertions. No runner/harness entrypoint, SQL helper, DB/session
transport, fixture/shared-service writer, migration, browser or integration
invocation. Results are not preservation/permission/concurrency experiments,
independent G01-G04 retests, H/P passes or research credit. Proposed exact
preflight/run commands remain revision 1.2 commands, NOT INVOKED/NOT ADOPTABLE.

## Limits, handoff and rollback

Operations MAU-141 owns actual target reconciliation (`rms_synthetic` proposal
versus existing staging resources), schema/runtime/lock/physical mappings,
ordinary-role/editor/viewer bindings, restricted baseline/primary/fallback sinks,
server stop/resource/containment capability and coordinated session evidence.
Nothing missing is invented, installed or authorized by these helper results.
Director coordinates one concrete execution proposal on blocked MAU-140 after
corrected source review and independent Test adoption; no new task or blanket
readiness acknowledgement is requested. Source-only rollback is decline/revert
under Director review; no DB rollback, cleanup, merge or deployment occurs.

All G01-G04 findings stay open until attributed independent review/retest.
H01-H20/P01-P06 NOT RUN; Test INCONCLUSIVE/NOT ADOPTABLE; Risk INCONCLUSIVE /
NOT ACCEPTED (HIGH); 34 Stage 1 cases, separately restricted OPEN incident and
all existing research/release holds remain unchanged. No self-acceptance.
