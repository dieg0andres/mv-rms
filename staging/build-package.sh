#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
commit=0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0
tree=c1219ad5bd24bbb43b11f74938c7b2b4c8e08f77
test "$(git rev-parse "$commit^{tree}")" = "$tree"
output=${1:?usage: staging/build-package.sh OUTPUT_DIRECTORY}
mkdir -p "$output"
output=$(realpath "$output")
test ! -e "$output/metadata.json" || { echo 'Refusing to overwrite an existing package' >&2; exit 1; }
git archive --format=tar "$commit" | gzip -n > "$output/product.tar.gz"
(cd "$output" && sha256sum product.tar.gz > product.tar.gz.sha256)
static_sha256=$(git show "$commit:static/rms/rms_forms.js" | sha256sum | cut -d' ' -f1)
printf '{"commit":"%s","tree":"%s","static_sha256":"%s","summary":"Initial Source-to-Idea demonstration; fictional data only."}\n' \
  "$commit" "$tree" "$static_sha256" > "$output/metadata.json"
cp staging/{Dockerfile,compose.yaml,entrypoint.sh,requirements-staging.lock,runtime.py,request_policy.py,create-principals.py,README.md} "$output/"
mkdir -p "$output/browser"
cp staging/browser/{package.json,package-lock.json,open-staging.mjs,preflight-headless.mjs,HEADLESS.md} "$output/browser/"
cp tests/browser/test-ui01.mjs "$output/browser/"
printf '%s\n' 'secrets/' 'backups/' > "$output/.gitignore"
printf 'Candidate %s; tree %s; static SHA-256 %s\n' "$commit" "$tree" "$static_sha256"
