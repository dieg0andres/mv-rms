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
interpreter="$PWD/.venv/bin/python"
historic="$out/pre-event-evidence"
mkdir -- "$historic"
# Populate the old schema using its own models and original immutable digests.
git archive 017927f18b0b1150a23bb824e16947aac99beefd | tar -x -C "$historic"
RMS_REHEARSAL_PASSWORD=$(.venv/bin/python -c 'from secrets import token_urlsafe; print(token_urlsafe(32))')
export RMS_REHEARSAL_PASSWORD
if [[ -n ${RMS_REHEARSAL_PACKAGE:-} ]]; then
    .venv/bin/python staging/check-release-assets.py "$RMS_REHEARSAL_PACKAGE" "$out"
fi
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
historic_check() (
    cd "$historic"
    PYTHONPATH="$historic" RMS_DB_USER="$1" RMS_DB_NAME="$2" "$interpreter" scripts/rms-python/runtime-grants-check.py "${@:3}"
)
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
  AND (:'scope'='all'
       OR (:'scope'='baseline' AND tablename <> 'django_migrations' AND tablename !~ '^rms_run')
       OR (:'scope'='pre_assurance' AND tablename NOT IN ('django_migrations','auth_permission','django_content_type',
                                                         'rms_runreview','rms_rundecision','rms_runlesson')))
ORDER BY tablename \gexec
SELECT format('SELECT %L, last_value, is_called FROM %I.%I', sequencename,schemaname,sequencename)
FROM pg_sequences WHERE schemaname='public' AND (:'scope'='all' OR sequencename NOT IN ('django_migrations_id_seq','auth_permission_id_seq','django_content_type_id_seq'))
ORDER BY sequencename \gexec
SQL
}

inventory() {
    pg -At -U "$owner" -d "$1" -v runtime="$runtime" <<'SQL'
SELECT relname, relkind, pg_get_userbyid(relowner), relacl FROM pg_class
WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p','S') ORDER BY relname;
SELECT c.relname, t.tgname, t.tgenabled, p.proname, pg_get_userbyid(p.proowner), p.prosecdef,
       has_function_privilege(:'runtime', p.oid, 'EXECUTE'), pg_get_triggerdef(t.oid)
FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_proc p ON p.oid=t.tgfoid
WHERE c.relnamespace='public'::regnamespace AND NOT t.tgisinternal ORDER BY c.relname, t.tgname;
SQL
}

before_evidence() {
    snapshot "$1" all | grep -Ev '^(rms_runlifecycleevent|django_migrations|django_migrations_id_seq)\|'
    pg -At -U "$owner" -d "$1" -c "SELECT id, (to_jsonb(e) - 'partial_evidence_bytes' - 'partial_evidence_sha256')::text
        FROM public.rms_runlifecycleevent e ORDER BY id"
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
check "$runtime" "$source_db" readiness 503
snapshot "$source_db" baseline > "$out/after-0008.tsv"
cmp "$out/before.tsv" "$out/after-0008.tsv"
run=$(check "$runtime" "$source_db" register "$out/plan.json")
snapshot "$source_db" all | grep -E '^rms_(runattempt|idempotencyrecord)\|' > "$out/registration-before.tsv"
manage migrate rms 0009 --noinput --verbosity 0
grants "$source_db" 0009_run_results
snapshot "$source_db" baseline > "$out/after-0009.tsv"
# Registration legitimately adds an idempotency receipt; compare everything else.
cmp <(grep -Ev '^rms_idempotencyrecord\|' "$out/before.tsv") <(grep -Ev '^rms_idempotencyrecord\|' "$out/after-0009.tsv")
snapshot "$source_db" all | grep -E '^rms_(runattempt|idempotencyrecord)\|' > "$out/registration-after.tsv"
cmp "$out/registration-before.tsv" "$out/registration-after.tsv"
historic_check "$runtime" "$source_db" results "$out/plan.json" "$run" "$owner" > "$out/replay.json"
check "$runtime" "$source_db" readiness 503
snapshot "$source_db" pre_assurance > "$out/before-0010.tsv"
manage migrate rms 0010 --noinput --verbosity 0
grants "$source_db" 0010_run_assurance
snapshot "$source_db" pre_assurance > "$out/after-0010.tsv"
cmp "$out/before-0010.tsv" "$out/after-0010.tsv"
check "$runtime" "$source_db" readiness 503
historic_check "$runtime" "$source_db" assurance "$out/replay.json" "$owner" > "$out/assurance.json"
before_evidence "$source_db" > "$out/before-0011.tsv"
manage migrate rms 0011 --noinput --verbosity 0
grants "$source_db" 0011_run_event_evidence
before_evidence "$source_db" > "$out/after-0011.tsv"
cmp "$out/before-0011.tsv" "$out/after-0011.tsv"
check "$runtime" "$source_db" readiness 200
check "$runtime" "$source_db" event_evidence "$out/plan.json" > "$out/event-evidence.json"
inventory "$source_db" > "$out/source-inventory.tsv"
snapshot "$source_db" all > "$out/source.tsv"
"$bin/pg_dump" -w -Fc -U "$owner" -d "$source_db" -f "$out/synthetic.dump"
SECONDS=0
"$bin/pg_restore" -w --single-transaction --exit-on-error --no-owner --no-acl -U "$owner" -d "$restore_db" "$out/synthetic.dump"
crypto "$restore_db"
grants "$restore_db" 0011_run_event_evidence
inventory "$restore_db" > "$out/restore-inventory.tsv"
cmp "$out/source-inventory.tsv" "$out/restore-inventory.tsv"
snapshot "$restore_db" all > "$out/restore.tsv"
cmp "$out/source.tsv" "$out/restore.tsv"
check "$runtime" "$restore_db" restore "$out/plan.json" "$out/replay.json" "$owner"
check "$runtime" "$restore_db" assurance_restore "$out/assurance.json" "$owner"
check "$runtime" "$restore_db" event_evidence_restore "$out/event-evidence.json"
printf 'PASS PostgreSQL 17: 0007 -> 0008 registration -> 0009 results -> 0010 assurance -> 0011 event evidence; restore+grants+verification %ss\n' "$SECONDS"
