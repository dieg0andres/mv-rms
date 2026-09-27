#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != --verify ]; }; then
  echo 'Usage: provision-workspace.sh [--verify]' >&2
  exit 2
fi
tool_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace=$(git rev-parse --show-toplevel)
lock="$workspace/requirements.lock"
if [ ! -f "$lock" ]; then
  if [ "${1:-}" = --verify ]; then echo 'No lock to verify.' >&2; exit 1; fi
  echo 'RMS dependencies NOT APPLICABLE: this checkout has no requirements.lock; no virtualenv was provisioned.'
  exit 0
fi
test -x "$tool_root/bin/uv" && test -x "$tool_root/bin/python3.13" || {
  echo 'RMS toolchain missing; run reviewed bootstrap with Operations.' >&2
  exit 1
}
exec 8>"$tool_root/bootstrap.lock"
flock -s 8
mkdir -p "$tool_root/cache/workspace-locks"
workspace_key=$(printf '%s' "$workspace" | sha256sum | cut -c1-32)
exec 9>"$tool_root/cache/workspace-locks/$workspace_key.lock"
flock -x 9
uv_digest=$(sha256sum "$tool_root/bin/uv" | cut -d ' ' -f1)
python_digest=$(sha256sum "$tool_root/bin/python3.13" | cut -d ' ' -f1)
test "$uv_digest" = 242e462a63f5a3c0421d68557006193ecbfb61321cba0fe8542213ac62d92563 || {
  echo 'Unexpected uv binary hash; preserve environment and investigate.' >&2; exit 1;
}
test "$python_digest" = 20a5569a1bac8de02122347777b6cf2ae12ec1eafd42db990c6a0c5407f96b8e || {
  echo 'Unexpected Python binary hash; preserve environment and investigate.' >&2; exit 1;
}
lock_digest=$(sha256sum "$lock" | cut -d ' ' -f1)
venv="$workspace/.venv"
marker="$venv/.rms-python-state"
export UV_CACHE_DIR="$tool_root/cache" UV_PYTHON_INSTALL_DIR="$tool_root/python"
verify() {
  test -x "$venv/bin/python" && test -f "$marker" || {
    echo 'Unmarked or incomplete virtualenv; preserve it and use an Operations-controlled clean checkout.' >&2; exit 1;
  }
  interpreter=$(
    "$venv/bin/python" -I -c 'import os, sys; print("Python " + sys.version.split()[0] + " " + os.path.realpath(sys._base_executable))'
  )
  test "$interpreter" = "Python 3.13.15 $(readlink -f "$tool_root/bin/python3.13")" || {
    echo 'Wrong virtualenv interpreter; preserve it and reprovision a clean checkout.' >&2; exit 1;
  }
  freeze_digest=$("$tool_root/bin/uv" --no-config pip freeze --python "$venv/bin/python" | sha256sum | cut -d ' ' -f1)
  expected=$(printf 'workspace=%s\nlock=%s\nuv=%s\npython=%s\npackages=%s' "$workspace" "$lock_digest" "$uv_digest" "$python_digest" "$freeze_digest")
  test "$(cat "$marker")" = "$expected" || {
    echo 'Virtualenv marker/lock/packages mismatch; preserve it and reprovision a clean checkout.' >&2; exit 1;
  }
  "$tool_root/bin/uv" --quiet --no-config pip sync --check --python "$venv/bin/python" \
    --require-hashes --only-binary :all: --index-url https://pypi.org/simple "$lock"
}
if [ -e "$venv" ]; then
  verify
elif [ "${1:-}" = --verify ]; then
  echo 'No virtualenv to verify; provision this exact checkout first.' >&2
  exit 1
else
  "$tool_root/bin/uv" --no-config venv --python "$tool_root/bin/python3.13" "$venv"
  "$tool_root/bin/uv" --no-config pip sync --python "$venv/bin/python" \
    --require-hashes --only-binary :all: --index-url https://pypi.org/simple "$lock"
  test "$("$venv/bin/python" -I -c 'import os, sys; print("Python " + sys.version.split()[0] + " " + os.path.realpath(sys._base_executable))')" = "Python 3.13.15 $(readlink -f "$tool_root/bin/python3.13")"
  freeze_digest=$("$tool_root/bin/uv" --no-config pip freeze --python "$venv/bin/python" | sha256sum | cut -d ' ' -f1)
  printf 'workspace=%s\nlock=%s\nuv=%s\npython=%s\npackages=%s\n' "$workspace" "$lock_digest" "$uv_digest" "$python_digest" "$freeze_digest" > "$marker.new"
  mv "$marker.new" "$marker"
  verify
fi
if [ "${1:-}" != --verify ]; then printf 'RMS locked workspace verified: %s / Python 3.13.15\n' "$workspace"; fi
