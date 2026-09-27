#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ] || [[ "$1" != /* ]]; then
  echo 'Usage: bash scripts/rms-python/bootstrap.sh /absolute/project-local/toolchains/rms' >&2
  exit 2
fi
tool_root="$1"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$tool_root/bin" "$tool_root/python" "$tool_root/cache" "$tool_root/bootstrap"
tool_root=$(cd -- "$tool_root" && pwd)
installer="$tool_root/bootstrap/install-uv-0.12.19.sh"
if [ ! -f "$installer" ]; then
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --output "$installer" \
    https://github.com/astral-sh/uv/releases/download/0.12.19/uv-installer.sh
fi
echo '61b349611f1b6e1ba33645f30c36da5287df2609dd7af8605d96a031435eb35b  '"$installer" | sha256sum --check --status
if [ ! -x "$tool_root/bin/uv" ]; then
  UV_UNMANAGED_INSTALL="$tool_root/bin" sh "$installer"
fi
test "$("$tool_root/bin/uv" --version)" = 'uv 0.12.19 (x86_64-unknown-linux-gnu)' || {
  echo 'Expected uv 0.12.19 on Linux x86_64; stop before provisioning.' >&2
  exit 1
}
export UV_CACHE_DIR="$tool_root/cache" UV_PYTHON_INSTALL_DIR="$tool_root/python"
"$tool_root/bin/uv" --no-config python install --no-bin 3.13.15
managed_python=$("$tool_root/bin/uv" --no-config python find --managed-python --no-project 3.13.15)
test "$("$managed_python" --version)" = 'Python 3.13.15'
ln -sfn "$managed_python" "$tool_root/bin/python3.13"
install -m 755 "$script_dir/python3" "$tool_root/bin/python3"
ln -sfn python3 "$tool_root/bin/python"
install -m 755 "$script_dir/provision-workspace.sh" "$tool_root/provision-workspace.sh"
install -m 644 "$script_dir/shell-env.sh" "$tool_root/shell-env.sh"
printf 'RMS toolchain ready: %s (%s)\n' "$tool_root" "$("$tool_root/bin/python3.13" --version)"
