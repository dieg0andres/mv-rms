# RMS synthetic staging — GitHub rebuild and review

This is the repository recipe for the **existing** RMS Increment 1 candidate, not authorization to merge, deploy, change the VPS, or extend staging access. The staging application was reported live by the authorized operator on September 26, 2026; Engineering has **not** independently inventoried the VPS. Codex/operator supplies actual host paths, image digests, route, configuration hashes, grants, and recovery evidence separately. Do not infer current host state from this document. The September 26 MAU-44 founder instruction authorizes a reviewed, unmerged repository PR and reproducibility review only.

## Immutable product and recipe inputs

- Product application commit: `0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0`, tree: `c1219ad5bd24bbb43b11f74938c7b2b4c8e08f77`. The builder archives **that commit**, not PR HEAD; the archive contains `requirements.lock`, `stack.lock`, Django sources/migrations, frontend templates/static JS, synthetic fixtures and contracts. Changing a staging adapter or Test runner does not silently change this product pin.
- PR HEAD separately pins the adapter and recipe: `staging/{Dockerfile,compose.yaml,build-package.sh,entrypoint.sh,runtime.py,request_policy.py,create-principals.py,requirements-staging.lock,README.md}`, `staging/browser/{package.json,package-lock.json,staging-origin.mjs,preflight-headless.mjs,HEADLESS.md}` and `tests/browser/test-ui01.mjs`. The builder copies the reviewed Test script into `browser/test-ui01.mjs`. `tests/test_staging_request_policy.py` and `docs/verification/rms-si-ui01-browser-evidence.md` are review/test contracts, not private results. `.env.example` contains development placeholders only.
- `requirements.lock` and `requirements-staging.lock` pin Python distributions with SHA-256 hashes; `staging/browser/package-lock.json` pins npm dependencies. Docker uses version tags `python:3.13.15-slim-bookworm`, `postgres:17.11-bookworm`, and the operator-reviewed browser image `mcr.microsoft.com/playwright:v1.56.1-noble`. **Those tags are mutable**, not immutable image pins: record resolved registry digests and platform at each actual build, and refuse to claim byte-identical image rebuilds without them. The package records an archive SHA-256 and static JS SHA-256; record adapter/configuration SHA-256 and the resulting app image ID separately.
- `staging/legacy/`, `staging/dist/`, `secrets/`, `backups/`, `test-results/`, local credentials, host archives and unrestricted evidence are **not** source inputs; do not add them to Git or a PR. The original fictional product commit must remain reachable in the fetched Git history.

## Reproduce the package from a clean checkout

On an approved build machine with Git, Bash, coreutils, tar and gzip, use the **reviewed PR head SHA** supplied by the Director. Build locally only; no Docker, VPS access, credentials or network service operation is required for this step:

```sh
git clone https://github.com/dieg0andres/mv-rms.git mv-rms-rebuild
cd mv-rms-rebuild
git fetch origin pull/PR_NUMBER/head:refs/remotes/origin/review-staging
# Verify the announced immutable PR SHA before building; never build a moving ref unexamined.
test "$(git rev-parse refs/remotes/origin/review-staging)" = "REVIEWED_PR_HEAD_SHA"
git checkout --detach REVIEWED_PR_HEAD_SHA
test "$(git rev-parse 0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0^{tree})" = c1219ad5bd24bbb43b11f74938c7b2b4c8e08f77
test -z "$(git status --porcelain)"
OUTPUT=$(mktemp -d)
bash staging/build-package.sh "$OUTPUT"
(cd "$OUTPUT" && sha256sum -c product.tar.gz.sha256)
git archive --format=tar 0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0 | gzip -n | sha256sum
sha256sum "$OUTPUT"/{metadata.json,Dockerfile,compose.yaml,runtime.py,request_policy.py,requirements-staging.lock,entrypoint.sh,create-principals.py}
sha256sum "$OUTPUT"/browser/*
cmp tests/browser/test-ui01.mjs "$OUTPUT/browser/test-ui01.mjs"
```

Compare the archive hash from the second pipeline with `product.tar.gz.sha256`, the `metadata.json` commit/tree/static digest with the product Git object, and recorded adapter/runner hashes with the reviewed PR head. A second build to a different empty output directory should yield the same archive hash and manifest for the same checkout. The script refuses to overwrite an existing package; retain or remove disposable build outputs according to the approved local workspace procedure, never add them to Git. A package built at PR HEAD is **not** evidence of deployment or independent verification.

## Configuration contract (operator-owned, not executed here)

`staging/compose.yaml` deliberately has no committed private endpoint or host secret path. The authorized operator supplies `RMS_STAGING_HOST` (approved exact private hostname **with port**) and `RMS_STAGING_SECRETS_DIR` (absolute, access-controlled directory containing `db_password` and `django_key`) using an approved out-of-repository injection method before reviewing `docker compose config`. `RMS_STAGING_ORIGIN` is `https://` plus that same host and port, **without** a trailing slash, for the unauthenticated preflight only. No desktop password helper is packaged; the operator uses an approved browser/credential handoff outside this package. Never put passwords or a secret-bearing `.env` in the repository, package, issue, or logs. A wrong/unset host, unsafe Origin or unknown credential must fail closed; do not weaken the policy to make a preview work.

The package's `compose.yaml` is a template, **not** a live host inventory. Its project/volume/ports, Linux user, secret-file permissions, DNS/private TLS, DB isolation, installed Docker/Tailscale behavior, image platform/digests and host resource limits require operator confirmation against the actual approved environment. This PR neither runs Compose nor modifies the working staging instance. Existing immutable evidence and any failed attempts must be retained. Operations owns deployment/update, backups and recovery, and must review migration failure/restore behavior before any authorized host change. No new migration is introduced by this recipe. A local checksum or database dump does not establish independent evidence custody or off-VPS recovery.

`staging/browser/HEADLESS.md` describes the separate operator-run Test route; `tests/browser/test-ui01.mjs` is its reviewed, synthetic-only input. Test independently reviews the **exact PR head**, preconditions, redacted artifacts and failures; no operator/browser action here grants research or Risk acceptance. Consult the latest MAU-95 verdict rather than treating the historical UI-01 INCONCLUSIVE entry in `docs/verification/rms-si-1-independent-verification-report.md` as a current verdict. No real data, public route, live connector, trading, merge or deployment is part of this PR.
