"""Preserve unresolved attempts, their reconciliation, and exact partial observations."""

from django.db import migrations, models
from django.db.models import Q


EVENT_BINDING = """
CREATE FUNCTION rms_check_observed_event() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
DECLARE
    prior rms_runlifecycleevent%ROWTYPE;
BEGIN
    IF (NEW.partial_evidence_bytes IS NULL) <> (NEW.partial_evidence_sha256 IS NULL)
        OR (NEW.partial_evidence_bytes IS NOT NULL AND (
            octet_length(NEW.partial_evidence_bytes) NOT BETWEEN 1 AND 8192
            OR NEW.partial_evidence_sha256 IS DISTINCT FROM encode(digest(NEW.partial_evidence_bytes, 'sha256'), 'hex')
        )) THEN
        RAISE EXCEPTION 'Invalid event evidence' USING ERRCODE = '23514';
    END IF;
    IF NEW.previous_event_id IS NOT NULL THEN
        SELECT * INTO prior FROM rms_runlifecycleevent WHERE id = NEW.previous_event_id;
        IF NOT FOUND OR prior.run_id <> NEW.run_id OR prior.sequence + 1 <> NEW.sequence
            OR prior.state NOT IN ('running', 'unknown') THEN
            RAISE EXCEPTION 'Invalid observed event predecessor' USING ERRCODE = '23514';
        END IF;
        IF prior.state = 'unknown' AND (NEW.state NOT IN ('completed', 'failed', 'cancelled')
            OR NEW.partial_evidence_bytes IS NULL OR btrim(NEW.reason) = '') THEN
            RAISE EXCEPTION 'Unknown state requires documented reconciliation' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER rr_binding ON rms_runlifecycleevent;
CREATE TRIGGER rr_binding BEFORE INSERT ON rms_runlifecycleevent
    FOR EACH ROW EXECUTE FUNCTION rms_check_observed_event();
"""

RESTORE_BINDING = """
DO $$ BEGIN
    IF EXISTS (SELECT FROM rms_runlifecycleevent WHERE state = 'unknown' OR partial_evidence_bytes IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot reverse populated event evidence or reconciliation history';
    END IF;
END $$;
DROP TRIGGER rr_binding ON rms_runlifecycleevent;
CREATE TRIGGER rr_binding BEFORE INSERT ON rms_runlifecycleevent
    FOR EACH ROW EXECUTE FUNCTION rms_rr_check_binding();
DROP FUNCTION rms_check_observed_event();
"""


class Migration(migrations.Migration):
    dependencies = [('rms', '0010_run_assurance')]

    operations = [
        migrations.AddField('runlifecycleevent', 'partial_evidence_bytes',
                            models.BinaryField(null=True, editable=False)),
        migrations.AddField('runlifecycleevent', 'partial_evidence_sha256',
                            models.CharField(max_length=64, null=True, editable=False)),
        migrations.RemoveConstraint('runlifecycleevent', 'run_event_shape'),
        migrations.AddConstraint('runlifecycleevent', models.CheckConstraint(
            condition=(Q(sequence=1, previous_event__isnull=True, state__in=['running', 'failed', 'cancelled', 'unknown']) |
                       Q(sequence__in=[2, 3], previous_event__isnull=False, state__in=['completed', 'failed', 'cancelled', 'unknown'])),
            name='run_event_shape')),
        migrations.RunSQL(EVENT_BINDING, RESTORE_BINDING),
    ]
