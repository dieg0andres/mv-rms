# Generated for frozen RMS-SI-1.0 on 2026-09-22.

import django.db.models.deletion
import rms.models
import django.utils.timezone
import uuid
from django.db import migrations, models
from django.db.models import F


BACKFILL_SQL = r"""
DROP TRIGGER rms_source_version_immutable ON rms_sourceversion;

UPDATE rms_sourceversion AS version
   SET source_version_id = 'SRCV-' || version.id::text,
       title = 'Synthetic Source ' || source.source_id,
       source_type = 'other',
       citation = 'Synthetic Source ' || source.source_id,
       observed_available_at = source.created_at,
       correction_reason = CASE
           WHEN version.version = 1 THEN NULL
           ELSE 'Imported from the RMS-VS-1 append-only history.'
       END,
       changed_fields = CASE
           WHEN version.version = 1 THEN '[]'::jsonb
           ELSE '["content_sha256"]'::jsonb
       END,
       created_by = 'migration'
  FROM rms_source AS source
 WHERE source.id = version.source_id;

CREATE TRIGGER rms_source_version_immutable
BEFORE UPDATE OR DELETE ON rms_sourceversion
FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();
"""

FORWARD_INVARIANTS = r"""
ALTER TABLE rms_ideaversion
    ADD CONSTRAINT idea_version_predecessor_fk
    FOREIGN KEY (idea_id, corrects_version)
    REFERENCES rms_ideaversion (idea_id, version)
    DEFERRABLE INITIALLY IMMEDIATE;

CREATE FUNCTION rms_guard_idea_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Idea rows cannot be deleted'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF pg_trigger_depth() <> 2
       OR NEW.id <> OLD.id
       OR NEW.idea_id <> OLD.idea_id
       OR NEW.synthetic IS DISTINCT FROM OLD.synthetic
       OR NEW.created_at <> OLD.created_at
       OR NEW.latest_version <> OLD.latest_version + 1 THEN
        RAISE EXCEPTION 'Idea rows are immutable except for trigger-managed watermark advancement'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER rms_idea_change_guard
BEFORE UPDATE OR DELETE ON rms_idea
FOR EACH ROW EXECUTE FUNCTION rms_guard_idea_change();

CREATE FUNCTION rms_append_idea_version() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    current_version integer;
BEGIN
    SELECT latest_version INTO current_version
      FROM rms_idea
     WHERE id = NEW.idea_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Idea does not exist'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF NEW.version <> current_version + 1 THEN
        RAISE EXCEPTION 'Idea version must append exactly after the watermark'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF (NEW.version = 1 AND NEW.corrects_version IS NOT NULL)
       OR (NEW.version > 1 AND NEW.corrects_version <> current_version) THEN
        RAISE EXCEPTION 'Idea correction must link to its immediate predecessor'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    UPDATE rms_idea
       SET latest_version = NEW.version
     WHERE id = NEW.idea_id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER rms_idea_version_append
BEFORE INSERT ON rms_ideaversion
FOR EACH ROW EXECUTE FUNCTION rms_append_idea_version();

CREATE TRIGGER rms_idea_version_immutable
BEFORE UPDATE OR DELETE ON rms_ideaversion
FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();

CREATE TRIGGER rms_idea_contribution_immutable
BEFORE UPDATE OR DELETE ON rms_ideacontribution
FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();
"""

REVERSE_INVARIANTS = r"""
DROP TRIGGER IF EXISTS rms_idea_contribution_immutable ON rms_ideacontribution;
DROP TRIGGER IF EXISTS rms_idea_version_immutable ON rms_ideaversion;
DROP TRIGGER IF EXISTS rms_idea_version_append ON rms_ideaversion;
DROP TRIGGER IF EXISTS rms_idea_change_guard ON rms_idea;
DROP FUNCTION IF EXISTS rms_append_idea_version();
DROP FUNCTION IF EXISTS rms_guard_idea_change();
ALTER TABLE rms_ideaversion DROP CONSTRAINT IF EXISTS idea_version_predecessor_fk;
"""


class Migration(migrations.Migration):
    atomic = True
    dependencies = [("rms", "0002_source_invariants")]

    operations = [
        migrations.AddField(
            model_name="sourceversion",
            name="source_version_id",
            field=models.CharField(max_length=41, null=True, editable=False),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="correction_reason",
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="changed_fields",
            field=models.JSONField(default=list, editable=False),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="title",
            field=models.CharField(max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="source_type",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="citation",
            field=models.CharField(max_length=2000, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="observed_available_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="authors",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="publisher",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="canonical_url",
            field=models.CharField(blank=True, max_length=2048, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="rights_note",
            field=models.CharField(blank=True, max_length=4000, null=True),
        ),
        migrations.AddField(
            model_name="sourceversion",
            name="created_by",
            field=models.CharField(max_length=150, null=True, editable=False),
        ),
        migrations.RunSQL(BACKFILL_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.AlterField(
            model_name="sourceversion",
            name="source_version_id",
            field=models.CharField(
                default=rms.models.source_version_identifier,
                editable=False,
                max_length=41,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="sourceversion",
            name="title",
            field=models.CharField(max_length=500),
        ),
        migrations.AlterField(
            model_name="sourceversion",
            name="source_type",
            field=models.CharField(
                choices=[(value, value) for value in rms.models.SOURCE_TYPES],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="sourceversion",
            name="citation",
            field=models.CharField(max_length=2000),
        ),
        migrations.AlterField(
            model_name="sourceversion",
            name="observed_available_at",
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name="sourceversion",
            name="created_by",
            field=models.CharField(editable=False, max_length=150),
        ),
        migrations.CreateModel(
            name="Idea",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("idea_id", models.CharField(default=rms.models.idea_identifier, editable=False, max_length=40, unique=True)),
                ("synthetic", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("latest_version", models.PositiveIntegerField(default=0, editable=False)),
            ],
            options={
                "constraints": [models.CheckConstraint(condition=models.Q(("synthetic", True)), name="idea_synthetic_true")],
            },
        ),
        migrations.CreateModel(
            name="IdeaVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("idea_version_id", models.CharField(default=rms.models.idea_version_identifier, editable=False, max_length=41, unique=True)),
                ("version", models.PositiveIntegerField()),
                ("corrects_version", models.PositiveIntegerField(blank=True, null=True)),
                ("correction_reason", models.CharField(blank=True, max_length=1000, null=True)),
                ("changed_fields", models.JSONField(default=list, editable=False)),
                ("title", models.CharField(max_length=500)),
                ("mechanism", models.CharField(max_length=4000)),
                ("testable_claim", models.CharField(max_length=4000)),
                ("falsification", models.CharField(max_length=4000)),
                ("eligible_market", models.CharField(choices=[(value, value) for value in rms.models.ELIGIBLE_MARKETS], max_length=16)),
                ("workflow_status", models.CharField(choices=[(value, value) for value in rms.models.WORKFLOW_STATUSES], max_length=16)),
                ("rejection_reason", models.CharField(blank=True, max_length=2000, null=True)),
                ("synthetic", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("created_by", models.CharField(editable=False, max_length=150)),
                ("idea", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="rms.idea")),
            ],
            options={
                "ordering": ["version"],
                "constraints": [
                    models.UniqueConstraint(fields=("idea", "version"), name="idea_version_unique"),
                    models.CheckConstraint(condition=models.Q(("version__gt", 0)), name="idea_version_positive"),
                    models.CheckConstraint(condition=models.Q(("synthetic", True)), name="idea_version_synthetic_true"),
                    models.CheckConstraint(condition=models.Q(models.Q(("corrects_version__isnull", True), ("version", 1)), models.Q(("version__gt", 1), ("corrects_version", F("version") - 1)), _connector="OR"), name="idea_version_immediate_predecessor"),
                    models.CheckConstraint(condition=models.Q(models.Q(("rejection_reason__isnull", False), ("workflow_status", "rejected")), models.Q(models.Q(("workflow_status", "rejected"), _negated=True), ("rejection_reason__isnull", True)), _connector="OR"), name="idea_rejection_reason_state"),
                ],
            },
        ),
        migrations.CreateModel(
            name="IdeaContribution",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("contribution_id", models.CharField(default=rms.models.contribution_identifier, editable=False, max_length=40, unique=True)),
                ("contribution", models.CharField(max_length=4000)),
                ("position", models.PositiveSmallIntegerField()),
                ("idea_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="contributions", to="rms.ideaversion")),
                ("source_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="idea_contributions", to="rms.sourceversion")),
            ],
            options={
                "ordering": ["position"],
                "constraints": [
                    models.UniqueConstraint(fields=("idea_version", "position"), name="idea_contribution_position_unique"),
                    models.CheckConstraint(condition=models.Q(("position__gt", 0)), name="idea_contribution_position_positive"),
                ],
            },
        ),
        migrations.RunSQL(FORWARD_INVARIANTS, REVERSE_INVARIANTS),
    ]
