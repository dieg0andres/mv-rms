"""PostgreSQL preservation guards. Source only; not applied by this task."""

from django.db import migrations


IDENTITIES = (
    "rms_researchfamily", "rms_investigation", "rms_priorresearchassessment",
    "rms_hypothesis", "rms_researchassociationidentity",
)
VERSIONS = (
    ("rms_researchfamilyversion", "rms_researchfamily"),
    ("rms_investigationversion", "rms_investigation"),
    ("rms_priorresearchassessmentversion", "rms_priorresearchassessment"),
    ("rms_hypothesisversion", "rms_hypothesis"),
    ("rms_researchassociation", "rms_researchassociationidentity"),
    ("rms_assessmentexternalreference", "rms_researchassociationidentity"),
    ("rms_hypothesiscorrectionimpact", "rms_researchassociationidentity"),
)

FUNCTION_SQL = r"""
CREATE FUNCTION rms_hn_guard_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.latest_version <> 0 THEN
            RAISE EXCEPTION 'New identity watermark must be zero';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP <> 'UPDATE' THEN
        RAISE EXCEPTION 'Research identities are retained';
    END IF;
    IF pg_trigger_depth() <> 2
       OR (to_jsonb(NEW) - 'latest_version') IS DISTINCT FROM (to_jsonb(OLD) - 'latest_version')
       OR NEW.latest_version <> OLD.latest_version + 1 THEN
        RAISE EXCEPTION 'Only append triggers may advance research watermarks';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION rms_hn_append_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_version integer;
BEGIN
    EXECUTE format('SELECT latest_version FROM %I WHERE id = $1 FOR UPDATE', TG_ARGV[0])
       INTO current_version USING NEW.record_id;
    IF current_version IS NULL OR NEW.version <> current_version + 1 THEN
        RAISE EXCEPTION 'Research version must append after its identity watermark';
    END IF;
    IF (NEW.version = 1 AND (NEW.corrects_version IS NOT NULL OR NEW.correction_reason IS NOT NULL))
       OR (NEW.version > 1 AND (NEW.corrects_version IS DISTINCT FROM current_version
           OR NEW.correction_reason IS NULL OR btrim(NEW.correction_reason) = '')) THEN
        RAISE EXCEPTION 'Research correction requires its immediate predecessor and a reason';
    END IF;
    EXECUTE format('UPDATE %I SET latest_version = $1 WHERE id = $2', TG_ARGV[0])
       USING NEW.version, NEW.record_id;
    RETURN NEW;
END;
$$;

CREATE FUNCTION rms_hn_validate_graph() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE hyp uuid; inv uuid; origins integer; cases integer; families integer; assessments integer;
BEGIN
    IF TG_TABLE_NAME = 'rms_hypothesisversion' THEN hyp := NEW.id;
    ELSIF TG_TABLE_NAME = 'rms_investigationversion' THEN inv := NEW.id;
    ELSE
        hyp := NEW.hypothesis_version_id;
        inv := NEW.investigation_version_id;
        IF NEW.kind = 'IdeaFamily' AND NOT EXISTS (
            SELECT 1 FROM rms_researchassociationidentity r
             WHERE r.id = NEW.record_id AND r.idea_version_id = NEW.idea_version_id
        ) THEN RAISE EXCEPTION 'Idea classification must bind its exact identity'; END IF;
        IF NEW.kind = 'IdeaFamily' AND (NEW.rationale IS NULL OR btrim(NEW.rationale) = '') THEN
            RAISE EXCEPTION 'Idea classification requires an explicit grouping rationale';
        END IF;
    END IF;
    IF inv IS NOT NULL THEN
        SELECT count(*) FILTER (WHERE kind = 'InvestigationFamily'),
               count(*) FILTER (WHERE kind = 'PriorResearchInvestigation')
          INTO families, assessments FROM rms_researchassociation
         WHERE investigation_version_id = inv;
        IF families <> 1 OR assessments <> 1 THEN
            RAISE EXCEPTION 'Case requires one exact family and prior assessment';
        END IF;
    END IF;
    IF hyp IS NOT NULL THEN
        SELECT count(*) FILTER (WHERE kind = 'IdeaHypothesis'),
               count(*) FILTER (WHERE kind = 'HypothesisInvestigation')
          INTO origins, cases FROM rms_researchassociation WHERE hypothesis_version_id = hyp;
        IF origins <> 1 OR cases <> 1 THEN
            RAISE EXCEPTION 'Hypothesis requires exactly one origin and case';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM rms_researchassociation origin
            JOIN rms_researchassociation classification ON classification.id = origin.idea_family_version_id
            JOIN rms_researchassociation case_edge ON case_edge.hypothesis_version_id = hyp AND case_edge.kind = 'HypothesisInvestigation'
            JOIN rms_researchassociation family_edge ON family_edge.investigation_version_id = case_edge.investigation_version_id AND family_edge.kind = 'InvestigationFamily'
            JOIN rms_researchfamilyversion origin_family ON origin_family.id = classification.family_version_id
            JOIN rms_researchfamilyversion case_family ON case_family.id = family_edge.family_version_id
            WHERE origin.hypothesis_version_id = hyp AND origin.kind = 'IdeaHypothesis'
              AND classification.kind = 'IdeaFamily'
              AND classification.idea_version_id = origin.idea_version_id
              AND origin_family.record_id = case_family.record_id
              AND btrim(origin.rationale) <> ''
        ) THEN RAISE EXCEPTION 'Hypothesis origin and case must have compatible explicit families'; END IF;
    END IF;
    RETURN NULL;
END;
$$;

CREATE FUNCTION rms_hn_validate_impact() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE kind text; pinned uuid; newer uuid; pinned_record uuid; newer_record uuid;
        pinned_sequence integer; newer_sequence integer; endpoint_table text; parent_column text;
BEGIN
    FOREACH kind IN ARRAY ARRAY['source', 'idea', 'family', 'investigation', 'assessment', 'association'] LOOP
        pinned := (to_jsonb(NEW) ->> ('pinned_' || kind || '_id'))::uuid;
        newer := (to_jsonb(NEW) ->> ('newer_' || kind || '_id'))::uuid;
        IF pinned IS NOT NULL THEN
            endpoint_table := CASE kind
                WHEN 'source' THEN 'rms_sourceversion' WHEN 'idea' THEN 'rms_ideaversion'
                WHEN 'family' THEN 'rms_researchfamilyversion' WHEN 'investigation' THEN 'rms_investigationversion'
                WHEN 'assessment' THEN 'rms_priorresearchassessmentversion' ELSE 'rms_researchassociation' END;
            parent_column := CASE kind WHEN 'source' THEN 'source_id' WHEN 'idea' THEN 'idea_id' ELSE 'record_id' END;
            EXECUTE format('SELECT %I, version FROM %I WHERE id = $1', parent_column, endpoint_table)
              INTO pinned_record, pinned_sequence USING pinned;
            EXECUTE format('SELECT %I, version FROM %I WHERE id = $1', parent_column, endpoint_table)
              INTO newer_record, newer_sequence USING newer;
            IF pinned_record IS DISTINCT FROM newer_record OR pinned_sequence >= newer_sequence THEN
                RAISE EXCEPTION 'Impact must cite a newer version of the same pinned record';
            END IF;
        END IF;
    END LOOP;
    RETURN NEW;
END;
$$;

CREATE FUNCTION rms_hn_validate_assessment_links() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE assessment uuid; expected_count integer; expected_digest text;
        actual_count bigint; distinct_positions bigint; first_position integer;
        last_position integer; actual_digest text;
BEGIN
    IF TG_TABLE_NAME = 'rms_priorresearchassessmentversion' THEN
        assessment := NEW.id;
    ELSIF TG_TABLE_NAME = 'rms_researchassociation' THEN
        IF NEW.kind <> 'AssessmentRecord' THEN RETURN NULL; END IF;
        assessment := NEW.assessment_version_id;
    ELSE
        assessment := NEW.assessment_version_id;
    END IF;
    SELECT link_count, link_digest INTO expected_count, expected_digest
      FROM rms_priorresearchassessmentversion WHERE id = assessment;

    -- No relationship IDs are stored on the parent. Its immutable commitment
    -- binds the union of typed FK associations and labeled external references.
    WITH link_rows AS (
        SELECT a.position,
               CASE WHEN a.source_version_id IS NOT NULL THEN 'source'
                    WHEN a.idea_version_id IS NOT NULL THEN 'idea'
                    WHEN a.family_version_id IS NOT NULL THEN 'research_family'
                    ELSE 'investigation' END AS kind,
               COALESCE(s.source_version_id, i.idea_version_id, f.public_id, c.public_id) AS token
          FROM rms_researchassociation a
          LEFT JOIN rms_sourceversion s ON s.id = a.source_version_id
          LEFT JOIN rms_ideaversion i ON i.id = a.idea_version_id
          LEFT JOIN rms_researchfamilyversion f ON f.id = a.family_version_id
          LEFT JOIN rms_investigationversion c ON c.id = a.investigation_version_id
         WHERE a.kind = 'AssessmentRecord' AND a.assessment_version_id = assessment
        UNION ALL
        SELECT e.position, 'external_document',
               encode(digest(convert_to(e.reference, 'UTF8'), 'sha256'), 'hex')
          FROM rms_assessmentexternalreference e WHERE e.assessment_version_id = assessment
    )
    SELECT count(*), count(DISTINCT position), min(position), max(position),
           encode(digest(convert_to(COALESCE(
               string_agg(position::text || ':' || kind || ':' || token, E'\n' ORDER BY position) || E'\n',
               ''), 'UTF8'), 'sha256'), 'hex')
      INTO actual_count, distinct_positions, first_position, last_position, actual_digest
      FROM link_rows;
    IF expected_count IS NULL OR actual_count <> expected_count
       OR distinct_positions <> actual_count
       OR (actual_count > 0 AND (first_position <> 1 OR last_position <> actual_count))
       OR actual_digest IS DISTINCT FROM expected_digest THEN
        RAISE EXCEPTION 'Assessment link set must match its immutable ordered commitment'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END;
$$;
"""


def guard_sql():
    statements = [FUNCTION_SQL]
    for table in IDENTITIES:
        statements.append(f"CREATE TRIGGER hn_identity_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION rms_hn_guard_identity();")
    for table, identity in VERSIONS:
        statements.extend([
            f"ALTER TABLE {table} ADD CONSTRAINT hn_predecessor_fk FOREIGN KEY (record_id, corrects_version) REFERENCES {table} (record_id, version) DEFERRABLE INITIALLY IMMEDIATE;",
            f"CREATE TRIGGER hn_append BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION rms_hn_append_version('{identity}');",
            f"CREATE TRIGGER hn_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();",
        ])
    for table in (*IDENTITIES, *(table for table, _ in VERSIONS)):
        statements.append(f"CREATE TRIGGER hn_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION rms_reject_row_change();")
    for table in ("rms_hypothesisversion", "rms_investigationversion", "rms_researchassociation"):
        statements.append(f"CREATE CONSTRAINT TRIGGER hn_graph AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rms_hn_validate_graph();")
    statements.append("CREATE TRIGGER hn_impact BEFORE INSERT ON rms_hypothesiscorrectionimpact FOR EACH ROW EXECUTE FUNCTION rms_hn_validate_impact();")
    # Validate both an explicitly empty parent and every inserted child. Deferral
    # permits atomic assembly; immutable count/digest reject any late attachment,
    # including inserts made in a concurrent transaction or using a new identity.
    for table in ("rms_priorresearchassessmentversion", "rms_researchassociation", "rms_assessmentexternalreference"):
        statements.append(f"CREATE CONSTRAINT TRIGGER hn_assessment_links AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rms_hn_validate_assessment_links();")
    return "\n".join(statements)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [("rms", "0004_hypothesis_records")]
    # Irreversible by design: removing guards would expose retained history.
    # Application rollback retains additive tables; reversal needs separate review.
    operations = [migrations.RunSQL(guard_sql())]
