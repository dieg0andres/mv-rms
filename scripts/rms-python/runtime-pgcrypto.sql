\set ON_ERROR_STOP on
BEGIN;
SET LOCAL search_path = pg_catalog;
SELECT current_database() = :'target_db'
   AND current_setting('server_version_num')::int BETWEEN 170000 AND 179999
   AND current_user <> :'ddl_owner' AND pg_get_userbyid(datdba) = :'ddl_owner'
   AND EXISTS (SELECT FROM pg_extension WHERE extname='pgcrypto' AND extnamespace='public'::regnamespace)
   AS valid_target FROM pg_database WHERE datname=current_database() \gset
\if :valid_target
\else
DO $$ BEGIN RAISE EXCEPTION 'Wrong target, database owner, or pgcrypto schema'; END $$;
\endif
SELECT format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, %I', pg_proc.oid::regprocedure, :'runtime_role')
FROM pg_proc JOIN pg_depend d ON d.classid='pg_proc'::regclass AND d.objid=pg_proc.oid
JOIN pg_extension e ON d.refclassid='pg_extension'::regclass AND d.refobjid=e.oid AND d.deptype='e'
WHERE e.extname='pgcrypto' \gexec
GRANT EXECUTE ON FUNCTION public.digest(bytea, text) TO :"ddl_owner" WITH GRANT OPTION;
COMMIT;
