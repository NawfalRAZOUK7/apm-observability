# observability/migrations/0014_span_hypertable.py
"""Convert observability_span into a TimescaleDB hypertable on `time` (Phase 6).

Mirrors 0002_timescale: PostgreSQL-only, idempotent, drops the id PK (Timescale
requires unique indexes to include the partition column) before create_hypertable.
No-op on SQLite.
"""
from __future__ import annotations

import os

from django.db import migrations

TABLE = "observability_span"


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    sql = f"""
    DO $$
    DECLARE
        has_timescaledb boolean := FALSE;
    BEGIN
        SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')
        INTO has_timescaledb;
        IF NOT has_timescaledb THEN
            RAISE NOTICE 'TimescaleDB not available, skipping span hypertable';
            RETURN;
        END IF;

        DECLARE
            is_ht boolean;
            pk_name text;
        BEGIN
            SELECT EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'public' AND hypertable_name = '{TABLE}'
            ) INTO is_ht;

            IF NOT is_ht THEN
                SELECT conname INTO pk_name
                FROM pg_constraint
                WHERE conrelid = '{TABLE}'::regclass AND contype = 'p'
                LIMIT 1;
                IF pk_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE {TABLE} DROP CONSTRAINT %I', pk_name);
                END IF;
            END IF;
        END;

        PERFORM create_hypertable(
            '{TABLE}', 'time',
            if_not_exists => TRUE,
            migrate_data => TRUE,
            create_default_indexes => FALSE,
            chunk_time_interval => INTERVAL '1 day'
        );
        EXECUTE 'CREATE INDEX IF NOT EXISTS {TABLE}_time_desc_idx ON {TABLE} (time DESC)';
    END $$;
    """
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    if os.environ.get("APM_DESTRUCTIVE_DOWN") != "1":
        raise RuntimeError(
            "Cannot safely reverse 0014_span_hypertable. "
            "Set APM_DESTRUCTIVE_DOWN=1 for a destructive rollback (DATA LOSS)."
        )
    Span = apps.get_model("observability", "Span")
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP INDEX IF EXISTS {TABLE}_time_desc_idx;")
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE} CASCADE;")
    schema_editor.create_model(Span)


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0013_service_span"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
