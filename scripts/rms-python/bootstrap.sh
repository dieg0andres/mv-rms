#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ] || [[ "$1" != /* ]]; then
  echo 'Usage: bash scripts/rms-python/bootstrap.sh /absolute/project-local/toolchains/rms' >&2
  exit 2
fi
tool_root="$1"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$tool_root/bin" "$tool_root/python" "$tool_root/cache" "$tool_root/bootstrap/backups"
tool_root=$(cd -- "$tool_root" && pwd)
exec 9>"$tool_root/bootstrap.lock"
flock -x 9
installer="$tool_root/bootstrap/install-uv-0.12.19.sh"
if [ ! -f "$installer" ]; then
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --output "$installer" \
    https://github.com/astral-sh/uv/releases/download/0.12.19/uv-installer.sh
fi
printf '%s  %s\n' 61b349611f1b6e1ba33645f30c36da5287df2609dd7af8605d96a031435eb35b "$installer" | sha256sum --check --status
if [ ! -e "$tool_root/bin/uv" ]; then
  UV_UNMANAGED_INSTALL="$tool_root/bin" sh "$installer"
fi
printf '%s  %s\n' 242e462a63f5a3c0421d68557006193ecbfb61321cba0fe8542213ac62d92563 "$tool_root/bin/uv" | sha256sum --check --status || {
  echo 'Existing uv binary is not the reviewed artifact; preserve and investigate.' >&2; exit 1;
}
test "$("$tool_root/bin/uv" --version)" = 'uv 0.12.19 (x86_64-unknown-linux-gnu)' || {
  echo 'Expected uv 0.12.19 on Linux x86_64; stop before provisioning.' >&2; exit 1;
}
export UV_CACHE_DIR="$tool_root/cache" UV_PYTHON_INSTALL_DIR="$tool_root/python"
"$tool_root/bin/uv" --no-config python install --no-bin 3.13.15
managed_python="$tool_root/python/cpython-3.13.15-linux-x86_64-gnu/bin/python3.13"
if [ ! -x "$managed_python" ] || [ "$(realpath -e -- "$managed_python")" != "$managed_python" ]; then
  echo 'Managed Python must be a persistent executable in the pinned tool root; preserve and investigate.' >&2
  exit 1
fi
printf '%s  %s\n' 20a5569a1bac8de02122347777b6cf2ae12ec1eafd42db990c6a0c5407f96b8e "$managed_python" | sha256sum --check --status || {
  echo 'Existing Python binary is not the reviewed artifact; preserve and investigate.' >&2; exit 1;
}
test "$("$managed_python" --version)" = 'Python 3.13.15'
stage=$(mktemp -d "$tool_root/bootstrap/stage.XXXXXXXX")
install -m 755 "$script_dir/python3" "$stage/python3"
install -m 755 "$script_dir/provision-workspace.sh" "$stage/provision-workspace.sh"
install -m 644 "$script_dir/shell-env.sh" "$stage/shell-env.sh"
ln -s "$managed_python" "$stage/python3.13"
ln -s python3 "$stage/python"
backup="$tool_root/bootstrap/backups/$(date -u +%Y%m%dT%H%M%S%N)"
mkdir "$backup"
for file in bin/python3 bin/python bin/python3.13 provision-workspace.sh shell-env.sh; do
  if [ -e "$tool_root/$file" ] || [ -L "$tool_root/$file" ]; then
    cp -a -- "$tool_root/$file" "$backup/$(basename "$file")"
  fi
done
mv -fT "$stage/python3.13" "$tool_root/bin/python3.13"
mv -fT "$stage/python3" "$tool_root/bin/python3"
mv -fT "$stage/python" "$tool_root/bin/python"
mv -fT "$stage/provision-workspace.sh" "$tool_root/provision-workspace.sh"
mv -fT "$stage/shell-env.sh" "$tool_root/shell-env.sh"
test "$(readlink -- "$tool_root/bin/python3.13")" = "$managed_python" || {
  echo 'Installed Python helper does not target the persistent managed interpreter; restore the saved backup.' >&2; exit 1;
}
manifest="$tool_root/bootstrap/manifest-$(date -u +%Y%m%dT%H%M%S%N).sha256"
{
  printf 'OS: '; cat /etc/os-release | sed -n 's/^PRETTY_NAME=//p' | head -1
  printf 'Architecture: '; uname -m
  printf 'Tool root: %s\n' "$tool_root"
  printf 'Provider: Astral uv 0.12.19 / python-build-standalone CPython 3.13.15 (provider distribution can change)\n'
} > "${manifest%.sha256}.metadata"
sha256sum "$installer" "$tool_root/bin/uv" "$managed_python" \
  "$tool_root/bin/python3" "$tool_root/provision-workspace.sh" "$tool_root/shell-env.sh" > "$manifest"
sha256sum --check --status "$manifest"
printf 'RMS toolchain ready: %s (%s); manifest: %s; helper backup: %s\n' "$tool_root" "$("$tool_root/bin/python3.13" --version)" "$manifest" "$backup"
