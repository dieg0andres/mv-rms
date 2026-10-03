from django.db import migrations


FORWARD_SQL = r"""
ALTER TABLE rms_sourceversion
    ADD CONSTRAINT source_version_predecessor_fk
    FOREIGN KEY (source_id, corrects_version)
    REFERENCES rms_sourceversion (source_id, version)
    DEFERRABLE INITIALLY IMMEDIATE;

CREATE FUNCTION rms_reject_row_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE FUNCTION rms_guard_source_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Source rows cannot be deleted'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF pg_trigger_depth() <> 2
       OR NEW.id <> OLD.id
       OR NEW.source_id <> OLD.source_id
       OR NEW.synthetic IS DISTINCT FROM OLD.synthetic
       OR NEW.created_at <> OLD.created_at
       OR NEW.latest_version <> OLD.latest_version + 1 THEN
        RAISE EXCEPTION 'Source rows are immutable except for trigger-managed watermark advancement'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER rms_source_change_guard
BEFORE UPDATE OR DELETE ON rms_source
FOR EACH ROW EXECUTE FUNCTION rms_guard_source_change();

CREATE FUNCTION rms_append_source_version() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    current_version integer;
BEGIN
    SELECT latest_version INTO current_version
      FROM rms_source
     WHERE id = NEW.source_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source does not exist'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF NEW.version <> current_version + 1 THEN
        RAISE EXCEPTION 'Source version must append exactly after the watermark'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF (NEW.version = 1 AND NEW.corrects_version IS NOT NULL)
       OR (NEW.version > 1 AND NEW.corrects_version <> current_version) THEN
        RAISE EXCEPTION 'Source correction must link to its immediate predecessor'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    UPDATE rms_source
       SET latest_version = NEW.version
     WHERE id = NEW.source_id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER rms_source_version_append
BEFORE INSERT ON rms_sourceversion
FOR EACH ROW EXECUTE FUNCTION rms_append_source_version();

CREATE TRIGGER rms_source_version_immutable
BEFORE UPDATE OR DELETE ON rms_sourceversion
FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();

CREATE FUNCTION rms_validate_manifest() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    expected_text text;
    current_version integer;
BEGIN
    SELECT latest_version INTO current_version
      FROM rms_source
     WHERE id = NEW.source_id
     FOR SHARE;
    IF current_version IS NULL OR NEW.through_version <> current_version THEN
        RAISE EXCEPTION 'Manifest must cover the current Source watermark'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    SELECT '{"schema_version":1,"versions":[' ||
           string_agg(
               '{"byte_length":' || v.byte_length::text ||
               ',"content_sha256":' || to_json(v.content_sha256)::text ||
               ',"corrects_version":' || COALESCE(v.corrects_version::text, 'null') ||
               ',"source_id":' || to_json(s.source_id)::text ||
               ',"synthetic":true,"version":' || v.version::text || '}',
               ',' ORDER BY v.version
           ) || ']}'
      INTO expected_text
      FROM rms_sourceversion v
      JOIN rms_source s ON s.id = v.source_id
     WHERE v.source_id = NEW.source_id
       AND v.version <= NEW.through_version;

    IF expected_text IS NULL
       OR NEW.schema_version <> 1
       OR NEW.version_count <> NEW.through_version
       OR NEW.manifest_bytes <> convert_to(expected_text, 'UTF8') THEN
        RAISE EXCEPTION 'Manifest bytes do not match ordered Source versions'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER rms_source_manifest_validate
BEFORE INSERT ON rms_sourcemanifest
FOR EACH ROW EXECUTE FUNCTION rms_validate_manifest();

CREATE TRIGGER rms_source_manifest_immutable
BEFORE UPDATE OR DELETE ON rms_sourcemanifest
FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();

CREATE TRIGGER rms_idempotency_immutable
BEFORE UPDATE OR DELETE ON rms_idempotencyrecord
FOR EACH ROW EXECUTE FUNCTION rms_reject_row_change();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS rms_idempotency_immutable ON rms_idempotencyrecord;
DROP TRIGGER IF EXISTS rms_source_manifest_immutable ON rms_sourcemanifest;
DROP TRIGGER IF EXISTS rms_source_manifest_validate ON rms_sourcemanifest;
DROP TRIGGER IF EXISTS rms_source_version_immutable ON rms_sourceversion;
DROP TRIGGER IF EXISTS rms_source_version_append ON rms_sourceversion;
DROP TRIGGER IF EXISTS rms_source_change_guard ON rms_source;
DROP FUNCTION IF EXISTS rms_validate_manifest();
DROP FUNCTION IF EXISTS rms_append_source_version();
DROP FUNCTION IF EXISTS rms_guard_source_change();
DROP FUNCTION IF EXISTS rms_reject_row_change();
ALTER TABLE rms_sourceversion DROP CONSTRAINT IF EXISTS source_version_predecessor_fk;
"""


class Migration(migrations.Migration):
    dependencies = [("rms", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
