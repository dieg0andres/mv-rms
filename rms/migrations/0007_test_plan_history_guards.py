"""Atomic PostgreSQL history/association guards; application rollback retains them."""
from django.db import migrations

IDENTITIES=('rms_testplan','rms_criterionprofile','rms_datarequirement')
VERSIONS=(('rms_testplanversion','rms_testplan'),('rms_criterionprofileversion','rms_criterionprofile'),('rms_datarequirementversion','rms_datarequirement'))
SQL=r"""
CREATE FUNCTION rms_tp_validate_links() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE plan uuid; expected_count integer; expected_digest text; actual_count integer;
        actual_digest text; hypothesis_count integer; plan_record uuid; prior_hyp uuid; current_hyp uuid;
BEGIN
    plan := CASE WHEN TG_TABLE_NAME='rms_testplanversion' THEN NEW.id ELSE NEW.plan_version_id END;
    SELECT link_count,link_digest,record_id INTO expected_count,expected_digest,plan_record
      FROM rms_testplanversion WHERE id=plan;
    SELECT count(*),count(*) FILTER (WHERE a.kind='HypothesisPlan'),
           encode(digest(convert_to(COALESCE(string_agg(
               a.kind || ':' || a.position::text || ':' || COALESCE(h.public_id,c.public_id,d.public_id)
               || ':' || CASE WHEN a.required IS NULL THEN '-' WHEN a.required THEN '1' ELSE '0' END
               || ':' || a.public_id || E'\n', '' ORDER BY a.kind,a.position),''),'UTF8'),'sha256'),'hex')
      INTO actual_count,hypothesis_count,actual_digest
      FROM rms_testplanassociation a
      LEFT JOIN rms_hypothesisversion h ON h.id=a.hypothesis_version_id
      LEFT JOIN rms_criterionprofileversion c ON c.id=a.criterion_version_id
      LEFT JOIN rms_datarequirementversion d ON d.id=a.data_requirement_version_id
      WHERE a.plan_version_id=plan;
    IF expected_count IS NULL OR actual_count<>expected_count OR hypothesis_count<>1
       OR actual_digest IS DISTINCT FROM expected_digest THEN
        RAISE EXCEPTION 'Test Plan links must match their immutable ordered commitment'
          USING ERRCODE='integrity_constraint_violation';
    END IF;
    IF EXISTS (
      SELECT 1 FROM rms_testplanassociation a
      LEFT JOIN rms_criterionprofileversion c ON c.id=a.criterion_version_id
      LEFT JOIN rms_criterionprofile ci ON ci.id=c.record_id
      LEFT JOIN rms_datarequirementversion d ON d.id=a.data_requirement_version_id
      LEFT JOIN rms_datarequirement di ON di.id=d.record_id
      WHERE a.plan_version_id=plan AND (
        (a.kind='PlanCriterion' AND (ci.plan_id IS DISTINCT FROM plan_record
           OR a.required IS DISTINCT FROM (c.fields->>'mandatory')::boolean))
        OR (a.kind='PlanDataRequirement' AND (di.plan_id IS DISTINCT FROM plan_record
           OR a.required IS DISTINCT FROM (jsonb_array_length(d.fields->'used_by_configurations')>0))))
    ) THEN RAISE EXCEPTION 'Child must belong to this plan with derived applicability'; END IF;
    IF EXISTS (SELECT 1 FROM rms_testplanassociation WHERE plan_version_id=plan
       AND kind<>'HypothesisPlan' GROUP BY kind HAVING min(position)<>1 OR max(position)<>count(*)) THEN
       RAISE EXCEPTION 'Child positions must be contiguous';
    END IF;
    SELECT h.record_id INTO current_hyp FROM rms_testplanassociation a
      JOIN rms_hypothesisversion h ON h.id=a.hypothesis_version_id
      WHERE a.plan_version_id=plan AND a.kind='HypothesisPlan';
    SELECT h.record_id INTO prior_hyp FROM rms_testplanversion v
      JOIN rms_testplanversion predecessor ON predecessor.record_id=v.record_id AND predecessor.version=v.corrects_version
      JOIN rms_testplanassociation a ON a.plan_version_id=predecessor.id AND a.kind='HypothesisPlan'
      JOIN rms_hypothesisversion h ON h.id=a.hypothesis_version_id WHERE v.id=plan;
    IF prior_hyp IS NOT NULL AND prior_hyp IS DISTINCT FROM current_hyp THEN
      RAISE EXCEPTION 'Plan correction cannot change Hypothesis identity';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM rms_testplanassociation a JOIN rms_hypothesisversion h ON h.id=a.hypothesis_version_id
       WHERE a.plan_version_id=plan AND a.kind='HypothesisPlan' AND h.classification='synthetic'
         AND h.authority_reference='MAU-140:contract:3982eccc-e180-4ac9-bc70-9c4e16aa47f1') THEN
       RAISE EXCEPTION 'Plan must bind an authorized synthetic Hypothesis';
    END IF;
    RETURN NULL;
END;
$$;
CREATE FUNCTION rms_tp_validate_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_report rms_dataaccesscheck; expected_digest text; required_digest text;
BEGIN
    -- Serialize ordinary direct inserts as well as service writes at this plan.
    PERFORM 1 FROM rms_testplan WHERE id=(SELECT record_id FROM rms_testplanversion WHERE id=NEW.plan_version_id) FOR UPDATE;
    IF NOT EXISTS (SELECT 1 FROM rms_testplanassociation a
        JOIN rms_datarequirementversion d ON d.id=a.data_requirement_version_id
        WHERE a.plan_version_id=NEW.plan_version_id AND a.kind='PlanDataRequirement'
          AND a.data_requirement_version_id=NEW.data_requirement_version_id
          AND d.fields->'used_by_configurations' ? NEW.configuration_key) THEN
        RAISE EXCEPTION 'Check requirement/configuration must belong to exact plan';
    END IF;
    SELECT x->>'digest' INTO expected_digest FROM rms_testplanversion v,
      LATERAL jsonb_array_elements(v.configurations) x
      WHERE v.id=NEW.plan_version_id AND x->>'key'=NEW.configuration_key;
    SELECT content_digest INTO required_digest FROM rms_datarequirementversion WHERE id=NEW.data_requirement_version_id;
    IF expected_digest IS NULL OR NEW.configuration_digest IS DISTINCT FROM expected_digest
       OR NEW.requirement_digest IS DISTINCT FROM required_digest THEN
        RAISE EXCEPTION 'Check digests must match exact definition';
    END IF;
    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT * INTO old_report FROM rms_dataaccesscheck WHERE id=NEW.supersedes_id;
        IF old_report.id IS NULL OR old_report.plan_version_id IS DISTINCT FROM NEW.plan_version_id
           OR old_report.data_requirement_version_id IS DISTINCT FROM NEW.data_requirement_version_id
           OR old_report.configuration_key IS DISTINCT FROM NEW.configuration_key
           OR EXISTS (SELECT 1 FROM rms_dataaccesscheck WHERE supersedes_id=old_report.id)
           OR NEW.fields->>'correction_reason' IS NULL OR btrim(NEW.fields->>'correction_reason')='' THEN
           RAISE EXCEPTION 'Correction must supersede current report at identical binding';
        END IF;
    ELSIF NEW.fields->>'correction_reason' IS NOT NULL THEN
        RAISE EXCEPTION 'Initial check cannot claim a correction';
    END IF;
    RETURN NEW;
END;
$$;
"""


def guard_sql():
    statements=[SQL]
    for table in IDENTITIES:
        statements.append(f'CREATE TRIGGER tp_identity_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION rms_hn_guard_identity();')
    for table,identity in VERSIONS:
        statements.extend([
            f'ALTER TABLE {table} ADD CONSTRAINT tp_predecessor_fk FOREIGN KEY (record_id,corrects_version) REFERENCES {table} (record_id,version) DEFERRABLE INITIALLY IMMEDIATE;',
            f'CREATE TRIGGER tp_append BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION rms_hn_append_version(\'{identity}\');',
            f'CREATE TRIGGER tp_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();',
        ])
    for table in ('rms_testplanassociation','rms_dataaccesscheck'):
        statements.append(f'CREATE TRIGGER tp_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();')
    for table in (*IDENTITIES,*(t for t,_ in VERSIONS),'rms_testplanassociation','rms_dataaccesscheck'):
        statements.append(f'CREATE TRIGGER tp_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION rms_reject_row_change();')
    for table in ('rms_testplanversion','rms_testplanassociation'):
        statements.append(f'CREATE CONSTRAINT TRIGGER tp_sealed_links AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rms_tp_validate_links();')
    statements.append('CREATE TRIGGER tp_check_binding BEFORE INSERT ON rms_dataaccesscheck FOR EACH ROW EXECUTE FUNCTION rms_tp_validate_check();')
    return '\n'.join(statements)


class Migration(migrations.Migration):
    atomic=True
    dependencies=[('rms','0006_test_plan_records')]
    operations=[migrations.RunSQL(guard_sql())]
