#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${PAPERCLIP_RUN_SCRATCH_DIR:?Use a disposable run-owned PostgreSQL cluster}"
: "${RMS_CUSTODY_PGBIN:?Provide the pinned PostgreSQL 17 bin directory}"
: "${RMS_DB_PORT:?Provide the private test socket port}"
: "${RMS_DB_HOST:?Provide the private test socket directory}"
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
[[ $(realpath "$RMS_DB_HOST") == "$(realpath "$PAPERCLIP_RUN_SCRATCH_DIR")"/* && -d "$RMS_DB_HOST" ]]
unset PGHOSTADDR PGSERVICE PGOPTIONS PGPASSWORD RMS_DB_PASSWORD
export PGHOST="$RMS_DB_HOST" PGPORT="$RMS_DB_PORT" PYTHONDONTWRITEBYTECODE=1 LC_ALL=C
pgbin="$RMS_CUSTODY_PGBIN"
pg() { "$pgbin/psql" -Xwq -v ON_ERROR_STOP=1 "$@"; }
[[ $(pg -At -U fixture_admin -d postgres -c "SELECT current_user || ':' || current_setting('server_version_num') WHERE inet_server_addr() IS NULL") == fixture_admin:170011 ]]
output=$(mktemp -d "$PAPERCLIP_RUN_SCRATCH_DIR/custody-rehearsal.XXXXXX")
tag="rms_ma170_rehearsal_$(date +%s)_$$_$RANDOM"
source_db="${tag}_src"
restore_db="${tag}_dst"
runtime="${tag}_rt"
verifier="${tag}_ver"
outsider="${tag}_out"
rejected_db="${tag}_rej"
admin() { pg -U fixture_admin "$@"; }
admin -d postgres -v runtime="$runtime" -v verifier="$verifier" -v outsider="$outsider" <<'SQL'
BEGIN;
CREATE ROLE :"runtime" LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
CREATE ROLE :"verifier" LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
CREATE ROLE :"outsider" LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
GRANT :"runtime" TO :"verifier" WITH INHERIT FALSE, SET TRUE;
COMMIT;
SQL
made_databases=()
cleanup() {
    local result=$? database
    trap - EXIT
    for database in "${made_databases[@]}"; do "$pgbin/dropdb" -w -U fixture_admin "$database" || result=1; done
    admin -d postgres -v runtime="$runtime" -v verifier="$verifier" -v outsider="$outsider" <<'SQL' || result=1
DROP ROLE :"verifier", :"runtime", :"outsider";
SQL
    printf 'cleanup exit=%s; local fixture receipts: %s\n' "$result" "$output"
    exit "$result"
}
trap cleanup EXIT
"$pgbin/createdb" -w -U fixture_admin -O fixture_owner --template=template0 "$source_db"
made_databases+=("$source_db")
manage() { RMS_DB_USER=fixture_owner RMS_DB_NAME="$source_db" .venv/bin/python manage.py "$@"; }
probe() {
    RMS_DB_USER="$1" RMS_DB_NAME="$2" RMS_CUSTODY_PROBE="$3" .venv/bin/python manage.py shell \
        -c 'from tests.custody_recovery_probe import main; main()' | tail -n 1
}

manage migrate auth --noinput --verbosity 0
manage migrate rms 0010_run_assurance --noinput --verbosity 0
admin -d "$source_db" -v target_db="$source_db" -v ddl_owner=fixture_owner -v runtime_role="$runtime" \
    -f scripts/rms-python/runtime-pgcrypto.sql
pg -U fixture_owner -d "$source_db" -v target_db="$source_db" -v ddl_owner=fixture_owner \
    -v runtime_role="$runtime" -v rms_leaf=0010_run_assurance -f scripts/rms-python/runtime-grants.sql
manage migrate rms 0010_synthetic_gate_events --noinput --verbosity 0
probe fixture_owner "$source_db" seed > "$output/pre.json"
"$pgbin/pg_dump" -w -U fixture_owner -Fc -f "$output/pre.dump" "$source_db"
manage migrate rms 0011_custody --noinput --verbosity 0
probe fixture_owner "$source_db" post-migration > "$output/post.json"

pg -U fixture_owner -d "$source_db" -v runtime="$runtime" <<'SQL'
BEGIN;
REVOKE ALL ON public.rms_custodyevent FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.rms_custody_event_guard() FROM PUBLIC, :"runtime";
GRANT SELECT, INSERT ON public.rms_custodyevent TO :"runtime";
GRANT SELECT ON public.rms_syntheticgateevent TO :"runtime";
COMMIT;
SQL
probe "$runtime" "$source_db" seal > "$output/sealed.json"
"$pgbin/pg_dump" -w -U fixture_owner -Fc -f "$output/sealed.dump" "$source_db"
chmod 0400 "$output/pre.dump" "$output/sealed.dump"
(cd "$output" && sha256sum pre.dump sealed.dump > dumps.sha256 && sha256sum -c dumps.sha256)
if (cd "$output" && awk '$2 == "sealed.dump" {print $1 "  pre.dump"}' dumps.sha256 | sha256sum -c --status); then
    printf 'Stale checkpoint was accepted in place of the sealed backup\n' >&2
    exit 1
fi
access_log="$output/restore-access.log"
record_access() { printf '%s\n' "$*" | tee -a "$access_log"; }

access_denied() {
    local target=$1 role=$2 phase=$3 expected=$4
    if pg -U "$role" -d "$target" -Atc 'SELECT 1' > "$output/connect.log" 2>&1; then
        printf '%s: %s unexpectedly connected to %s\n' "$phase" "$role" "$target" >&2
        return 1
    fi
    if ! rg -Fq "$expected" "$output/connect.log"; then
        cat "$output/connect.log" >&2
        return 1
    fi
    record_access "$phase db=$target login=$role: denied ($expected)"
}

ordinary_denied() {
    access_denied "$1" "$runtime" "$2" "$3" && access_denied "$1" "$outsider" "$2" "$3"
}

prepare_restore() {
    local target=$1
    admin -d postgres -v target_db="$target" <<'SQL'
CREATE DATABASE :"target_db" OWNER fixture_owner TEMPLATE template0 ALLOW_CONNECTIONS false;
SQL
    made_databases+=("$target")
    ordinary_denied "$target" created 'not currently accepting connections'
    admin -d postgres -v target_db="$target" -v runtime="$runtime" -v verifier="$verifier" -v outsider="$outsider" <<'SQL'
BEGIN;
REVOKE ALL ON DATABASE :"target_db" FROM PUBLIC, :"runtime", :"outsider";
GRANT CONNECT ON DATABASE :"target_db" TO :"verifier";
ALTER DATABASE :"target_db" ALLOW_CONNECTIONS true;
COMMIT;
SQL
    ordinary_denied "$target" before_import 'permission denied for database'
    "$pgbin/pg_restore" -w -U fixture_admin --exit-on-error --single-transaction -d "$target" "$output/sealed.dump"
    ordinary_denied "$target" after_import_before_reconciliation 'permission denied for database'
}

runtime_privileges() {
    local login=$1 target=$2
    [[ $(pg -U "$login" -d "$target" -At -v runtime="$runtime" <<'SQL'
SELECT current_user = :'runtime'
       AND has_table_privilege(current_user, 'rms_custodyevent', 'SELECT')
       AND has_table_privilege(current_user, 'rms_custodyevent', 'INSERT')
       AND NOT has_table_privilege(current_user, 'rms_custodyevent', 'UPDATE,DELETE,TRUNCATE,TRIGGER,MAINTAIN')
       AND NOT has_any_column_privilege(current_user, 'rms_custodyevent', 'UPDATE,REFERENCES')
       AND NOT has_function_privilege(current_user, 'rms_custody_event_guard()', 'EXECUTE')
       AND NOT has_database_privilege(current_user, current_database(), 'CREATE,TEMPORARY')
       AND NOT has_schema_privilege(current_user, 'public', 'CREATE');
SQL
    ) == t ]]
}

reconcile_and_release() {
    local target=$1 expected=$2 receipt=$3 comparison=0
    PGOPTIONS="-c role=$runtime" runtime_privileges "$verifier" "$target" || return 1
    PGOPTIONS="-c role=$runtime" probe "$verifier" "$target" verify > "$receipt" || return 1
    cmp -s "$expected" "$receipt" || comparison=$?
    if [[ "$comparison" == 1 ]]; then
        record_access "reconciliation_rejected db=$target verifier=$verifier effective_role=$runtime: checkpoint mismatch"
        return 42
    fi
    [[ "$comparison" == 0 ]] || return 1
    ordinary_denied "$target" reconciled_before_release 'permission denied for database' || return 1
    local receipt_sha256
    receipt_sha256=$(sha256sum < "$receipt" | cut -d' ' -f1) || return 1
    record_access "reconciliation_passed db=$target verifier=$verifier effective_role=$runtime receipt_sha256=$receipt_sha256" || return 1
    admin -d postgres -v target_db="$target" -v runtime="$runtime" -v verifier="$verifier" <<'SQL' || return 1
BEGIN;
REVOKE CONNECT ON DATABASE :"target_db" FROM :"verifier";
GRANT CONNECT ON DATABASE :"target_db" TO :"runtime";
COMMIT;
SQL
    record_access "release_committed db=$target login=$runtime"
}

runtime_privileges "$runtime" "$source_db"
prepare_restore "$rejected_db"
reject_status=0
reconcile_and_release "$rejected_db" "$output/pre.json" "$output/rejected.json" || reject_status=$?
[[ "$reject_status" == 42 ]]
ordinary_denied "$rejected_db" after_rejected_reconciliation 'permission denied for database'

prepare_restore "$restore_db"
reconcile_and_release "$restore_db" "$output/sealed.json" "$output/restored.json"
access_denied "$restore_db" "$outsider" after_release 'permission denied for database'
access_denied "$restore_db" "$verifier" after_release 'permission denied for database'
runtime_privileges "$runtime" "$restore_db"
record_access "after_release db=$restore_db login=$runtime: connected with expected runtime grants"
probe "$runtime" "$restore_db" verify > "$output/runtime-restored.json"
cmp "$output/restored.json" "$output/runtime-restored.json"
ordinary_denied "$rejected_db" after_separate_successful_release 'permission denied for database'

if manage migrate rms 0010_run_assurance --noinput --verbosity 0 > "$output/unsafe-reverse.log" 2>&1; then
    printf 'Populated reverse unexpectedly succeeded\n' >&2
    exit 1
fi
rg -q 'Refusing to reverse populated custody history' "$output/unsafe-reverse.log"
probe "$runtime" "$source_db" verify > "$output/reverse-protected.json"
cmp "$output/sealed.json" "$output/reverse-protected.json"

RMS_CUSTODY_OUTPUT="$output" .venv/bin/python - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess

output = Path(os.environ['RMS_CUSTODY_OUTPUT'])
def load(name):
    return json.loads((output / (name + '.json')).read_bytes())

pre, post, sealed, restored = map(load, ('pre', 'post', 'sealed', 'restored'))
assert pre['tables'] == {table: post['tables'][table] for table in pre['tables']}
assert pre['objects'] == post['objects'] == restored['objects']
assert post['tables']['rms_custodyevent']['count'] == 0
assert restored == sealed and sealed['tables']['rms_custodyevent']['count'] == 4
assert pre['watermark'] != restored['watermark']
manifest = {
    'schema': 'fixture:MAU-170:migration-restore:v2',
    'tools': subprocess.check_output([os.environ['RMS_CUSTODY_PGBIN'] + '/pg_restore', '--version'], text=True).strip(),
    'scope': 'disposable_local_invented_fixture_only',
    'migration_sha256': hashlib.sha256(Path('rms/migrations/0011_custody.py').read_bytes()).hexdigest(),
    'permissions': 'created closed; isolated verifier assumes runtime privileges; runtime connects only after reconciliation',
    'id_mapping': [{'source': item['result_version_id'], 'target': item['result_version_id']}
                   for item in pre['objects']],
    'pre_migration': pre, 'post_migration': post, 'restored': restored,
    'checks': {'preserved_history': True, 'populated_reverse_refused': True, 'restore_reconciled': True,
               'export_reproduced': True, 'stale_checkpoint_watermark_differs': True, 'scope_denials': True,
               'ordinary_access_denied_until_reconciled': True, 'rejected_target_never_released': True,
               'unrelated_login_denied_after_release': True},
    'restore_access_log_sha256': hashlib.sha256((output / 'restore-access.log').read_bytes()).hexdigest(),
    'rollback': 'Keep writes gated. Restore a new target from the matching checkpoint; never reverse populated custody.',
    'dumps': dict((name, checksum) for checksum, name in (line.split() for line in (output / 'dumps.sha256').read_text().splitlines())),
}
value = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
(output / 'migration-restore-manifest.json').write_bytes(value + b'\n')
print('local migration/restore manifest SHA-256:', hashlib.sha256(value + b'\n').hexdigest())
print('archive sizes:', {name: (output / name).stat().st_size for name in manifest['dumps']})
PY
