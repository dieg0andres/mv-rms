#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${RMS_SYNTHETIC_TOOL_ROOT:?Set to the existing authorized fixture tool root}"
: "${RMS_REHEARSAL_SCRATCH:?Set to a fresh run-owned output directory}"
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export DJANGO_SETTINGS_MODULE=rms_project.settings PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
source "$RMS_SYNTHETIC_TOOL_ROOT/postgres-test-env.sh"
fixture="$RMS_SYNTHETIC_TOOL_ROOT/postgres-test"
bin="$fixture/pg17/usr/lib/postgresql/17/bin"
export LD_LIBRARY_PATH="$fixture/pg17/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
[[ "$RMS_DB_HOST" == /tmp/rms-pg-* && "$RMS_DB_PORT:$RMS_DB_NAME:$RMS_DB_USER" == 55471:rms_synthetic:rms_synthetic_test ]]
[[ $(readlink -- "$RMS_DB_HOST") == "$fixture/socket" ]]
unset PGHOSTADDR PGSERVICE PGOPTIONS
export PGHOST="$RMS_DB_HOST" PGPORT="$RMS_DB_PORT"
pg() { "$bin/psql" -Xwq -v ON_ERROR_STOP=1 "$@"; }
[[ $(pg -U "$RMS_DB_USER" -d "$RMS_DB_NAME" -Atc "SELECT current_user || ':' || (current_setting('server_version_num')::int / 10000) WHERE inet_server_addr() IS NULL") == rms_synthetic_test:17 ]]
mkdir -- "$RMS_REHEARSAL_SCRATCH"
out=$(realpath "$RMS_REHEARSAL_SCRATCH")
tag="mau162_$(date -u +%s)_$$_$RANDOM"
owner="${tag}_owner" runtime="${tag}_runtime" source_db="${tag}_source" restore_db="${tag}_restore"
admin() { pg -U rms_local_admin -d postgres "$@"; }
admin -1 -v owner="$owner" -v runtime="$runtime" <<'SQL'
CREATE ROLE :"owner" LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
CREATE ROLE :"runtime" LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
SQL
made_source=0 made_restore=0
cleanup() {
    local result=$?
    trap - EXIT
    if [[ "$made_restore" == 1 ]]; then "$bin/dropdb" -w -U rms_local_admin "$restore_db" || result=1; fi
    if [[ "$made_source" == 1 ]]; then "$bin/dropdb" -w -U rms_local_admin "$source_db" || result=1; fi
    admin -1 -v owner="$owner" -v runtime="$runtime" <<'SQL' || result=1
DROP ROLE :"runtime", :"owner";
SQL
    printf 'fixture cleanup exit=%s (source=%s restore=%s)\n' "$result" "$source_db" "$restore_db"
    exit "$result"
}
trap cleanup EXIT
"$bin/createdb" -w -U rms_local_admin --owner="$owner" --template=template0 "$source_db"
made_source=1
"$bin/createdb" -w -U rms_local_admin --owner="$owner" --template=template0 "$restore_db"
made_restore=1

manage() { RMS_DB_USER="$owner" RMS_DB_NAME="$source_db" .venv/bin/python manage.py "$@"; }
check() { RMS_DB_USER="$1" RMS_DB_NAME="$2" .venv/bin/python scripts/rms-python/runtime-grants-check.py "${@:3}"; }
crypto() {
    pg -U rms_local_admin -d "$1" -v target_db="$1" -v ddl_owner="$owner" -v runtime_role="$runtime" \
        -f scripts/rms-python/runtime-pgcrypto.sql
}
grants() {
    pg -U "$owner" -d "$1" -v target_db="$1" -v ddl_owner="$owner" -v runtime_role="$runtime" \
        -v rms_leaf="$2" -f scripts/rms-python/runtime-grants.sql
}
snapshot() {
    pg -At -U "$owner" -d "$1" -v scope="$2" <<'SQL'
SELECT format('SELECT %L, count(*), encode(public.digest(convert_to(coalesce(string_agg(data, E''\n'' ORDER BY data COLLATE "C"), ''''), ''UTF8''), ''sha256''), ''hex'') FROM (SELECT row_to_json(t)::text AS data FROM %I.%I t %s) s', tablename,schemaname,tablename,
  CASE WHEN :'scope'='baseline' AND tablename='django_content_type' THEN
    $$WHERE NOT (app_label='rms' AND model IN ('runattempt','runlifecycleevent','runretry','runresultversion'))$$
  WHEN :'scope'='baseline' AND tablename='auth_permission' THEN
    $$WHERE content_type_id NOT IN (SELECT id FROM public.django_content_type
       WHERE app_label='rms' AND model IN ('runattempt','runlifecycleevent','runretry','runresultversion'))$$
  ELSE '' END)
FROM pg_tables WHERE schemaname='public'
  AND (:'scope'='all' OR (tablename <> 'django_migrations' AND tablename !~ '^rms_run'))
ORDER BY tablename \gexec
SELECT format('SELECT %L, last_value, is_called FROM %I.%I', sequencename,schemaname,sequencename)
FROM pg_sequences WHERE schemaname='public' AND (:'scope'='all' OR sequencename NOT IN ('django_migrations_id_seq','auth_permission_id_seq','django_content_type_id_seq'))
ORDER BY sequencename \gexec
SQL
}

manage migrate rms 0007 --noinput --verbosity 0
manage migrate auth --noinput --verbosity 0
check "$owner" "$source_db" principals
crypto "$source_db"
grants "$source_db" 0007_test_plan_history_guards
check "$runtime" "$source_db" seed > "$out/plan.json"
snapshot "$source_db" baseline > "$out/before.tsv"
manage migrate rms 0008 --noinput --verbosity 0
grants "$source_db" 0008_run_attempts
snapshot "$source_db" baseline > "$out/after-0008.tsv"
cmp "$out/before.tsv" "$out/after-0008.tsv"
run=$(check "$runtime" "$source_db" register "$out/plan.json")
snapshot "$source_db" all | rg '^rms_(runattempt|idempotencyrecord)\|' > "$out/registration-before.tsv"
manage migrate rms 0009 --noinput --verbosity 0
grants "$source_db" 0009_run_results
snapshot "$source_db" baseline > "$out/after-0009.tsv"
# Registration legitimately adds an idempotency receipt; compare everything else.
cmp <(rg -v '^rms_idempotencyrecord\|' "$out/before.tsv") <(rg -v '^rms_idempotencyrecord\|' "$out/after-0009.tsv")
snapshot "$source_db" all | rg '^rms_(runattempt|idempotencyrecord)\|' > "$out/registration-after.tsv"
cmp "$out/registration-before.tsv" "$out/registration-after.tsv"
check "$runtime" "$source_db" results "$out/plan.json" "$run" "$owner" > "$out/replay.json"
snapshot "$source_db" all > "$out/source.tsv"
"$bin/pg_dump" -w -Fc -U "$owner" -d "$source_db" -f "$out/synthetic.dump"
SECONDS=0
"$bin/pg_restore" -w --single-transaction --exit-on-error --no-owner --no-acl -U "$owner" -d "$restore_db" "$out/synthetic.dump"
crypto "$restore_db"
grants "$restore_db" 0009_run_results
snapshot "$restore_db" all > "$out/restore.tsv"
cmp "$out/source.tsv" "$out/restore.tsv"
check "$runtime" "$restore_db" restore "$out/plan.json" "$out/replay.json" "$owner"
printf 'PASS PostgreSQL 17: 0007 -> 0008 registration -> 0009 results; restore+grants+verification %ss\n' "$SECONDS"
