# RMS PostgreSQL runtime grants and recovery — MAU-162

**Decision:** publish for operator and Engineering review. **Rollout remains NO-GO.** No installed deployment, shared database, service configuration, or live grants were changed. The operator’s MAU-159 receipt `9e2eccf5-9f4f-4ed4-afdf-5764b3d4d82b` reports that the installed app uses a superuser with `BYPASSRLS`, and the preview was at `95df670d` / migration `0007_test_plan_history_guards`. A healthy container or unauthenticated 401 does not prove database separation.

## Run the isolated rehearsal

From the release workspace with the locked `.venv`, using the authorized fixture route, a fresh scratch path and one writer per target:

```bash
RMS_SYNTHETIC_TOOL_ROOT=/approved/existing/rms-tool-root \
RMS_REHEARSAL_SCRATCH=/approved/run-scratch/unique-empty-path \
  bash scripts/rms-python/rehearse-runtime-grants.sh
```

The harness uses the existing private PostgreSQL 17 socket and the fixture admin only for two unique disposable databases, two disposable fixture roles, and extension ACLs. It does not start/reset the service or write to `rms_synthetic`. It drops only its own successfully created targets and roles. Treat a cleanup failure as an operator incident; do not reset the fixture. Do not upload the synthetic dump or raw fixture snapshots; retain only approved sanitized checksums and results. The smoke harness imports the branch’s invented-only result test helpers; the operator grant SQL does not.

## Grant and cutover recipe — Codex/operator only, after authorization

1. Bind the exact immutable package, commit/tree, migrations, settings, image digest and ACL scripts. Inspect sanitized database, schema, extension, owner, ACL, role/membership, authentication and default-privilege inventories. This recipe assumes a **dedicated RMS database** with Django objects and `pgcrypto` in `public`; it revokes `PUBLIC` privileges there. Stop if anything else depends on those privileges. Confirm the runtime login is restricted to the target database by the approved PostgreSQL authentication/network policy; database grants on the target do not restrict other databases. Keep the legacy database intact and outside the app connection path. Do not change `POSTGRES_USER` in an initialized volume or use the bootstrap login as an app credential.
2. Use distinct, fresh logins for database/migration ownership and for the app. Operator provisions each with `LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT`, no memberships, and independently managed credentials. Reserve the owner credential for the offline migration job; the runtime service must not mount it. The cluster/extension admin is a separate identity and must not be used by the app. Use separately approved encrypted connections/secret mounts; the placeholders below are names and connection service aliases, never passwords. Verify the credential binding from an actual app process, not a standalone psql session alone.
3. Gate writes and take an approved custom-format consistent backup. Capture a separate reviewed role/ACL manifest (a database dump does not create cluster logins); do not export password hashes or bind an ordinary artifact to a real backup. Restore into a new empty `template0` database **owned by the new DDL login** and run Django migrations as that login. Use `--no-owner --no-acl` intentionally; the following scripts rebuild reviewed privileges and fail closed if the owner, database, major version or migration leaf is wrong. Never run `--clean` against a retained database, and never use `REASSIGN OWNED` against a shared cluster as a shortcut.

```bash
# Operator prebinds each approved service alias to the intended identity and database.
# LEGACY_BACKUP_SERVICE: authorized reader of the source; OWNER_SERVICE and
# EXTENSION_ADMIN_SERVICE: the SAME new target database, distinct identities.
# TARGET_DB, DDL_OWNER, RUNTIME_ROLE: literal catalog names; ARCHIVE: protected path.
# LEAF_STEP and LEAF_NAME: one reviewed pair for 0007, 0008, or 0009.
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

Treat restore, migration and both ACL transactions as separate gates. A failure keeps the **new target off the app route**. Do not enable writes until all checks pass. An operator comparing exact candidate inventory must account for any future migrations or optional services; the scripts do not approve unknown objects or roles. Bind the runtime secret separately from the PostgreSQL bootstrap secret. Require role/protection receipts, fresh private TLS and unauthenticated `401`, real authenticated editor/founder/outsider `/api/v1` and UI behavior (including exact historical plan routes), and independent Test/Risk acceptance before exposing the candidate.

## Why these grants

- Basic Authentication reads `auth_user`, `auth_group` and `auth_user_groups`. No auth writes, sessions, Django migration ledger access, or sequence privileges are needed by the runtime. RMS identities are UUIDs/application-generated keys; Django’s integer-ID sequences are owner-side only. New auth or login flows are a new grant review.
- Explicit RMS `SELECT` and `INSERT` allow service appends, not updates/deletes of version rows. Invoker triggers need `UPDATE (latest_version)` for guarded counters. `0009` uses `SELECT … FOR UPDATE` on `rms_runattempt`; PostgreSQL requires `UPDATE` on at least one column, so the recipe permits only `id`. The immutable trigger rejects even `SET id=id` on a populated row. Do not broaden to table-level `UPDATE` or turn off triggers. If Engineering replaces the row lock with a reviewed alternative, remove the column grant and rerun concurrency checks.
- The offline extension admin revokes `PUBLIC` access to `pgcrypto` routines; the owner can delegate only `digest(bytea,text)` used by the invoker triggers. Installed `pgcrypto` function ownership differs from ordinary application ownership even when the database owner installed the trusted extension. The SQL verifies no other `public` routine is executable by the runtime.
- This protects against editing existing history and bypassing DDL controls under the runtime identity. It is not per-user DB isolation or proof that a compromised application cannot submit a new row. Django enforces editor/viewer scope, idempotency and attribution at the application boundary. Monitor privileged access and keep independent evidence checks separate.

## Rollback without deleting history

- **Before opening writes:** leave the candidate off-route. Retain the failed target and evidence per operator controls. Prefer a new empty target restored from the write-gated checkpoint and apply the same scripts at its supported leaf (for the installed baseline: `LEAF_STEP=0007`, `LEAF_NAME=0007_test_plan_history_guards`). Reconnect only with a verified non-superuser runtime and an approved compatible package. Never “roll back” by reintroducing the app’s superuser credential.
- **After opening writes:** gate writes immediately and retain both targets. Prefer rolling back only the app package on the **same newer schema** if that exact prior package has already passed the ordinary-role, old-flow and private-route checks on the newer schema. Otherwise restore the newest consistent checkpoint into a separate DB using the commands above and reconcile any writes since the checkpoint before switching; if that cannot be done without silent data loss, stay offline and escalate. Do not point to the stale legacy source or reverse `0008`/`0009` to downgrade; that risks losing attempts, lifecycle, result, and evidence history. Prove users/roles/history and digests, runtime denial and private route continuity before reopening.
- Alternative: an in-place owner/ACL transfer has more shared-state risk and a weaker rollback boundary; not recommended. No new resource or founder approval is assumed. If Codex cannot use an existing authorized isolated/restore target, secret binding or maintenance slot, the CEO should take that exact access/resource/maintenance decision to Diego rather than substitute a shared environment. No dissent to the existing NO-GO; the validated fixture narrows one blocker only.

## Evidence — November 22, 2026

- Existing isolate: PostgreSQL `17.11` (`server_version_num=170011`), helper SHA-256 `5200755775b849a7a5e6bae86f05443bfe1059b3e75882768e5872fc5faa8fdf`. Workspace HEAD `949c1a4402da67910a31a28c77962757ccc8ca66` plus the **unfrozen** release-branch working tree. Migration SHA-256: `0007` `e49ce11265defeb8cc9b0de4c9f26150e78db0416baf62222516ce8e1a9bba50`; `0008` `8a8b20fc62c8a599d9e91bdba5dff4a5ae3515fdebfb3b693ce30903d373da04`; `0009` `1e8eceabc73440646a0dc0e1f1c072187b3ab4b114bde626cc21cee004c4fd52`.
- Rehearsal 1 caught trusted extension ownership and was corrected. Rehearsal 2 caught additive Django content-type and permission entries and was corrected to compare preexisting rows (separate from new run metadata and migration sequences). All temporary databases and roles were cleaned up.
- Rehearsal 3 passed: ordinary login seeded invented Source/Hypothesis/Test Plan history and amended the plan; registered against the older exact plan version at `0008`; `0009` preserved the registered attempt and its receipt; verified failed attempt → retry → completion → initial mandatory-fail result → immutable correction, idempotent replay, application role checks and raw SQL denials. Source counter direct update and attempt ID direct update were rejected by triggers. No backtest or research evidence was generated.
- Rebuilt a second database from a post-write custom dump and reapplied ACLs. All 47 table/sequence snapshot entries matched (manifest SHA-256 `16c03eb83364f8722f51b936e11373f3323f5fad1f4e4018361bed64423ce98f`). Restored API read, stored row digest, recomputed artifact SHA-256 and mutation denials passed. Restore + ACL application + checks took **3 seconds on the small synthetic fixture**, not a host RTO or estimate for actual data. Legacy app fallback, the installed process’s new identity, private TLS/browser, concurrency and the final exact candidate remain unverified.
- References: MAU-159 operator receipt above; MAU-162 wake `c9916d61-0180-4c06-8e0b-90629df74885`; PostgreSQL 17 documentation sections `GRANT`, `Privileges`, and `pg_restore`. Engineering owns freezing the candidate after MAU-164; independent Test and Risk own acceptance; Codex owns the host operation and operator receipts.
