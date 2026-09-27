#!/usr/bin/env bash
set -euo pipefail
tool_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace=$(git rev-parse --show-toplevel)
if [ ! -f "$workspace/requirements.lock" ]; then
  echo 'No repository-declared requirements.lock at this checkout; stop before provisioning.' >&2
  exit 1
fi
test -x "$tool_root/bin/uv" && test -x "$tool_root/bin/python3.13" || {
  echo 'RMS toolchain missing; run the repository bootstrap with Operations.' >&2
  exit 1
}
export UV_CACHE_DIR="$tool_root/cache" UV_PYTHON_INSTALL_DIR="$tool_root/python"
if [ ! -x "$workspace/.venv/bin/python" ]; then
  "$tool_root/bin/uv" --no-config venv --python "$tool_root/bin/python3.13" "$workspace/.venv"
fi
"$tool_root/bin/uv" --no-config pip install --python "$workspace/.venv/bin/python" \
  --index-url https://pypi.org/simple --require-hashes --only-binary :all: --no-deps \
  -r "$workspace/requirements.lock"
"$workspace/.venv/bin/python" -c 'import sys, ssl, sqlite3, venv; print("RMS workspace Python ready:", sys.version.split()[0], sys.executable)'
