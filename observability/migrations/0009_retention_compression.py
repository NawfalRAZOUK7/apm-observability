# observability/migrations/0009_retention_compression.py
from __future__ import annotations

import os

from django.db import migrations


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def forwards(apps, schema_editor):
    """
    Data lifecycle policies on the raw hypertable (PostgreSQL + TimescaleDB only):
      - Retention: drop raw chunks older than APM_RETENTION_DAYS.

    Raw data is dropped while the hourly/daily continuous aggregates keep the
    long-term history -- the idiomatic time-series lifecycle. All statements are
    idempotent and guarded so SQLite / plain-PostgreSQL runs are no-ops.

    Native columnar compression (a.k.a. "columnstore") is deliberately NOT enabled
    here: TimescaleDB refuses it on any table with row-level security
    ("columnstore cannot be used on table with row security"), and conversely
    refuses to enable RLS once columnstore is on. Tenant isolation (0012/0015/0017
    install the `tenant_isolation` policy on this table) is a security invariant and
    wins over the storage optimisation. Retention + the continuous aggregates are
    unaffected -- neither depends on compression.
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    retention_days = _int_env("APM_RETENTION_DAYS", 90)

    sql = f"""
    DO $$
    DECLARE
        has_timescaledb boolean := FALSE;
        is_ht boolean := FALSE;
    BEGIN
        SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')
            INTO has_timescaledb;
        IF NOT has_timescaledb THEN
            RAISE NOTICE 'TimescaleDB not available, skipping lifecycle policies';
            RETURN;
        END IF;

        SELECT EXISTS (
            SELECT 1 FROM timescaledb_information.hypertables
            WHERE hypertable_schema = 'public'
              AND hypertable_name = 'observability_apirequest'
        ) INTO is_ht;
        IF NOT is_ht THEN
            RAISE NOTICE 'observability_apirequest is not a hypertable, skipping';
            RETURN;
        END IF;

        -- Drop raw chunks older than the retention window.
        PERFORM add_retention_policy(
            'observability_apirequest',
            INTERVAL '{retention_days} days',
            if_not_exists => TRUE
        );
    END $$;
    """

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def backwards(apps, schema_editor):
    """Remove the lifecycle policies (idempotent).

    `remove_compression_policy` is still called so that a database created by an
    earlier revision of this migration -- which did enable columnstore -- unwinds
    cleanly; it is a no-op everywhere else.
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    sql = """
    DO $$
    DECLARE
        has_timescaledb boolean := FALSE;
    BEGIN
        SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')
            INTO has_timescaledb;
        IF NOT has_timescaledb THEN
            RETURN;
        END IF;

        PERFORM remove_retention_policy('observability_apirequest', if_exists => TRUE);
        PERFORM remove_compression_policy('observability_apirequest', if_exists => TRUE);
    END $$;
    """

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0008_embeddings"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
