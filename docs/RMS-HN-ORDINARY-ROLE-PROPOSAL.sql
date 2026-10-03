-- SOURCE PROPOSAL ONLY. Diego must approve this new role/access separately.
-- Existing rms_staging maintenance administrator; no password in SQL/artifacts.
BEGIN;
SET LOCAL lock_timeout = '1000ms';
SET LOCAL statement_timeout = '5000ms';
DO $$ BEGIN
 IF current_database() <> 'rms_staging' OR session_user <> 'rms_staging' THEN
  RAISE EXCEPTION 'Wrong maintenance target';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rms_hn_app') THEN
  RAISE EXCEPTION 'Role already exists; inspect rather than overwrite';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM public.django_migrations WHERE app='rms' AND name='0005_hypothesis_history_guards') THEN
  RAISE EXCEPTION 'Feature schema/guards absent';
 END IF;
END $$;
CREATE ROLE rms_hn_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD NULL;
GRANT CONNECT ON DATABASE rms_staging TO rms_hn_app;
GRANT USAGE ON SCHEMA public TO rms_hn_app;
GRANT SELECT ON public.auth_user, public.auth_group, public.auth_user_groups, public.auth_user_user_permissions, public.auth_group_permissions, public.auth_permission, public.django_content_type, public.django_migrations TO rms_hn_app;
GRANT SELECT, INSERT ON public.rms_source, public.rms_idea, public.rms_researchfamily, public.rms_investigation, public.rms_priorresearchassessment, public.rms_hypothesis, public.rms_researchassociationidentity, public.rms_sourceversion, public.rms_sourcemanifest, public.rms_ideaversion, public.rms_ideacontribution, public.rms_idempotencyrecord, public.rms_researchfamilyversion, public.rms_investigationversion, public.rms_priorresearchassessmentversion, public.rms_hypothesisversion, public.rms_researchassociation, public.rms_assessmentexternalreference, public.rms_hypothesiscorrectionimpact TO rms_hn_app;
GRANT UPDATE (latest_version) ON public.rms_source TO rms_hn_app;
GRANT UPDATE (latest_version) ON public.rms_idea TO rms_hn_app;
GRANT UPDATE (latest_version) ON public.rms_researchfamily TO rms_hn_app;
GRANT UPDATE (latest_version) ON public.rms_investigation TO rms_hn_app;
GRANT UPDATE (latest_version) ON public.rms_priorresearchassessment TO rms_hn_app;
GRANT UPDATE (latest_version) ON public.rms_hypothesis TO rms_hn_app;
GRANT UPDATE (latest_version) ON public.rms_researchassociationidentity TO rms_hn_app;
-- Invoker-rights version append triggers; no SECURITY DEFINER or ownership change.
GRANT EXECUTE ON FUNCTION public.rms_reject_row_change(), public.rms_guard_source_change(), public.rms_append_source_version(), public.rms_validate_manifest(), public.rms_guard_idea_change(), public.rms_append_idea_version(), public.rms_hn_guard_identity(), public.rms_hn_append_version(), public.rms_hn_validate_graph(), public.rms_hn_validate_impact(), public.rms_hn_validate_assessment_links() TO rms_hn_app;
-- Effective PUBLIC privileges must not silently defeat the intended denials.
-- Abort, then request the smallest observed remedy; no company-wide REVOKE here.
DO $$ DECLARE item regclass; BEGIN
 IF has_schema_privilege('rms_hn_app', 'public', 'CREATE') OR
    EXISTS (SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='rms_hn_app')) THEN
  RAISE EXCEPTION 'Unexpected schema CREATE or membership';
 END IF;
 FOR item IN SELECT c.oid::regclass FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE n.nspname='public' AND c.relkind IN ('r','p') AND
             (c.relname LIKE 'rms\_%' ESCAPE '\' OR c.relname LIKE 'auth\_%' ESCAPE '\' OR c.relname IN ('django_content_type','django_migrations')) LOOP
  IF has_table_privilege('rms_hn_app', item, 'DELETE') OR
     has_table_privilege('rms_hn_app', item, 'TRUNCATE') OR
     has_table_privilege('rms_hn_app', item, 'UPDATE') THEN
   RAISE EXCEPTION 'Unexpected effective full-table write privilege';
  END IF;
 END LOOP;
 IF EXISTS (
  SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
  WHERE n.nspname='public' AND c.relkind IN ('r','p') AND
   (c.relname LIKE 'rms\_%' ESCAPE '\' OR c.relname LIKE 'auth\_%' ESCAPE '\' OR c.relname IN ('django_content_type','django_migrations')) AND
   has_column_privilege('rms_hn_app', c.oid, a.attnum, 'UPDATE') AND NOT
   (a.attname='latest_version' AND c.relname IN ('rms_source','rms_idea','rms_researchfamily','rms_investigation','rms_priorresearchassessment','rms_hypothesis','rms_researchassociationidentity'))
 ) OR EXISTS (
  SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relkind IN ('r','p') AND
   (c.relname LIKE 'auth\_%' ESCAPE '\' OR c.relname IN ('django_content_type','django_migrations')) AND
   has_table_privilege('rms_hn_app', c.oid, 'INSERT')
 ) THEN RAISE EXCEPTION 'Unexpected auth INSERT or column UPDATE privilege'; END IF;
END $$;
COMMIT;
-- Operations separately sets/binds a login secret through approved secret handling
-- only after the recorded access decision. This passwordless SQL is not evidence
-- of an authenticated receiving app/Test connection. No new Django user/group,
-- sequence privilege, DELETE/TRUNCATE, schema/DB/role ownership or membership.
