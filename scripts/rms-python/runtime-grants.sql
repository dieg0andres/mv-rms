\set ON_ERROR_STOP on
BEGIN;
SET LOCAL search_path = pg_catalog;
SELECT current_database() = :'target_db'
   AND current_setting('server_version_num')::int BETWEEN 170000 AND 179999
   AND current_user = session_user AND current_user = :'ddl_owner'
   AND current_user = pg_get_userbyid(datdba)
   AND NOT EXISTS (SELECT FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls))
   AND EXISTS (SELECT FROM pg_roles WHERE rolname=:'runtime_role' AND rolcanlogin
               AND NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)
               AND NOT EXISTS (SELECT FROM pg_auth_members WHERE member=pg_roles.oid))
   AND current_user <> :'runtime_role' AS valid_target
FROM pg_database WHERE datname=current_database() \gset
\if :valid_target
\else
DO $$ BEGIN RAISE EXCEPTION 'Wrong target, owner, runtime role, or PostgreSQL major'; END $$;
\endif

SELECT COALESCE(max(name) = :'rms_leaf', false) AND :'rms_leaf' IN
    ('0007_test_plan_history_guards', '0008_run_attempts', '0009_run_results', '0010_run_assurance', '0011_run_event_evidence')
    AND (:'rms_leaf' NOT IN ('0010_run_assurance','0011_run_event_evidence') OR bool_or(name = '0009_run_results'))
    AND (:'rms_leaf' <> '0011_run_event_evidence' OR bool_or(name = '0010_run_assurance')) AS valid_leaf,
    :'rms_leaf' IN ('0008_run_attempts', '0009_run_results', '0010_run_assurance', '0011_run_event_evidence') AS has_runs,
    :'rms_leaf' IN ('0009_run_results', '0010_run_assurance', '0011_run_event_evidence') AS has_results,
    :'rms_leaf' IN ('0010_run_assurance', '0011_run_event_evidence') AS has_assurance
FROM public.django_migrations WHERE app='rms' \gset
\if :valid_leaf
\else
DO $$ BEGIN RAISE EXCEPTION 'Unsupported or mismatched RMS migration leaf'; END $$;
\endif

REVOKE ALL ON DATABASE :"target_db" FROM PUBLIC, :"runtime_role";
GRANT CONNECT ON DATABASE :"target_db" TO :"runtime_role";
REVOKE ALL ON SCHEMA public FROM PUBLIC, :"runtime_role";
GRANT USAGE ON SCHEMA public TO :"runtime_role";
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, :"runtime_role";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, :"runtime_role";
SELECT format('REVOKE EXECUTE ON ROUTINE %s FROM PUBLIC, %I', oid::regprocedure, :'runtime_role')
FROM pg_proc WHERE pronamespace='public'::regnamespace AND proowner=(SELECT oid FROM pg_roles WHERE rolname=current_user) \gexec
ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

SELECT format('REVOKE SELECT (%1$s), INSERT (%1$s), UPDATE (%1$s), REFERENCES (%1$s) ON %2$s FROM PUBLIC, %3$I',
              string_agg(quote_ident(attname), ', ' ORDER BY attnum), attrelid::regclass, :'runtime_role')
FROM pg_attribute JOIN pg_class ON pg_class.oid=attrelid
WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p','v','m','f') AND attnum>0 AND NOT attisdropped
GROUP BY attrelid \gexec

GRANT SELECT ON public.auth_user, public.auth_group, public.auth_user_groups TO :"runtime_role";
GRANT SELECT ON public.django_migrations TO :"runtime_role";
GRANT EXECUTE ON FUNCTION public.digest(bytea, text) TO :"runtime_role";

GRANT SELECT, INSERT ON
    public.rms_source, public.rms_sourceversion, public.rms_sourcemanifest,
    public.rms_idea, public.rms_ideaversion, public.rms_ideacontribution, public.rms_idempotencyrecord,
    public.rms_researchfamily, public.rms_researchfamilyversion, public.rms_investigation, public.rms_investigationversion,
    public.rms_priorresearchassessment, public.rms_priorresearchassessmentversion, public.rms_hypothesis, public.rms_hypothesisversion,
    public.rms_researchassociationidentity, public.rms_researchassociation, public.rms_assessmentexternalreference, public.rms_hypothesiscorrectionimpact,
    public.rms_testplan, public.rms_testplanversion, public.rms_criterionprofile, public.rms_criterionprofileversion,
    public.rms_datarequirement, public.rms_datarequirementversion, public.rms_testplanassociation, public.rms_dataaccesscheck
TO :"runtime_role";
GRANT UPDATE (latest_version) ON
    public.rms_source, public.rms_idea, public.rms_researchfamily, public.rms_investigation,
    public.rms_priorresearchassessment, public.rms_hypothesis, public.rms_researchassociationidentity,
    public.rms_testplan, public.rms_criterionprofile, public.rms_datarequirement
TO :"runtime_role";
\if :has_runs
GRANT SELECT, INSERT ON public.rms_runattempt TO :"runtime_role";
\endif
\if :has_results
GRANT SELECT, INSERT ON public.rms_runlifecycleevent, public.rms_runretry, public.rms_runresultversion TO :"runtime_role";
GRANT UPDATE (id) ON public.rms_runattempt TO :"runtime_role";
\endif
\if :has_assurance
GRANT SELECT, INSERT ON public.rms_runreview, public.rms_rundecision, public.rms_runlesson TO :"runtime_role";
SELECT bool_and(
    has_table_privilege(:'runtime_role', relation, 'SELECT')
    AND has_table_privilege(:'runtime_role', relation, 'INSERT')
    AND NOT has_table_privilege(:'runtime_role', relation, 'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
    AND NOT has_any_column_privilege(:'runtime_role', relation, 'UPDATE,REFERENCES')
    AND (SELECT count(*) = 3 FROM pg_trigger WHERE tgrelid=relation AND NOT tgisinternal AND tgenabled='O'
         AND tgname IN ('ra_binding','ra_no_edit','ra_no_truncate'))
) AS assurance_separated
FROM unnest(ARRAY['public.rms_runreview'::regclass,'public.rms_rundecision'::regclass,'public.rms_runlesson'::regclass]) AS relations(relation) \gset
\if :assurance_separated
\else
DO $$ BEGIN RAISE EXCEPTION 'Unexpected effective assurance privileges or missing guards'; END $$;
\endif
\endif

SELECT NOT EXISTS (
    SELECT FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p','S','v','m','f')
      AND relowner <> (SELECT oid FROM pg_roles WHERE rolname=current_user)
) AND NOT EXISTS (
    SELECT FROM pg_proc WHERE pronamespace='public'::regnamespace
      AND (prosecdef OR (proowner <> (SELECT oid FROM pg_roles WHERE rolname=current_user)
          AND NOT EXISTS (SELECT FROM pg_depend d JOIN pg_extension e ON d.refclassid='pg_extension'::regclass AND d.refobjid=e.oid
                          WHERE d.classid='pg_proc'::regclass AND d.objid=pg_proc.oid AND d.deptype='e' AND e.extname='pgcrypto'))
        OR (oid <> 'public.digest(bytea,text)'::regprocedure AND has_function_privilege(:'runtime_role', oid, 'EXECUTE')))
) AND NOT EXISTS (
    SELECT FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN ('public','information_schema')
      AND has_schema_privilege(:'runtime_role', oid, 'USAGE,CREATE')
) AND NOT has_schema_privilege(:'runtime_role', 'public', 'CREATE')
  AND NOT has_database_privilege(:'runtime_role', current_database(), 'CREATE,TEMPORARY')
  AND has_function_privilege(:'runtime_role', 'public.digest(bytea,text)', 'EXECUTE') AS separated \gset
\if :separated
\else
DO $$ BEGIN RAISE EXCEPTION 'Unexpected ownership, SECURITY DEFINER routine, or effective CREATE/USAGE privilege'; END $$;
\endif
COMMIT;
