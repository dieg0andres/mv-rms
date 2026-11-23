"""Additive immutable intake. Roll application back without removing history."""

import django.db.models.deletion
import django.db.models.expressions
import django.utils.timezone
import functools
import rms.hypothesis_models
import uuid
from django.db import migrations, models


GUARDS = r"""
CREATE TRIGGER intake_identity BEFORE INSERT OR UPDATE OR DELETE ON rms_researchintake
    FOR EACH ROW EXECUTE FUNCTION rms_hn_guard_identity();
ALTER TABLE rms_researchintakeversion ADD CONSTRAINT intake_predecessor_fk
    FOREIGN KEY (record_id, corrects_version) REFERENCES rms_researchintakeversion (record_id, version);
CREATE TRIGGER intake_append BEFORE INSERT ON rms_researchintakeversion
    FOR EACH ROW EXECUTE FUNCTION rms_hn_append_version('rms_researchintake');

CREATE FUNCTION rms_validate_intake_graph() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE screening rms_researchintakeversion%ROWTYPE;
BEGIN
    IF TG_TABLE_NAME = 'rms_researchintakeversion' THEN
        screening := NEW;
    ELSE
        SELECT * INTO STRICT screening FROM rms_researchintakeversion WHERE id = NEW.intake_version_id;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM rms_researchintake identity
        JOIN rms_ideaversion idea ON idea.idea_id = identity.idea_id
        JOIN rms_researchassociation family ON family.idea_version_id = idea.id
        WHERE identity.id = screening.record_id AND idea.id = screening.idea_version_id
          AND family.id = screening.family_binding_id AND family.kind = 'IdeaFamily'
          AND (screening.investigation_version_id IS NULL OR EXISTS (
            SELECT 1 FROM rms_researchassociation case_family
            WHERE case_family.investigation_version_id = screening.investigation_version_id
              AND case_family.kind = 'InvestigationFamily' AND case_family.family_version_id = family.family_version_id))
    ) THEN RAISE EXCEPTION 'Intake lineage does not match its exact Idea and family'; END IF;
    IF screening.assessment_count <> (
        SELECT count(*) FROM rms_intakesourceassessment row
        WHERE row.intake_version_id = screening.id
    ) OR screening.assessment_count <> (CASE WHEN screening.state = 'ready' THEN (
        SELECT count(*) FROM rms_ideacontribution contribution WHERE contribution.idea_version_id = screening.idea_version_id
    ) ELSE 0 END) OR EXISTS (
        SELECT 1 FROM rms_intakesourceassessment row
        JOIN rms_ideacontribution contribution ON contribution.id = row.contribution_id
        WHERE row.intake_version_id = screening.id AND contribution.idea_version_id <> screening.idea_version_id
    ) THEN RAISE EXCEPTION 'Intake must seal the exact set of assessed contributions'; END IF;
    IF TG_TABLE_NAME = 'rms_intakehypothesisbinding' THEN
      IF NOT EXISTS (
        SELECT 1 FROM rms_researchassociation origin
        JOIN rms_researchassociation context ON context.hypothesis_version_id = origin.hypothesis_version_id
        WHERE origin.kind = 'IdeaHypothesis' AND context.kind = 'HypothesisInvestigation'
          AND origin.hypothesis_version_id = NEW.hypothesis_version_id
          AND origin.idea_version_id = screening.idea_version_id AND origin.idea_family_version_id = screening.family_binding_id
          AND context.investigation_version_id = screening.investigation_version_id AND screening.state = 'ready'
      ) THEN RAISE EXCEPTION 'Hypothesis does not match its exact intake'; END IF;
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER intake_immutable BEFORE UPDATE OR DELETE ON rms_researchintakeversion FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();
CREATE CONSTRAINT TRIGGER intake_graph AFTER INSERT ON rms_researchintakeversion DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rms_validate_intake_graph();
CREATE TRIGGER intake_immutable BEFORE UPDATE OR DELETE ON rms_intakesourceassessment FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();
CREATE CONSTRAINT TRIGGER intake_graph AFTER INSERT ON rms_intakesourceassessment DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rms_validate_intake_graph();
CREATE TRIGGER intake_immutable BEFORE UPDATE OR DELETE ON rms_intakehypothesisbinding FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();
CREATE CONSTRAINT TRIGGER intake_graph AFTER INSERT ON rms_intakehypothesisbinding DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rms_validate_intake_graph();
CREATE TRIGGER intake_no_truncate BEFORE TRUNCATE ON rms_researchintakeversion FOR EACH STATEMENT EXECUTE FUNCTION rms_reject_row_change();
CREATE TRIGGER intake_no_truncate BEFORE TRUNCATE ON rms_intakesourceassessment FOR EACH STATEMENT EXECUTE FUNCTION rms_reject_row_change();
CREATE TRIGGER intake_no_truncate BEFORE TRUNCATE ON rms_intakehypothesisbinding FOR EACH STATEMENT EXECUTE FUNCTION rms_reject_row_change();
CREATE TRIGGER intake_no_truncate BEFORE TRUNCATE ON rms_researchintake FOR EACH STATEMENT EXECUTE FUNCTION rms_reject_row_change();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('rms', '0007_test_plan_history_guards'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResearchIntake',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('synthetic', models.BooleanField(default=True, editable=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('latest_version', models.PositiveIntegerField(default=0, editable=False)),
                ('public_id', models.CharField(default=functools.partial(rms.hypothesis_models.identifier, *('INT',), **{}), editable=False, max_length=42, unique=True)),
                ('idea', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='rms.idea')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ResearchIntakeVersion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('version', models.PositiveIntegerField()),
                ('schema_version', models.CharField(default='1.0', editable=False, max_length=8)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('recorded_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('created_by', models.CharField(editable=False, max_length=150)),
                ('classification', models.CharField(default='synthetic', editable=False, max_length=16)),
                ('authority_reference', models.CharField(default='MAU-140:contract:3982eccc-e180-4ac9-bc70-9c4e16aa47f1', editable=False, max_length=128)),
                ('state', models.CharField(editable=False, max_length=16)),
                ('row_digest', models.CharField(editable=False, max_length=64)),
                ('impact_status', models.CharField(default='unreviewed', editable=False, max_length=16)),
                ('corrects_version', models.PositiveIntegerField(editable=False, null=True)),
                ('correction_reason', models.CharField(max_length=4000, null=True)),
                ('changed_fields', models.JSONField(default=list, editable=False)),
                ('fields', models.JSONField(default=dict)),
                ('public_id', models.CharField(default=functools.partial(rms.hypothesis_models.identifier, *('INTV',), **{}), editable=False, max_length=42, unique=True)),
                ('assessment_count', models.PositiveIntegerField()),
                ('family_binding', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rms.researchassociation')),
                ('idea_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rms.ideaversion')),
                ('investigation_version', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='rms.investigationversion')),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='versions', to='rms.researchintake')),
            ],
            options={
                'ordering': ['version'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='IntakeSourceAssessment',
            fields=[
                ('public_id', models.CharField(default=functools.partial(rms.hypothesis_models.identifier, *('SASV',), **{}), editable=False, max_length=41, primary_key=True, serialize=False)),
                ('fields', models.JSONField()),
                ('rights_reference', models.CharField(max_length=128)),
                ('rights_expires_at', models.DateTimeField()),
                ('contribution', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rms.ideacontribution')),
                ('intake_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='source_assessments', to='rms.researchintakeversion')),
            ],
        ),
        migrations.CreateModel(
            name='IntakeHypothesisBinding',
            fields=[
                ('hypothesis_version', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True, serialize=False, to='rms.hypothesisversion')),
                ('intake_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='hypothesis_bindings', to='rms.researchintakeversion')),
            ],
        ),
        migrations.AddConstraint(
            model_name='researchintake',
            constraint=models.CheckConstraint(condition=models.Q(('synthetic', True)), name='researchintake_synthetic'),
        ),
        migrations.AddConstraint(
            model_name='researchintakeversion',
            constraint=models.UniqueConstraint(fields=('record', 'version'), name='researchintakeversion_sequence'),
        ),
        migrations.AddConstraint(
            model_name='researchintakeversion',
            constraint=models.CheckConstraint(condition=models.Q(('version__gt', 0)), name='researchintakeversion_positive'),
        ),
        migrations.AddConstraint(
            model_name='researchintakeversion',
            constraint=models.CheckConstraint(condition=models.Q(('authority_reference', 'MAU-140:contract:3982eccc-e180-4ac9-bc70-9c4e16aa47f1'), ('classification', 'synthetic'), ('schema_version', '1.0')), name='researchintakeversion_scope'),
        ),
        migrations.AddConstraint(
            model_name='researchintakeversion',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('correction_reason__isnull', True), ('corrects_version__isnull', True), ('version', 1)), models.Q(('correction_reason__isnull', False), ('corrects_version', django.db.models.expressions.CombinedExpression(models.F('version'), '-', models.Value(1))), ('version__gt', 1), models.Q(('correction_reason', ''), _negated=True)), _connector='OR'), name='researchintakeversion_predecessor'),
        ),
        migrations.AddConstraint(
            model_name='researchintakeversion',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('assessment_count__gt', 0), ('investigation_version__isnull', False), ('state', 'ready')), models.Q(('assessment_count', 0), ('investigation_version__isnull', True), ('state', 'early_closed')), _connector='OR'), name='intake_state_shape'),
        ),
        migrations.AddConstraint(
            model_name='intakesourceassessment',
            constraint=models.UniqueConstraint(fields=('intake_version', 'contribution'), name='intake_assessment_contribution'),
        ),
        migrations.RunSQL(GUARDS),
    ]
