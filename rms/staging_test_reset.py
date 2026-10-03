"""Bounded maintenance reset for founder-designated disposable staging RMS data.

Never used by request handlers. Caller owns the transaction and approved existing
container binding. A supplied label is not proof of Docker/container identity.
"""

BASE_TABLES = (
    "rms_source", "rms_sourceversion", "rms_sourcemanifest", "rms_idea",
    "rms_ideaversion", "rms_ideacontribution", "rms_idempotencyrecord",
)
HN_TABLES = (
    "rms_researchfamily", "rms_investigation", "rms_priorresearchassessment",
    "rms_hypothesis", "rms_researchassociationidentity",
    "rms_researchfamilyversion", "rms_investigationversion",
    "rms_priorresearchassessmentversion", "rms_hypothesisversion",
    "rms_researchassociation", "rms_assessmentexternalreference",
    "rms_hypothesiscorrectionimpact",
)
RMS_TABLES = tuple(sorted((*BASE_TABLES, *HN_TABLES)))
AUTH_TABLES = (
    "auth_user", "auth_group", "auth_permission", "auth_user_groups",
    "auth_user_user_permissions", "auth_group_permissions", "django_content_type",
)
OPTIONAL_PROTECTED = ("django_session",)
BASE_MIGRATIONS = {"0001_initial", "0002_source_invariants", "0003_source_idea_contract"}
HN_MIGRATIONS = {"0004_hypothesis_records", "0005_hypothesis_history_guards"}
POLICY_REF = "4dc2c3b8-534c-4053-abfc-d22b62f34392"


class ResetRejected(ValueError):
    """Stable, non-sensitive reason; do not dump database exceptions/rows."""


def require(condition, code):
    if not condition:
        raise ResetRejected(code)


def validate_binding(settings, *, project, container):
    require(project == "mv-rms-staging" and container == "mv-rms-staging-db-1", "wrong_staging_binding")
    require(settings.get("ENGINE") == "django.db.backends.postgresql", "wrong_database_engine")
    require(settings.get("NAME") == "rms_staging" and settings.get("HOST") == "db"
            and str(settings.get("PORT", "5432")) == "5432", "wrong_staging_target")
    # The observed existing administrator is maintenance-only, not H14's app role.
    require(settings.get("USER") == "rms_staging", "wrong_maintenance_identity")


def qualified(names):
    require(bool(names) and set(names) <= set((*RMS_TABLES, *AUTH_TABLES, *OPTIONAL_PROTECTED)), "unreviewed_table")
    return ", ".join('public."' + name + '"' for name in sorted(names))


def guards(cursor, tables):
    cursor.execute("""SELECT c.relname, t.tgenabled, t.tgtype, pn.nspname, p.proname
        FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_proc p ON p.oid = t.tgfoid JOIN pg_namespace pn ON pn.oid = p.pronamespace
        WHERE n.nspname = 'public' AND c.relname = ANY(%s)
          AND t.tgname = 'hn_no_truncate' AND NOT t.tgisinternal ORDER BY c.relname""", [list(tables)])
    return cursor.fetchall()


def auth_fingerprints(cursor, tables):
    # Hash only protected authentication state inside the DB. No account/password
    # row is returned, persisted or printed. Research rows are deliberately absent.
    result = {}
    for table in sorted(tables):
        cursor.execute("SELECT count(*), encode(sha256(convert_to(COALESCE("
                       "string_agg(to_jsonb(t)::text, E'\\n' ORDER BY to_jsonb(t)::text), ''), "
                       "'UTF8')), 'hex') FROM " + qualified([table]) + " t")
        result[table] = cursor.fetchone()
    return result


def reset_in_transaction(cursor, *, reseed=None):
    """Run only inside one outer atomic transaction; errors roll back DDL + data.

    Lock the exact tables, disable ONLY the reviewed statement TRUNCATE guards,
    restore them before any fixture insert, and leave row/version guards active.
    """
    require(getattr(getattr(cursor, 'db', None), 'in_atomic_block', False), "atomic_transaction_required")
    cursor.execute("SET LOCAL lock_timeout = '5000ms'")
    cursor.execute("SET LOCAL statement_timeout = '30000ms'")
    cursor.execute("SELECT current_database(), session_user, current_user, "
                   "current_setting('transaction_read_only'), inet_server_port()")
    require(cursor.fetchone() == ("rms_staging", "rms_staging", "rms_staging", "off", 5432), "effective_target_mismatch")
    cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
    require(cursor.fetchone() == (True,), "existing_maintenance_admin_required")
    cursor.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                   "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')")
    present = {row[0] for row in cursor.fetchall()}
    rms = present.intersection(RMS_TABLES)
    require({name for name in present if name.startswith('rms_')} == rms, "unreviewed_rms_table")
    require(rms in (set(BASE_TABLES), set(RMS_TABLES)), "incomplete_rms_schema")
    require(set(AUTH_TABLES) <= present, "authentication_schema_missing")
    require(reseed is None or rms == set(RMS_TABLES), "hypothesis_schema_required_for_reseed")
    cursor.execute("SELECT name FROM public.django_migrations WHERE app = 'rms'")
    migrations = {row[0] for row in cursor.fetchall()}
    expected = BASE_MIGRATIONS | (HN_MIGRATIONS if rms == set(RMS_TABLES) else set())
    require(migrations == expected, "unexpected_rms_migrations")
    protected = set(AUTH_TABLES) | (present & set(OPTIONAL_PROTECTED))
    # A brief exclusive maintenance slot is required; no app/test request overlaps
    # a reset. Auth readers can continue, but account mutations wait or time out.
    cursor.execute("LOCK TABLE " + qualified(protected) + " IN SHARE MODE")
    cursor.execute("LOCK TABLE " + qualified(rms) + " IN ACCESS EXCLUSIVE MODE")
    cursor.execute("""SELECT 1 FROM pg_constraint f
        JOIN pg_class target ON target.oid = f.confrelid
        JOIN pg_namespace tn ON tn.oid = target.relnamespace
        JOIN pg_class origin ON origin.oid = f.conrelid
        JOIN pg_namespace onsp ON onsp.oid = origin.relnamespace
        WHERE f.contype = 'f' AND tn.nspname = 'public' AND target.relname = ANY(%s)
          AND NOT (onsp.nspname = 'public' AND origin.relname = ANY(%s)) LIMIT 1""", [sorted(rms), sorted(rms)])
    require(cursor.fetchone() is None, "external_reference_into_rms")
    before_auth = auth_fingerprints(cursor, protected)
    hn = rms & set(HN_TABLES)
    before_guards = guards(cursor, hn) if hn else []
    expected_guards = [(table, 'O', 34, 'public', 'rms_reject_row_change') for table in sorted(hn)]
    require(before_guards == expected_guards, "history_guard_mismatch")
    for table in sorted(hn):
        cursor.execute("ALTER TABLE " + qualified([table]) + " DISABLE TRIGGER hn_no_truncate")
    # No CASCADE, RESTART IDENTITY, auth deletion, session_replication_role or
    # generic flush. Referencing RMS tables are included in this one statement.
    cursor.execute("TRUNCATE TABLE " + qualified(rms) + " CONTINUE IDENTITY RESTRICT")
    for table in sorted(hn):
        cursor.execute("ALTER TABLE " + qualified([table]) + " ENABLE TRIGGER hn_no_truncate")
    require((guards(cursor, hn) if hn else []) == before_guards, "history_guard_not_restored")
    if reseed is not None:
        reseed()  # Existing loader/service validation runs with every guard active.
    require((guards(cursor, hn) if hn else []) == before_guards, "history_guard_changed_by_fixture")
    require(auth_fingerprints(cursor, protected) == before_auth, "authentication_changed")
    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")  # Deferred fixture failures precede success.
    return {"target": "mv-rms-staging-db-1/rms_staging", "maintenance_role": "rms_staging",
            "tables_reset": sorted(rms), "reseeded": reseed is not None,
            "authentication_unchanged": True, "history_guards_restored": True,
            "policy_comment": POLICY_REF, "app_role_certification": False}
