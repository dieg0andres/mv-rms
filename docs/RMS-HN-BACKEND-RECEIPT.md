# MAU-145 Backend source-only receiving receipt

Observed October 3, 2026, run `cab01339-8210-4348-be4d-fb8ae24bb632`.
Reviewer: Director of Engineering. This record covers repository source only,
not integrated acceptance, preserving DB procedure adoption or stage release.

## Authority and actual startup

- Assigned task `8134410a-0e03-47c1-8dae-dd76e7bbe78a` / MAU-145, Backend
  `8026eea0-4dec-4d48-9e2c-fcd93ffad5a8`; harness checkout already held, not repeated.
- Native confirmation `b963d661-71bf-4a56-a591-0a42e31d843a` read back accepted at
  `2026-10-03T07:14:52.621Z` for bounded-source-plan revision
  `69f99154-495a-417f-8bd3-79137c560cdd`; proceed comment
  `92dabe90-a82f-4cea-81ff-b0daad2b3a9c`. Existing DB/integration gates unchanged.
- Injected project workspace `8258fcbb-78e0-44f2-bbf2-59e619b24920`; issue and
  execution-workspace API independently identify the actual approved binding
  `749e45e0-42a8-4bb7-a3b8-cb93c3fa220f`, same realized cwd/branch, metadata environment
  `c3931944-3432-4b78-ad1d-ff7e39cc78c0`. Project ID is
  `6fa1af9a-2486-44f2-b1c5-f152826cd54e`. No binding/default change.
- Remote `https://github.com/dieg0andres/mv-rms.git`, fetched `origin/master`
  `bd0e6b82634349ac2cbb75e91989e37dbb925014` through existing GitHub authentication;
  `git fetch --no-tags origin master` exit 0. Initial branch/HEAD identical to that
  fetched base. Branch retained exactly
  `MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api`.
  Initial and post-startup dirty work: none. No reset/checkout/rename/repoint.
- Accepted contract revision `3982eccc-e180-4ac9-bc70-9c4e16aa47f1`: all 12 sections
  and H01–H20 received from existing immutable source
  `de6b971b8b1ef8b5ab6d230641aaec0daeb7e374`, contract SHA-256
  `f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9`, recipe SHA-256
  `44c10594afef88ea3629c3a464157b35b359b9935960de763c901810af2cfbdb`.
  Director-owned preserved documents are not changed/copied into this patch.
- Existing provisioner SHA-256
  `fb0bc792212cccbde8f73556b5b17a11678bc741e200627382fd8c4fab341285` matches repository
  source; approved toolchain revision `5e4105e0546c976ed86254cbfb10537180d210b7`.
  Lock SHA-256 `d21ca3b1acbcd2bbd60637b3870b5498307084173e070a9f78834dc4b4341ea4`.
  `bash "$TOOLS/provision-workspace.sh" --verify` exit 0; no provisioning loop.
- Pinned imports from this receiving `.venv`: Python 3.13.15, Django 5.2.17,
  DRF 3.18.1, psycopg 3.3.6, exit 0. Actual minimal DB-free startup
  `BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'python3 -B manage.py check'`, exit 0,
  `System check identified no issues (0 silenced).` No DB environment sourced.
- Initial CLI namespace sandbox launch failed before execution with
  `bwrap: No permissions to create a new namespace`. Supported tool approval
  enabled execution; no host-policy change. Empty installed patch probe returned
  1 / no files modified; a subsequent stdin invocation failed because the installed
  entry point requires a UTF-8 argument. The correct installed capability used as
  `apply_patch` with that argument succeeded, no installation/shared configuration.

`TOOLS` remains the approved existing project-local `toolchains/rms` directory.
Actual startup comments are MAU-145 `99da5be1-fdbb-4637-91d8-3cee7eacaf75` and
MAU-140 `3cba045e-5167-494c-8095-a5f372efd3b7`, both response/readback confirmed.
Director owns the single parent startup-readiness table, not this receipt.

## Source identity and verification

First schema/validation commit, published and remote-content verified:
`57ac0a3efeb7e10738e3bfb0e788d5f85edec002`. Final proposal candidate is the later
commit recorded on MAU-145/140; this document cannot embed its own commit hash.

| Source | SHA-256 |
| --- | --- |
| `rms/hypothesis_schema.json` | `ef2fe7d0e71d644ca978d7a3878f9ced4338212969cb6cdbc34a46550b73c5bc` |
| `docs/RMS-HN-API-1.md` | `10f0b286eb290fba60ed4c63e8d2af10f6febd579cd6d7a1899c1dc048bce4c7` |
| `rms/hypothesis_validation.py` | `39ba12a56e0ef7201e7d2b1448de62de0a9b2c181b1625104418ba62c84880e0` |
| `rms/hypothesis_runner_manifest.json` | `bde60463078c9b9fdf20f9ae6f31daaaacd295233fc2c32d2db77c149231b82d` |
| `rms/hypothesis_preserving_runner.py` | `10d9f7738e3a9fd8d0202909d48862039133dc7ced759ae2fb9e3824828cc649` |
| `docs/RMS-HN-BACKEND-RUNNER.md` | `239cd50feeaf141ab5adec637928e7a7bc3009535daf43ca5b169a4283931fe8` |

The schema hash remained unchanged after early publication on MAU-140 comment
`7514e1e9-8b93-48d8-b85b-a450aa8b6359`, which explicitly mentioned Frontend's
actual MAU-146 owner. A posted request is not Frontend consumption/agreement.
Director obtains the exact receipt/adoption; no cross-role agreement is claimed.

First pure validation run: 20/20 PASS, 0.012 seconds, exit 0. Final proportionate
check uses only stdlib unittest, never Django's DB runner or the proposed runner:

```bash
BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'python3 -B -m unittest tests.django_hypothesis_backend_validation_tests tests.django_hypothesis_backend_runner_guard_tests tests.test_source_versions tests.test_source_manifests -v'
git diff --check
```

Observed: 50/50 PASS (20 validation/schema, 10 fail-closed guard, 20 existing pure
Source/version/manifest regressions), suite 0.019 seconds, exit 0. Whitespace check
passed. Bash timing measured wall 0.274 seconds, user CPU 0.167 seconds, system CPU
0.127 seconds. Optional `/usr/bin/time` was absent (exit 127 before tests); existing
Bash timing replaced it without installation. Memory/token/cost measurements are
unavailable, not estimated. No new purchase/service/resource; zero DB writes/access.

Fixtures: invented in-memory UUID namespace `00000000-0000-4000-8000-000000000145`,
invented research descriptions and negative metadata explicitly synthetic. No real
research, empirical execution, connector, preserved research evidence or credential.
Guard acceptance remains **HOLD** for every actual unavailable prerequisite despite
unit tests passing; no runner invocation or live probe occurred.

## Review, limits and rollback

Director reviews schema/request wrappers/signatures, pure semantic validation,
complete/incomplete paths and the intentionally inert runner/manifest. Operations
and independent Test must inspect the exact proposal through existing MAU-141/144
before any later adoption/execution; Director coordinates those receipts. Current
source includes no executable DB transport or persistence services, no migrations,
fixture loader, ORM/model change, route/view/template/frontend test or integration.

Risks: pure shape success cannot authorize references or establish atomicity,
object permissions, immutability, server concurrency/idempotency or research quality.
Guard metadata cannot authenticate authority/evidence. Actual schema/principals,
ordinary application-role proof, sequence noninterference, shared-use coordination
and committed distinct-session evidence remain unavailable. Future execution needs
a separately reviewed implementation/procedure, not a renamed default runner.
Migration/recovery impact is none; decline/revert source through normal Director
integration, with no DB rollback/reset/cleanup or deletion of existing work.

Native review is repository-only. H01–H20 remain unexecuted; Test INCONCLUSIVE,
Risk INCONCLUSIVE / NOT ACCEPTED (HIGH), 34 unexecuted Stage 1 cases and separately
restricted OPEN incident remain unchanged. No merge, deployment, integration,
authority/access expansion or independent acceptance is implied.

## Bounded correction receipt — October 3, 2026

Receiving correction run `dec0c81c-3a3c-4a25-9581-1b28b277f02f`, MAU-145.
Director wake comment `ffaec22a-3d73-43a8-9b52-7b8009650bde` and source-review
revision `9a3f0b14-1bac-4569-b01c-6c5a47a31cc5` change the next action from waiting
to these bounded corrections only. Native checkout response confirms Backend
ownership and this run; the existing Director review stage/return-assignee is retained.
Founder confirmation was read back ACCEPTED against unchanged source-plan revision
`69f99154-495a-417f-8bd3-79137c560cdd`, effective October 3, 07:14:52.621 UTC.

Current injected workspace remains `8258fcbb-78e0-44f2-bbf2-59e619b24920`, existing
cwd/remote/branch exactly as the original receiving receipt. Initial HEAD was
`a324f60173b9d7c259fc4f858dfb2831ada66e02`, working tree clean. No fetch/startup,
provisioner/import verification, workspace/binding change, branch switch or reset
was repeated; the accepted original startup is unchanged evidence, not a claim
that this correction run repeated it. Sandbox namespace launch initially failed
before command execution; supported tool approval allowed bounded commands without
host-policy/service changes. Existing native executable-name `apply_patch` dispatch
used one run-owned scratch alias; no installation or shared configuration change.

Changed scope is exactly runner source, runner manifest, preserving procedure,
this appended receipt and invented pure guard tests. Manifest revision is 1.1.
P01–P06 are now explicit source proposals: effect/alias/lifecycle inventory;
external candidate/file/command identity with absent settings; every immutable
entity/version/association/impact versus permitted projections and success-is-FAIL
denial semantics; full preservation/additive/compatibility inventory with unknowns
HOLD; bounded cancellation/interrupted Operations handoff; deterministic durable
overlapping A/B create/replay/conflict/correction/no-change scenario. No schema,
signature, validator, model, migration, route, frontend or integration source changed.
Actual schema/roles/privileges/routing/capacity/receipt sink remain unavailable/HOLD.

### Correction verification and pins

Exact focused command (existing approved toolchain, invented metadata only):

```bash
TOOLS=/paperclip/instances/default/projects/f6bf0bf4-801d-4dd1-8e60-02a58d2052ef/6fa1af9a-2486-44f2-b1c5-f152826cd54e/toolchains/rms
BASH_ENV="$TOOLS/shell-env.sh" bash -lc 'time python3 -B -m unittest tests.django_hypothesis_backend_runner_guard_tests -v'
git diff --check
```

Observed October 3, 2026, 08:10:46 UTC in this run: **22/22 PASS**, unittest
0.044 seconds, exit 0; Bash wall 0.283 seconds, user CPU 0.173 seconds, system CPU
0.127 seconds. Whitespace check PASS. The command never calls `PreservingRunner.run`;
its unconditional raise and absence of DB imports are inspected via AST only.
Tests include all ten previous guard tests plus twelve new malformed metadata,
time, stale source identity, changed target/binding, indirect lifecycle/import/
settings/alias/router/connection and proposal-shape checks. Owned findings/HOLD and
DB access false are asserted; local hash matches and invented metadata never release
execution. Every actual receipt remains null. Fixed synthetic assessment time is
`2026-10-03T08:00:00+00:00`; invented candidate `1111111111111111111111111111111111111111`
is a negative fixture, not a published commit/binding. Namespace/record examples in
P06 are symbolic invented future inputs, not installed fixtures or live evidence.

| Changed source | SHA-256 |
| --- | --- |
| `rms/hypothesis_preserving_runner.py` | `beeb6a9ce02ffae8c4573c06133d4041ff3319cddfaa38b2604e135ad7db04f3` |
| `rms/hypothesis_runner_manifest.json` | `248d005cc6df06d407ef6c4d1a65a9505d280e33f5f1d2abd58d514410b95e48` |
| `docs/RMS-HN-BACKEND-RUNNER.md` | `c371941d55443e76ebafb0036dcfbf1aa4957896cb164c4850cd8712acc60b76` |
| `tests/django_hypothesis_backend_runner_guard_tests.py` | `3f7f607a8cfacf477a95e7987b0e0fd9a58f6cbd54c888375572ea75bbdb0fe3` |

The final candidate and this receipt own hash are external in the MAU-145
resubmission receipt/work product, avoiding self-referential commit/hash claims.
Rechecked adopted schema/signature/validator hashes exactly match the earlier table.
Preserved contract and recipe Git-object hashes also match the original receipt.
Earlier candidate and 50/50 results remain above, attributed only to earlier run
`cab01339-8210-4348-be4d-fb8ae24bb632`; they were not rerun and are not new evidence.
No full-suite/build, installed settings, DB probe, runner, migration or fixture
execution occurred. Memory/token/cost measurements are unavailable; no incremental
spending/resource/credential/access change. DB access/writes: zero.

Director of Engineering is the same named native repository-only reviewer.
Operations/Test inspect this corrected pinned proposal through existing MAU-141/144
before later adoption/execution; no recipient start or independent acceptance is
claimed. P01–P06/H01–H20 NOT RUN; Test INCONCLUSIVE / NOT ADOPTABLE; Risk
INCONCLUSIVE / NOT ACCEPTED (HIGH); 34 unexecuted Stage 1 cases and separately
restricted OPEN incident unchanged. MAU-142/143/144 and all DB/integration gates
remain unchanged. Rollback is source decline/revert through Director only, with
no database recovery/reset/cleanup. No self-merge, deployment or stage release.
