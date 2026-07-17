# observability/migrations/0017_metrics_logs_hypertable_rls.py
"""Convert metric/log tables to TimescaleDB hypertables + install tenant RLS.

PostgreSQL-only, idempotent, no-op on SQLite. Mirrors the span hypertable
(0014) and the permissive-when-unset RLS policy (0015) for the two new signals.
"""

from __future__ import annotations

import os

from django.db import migrations

POLICY_NAME = "tenant_isolation"
TABLES = ("observability_metricpoint", "observability_logrecord")


def _hypertable_sql(table: str) -> str:
    return f"""
    DO $$
    DECLARE has_ts boolean := FALSE;
    BEGIN
        SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='timescaledb') INTO has_ts;
        IF NOT has_ts THEN RAISE NOTICE 'no timescaledb, skip {table}'; RETURN; END IF;
        DECLARE is_ht boolean; pk_name text;
        BEGIN
            SELECT EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_schema='public' AND hypertable_name='{table}'
            ) INTO is_ht;
            IF NOT is_ht THEN
                SELECT conname INTO pk_name FROM pg_constraint
                WHERE conrelid='{table}'::regclass AND contype='p' LIMIT 1;
                IF pk_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', pk_name);
                END IF;
            END IF;
        END;
        PERFORM create_hypertable('{table}','time',
            if_not_exists=>TRUE, migrate_data=>TRUE,
            create_default_indexes=>FALSE, chunk_time_interval=>INTERVAL '1 day');
        EXECUTE 'CREATE INDEX IF NOT EXISTS {table}_time_desc_idx ON {table} (time DESC)';
    END $$;
    """


def _rls_sql(table: str) -> str:
    return f"""
    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS {POLICY_NAME} ON {table};
    CREATE POLICY {POLICY_NAME} ON {table}
    USING (
        current_setting('app.current_project', true) IS NULL
        OR current_setting('app.current_project', true) = ''
        OR project_id = NULLIF(current_setting('app.current_project', true), '')::bigint
    );
    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
    """


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(_hypertable_sql(table))
            cursor.execute(_rls_sql(table))


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    if os.environ.get("APM_DESTRUCTIVE_DOWN") != "1":
        raise RuntimeError("Set APM_DESTRUCTIVE_DOWN=1 to reverse 0017 (DATA LOSS).")
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table};")
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0016_logrecord_metricpoint"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
