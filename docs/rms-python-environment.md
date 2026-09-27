# RMS Python toolchain — local setup and recovery

## Scope and evidence

This is the Linux x86_64, non-root, project-local development environment for RMS. The separately reviewed PR #1 product checkout supplies `requirements.lock`; the default `master` scaffold does **not** contain that lock. This runbook and a provisioned checkout do not authorize merge, deployment, live/production data, or research qualification. No credentials, host permission changes, or services are required.

As of September 27, 2026, the operator's existing tool root is `/paperclip/instances/default/projects/f6bf0bf4-801d-4dd1-8e60-02a58d2052ef/6fa1af9a-2486-44f2-b1c5-f152826cd54e/toolchains/rms`. The operator reported uv 0.12.19, CPython 3.13.15, Django 5.2.17, DRF 3.18.1, psycopg 3.3.6, and 3/3 passing staging-request-policy tests in a clean detached checkout at commit `1d4e212bf655e17f0a2b767834f8903d7f6828ac`, tree `dc1bc42ba0a32e8f1dd8bda6957551802e17c328`. This is **operator evidence**, not an independent Test verdict. MAU-126 owns the independent suite result, including any failures; Risk's assessment remains separate.

## Recreate or repair (Operations owner)

From a checkout containing these scripts, choose an **absolute, persistent, project-local** tool path outside all Git worktrees; never put downloaded binaries or caches into the repository. For the current Paperclip project, use the tool root above. For a different authorized project root, substitute its own path. The commands below require Bash, Git, curl, sha256sum, coreutils, HTTPS reachability to Astral's official release and PyPI, and writable project-local directories. Verify available disk space and Linux x86_64 first. No `sudo`, global PATH/profile edits, or container restart:

```bash
TOOLS=/absolute/project/toolchains/rms
bash scripts/rms-python/bootstrap.sh "$TOOLS"
"$TOOLS/bin/uv" --version
"$TOOLS/bin/python3.13" --version
```

`bootstrap.sh` downloads Astral's uv 0.12.19 release installer over HTTPS, verifies SHA-256 `61b349611f1b6e1ba33645f30c36da5287df2609dd7af8605d96a031435eb35b` **before executing it**, and installs uv into `TOOLS/bin` without touching shell profiles. It uses that pinned uv to install exact CPython 3.13.15 into `TOOLS/python` and copies the repository's wrapper, provisioning script, and shell setup into the durable tool root. It fails on unexpected uv version/architecture or installer checksum. If an existing tool root is damaged or a digest differs, stop, preserve the failed state, and have Operations investigate the source/restore a reviewed tool root; do not bypass the checksum or overwrite an unexplained installer. `uv python install` pins the interpreter version but not necessarily byte-identical runtime distributions across platforms or provider changes; record OS/platform and actual binary hashes for evidence-sensitive rebuilds.

In project configuration, prepend `TOOLS/bin` to `PATH`, set `BASH_ENV` to `TOOLS/shell-env.sh`, and set the provision command to `bash TOOLS/provision-workspace.sh` (replace `TOOLS` with the **literal absolute path** in each setting). `BASH_ENV` restores the tool path in noninteractive `bash -lc` shells that reset PATH. The tool root remains independent of a particular branch/worktree; the `python3` wrapper selects the current checkout's `.venv`, falling back to pinned 3.13.15 before provisioning. Changes to Paperclip project settings are Operations-owned; no live setting is modified by this PR.

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

The per-checkout `.venv` is Git-ignored, built with the pinned interpreter, and installed from **that checkout's** `requirements.lock` with `--require-hashes --only-binary :all: --no-deps`. Lockfile hashes verify individual wheels, not the OS/container or Python binary. Provisioning fails closed if the lockfile is absent and must not silently borrow another checkout's requirements. `python3` resolution is per current Git top-level directory; invoke from within the intended checkout. For recovery, confirm tool root/version/installer digest, rerun bootstrap to restore scripts/interpreter, then provision each checkout again. Do not reuse a `.venv` after changing its Python or lock: provision a clean checkout or have Operations safely recreate the local ignored `.venv` after preserving any required evidence. Never upload caches, virtualenvs, credentials, or failed-run secrets.

## Verification and handoff
Engineering smoke check (September 27, 2026): in disposable run-owned storage, fetched and verified the pinned official installer, bootstrapped fresh uv 0.12.19 and CPython 3.13.15, repeated bootstrap successfully, cloned PR #1 at the SHA/tree above, and provisioned its six locked packages. In a reset-PATH noninteractive login shell, `command -v python3` selected the new tool root, `python3 --version` was 3.13.15, and imports returned Django 5.2.17 / DRF 3.18.1 / psycopg 3.3.6. `python3 -m unittest discover -s tests -p test_staging_request_policy.py -v` returned 3/3 PASS (exit 0); the disposable checkout remained clean. This is an Engineering smoke check only, **not** MAU-126 independent Test evidence or a full-suite verdict.


Record command path, version, dependency imports, reviewed commit and tree, shell type, test commands/exit codes and clean checkout status; recheck from a fresh agent login shell and another checkout before calling the environment reusable. Run only repository-declared tests and synthetic fixtures; avoid live database endpoints. This document is a reconstruction procedure, not a Test or Risk verdict. Operations reviews the commands against actual configured project settings and retains recovery ownership. Engineering maintains these scripts; Test independently executes the missing PR #1 Python suite on the frozen product head, with adverse results preserved. Escalate a moved PR head for rebaseline rather than silently attributing an older run to new code.

References: MAU-125 operator handoff (September 27, 2026); repository `requirements.lock` in PR #1; official Astral uv [installer options](https://docs.astral.sh/uv/configuration/installer/), [Python install](https://docs.astral.sh/uv/guides/install-python/), and [pip compatibility](https://docs.astral.sh/uv/pip/compatibility/). Installer digest was independently checked against the official release on September 27, 2026.
