#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ] || [[ "$1" != /* ]]; then
  echo 'Usage: bash scripts/rms-python/bootstrap-postgres-test.sh /absolute/project-local/toolchains/rms' >&2
  exit 2
fi
. /etc/os-release
if [ "$ID" != debian ] || [ "$VERSION_ID" != 13 ] || [ "$(uname -m)" != x86_64 ]; then
  echo 'Only Debian 13 x86_64 is supported by these pinned packages.' >&2
  exit 1
fi
tool_root=$(cd -- "$1" && pwd)
test -x "$tool_root/bin/python3.13" || { echo 'Bootstrap the RMS Python toolchain first.' >&2; exit 1; }
exec 9>"$tool_root/bootstrap.lock"
flock -x 9
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root="$tool_root/postgres-test"
mkdir -p "$root/packages"
package() {
  local name="$1" path="$2" digest="$3" target="$root/packages/$1.deb"
  if [ ! -f "$target" ]; then
    curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
      "https://deb.debian.org/debian/$path" -o "$target"
  fi
  printf '%s  %s\n' "$digest" "$target" | sha256sum --check --status || {
    echo "Unexpected $name package digest; preserve and investigate before retrying." >&2
    exit 1
  }
}
package postgresql-17 pool/main/p/postgresql-17/postgresql-17_17.11-0+deb13u1_amd64.deb d2ce1ddffafa783f9acda4c92c86fc21e8288bff3782d739294f14fa797d7886
package postgresql-client-17 pool/main/p/postgresql-17/postgresql-client-17_17.11-0+deb13u1_amd64.deb 9d8558f8dd57c8e92e218a20698383575d53742ca3f9e7c2b7fe5f246d5216ae
package libpq5 pool/main/p/postgresql-17/libpq5_17.11-0+deb13u1_amd64.deb 20a4c9ef58b4baf90deda67cfb2cc062871c062830dddc234d28f5ac7931b86b
package libxml2 pool/main/libx/libxml2/libxml2_2.12.7+dfsg+really2.9.14-2.1+deb13u3_amd64.deb e0c6b63ce4602a036a526f60fe5e6c1586710688058d98fc1001b9b3147b7efd
package libicu76 pool/main/i/icu/libicu76_76.1-4_amd64.deb c1bf762996de9ecba9b9d871e4928a8090f023a3e9e7fa3240b3d90f892a01dc
package libreadline8t64 pool/main/r/readline/libreadline8t64_8.2-6_amd64.deb eeadf2b5e755c9f183883feea2d9b5b28560284275d5f54d3e55d0923b1d0967
if [ ! -d "$root/pg17" ]; then
  if [ -e "$root/pg17.next" ]; then
    echo 'Partial extraction at pg17.next; investigate rather than overwriting it.' >&2
    exit 1
  fi
  mkdir "$root/pg17.next"
  for name in postgresql-17 postgresql-client-17 libpq5 libxml2 libicu76 libreadline8t64; do
    dpkg-deb -x "$root/packages/$name.deb" "$root/pg17.next"
  done
  mv "$root/pg17.next" "$root/pg17"
fi
export LD_LIBRARY_PATH="$root/pg17/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
bin_dir="$root/pg17/usr/lib/postgresql/17/bin"
printf '%s  %s\n' 6468a969338215cb3912cf9c0b894bdbbd37b9a709926db078e9a5bf8bdc3e16 "$bin_dir/postgres" | sha256sum --check --status || { echo 'Unexpected PostgreSQL server binary; preserve it.' >&2; exit 1; }
test "$("$bin_dir/postgres" --version)" = 'postgres (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1)' || {
  echo 'Unexpected existing PostgreSQL binary; stop without overwriting.' >&2
  exit 1
}
install -m 755 "$script_dir/postgres-test.sh" "$tool_root/postgres-test.sh"
install -m 644 "$script_dir/postgres-test-env.sh" "$tool_root/postgres-test-env.sh"
printf 'Project-local PostgreSQL 17.11 ready at %s (no host install, no server started)\n' "$root"
