# RMS PostgreSQL runtime grants and recovery

The PostgreSQL 17 procedure covers the supported RMS schema leaves `0007`, `0008` and `0009`. The results below are from a disposable synthetic fixture, not a release candidate or live environment.

## Separate release verdicts

- **Synthetic software verdict: pending.** Independent Test and Risk may issue a software-only verdict on one frozen candidate after isolated verification, including least-privilege runtime and history-preserving restore checks. A fixture rehearsal alone does not qualify the candidate, and a passing verdict does not authorize installation.
- **Installation and cutover verdict: deferred; not authorized.** Leave the deployed service, login and ingress unchanged. Live-account and authenticated private-route proofs, timed restore and safe fallback for cutover, and the installation itself require a separate authorized operator action.

## Run the isolated rehearsal

From the release workspace with the locked `.venv`, using the authorized fixture route, a fresh scratch path and one writer per target:

```bash
RMS_SYNTHETIC_TOOL_ROOT=/approved/existing/rms-tool-root \
RMS_REHEARSAL_SCRATCH=/approved/run-scratch/unique-empty-path \
  bash scripts/rms-python/rehearse-runtime-grants.sh
```

The harness uses the existing private PostgreSQL 17 socket and the fixture admin only for two unique disposable databases, two disposable fixture roles, and extension ACLs. It does not start/reset the service or write to `rms_synthetic`. It drops only its own successfully created targets and roles. Treat a cleanup failure as an operator incident; do not reset the fixture. Do not upload the synthetic dump or raw fixture snapshots; retain only approved sanitized checksums and results. The smoke harness imports the branch’s invented-only result and assurance test helpers; the operator grant SQL does not. The harness uses an ephemeral fixture password only inside the disposable rehearsal; never export it or the raw backup as evidence.

For a release rehearsal, also set `RMS_REHEARSAL_PACKAGE` to the absolute path of the exact output of `staging/build-release.py`. The smoke checks the product archive and verifies both documented Runs asset paths for content type and checksum through the runtime allowlist. Authenticated readiness under the ordinary login must fail with migrations pending and succeed after upgrade and restore. The migration ledger and its sequence must still reject writes. Repeat these checks over the isolated candidate’s HTTP/browser route for independent acceptance.

## Grant and cutover recipe — Codex/operator only, after authorization

1. Bind the exact immutable package, commit/tree, migrations, settings, image digest and ACL scripts. Inspect sanitized database, schema, extension, owner, ACL, role/membership, authentication and default-privilege inventories. This recipe assumes a **dedicated RMS database** with Django objects and `pgcrypto` in `public`; it revokes `PUBLIC` privileges there. Stop if anything else depends on those privileges. Confirm the runtime login is restricted to the target database by the approved PostgreSQL authentication/network policy; database grants on the target do not restrict other databases. Keep the legacy database intact and outside the app connection path. Do not change `POSTGRES_USER` in an initialized volume or use the bootstrap login as an app credential.
2. Use distinct, fresh logins for database/migration ownership and for the app. Operator provisions each with `LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT`, no memberships, and independently managed credentials. Reserve the owner credential for the offline migration job; the runtime service must not mount it. The cluster/extension admin is a separate identity and must not be used by the app. Use separately approved encrypted connections/secret mounts; the placeholders below are names and connection service aliases, never passwords. Verify the credential binding from an actual app process, not a standalone psql session alone.
3. Gate writes and take an approved custom-format consistent backup. Capture a separate reviewed role/ACL manifest (a database dump does not create cluster logins); do not export password hashes or bind an ordinary artifact to a real backup. Restore into a new empty `template0` database **owned by the new DDL login** and run Django migrations as that login. Use `--no-owner --no-acl` intentionally; the following scripts rebuild reviewed privileges and fail closed if the owner, database, major version or migration leaf is wrong. Never run `--clean` against a retained database, and never use `REASSIGN OWNED` against a shared cluster as a shortcut.

```bash
# Operator prebinds each approved service alias to the intended identity and database.
# LEGACY_BACKUP_SERVICE: authorized reader of the source; OWNER_SERVICE and
# EXTENSION_ADMIN_SERVICE: the SAME new target database, distinct identities.
# TARGET_DB, DDL_OWNER, RUNTIME_ROLE: literal catalog names; ARCHIVE: protected path.
# LEAF_STEP and LEAF_NAME: 0010 / 0010_run_assurance for this slice.
PGSERVICE="$LEGACY_BACKUP_SERVICE" pg_dump -w -Fc -f "$ARCHIVE"
PGSERVICE="$OWNER_SERVICE" pg_restore -w --single-transaction --exit-on-error \
  --no-owner --no-acl -d "$TARGET_DB" "$ARCHIVE"
# In the offline job only, bind RMS_DB_* (including the protected owner secret) to the new target.
python manage.py migrate rms "$LEAF_STEP" --noinput
PGSERVICE="$EXTENSION_ADMIN_SERVICE" psql -Xw -v target_db="$TARGET_DB" \
  -v ddl_owner="$DDL_OWNER" -v runtime_role="$RUNTIME_ROLE" -f scripts/rms-python/runtime-pgcrypto.sql
PGSERVICE="$OWNER_SERVICE" psql -Xw -v target_db="$TARGET_DB" -v ddl_owner="$DDL_OWNER" \
  -v runtime_role="$RUNTIME_ROLE" -v rms_leaf="$LEAF_NAME" -f scripts/rms-python/runtime-grants.sql
```

Treat restore, migration and both ACL transactions as separate gates. A failure keeps the **new target off the app route**. Do not enable writes until all checks pass. An operator comparing exact candidate inventory must account for any future migrations or optional services; the scripts do not approve unknown objects or roles. Bind the runtime secret separately from the PostgreSQL bootstrap secret. For a separately authorized cutover, require role/protection receipts from the running app, fresh private TLS and unauthenticated `401`, authenticated editor/founder/outsider `/api/v1` and UI behavior (including exact historical plan routes), and independent Test/Risk acceptance before exposing the candidate.

## Synthetic application roles and labels

`founder_viewer` provides read-only “View result and history”, even if assigned an assurance grant or also placed in `editor`. `editor` provides read admission and existing editor actions, not assurance authority. Three separate invented, editor-admitted accounts use an unexpired trusted grant binding their own actor ID, exact result UUID and digest, and one action: “Publish review”, “Record disposition”, or “Record lesson”. These are the intended labels; verify rendered copy at integration. Hints come from the shared action policy, not group names. No real grants or credentials are part of this package. See `RMS-RUN-ASSURANCE-API.md` for grant format and the denial matrix.

## Why these grants

- Basic Authentication reads `auth_user`, `auth_group` and `auth_user_groups`. `GET /api/v1/readiness` reads `django_migrations` through Django’s `MigrationExecutor`. Grant only `SELECT` on that ledger; the ordinary login cannot record, alter or remove migrations or use the ledger sequence. No auth writes, sessions or sequence privileges are needed by the runtime. RMS identities are UUIDs/application-generated keys; Django’s integer-ID sequences remain owner-side only. New auth or login flows are a new grant review.
- Explicit RMS `SELECT` and `INSERT` allow service appends, not updates/deletes of version rows. Invoker triggers need `UPDATE (latest_version)` for guarded counters. `0009` uses `SELECT … FOR UPDATE` on `rms_runattempt`; PostgreSQL requires `UPDATE` on at least one column, so the recipe permits only `id`. The immutable trigger rejects even `SET id=id` on a populated row. Do not broaden to table-level `UPDATE` or turn off triggers. If Engineering replaces the row lock with a reviewed alternative, remove the column grant and rerun concurrency checks.
- At `0010_run_assurance`, grant only `SELECT, INSERT` on `public.rms_runreview`, `public.rms_rundecision`, and `public.rms_runlesson`. No new sequence or default grants. Verify separate migration ownership, invoker rights and the three active guards per table. Do not grant direct trigger execution. Compare prior history and sequences across populated `0009` → `0010`, then compare rows, ACL/trigger inventory and the exact original/corrected reads on a separate restore.
- The offline extension admin revokes `PUBLIC` access to `pgcrypto` routines; the owner can delegate only `digest(bytea,text)` used by the invoker triggers. Installed `pgcrypto` function ownership differs from ordinary application ownership even when the database owner installed the trusted extension. The SQL verifies no other `public` routine is executable by the runtime.
- This protects against editing existing history and bypassing DDL controls under the runtime identity. It is not per-user DB isolation or proof that a compromised application cannot submit a new row. Django enforces editor/viewer scope, idempotency and attribution at the application boundary. Monitor privileged access and keep independent evidence checks separate.

## Rollback without deleting history

- **Before opening writes:** leave the candidate off-route. Retain the failed target and evidence per operator controls. Prefer a new empty target restored from the write-gated checkpoint and apply the same scripts at its supported leaf (for a `0007` baseline: `LEAF_STEP=0007`, `LEAF_NAME=0007_test_plan_history_guards`). Reconnect only with a verified non-superuser runtime and an approved compatible package. Never use a privileged login as an application rollback path.
- **After opening writes:** gate writes immediately and retain both targets. Prefer rolling back only the app package on the **same newer schema** if that exact prior package has already passed the ordinary-role, old-flow and private-route checks on the newer schema. Otherwise restore the newest consistent checkpoint into a separate DB using the commands above and reconcile any writes since the checkpoint before switching; if that cannot be done without silent data loss, stay offline and escalate. Do not point to the stale legacy source or reverse `0008`/`0009`/populated `0010` to downgrade; that risks losing attempts, lifecycle, result, and evidence history. Prove users/roles/history and digests, runtime denial and private route continuity before reopening.
- Alternative: an in-place owner/ACL transfer has more shared-state risk and a weaker rollback boundary; not recommended. If a separately authorized action lacks an isolated restore target, separate runtime secret binding or maintenance window, stop and escalate that specific prerequisite. Do not substitute a shared environment or infer authorization from the fixture results.

## Evidence — November 22, 2026

- Existing isolate: PostgreSQL `17.11` (`server_version_num=170011`), helper SHA-256 `5200755775b849a7a5e6bae86f05443bfe1059b3e75882768e5872fc5faa8fdf`. Workspace HEAD `949c1a4402da67910a31a28c77962757ccc8ca66` plus the **unfrozen** release-branch working tree. Migration SHA-256: `0007` `e49ce11265defeb8cc9b0de4c9f26150e78db0416baf62222516ce8e1a9bba50`; `0008` `8a8b20fc62c8a599d9e91bdba5dff4a5ae3515fdebfb3b693ce30903d373da04`; `0009` `1e8eceabc73440646a0dc0e1f1c072187b3ab4b114bde626cc21cee004c4fd52`.
- Rehearsal 1 caught trusted extension ownership and was corrected. Rehearsal 2 caught additive Django content-type and permission entries and was corrected to compare preexisting rows (separate from new run metadata and migration sequences). All temporary databases and roles were cleaned up.
- Rehearsal 3 passed: ordinary login seeded invented Source/Hypothesis/Test Plan history and amended the plan; registered against the older exact plan version at `0008`; `0009` preserved the registered attempt and its receipt; verified failed attempt → retry → completion → initial mandatory-fail result → immutable correction, idempotent replay, application role checks and raw SQL denials. Source counter direct update and attempt ID direct update were rejected by triggers. No backtest or research evidence was generated.
- Rebuilt a second database from a post-write custom dump and reapplied ACLs. All 47 table/sequence snapshot entries matched (manifest SHA-256 `16c03eb83364f8722f51b936e11373f3323f5fad1f4e4018361bed64423ce98f`). Restored API read, stored row digest, recomputed artifact SHA-256 and mutation denials passed. Restore + ACL application + checks took **3 seconds on the small synthetic fixture**, not an installation recovery-time target or an estimate for actual data. Concurrency and exact-candidate checks were outside this rehearsal. Live checks remain deferred.
