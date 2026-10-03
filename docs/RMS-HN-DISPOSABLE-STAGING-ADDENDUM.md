# Disposable staging addendum and executable test path — October 3, 2026

This is the active test/reset procedure for [MAU-140](/MAU/issues/MAU-140).
The [founder decision at18:17:30.162UTC](/MAU/issues/MAU-140#comment-4dc2c3b8-534c-4053-abfc-d22b62f34392)
permits erasing/reseeding development RMS research/test records in the **existing**
`mv-rms-staging` project, `mv-rms-staging-db-1` container, database `rms_staging`.
Preserve users, password hashes, groups, memberships, permissions and login access.
Diego will announce any later requirement to retain research records. This changes
test-data retention; it does not change immutable version/lineage behavior during
ordinary application use, independent H01–H20, code/review evidence or acceptance.

The earlier `RMS-HN-TEST-DEMO-APPROVAL.md`, its source amendment and full research-row
preservation prototypes remain historical unapproved records. Their full-row
hashing, restricted-sink acknowledgement, preservation budget and rollback packet
are **not prerequisites** for this path. Do not execute their obsolete source pins.
The exact original contract, past failures and independent findings remain intact.

## Observed state and actual outstanding decisions

Operator comments [17:41:26UTC](/MAU/issues/MAU-140#comment-c9e56daa-1401-4cdb-ac84-f196d59191c9)
and [17:45:37UTC](/MAU/issues/MAU-140#comment-53672222-181e-4b31-bf17-7bfe0c0d4544)
report an actual read-only inventory: `rms_staging` has RMS migrations0001–0003
only, no Hypothesis table; its sole non-pg SQL role `rms_staging` has superuser,
createdb, createrole, login and bypassrls. It is an existing maintenance identity,
**not an ordinary application identity or an app-denial test result**. App and DB
containers remain running with their September26 start times; this source does not
establish a new runtime observation. The source baseline is published draft
[PR4](https://github.com/dieg0andres/mv-rms/pull/4) at8c58569. The Director's successor
contains the independently reported404 input correction and this reset procedure;
use the exact successor manifest/checkpoint from the handoff receipt, not PR4's
older head. No successor deployment/merge or independent retest is claimed here.

Operations/Codex can review source and the existing authorized test scope now.
Only these concrete release/access actions need Diego's separate recorded decision:

1. Apply additive RMS0004/0005 and serve the **reviewed successor** on the existing
   staging app/DB/private route, using the existing project, volume and credentials.
   Do not run `create-principals.py`, migrate auth backwards, reset users, merge PR4,
   or create a replacement service/database. `migrate rms0005` may append model
   content types/permissions; retain every existing row and membership/permission
   assignment and record those additive schema effects. No existing user acquires
   a new assignment from the update.
2. Provision one ordinary SQL app/test identity `rms_hn_app` with the narrowly listed
   grants in the separately pinned `RMS-HN-ORDINARY-ROLE-PROPOSAL.sql`. This is **new
   security-sensitive role access**, currently unapproved. Operations owns approved
   secret handling and binds the existing app and independent Test to this role.
   No account creation, user/group changes or password in source/output. The SQL
   stops if the role exists or feature guards are absent. A passwordless proposal
   is not a usable authenticated login; do not claim connectivity until observed.

Record approver, exact reviewed commit/tree/manifest, target, role/access scope,
effective window and stop conditions. The founder already authorizes disposable
RMS resets; no further research-retention approval loop is proposed. A reset-only
maintenance command on the current0001–0003 schema needs neither a new SQL role nor
a Hypothesis migration, but cannot demonstrate Hypothesis behavior.

After the recorded staging update decision and the reviewed source is available
in the existing container, the exact additive migration commands under the
existing maintenance binding are:

```sh
docker exec -w /srv/releases/product mv-rms-staging-app-1 \
  /srv/adapter/entrypoint.sh /usr/local/bin/python manage.py migrate rms 0005_hypothesis_history_guards --plan
docker exec -w /srv/releases/product mv-rms-staging-app-1 \
  /srv/adapter/entrypoint.sh /usr/local/bin/python manage.py migrate rms 0005_hypothesis_history_guards --noinput
```

Inspect the plan first: only RMS0004/0005 may be pending. Record migration/guard
readback and existing auth assignments before/after; stop on any unexpected plan,
missing extension capability, auth change or uncertain commit. Do not install an
extension, reverse0005, rotate users or broaden rights to force success. After
an app failure, Operations can restore the prior **app image/configuration** on
the same resources; retain additive schema/guards. Research rows need no backup
as a test prerequisite. Source, account/auth state and existing review evidence
remain protected. The existing operator backup receipt remains historical evidence.

## One repeatable reset/reseed command

Implementation: `rms/management/commands/reset_rms_staging.py` and
`rms/staging_test_reset.py`. Default mode prints an **offline plan**, opens no DB
connection and performs no migration/deployment. `--execute` selects the mutation;
that flag does not establish container identity or grant access/release authority.

Operations executes in the already approved staging container context after source
availability and applicable release authorization. First inspect existing Docker
project/container/network/volume labels against the supplied inventory; do not
create a container, install a helper, discover a new target or broaden access. Use
the existing maintenance binding `RMS_DB_NAME=rms_staging`, `RMS_DB_HOST=db`,
`RMS_DB_PORT=5432`, `RMS_DB_USER=rms_staging`, with its existing secret mount. Existing
app `test_editor` and `founder_viewer` names are recipe names, **not verified receiving
account bindings**; bind the actual existing active editor/viewer and validate group
membership and login locally. Do not create them if absent.

After the reviewed source is present under `/srv/releases/product`, the existing
entrypoint injects mounted secrets without printing them. On the authorized Docker
host, the concrete plan command is:

```sh
docker exec -w /srv/releases/product mv-rms-staging-app-1 \
  /srv/adapter/entrypoint.sh /usr/local/bin/python manage.py reset_rms_staging \
  --project mv-rms-staging --database-container mv-rms-staging-db-1
```

For an authorized targeted reset on either the existing Source/Idea schema or the
full reviewed Hypothesis schema, add `--execute`. For the full Hypothesis demo,
after0004/0005 and source release, append:

```sh
--execute --reseed --actor EXISTING_EDITOR_USERNAME --review-time 2026-10-03T00:00:00Z
```

`EXISTING_EDITOR_USERNAME` is the observed username, not a new account. Bind the
maintenance SQL identity through the existing approved runtime injection if the
app has already switched to the ordinary SQL role; this command rejects an
ordinary maintenance principal. Never reuse that maintenance binding for H14.
No password, private route or other secret appears in argv or the receipt. The
command's root-source/import pin is established by the reviewed release package;
record actual commit/tree/package/app image IDs and mounted source before execution.

Each execution uses **one outer atomic transaction**:

- Verify configured and effective database/login/port, existing maintenance role,
  exact seven-table or nineteen-table RMS schema and corresponding migrations.
  Partial/unknown RMS schema, missing auth tables, unexpected migrations or a
  reference into RMS from any outside table stop before mutation.
- Obtain short bounded table locks in an exclusive maintenance slot. Auth tables
  use SHARE locks to prevent account changes while allowing reads. Take only
  protected auth-state count/hash comparisons inside PostgreSQL; emit no account
  rows/password hashes and take no research-row inventory. No reset overlaps an
  application or Test write. Lock timeout5s, individual statement timeout30s.
- For the full schema, verify all twelve `hn_no_truncate` statement guards match
  reviewed0005. Temporarily disable **only those guards**, leaving every row/version
  guard intact. Execute the explicit nineteen-table `TRUNCATE ... CONTINUE IDENTITY
  RESTRICT`, without CASCADE or sequence restart. The old seven-table schema uses
  its explicit subset. No auth/session/migration table is cleared.
- Restore and check those twelve guards **before** reseeding through the existing
  idempotent `load_rms_hn_fixture`. It uses the existing editor and fictional F1
  identities, nine idempotency receipts and56 RMS rows. Reset removes old fixture
  markers; repeat loader without reset retains its original idempotence/conflict
  behavior. All ordinary product guards/service validation remain active.
- Check guards again, verify unchanged protected auth state, force deferred
  constraints before committing, then emit a receipt and fictional record IDs.
  Do not print a success receipt before the outer commit returns.

Validation/fixture failures roll back that transaction's row and trigger changes.
A database/connection error is conservatively **RESULT UNCERTAIN**, including a
possible lost COMMIT response. Stop; Operations inspects auth, guard states, fixture
marker/version digests and actual target before any retry. Do not blindly retry or
restore disposable research rows from a backup. A fresh reset/reseed is permitted
after the result is reconciled; authentication failures require investigation.
No automatic destructive recovery, permission grant or migration occurs.

## Independent verification and browser demonstration

The existing [Test owner](/MAU/issues/MAU-144) independently retests the404 failure
against the exact successor before live operations; unchanged original failing
evidence is preserved. Source preparation does not wait on a parent/Test scheduling
edge, and no new task or writer is required. Reproduce new source checks with the
absolute assigned `.venv/bin/python scripts/check-rms-staging-reset.py --output
NEW_EVIDENCE_DIRECTORY`; Django and psycopg connections are denied. These simulations
do not prove PostgreSQL rollback, actual grants, successful startup, H01–H20 or UI.

After the concrete release/access decision, Operations performs the bounded reset/
reseed and records the committed receipt. Test uses **the same existing DB**, real
ordinary login and existing separately bound editor/viewer through the existing
private route, records release identity and maps all H01–H20 at the exact source:

1. Confirm editor/viewer login still works and original assignments are unchanged.
   Open Home, Source and Idea selection/pagination, saved exact versions, family,
   Research case, manual assessment and Hypothesis draft. Follow root navigation,
   save a valid draft and proposed record, history, correction and exact lineage;
   distinguish intended Hypothesis and later final Test Plan benchmarks. Capture
   keyboard/focus/labels and escaped submitted input at invalid/missing-reference
   saves,401/403 denial, conflict and service-error paths, without reference leakage
   or any false successful-save indication.
2. Use two separately authenticated editor browser contexts/independent DB sessions
   on the same post-reset fixture. For H10 send identical create key/payload
   concurrently; expect one201 and one identical replay, one saved version/link
   set. Different payload with the same key must return409 and add nothing.
   For H11 submit two distinct correction keys from the same predecessor; expect
   one201 version increment and one409 stale version with its input preserved.
   Retain both requests/statuses, PIDs and actual PostgreSQL lock/wait/commit
   observation; sequential calls are not concurrency evidence. Adopt the refreshed
   predecessor/context with a new key and verify the losing user's retry normally.
3. H14 runs direct mutation attempts against selected **disposable** immutable
   version/association records under the actual ordinary SQL login. Use rollback
   transactions and verify UPDATE/DELETE/TRUNCATE fail by rights/active guards and
   row digests do not change. Record effective grants/flags and no schema ownership
   or privileged membership. An administrator denial probe cannot certify this.
   Keep the maintenance reset capability separate from ordinary application rights.
4. Rerun loader without reset to prove its documented idempotence; then use the same
   reset command for the next disposable window and confirm both users' logins and
   memberships still work. Never use Django `TestCase`/DiscoverRunner test-database
   creation, generic `flush`, database drop/recreate or `--keepdb` against staging.
   DB-backed cases use the named existing target/transactions, not `rms_synthetic`.

Test records PASS/FAIL/INCONCLUSIVE/unexecuted per assertion; genuine overlapping DB
and authenticated browser observations remain pending. Founder browser outcome,
normal review/merge/staging records and section12 acceptance remain separate. The
standing PR-wide Test INCONCLUSIVE, Risk INCONCLUSIVE/NOT ACCEPTED(HIGH),34 unexecuted
Stage1 cases and restricted OPEN incident are unchanged, without disclosure here.

Recommendation: checkpoint this bounded successor, independent source retest now,
then authorize only the two named access/release actions and run this existing-target
procedure. An admin-only browser preview could show UI after release but cannot
close ordinary-role denial acceptance; a new database or waived assertion would not
satisfy the mandate. Remaining limitations are observed schema/access/release gaps,
not research-data retention. No new reviewer verdict/dissent on this successor is
claimed; preserve Test's original F1 until its independent retest is recorded.
