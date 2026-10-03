# Task-bound RMS startup and handoff

Verified October 3, 2026, Operations run
`25a2c2ea-612a-4302-9fb1-9f2de10a6c7f`, under MAU-140 contract revision
`3982eccc-e180-4ac9-bc70-9c4e16aa47f1`, section 11. This is software startup,
not feature acceptance, research/Risk approval, merge, or deployment.

## Existing configuration

Operations confirms each issue's assignee and persisted execution-workspace
binding using authenticated Paperclip reads. A default cwd or project workspace
ID is not a task execution binding. Each recipient supplies its own actual run,
command, result, and receipt; Director owns the sole parent startup-readiness table.

- Project: `6fa1af9a-2486-44f2-b1c5-f152826cd54e`.
- Primary project workspace: `8258fcbb-78e0-44f2-bbf2-59e619b24920`.
- Environment: `c3931944-3432-4b78-ad1d-ff7e39cc78c0`.
- Project policy: `defaultMode=isolated_workspace`, strategy `git_worktree`,
  `sharedWorkspaceConcurrency=serialize`, issue overrides allowed.
- Primary repository: `https://github.com/dieg0andres/mv-rms.git`, configured ref
  `master`; actual realized task base `origin/master`.
- Strategy `baseRef`, `branchTemplate`, and `worktreeParentDir` were empty
  strings. No separately named template is verified. Retain actual realization
  metadata and do not invent template/default semantics.
- Provision command: `bash` plus the existing toolchain's `provision-workspace.sh`.

The approved existing tool root for this project is
`/paperclip/instances/default/projects/f6bf0bf4-801d-4dd1-8e60-02a58d2052ef/6fa1af9a-2486-44f2-b1c5-f152826cd54e/toolchains/rms`.
Set `TOOLS` to that existing path. Do not independently bootstrap, install, or
replace helpers. Latest bootstrap/provisioner source change:
`5e4105e0546c976ed86254cbfb10537180d210b7`.

## Recipient verification

Run in the actual assigned checkout and record task-visible binding, branch,
HEAD, cleanliness, run ID, commands, and exit codes. Preserve failed/uncommitted
work; do not reset, erase, retry an unchanged rejection, or bypass verification.

```bash
test -n "$PAPERCLIP_TASK_ID"
test -n "$PAPERCLIP_RUN_ID"
test "$(pwd -P)" = "$PAPERCLIP_WORKSPACE_CWD"
test "$(git rev-parse --show-toplevel)" = "$PAPERCLIP_WORKSPACE_CWD"
git branch --show-current
git rev-parse HEAD origin/master
git status --short
bash "$TOOLS/provision-workspace.sh" --verify
export BASH_ENV="$TOOLS/shell-env.sh"
bash -lc 'command -v python3; python3 -I -B -c "import sys, django, rest_framework, psycopg; print(sys.version.split()[0], sys.executable, django.get_version(), rest_framework.VERSION, psycopg.__version__)"'
```

Operations fetched `master` with `git fetch --no-tags origin master` on October 3,
2026 at 06:20:58 UTC. No checkout, branch, or HEAD changed. Fetched base and all
three recipient HEADs were `bd0e6b82634349ac2cbb75e91989e37dbb925014`.
Each task-local `.venv` and `.venv/.rms-python-state` passed verification.
Verify-only uses existing coordination locks/cache bookkeeping, not installation.

Expected pins: CPython 3.13.15, uv 0.12.19, Django 5.2.17, DRF 3.18.1,
psycopg/psycopg-binary 3.3.6, asgiref 3.12.1, sqlparse 0.6.0.
Attested live provisioner SHA-256:
`fb0bc792212cccbde8f73556b5b17a11678bc741e200627382fd8c4fab341285`.
Lock SHA-256:
`d21ca3b1acbcd2bbd60637b3870b5498307084173e070a9f78834dc4b4341ea4`.
All six entries in
`TOOLS/bootstrap/manifest-20260927T150533074347906.sha256` verified; its
`.metadata` records Debian 13 x86_64 and the pinned provider/runtime. This does
not prove container recreation or restore. Preserve historical adverse evidence
in `docs/rms-python-environment.md` and Paperclip.

## Existing safe facility and minimal commands

Existing project-local PostgreSQL 17.11 uses database `rms_synthetic`, role
`rms_synthetic_test`, and a private Unix socket. It is not staging. Operations
verified pinned imports and SELECT-only access from each recipient checkout,
with transaction read-only mode enabled. Do not print secrets/connection strings
or inherit a different database target.

```bash
source "$TOOLS/postgres-test-env.sh"
test "$RMS_DB_NAME" = rms_synthetic
test "$RMS_DB_USER" = rms_synthetic_test
test "$RMS_DB_PORT" = 55471
test "$RMS_DB_HOST" = /tmp/rms-pg-3e28c0c243bd8129
```

Backend's minimal service startup:

```bash
bash -lc 'python3 -B manage.py check'
```

Frontend and independent Test each run the existing database-free template module:

```bash
bash -lc 'python3 -B manage.py test tests.django_rms_si_frontend_template_tests -v 2'
```

Operations ran both in MAU-141: system check exit 0; template tests 3/3 PASS,
exit 0, explicitly `Skipping setup of unused database(s): default`.
These recipe checks do not replace any recipient's actual startup receipt or
independent H01–H20 execution. Do not expand test labels without rechecking data
targets and procedure.

Director's October 3 bounded alternative also passed in MAU-141, 6/6, exit 0:

```bash
bash -lc 'PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_source_versions -v'
```

This existing module instantiates only the invented in-memory `SourceVersionKernel`;
it does not invoke a Django database runner. It is a command/runtime startup probe,
not a repeat of MAU-44 acceptance or an H01–H20 result.

Each recipient can prove existing target access without mutation after the target
guards above, using an explicitly read-only transaction:

```bash
python3 -I -B - <<'PY'
import os
import psycopg

connection = psycopg.connect(
    host=os.environ["RMS_DB_HOST"], port="55471", dbname="rms_synthetic",
    user="rms_synthetic_test", password="",
    options="-c default_transaction_read_only=on", connect_timeout=5,
)
print(connection.execute(
    "SELECT current_database(), current_user, current_setting('transaction_read_only')"
).fetchone())
connection.rollback()
connection.close()
PY
```

Observed role flags: not superuser, CREATEDB, no role creation, replication, or
RLS bypass. Existing CREATEDB entitlement is not permission to exercise it in
this increment. This test-role connection does not certify ordinary staging
application-role history protection; Test must separately establish H14 evidence.

## Exact database-using acceptance limitation

`test_rms_synthetic` was absent. One read-only connection attempt returned exit 1:
`FATAL: database "test_rms_synthetic" does not exist`.
The normal database-using Django runner would create this database;
`--keepdb` does not prevent creation when absent. Operations ran no such runner,
migration, fixture write, flush/reset/init/start, or database/service creation.

Director owns the remedy: identify an already-approved transaction-only procedure
on the existing synthetic facility that preserves records, or route the exact
bounded test-database lifecycle decision through CEO/founder. Operations executes
only an authorized remedy; Test verifies it independently. Database-free startup
and authorized preparation can proceed without another readiness approval.
Database-using acceptance remains unexecuted until the exact procedure is resolved.
Director/Test must schedule shared database use: checkout isolation is not database
isolation or evidence of simultaneous test throughput.

## Handoff template

- What: task, accepted contract/API revisions, exact branch/HEAD or candidate,
  changed scope, unresolved criteria.
- Where: task-visible execution-workspace ID, verified checkout/environment,
  target and approved procedure by non-secret name.
- How: exact next command, fixture or absence of writes, expected result, bounds.
- Who: receiving owner, Director as coordinator.
- Receipt: actual receiving run, command, exit/result; otherwise one precise
  failure with owner/action. A posted comment or queued wake is not receipt.

Director incorporates this documentation into the reviewed feature change; it is
not yet GitHub-published or an integrated candidate. No configuration default,
owner, privilege, staging resource, incident route, or affected-work hold changes.
