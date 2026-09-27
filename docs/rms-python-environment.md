# RMS Python toolchain — local setup and recovery

## Scope and evidence

This is the Linux x86_64, non-root, project-local development environment for RMS. The separately reviewed PR #1 product checkout supplies `requirements.lock`; the default `master` scaffold does **not** contain that lock. This runbook and a provisioned checkout do not authorize merge, deployment, live/production data, or research qualification. Reconstructing Python needs no credentials, host permission changes, or services; the separate Django database suite requires an isolated synthetic PostgreSQL test target.

As of September 27, 2026, the operator's existing tool root is `/paperclip/instances/default/projects/f6bf0bf4-801d-4dd1-8e60-02a58d2052ef/6fa1af9a-2486-44f2-b1c5-f152826cd54e/toolchains/rms`. The operator reported uv 0.12.19, CPython 3.13.15, Django 5.2.17, DRF 3.18.1, psycopg 3.3.6, and 3/3 passing staging-request-policy tests in a clean detached checkout at commit `1d4e212bf655e17f0a2b767834f8903d7f6828ac`, tree `dc1bc42ba0a32e8f1dd8bda6957551802e17c328`. This is **operator evidence**; MAU-126 records the independent Test result and limitations below. Risk's assessment remains separate.

## Recreate or repair (Operations owner)

From a checkout containing these scripts, choose an **absolute, persistent, project-local** tool path outside all Git worktrees; never put downloaded binaries or caches into the repository. For the current Paperclip project, use the tool root above. For a different authorized project root, substitute its own path. The commands below require Bash, Git, curl, sha256sum, coreutils, HTTPS reachability to Astral's official release and PyPI, and writable project-local directories. Verify available disk space and Linux x86_64 first. No `sudo`, global PATH/profile edits, or container restart:

```bash
TOOLS=/absolute/project/toolchains/rms
bash scripts/rms-python/bootstrap.sh "$TOOLS"
"$TOOLS/bin/uv" --version
"$TOOLS/bin/python3.13" --version
```

`bootstrap.sh` downloads Astral's uv 0.12.19 installer over HTTPS and checks SHA-256 `61b349611f1b6e1ba33645f30c36da5287df2609dd7af8605d96a031435eb35b` **before executing it**. It verifies the actual uv executable SHA-256 `242e462a63f5a3c0421d68557006193ecbfb61321cba0fe8542213ac62d92563` and managed CPython 3.13.15 executable SHA-256 `20a5569a1bac8de02122347777b6cf2ae12ec1eafd42db990c6a0c5407f96b8e` before switching any helper; unexpected provider bytes stop for Operations investigation. An exclusive project-local `flock` serializes bootstrap against locked-workspace provisioning, stages replacements, archives existing helper copies under `TOOLS/bootstrap/backups/`, and writes a checkable `manifest-*.sha256` plus OS/architecture/provider metadata. Those hashes cover the installer, binaries, and installed helpers, **not** the entire Python distribution archive, OS, container image, or another provider version. Do not bypass a checksum or overwrite an unexplained artifact. Recovery still depends on online GitHub/Astral/PyPI availability and the persistent `/paperclip` mount; this is not an offline backup.

In project configuration, prepend `TOOLS/bin` to `PATH`, set `BASH_ENV` to `TOOLS/shell-env.sh`, and set the global provision command to `bash TOOLS/provision-workspace.sh` (substitute the **literal absolute path**). The reviewed dispatcher explicitly reports **NOT APPLICABLE**, creates no `.venv`, and exits 0 on a checkout without `requirements.lock`; this is not proof of dependencies. On a locked checkout it creates an exact-state `.venv` or refuses an existing unmarked/mismatched one. `BASH_ENV` restores the tool path in noninteractive `bash -c` and `bash -lc`; `/bin/sh` and interactive Bash ignore it and require the injected `PATH` to survive or an explicit approved source/export. Verify `command -v python3` rather than requiring the tool directory to be first in the effective PATH. The installed project currently still uses its older prototype helpers; Operations must review this revision, then coordinate their replacement before the revised code can be claimed as the live control. This PR alone changes no project setting or live helper.

In each **authorized** product checkout at its reviewed exact SHA (verify the live PR head and tree first), run:

```bash
cd /absolute/path/to/product-checkout
test -f requirements.lock
bash "$TOOLS/provision-workspace.sh"
export BASH_ENV="$TOOLS/shell-env.sh"
bash -lc 'command -v python3; python3 --version; python3 -c "import django, rest_framework, psycopg; print(django.get_version(), rest_framework.VERSION, psycopg.__version__)"'
git rev-parse HEAD HEAD^{tree}
git status --short
```

A locked checkout's ignored `.venv` uses the reviewed Python binary and `uv pip sync --require-hashes --only-binary :all:` against **its own** `requirements.lock`. The helper writes an exact-state marker with checkout path, lock digest, uv/Python hashes, and installed-package manifest digest; subsequent provisioning and the `python3` wrapper verify it and `uv pip sync --check` before Python executes. Stale locks, foreign interpreters, missing markers, and extra packages **fail closed**; the helper does not silently delete or repair a reused environment. A no-lock checkout has no dependency provisioning and its wrapper selects the pinned base interpreter, ignoring any leftover `.venv`. Lockfile hashes verify wheels, not the OS/container or every installed file. If a virtualenv fails verification, preserve the state and use an Operations-controlled clean checkout; do not relabel a rejection as a successful setup.

## Verification and handoff
Engineering smoke check (September 27, 2026): in disposable run-owned storage, fetched and verified the pinned official installer, bootstrapped fresh uv 0.12.19 and CPython 3.13.15, repeated bootstrap successfully, cloned PR #1 at the SHA/tree above, and provisioned its six locked packages. In a reset-PATH noninteractive login shell, `command -v python3` selected the new tool root, `python3 --version` was 3.13.15, and imports returned Django 5.2.17 / DRF 3.18.1 / psycopg 3.3.6. `python3 -m unittest discover -s tests -p test_staging_request_policy.py -v` returned 3/3 PASS (exit 0); the disposable checkout remained clean. This is an Engineering smoke check only, **not** MAU-126 independent Test evidence or a full-suite verdict.


Record executable path, version, dependency imports, reviewed commit and tree, shell type, commands/exit codes, and checkout status; recheck from a fresh **noninteractive Bash** (`bash -c`/`bash -lc`) and a separate checkout before calling the environment reusable. Run only repository-declared tests and synthetic fixtures; avoid live database endpoints. This document is reconstruction guidance, not Test or Risk acceptance. Operations (MAU-127) owns configuration/recovery review and must re-review these corrections before live helper replacement. Engineering maintains the scripts; independent Test owns the separate PR #1 database suite (MAU-129), with adverse results retained. Rebaseline a moved PR head explicitly, never silently carry forward older evidence.

### Operations corrective verification and decisions

Operations MAU-127 reviewed the earlier PR #2 head `16929e36` and requested changes: unmarked or stale virtualenv reuse, no-lock global provision conflict, inaccurate shell scope, missing measured restore/manifest, and un-serialized live helper replacement. The revised dispatcher/strict checks above are **new Engineering work, not yet Operations-accepted live settings**. In a separate disposable root on September 27, 2026, Engineering timed an **online reconstruction in 3 seconds**, with 153 MiB resulting tool root, recorded a checkable SHA-256 manifest, created and verified six locked wheels from the frozen PR #1 lock in a synthetic Git fixture, and confirmed no-lock checkout reported NOT APPLICABLE without a `.venv`. Changed lock, undeclared-package metadata, and wrong interpreter probes were each rejected; restoring the original locked fixture passed. `bash -n`/`sh -n` and `git diff --check` pass. This is a local controlled matrix, **not** a measured backup restore, container restart/recreation test, product-suite pass, or Operations acceptance. Retain Ops MAU-127's adverse earlier revision and request a fresh focused review of the changed PR head before any live Python helper replacement.

Diego's scoped confirmation `f9ce0ab6-aaf6-4b31-95e5-10b346984556` was accepted September 27, 2026 at 01:16:38 UTC by the human operator who issued this task comment: one $0 non-root, project-local PostgreSQL 17 synthetic target, no live/staging data, host/root action, credential expansion, merge, or deployment. Alternative if independent Test cannot access this isolated endpoint: keep the 40 database cases NOT RUN and PR #1 blocked; never substitute SQLite, mocks, staging data, or previously passing no-DB checks for actual database evidence. A moved PR head, unexpected data access, new spending/permissions, or altered review criteria goes back to Diego and Risk. T0+2 business days for owner/dependency reporting and T0+5 for an integrated recommendation remain proposed only when required staffing/authorization/access is available.

### Independent Test result and database dependency

On September 27, 2026, independent Test (MAU-126) verified the frozen PR #1 commit/tree above, clean checkout, login-shell Python 3.13.15, and locked dependency imports. `python3 -m unittest discover -s tests -p 'test_*.py' -v` passed **23/23** (exit 0); a fresh login shell repeated the targeted **3/3** and `python3 manage.py check` exited 0. The missing-Python blocker is resolved. Eight Django database modules discovered **40 cases**, but **zero executed**: test-database creation failed against an intentionally nonexistent PostgreSQL socket (exit 1). Preserve the original MAU-126 traceback; this is neither a product-code test failure nor a full-suite pass. Independent Risk on MAU-128 owns PR #1 readiness, not Engineering.

### Isolated synthetic PostgreSQL 17.11 for Test (Engineering setup; Operations recovery owner)

On this Debian 13 x86_64 container only, `scripts/rms-python/bootstrap-postgres-test.sh` downloads six pinned Debian packages for PostgreSQL 17.11 and its client/runtime libraries over HTTPS, checks their SHA-256 values **before** `dpkg-deb -x`, and extracts only to `TOOLS/postgres-test/`. Versions, paths, and all six hashes are in that script; the server binary is also checked on reuse. No host package install, root action, external service, shared database, or new secret is used. Engineering verified a disposable server with synthetic SQL and evidence-preserving stop/reset, then initialized and started the persistent project-local target on September 27, 2026. Server SHA-256 from the verified Debian package is `6468a969338215cb3912cf9c0b894bdbbd37b9a709926db078e9a5bf8bdc3e16`. The installed PostgreSQL helper is separate from the installed Python prototype; neither an endpoint smoke check nor this runbook replaces independent Test.

Run from the documentation checkout with the existing absolute project tool root (use the path from Scope and evidence, not the literal placeholder):

```bash
TOOLS=/absolute/project/toolchains/rms
bash scripts/rms-python/bootstrap-postgres-test.sh "$TOOLS"
"$TOOLS/postgres-test.sh" init
"$TOOLS/postgres-test.sh" start
"$TOOLS/postgres-test.sh" status
```

`start` is idempotent. It binds **no TCP listener**; its sole Unix socket is inside `TOOLS/postgres-test/socket/` (mode 0700). Because the Paperclip project path exceeds PostgreSQL's 107-byte socket path limit, it creates a collision-checked short symlink under `/tmp/rms-pg-<hash>` pointing into that directory. If this link belongs to another target, the script fails closed. `start` creates only the synthetic `rms_synthetic` database and its `rms_synthetic_test` login role (`CREATEDB`, no superuser, no role creation, no replication, no RLS bypass); Django needs `CREATEDB` for `test_rms_synthetic`. Unix-socket trust auth is restricted by the socket directory's owner/mode, but **any process under the same local OS user can also assume the cluster admin role**; this is only an isolated synthetic, nonsecret test target, not a general multi-user security boundary. Do not use it for staging, live, confidential, or reserved-test data. The alias is a user-owned ephemeral `/tmp` symlink; all packages, data, and actual socket files stay project-local.

For an authorized PR #1 checkout after Test rechecks its **live** PR head/SHA/tree, the Test agent can execute (without copying any project environment variables into a shared service):

```bash
cd /absolute/path/to/verified-pr1-checkout
source "$TOOLS/postgres-test-env.sh"
PYTHONDONTWRITEBYTECODE=1 python3 manage.py test \
  tests.django_contract_tests tests.django_fixture_tests \
  tests.django_rms_si_frontend_page_tests tests.django_rms_si_frontend_template_tests \
  tests.django_rms_si_independent_tests tests.django_source_api_tests \
  tests.django_source_history_page_tests tests.django_source_idea_tests -v 1
```

`postgres-test-env.sh` exports only the synthetic socket path, port `55471`, database and role; the password is empty. Do **not** treat Engineering's endpoint smoke check as independent Test's execution of 40 cases. MAU-129 owns the fresh full-suite run; record its commands, counts, exit codes, skips, sanitized logs, and clean exact-head lineage there. MAU-126's previous unexecuted-case failure remains historical and unchanged. Risk MAU-128's INCONCLUSIVE/NOT ACCEPTED verdict also stands until Risk issues a new independent decision on any complete MAU-129 evidence.

Recovery: after coordinating with Test (never during a run), `"$TOOLS/postgres-test.sh" stop` stops only this cluster. `"$TOOLS/postgres-test.sh" reset` works only while stopped, **archives** the prior data directory under `TOOLS/postgres-test/archive/` without deleting evidence, initializes a new empty cluster and restarts it with the synthetic role/database. `"$TOOLS/postgres-test.sh" start` restarts after a runtime reset and recreates the short alias if `/tmp` was cleared. If a package checksum, existing role/owner, socket alias, runtime library, or cluster version differs, stop and have Operations investigate rather than overriding an unknown target. To roll back *future approved Python helper activation*, stop provisioning, acquire the bootstrap lock, and have Operations restore the recorded previous helper backup atomically while retaining both manifests and adverse evidence; do not downgrade/overwrite an active Test checkout. This installation has **not** been tested across container recreation, other distributions, different OS users, or concurrent Test resets. PR #2 needs fresh Operations review; merge/deploy remains Diego's decision.

References: MAU-125 operator handoff and MAU-126 independent Test record (September 27, 2026); repository `requirements.lock` in PR #1; official Astral uv [installer options](https://docs.astral.sh/uv/configuration/installer/), [Python install](https://docs.astral.sh/uv/guides/install-python/), and [pip compatibility](https://docs.astral.sh/uv/pip/compatibility/). Installer digest was independently checked against the official release on September 27, 2026.
