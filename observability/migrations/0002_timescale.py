# observability/migrations/0002_timescale.py
from __future__ import annotations

import os
from django.db import migrations


def forwards(apps, schema_editor):
    """
    Step 3 (part 1):
    - Enable TimescaleDB extension (PostgreSQL only)
    - Drop PK on (id) because Timescale requires unique indexes to include partition column (time)
    - Convert observability_apirequest into hypertable on `time` (idempotent)
    - Add recommended index for ordering by time
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    statements = [
        # Check if TimescaleDB extension is available before creating it
        """
        DO $$
        BEGIN
            -- Try to create TimescaleDB extension, but don't fail if it's not available
            BEGIN
                CREATE EXTENSION IF NOT EXISTS timescaledb;
                RAISE NOTICE 'TimescaleDB extension created successfully';
            EXCEPTION
                WHEN OTHERS THEN
                    RAISE NOTICE 'TimescaleDB extension not available, skipping TimescaleDB setup';
                    RETURN;
            END;
        END $$;
        """,
        # Check if TimescaleDB is available before using TimescaleDB-specific features
        """
        DO $$
        DECLARE
            has_timescaledb boolean := FALSE;
        BEGIN
            -- Check if TimescaleDB extension exists
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            ) INTO has_timescaledb;

            IF NOT has_timescaledb THEN
                RAISE NOTICE 'TimescaleDB not available, skipping hypertable creation';
                RETURN;
            END IF;

            -- TimescaleDB is available, proceed with hypertable setup
            -- If not already a hypertable, drop the primary key constraint on id (Timescale requirement).
            DECLARE
                is_ht boolean;
                pk_name text;
            BEGIN
                SELECT EXISTS (
                    SELECT 1
                    FROM timescaledb_information.hypertables
                    WHERE hypertable_schema = 'public'
                      AND hypertable_name = 'observability_apirequest'
                ) INTO is_ht;

                IF NOT is_ht THEN
                    SELECT conname
                    INTO pk_name
                    FROM pg_constraint
                    WHERE conrelid = 'observability_apirequest'::regclass
                      AND contype = 'p'
                    LIMIT 1;

                    IF pk_name IS NOT NULL THEN
                        EXECUTE format('ALTER TABLE observability_apirequest DROP CONSTRAINT %I', pk_name);
                    END IF;
                END IF;
            END;

            -- Convert to hypertable (idempotent)
            PERFORM create_hypertable(
                'observability_apirequest',
                'time',
                if_not_exists => TRUE,
                migrate_data => TRUE,
                create_default_indexes => FALSE,
                chunk_time_interval => INTERVAL '1 day'
            );

            -- Optional index that helps ORDER BY time DESC
            EXECUTE 'CREATE INDEX IF NOT EXISTS observability_apirequest_time_desc_idx ON observability_apirequest (time DESC)';
        END $$;
        """,
    ]

    with schema_editor.connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


def backwards(apps, schema_editor):
    """
    Destructive full undo (DATA LOSS) when enabled.

    Why: there's no safe "unhypertable" switch.
    So if you want to rollback to 0001 cleanly:
      - DROP the table (hypertable + chunks) -> DATA LOSS
      - Recreate the normal Django table for 0001 state.

    Enable with:
      export APM_DESTRUCTIVE_DOWN=1

    Optional:
      export APM_DROP_TIMESCALE_EXTENSION_ON_DOWN=1
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    if os.environ.get("APM_DESTRUCTIVE_DOWN") != "1":
        # To avoid lying to Django migration state with an unsafe/no-op rollback,
        # we block rollback unless you explicitly allow destructive down.
        raise RuntimeError(
            "Cannot safely reverse 0002_timescale. "
            "Set APM_DESTRUCTIVE_DOWN=1 to perform a destructive rollback (DATA LOSS)."
        )

    ApiRequest = apps.get_model("observability", "ApiRequest")

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS observability_apirequest_time_desc_idx;")
        cursor.execute("DROP TABLE IF EXISTS observability_apirequest CASCADE;")

    # Recreate normal table to match 0001 schema state
    schema_editor.create_model(ApiRequest)

    if os.environ.get("APM_DROP_TIMESCALE_EXTENSION_ON_DOWN") == "1":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE;")


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
