#!/usr/bin/env bash
set -euo pipefail
umask 077
if [ "$#" -ne 1 ]; then
  echo 'Usage: postgres-test.sh {init|start|stop|reset|status}' >&2
  exit 2
fi
tool_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root="$tool_root/postgres-test"
bin_dir="$root/pg17/usr/lib/postgresql/17/bin"
data_dir="$root/data"
socket_dir="$root/socket"
socket_alias="/tmp/rms-pg-$(printf '%s' "$root" | sha256sum | cut -c1-16)"
port=55471
export LD_LIBRARY_PATH="$root/pg17/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
test -x "$bin_dir/postgres" || { echo 'Run bootstrap-postgres-test.sh first.' >&2; exit 1; }
case "$root" in *"'"*|*$'\n'*) echo 'Unsupported tool path.' >&2; exit 1;; esac
check_data() {
  test -f "$data_dir/PG_VERSION" && test "$(cat "$data_dir/PG_VERSION")" = 17 || {
    echo 'Missing or unexpected test cluster; run init or investigate.' >&2
    exit 1
  }
}
running() { "$bin_dir/pg_ctl" -D "$data_dir" status >/dev/null 2>&1; }
connect_admin() { "$bin_dir/psql" -X -w -v ON_ERROR_STOP=1 -h "$socket_alias" -p "$port" -U rms_local_admin -d postgres "$@"; }
initialize() {
  if [ -e "$data_dir" ]; then
    check_data
    return
  fi
  mkdir -p "$socket_dir"
  chmod 700 "$socket_dir"
  "$bin_dir/initdb" -D "$data_dir" -U rms_local_admin -A trust -E UTF8 --locale=C --no-instructions
}
start() {
  check_data
  mkdir -p "$socket_dir"
  chmod 700 "$socket_dir"
  if [ -L "$socket_alias" ]; then
    test "$(readlink -- "$socket_alias")" = "$socket_dir" || { echo "Unexpected socket alias; stop and investigate." >&2; exit 1; }
  elif [ -e "$socket_alias" ]; then
    echo "Occupied socket alias; stop and investigate." >&2
    exit 1
  else
    ln -s "$socket_dir" "$socket_alias"
  fi
  if ! running; then
    "$bin_dir/pg_ctl" -D "$data_dir" -l "$root/server.log" \
      -o "-c listen_addresses='' -c unix_socket_directories='$socket_alias' -c unix_socket_permissions=0700 -p $port" -w start
  fi
  if [ "$(connect_admin -Atc "SELECT count(*) FROM pg_roles WHERE rolname = 'rms_synthetic_test' AND rolcreatedb AND NOT rolsuper AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls")" != 1 ]; then
    if [ "$(connect_admin -Atc "SELECT count(*) FROM pg_roles WHERE rolname = 'rms_synthetic_test'")" != 0 ]; then
      echo 'Unexpected existing test role privileges; stop and investigate.' >&2
      exit 1
    fi
    connect_admin -c 'CREATE ROLE rms_synthetic_test LOGIN CREATEDB NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS'
  fi
  if [ "$(connect_admin -Atc "SELECT count(*) FROM pg_database WHERE datname = 'rms_synthetic' AND datdba = (SELECT oid FROM pg_roles WHERE rolname = 'rms_synthetic_test')")" != 1 ]; then
    if [ "$(connect_admin -Atc "SELECT count(*) FROM pg_database WHERE datname = 'rms_synthetic'")" != 0 ]; then
      echo 'Unexpected existing test database owner; stop and investigate.' >&2
      exit 1
    fi
    "$bin_dir/createdb" -w -h "$socket_alias" -p "$port" -U rms_local_admin -O rms_synthetic_test rms_synthetic
  fi
  "$bin_dir/psql" -X -w -At -h "$socket_alias" -p "$port" -U rms_synthetic_test -d rms_synthetic -c 'SELECT current_user, current_database()'
}
case "$1" in
  init) initialize ;;
  start) start ;;
  stop) check_data; if running; then "$bin_dir/pg_ctl" -D "$data_dir" -m fast -w stop; fi ;;
  status) check_data; "$bin_dir/pg_ctl" -D "$data_dir" status ;;
  reset)
    check_data
    if running; then echo 'Stop the test server and coordinate with Test before resetting.' >&2; exit 1; fi
    mkdir -p "$root/archive"
    mv "$data_dir" "$root/archive/data-$(date -u +%Y%m%dT%H%M%S%N)"
    initialize
    start
    ;;
  *) echo 'Usage: postgres-test.sh {init|start|stop|reset|status}' >&2; exit 2 ;;
esac
