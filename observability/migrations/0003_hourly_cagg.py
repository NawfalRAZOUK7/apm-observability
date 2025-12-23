# observability/migrations/0003_hourly_cagg.py
from __future__ import annotations

from django.db import migrations


def forwards(apps, schema_editor):
    """
    Step 3 (part 2): Hourly continuous aggregate + refresh policy + realtime.

    Creates continuous aggregate view: apirequest_hourly
      bucket = time_bucket('1 hour', time)
      group by (bucket, service, endpoint)

    Metrics:
      hits            = COUNT(*)
      errors          = COUNT(*) FILTER (WHERE status_code >= 500)
      avg_latency_ms  = AVG(latency_ms)
      max_latency_ms  = MAX(latency_ms)

    Indexes:
      (bucket DESC)
      (service, endpoint, bucket DESC)

    Realtime:
      timescaledb.materialized_only = false

    Refresh policy:
      start_offset      7 days
      end_offset        1 hour
      schedule_interval 15 minutes
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    statements = [
        # Check if TimescaleDB is available before creating continuous aggregates
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
                RAISE NOTICE 'TimescaleDB not available, skipping continuous aggregate creation';
                RETURN;
            END IF;

            -- TimescaleDB is available, proceed with continuous aggregate setup
            -- 1) Create continuous aggregate (WITH NO DATA => policy/manual refresh fills it)
            CREATE MATERIALIZED VIEW IF NOT EXISTS apirequest_hourly
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket(INTERVAL '1 hour', time) AS bucket,
                service,
                endpoint,
                COUNT(*)::bigint AS hits,
                COUNT(*) FILTER (WHERE status_code >= 500)::bigint AS errors,
                AVG(latency_ms)::double precision AS avg_latency_ms,
                MAX(latency_ms)::integer AS max_latency_ms
            FROM observability_apirequest
            GROUP BY 1, 2, 3
            WITH NO DATA;

            -- 2) Enable realtime aggregation (include newest raw rows before refresh)
            ALTER MATERIALIZED VIEW apirequest_hourly SET (timescaledb.materialized_only = false);

            -- 3) Indexes
            CREATE INDEX IF NOT EXISTS apirequest_hourly_bucket_desc_idx ON apirequest_hourly (bucket DESC);
            CREATE INDEX IF NOT EXISTS apirequest_hourly_svc_ep_bucket_desc_idx ON apirequest_hourly (service, endpoint, bucket DESC);

            -- 4) Refresh policy (best-effort idempotent across Timescale versions)
            BEGIN
                -- Remove any existing policy first (ignore if not present / unsupported)
                BEGIN
                    PERFORM remove_continuous_aggregate_policy('apirequest_hourly'::regclass, if_exists => TRUE);
                EXCEPTION
                    WHEN undefined_function THEN
                        BEGIN
                            PERFORM remove_continuous_aggregate_policy('apirequest_hourly'::regclass, if_not_exists => TRUE);
                        EXCEPTION
                            WHEN undefined_function THEN
                                BEGIN
                                    PERFORM remove_continuous_aggregate_policy('apirequest_hourly'::regclass);
                                EXCEPTION
                                    WHEN others THEN NULL;
                                END;
                            WHEN others THEN NULL;
                        END;
                    WHEN others THEN NULL;
                END;

                -- Add the desired policy:
                -- Try with if_not_exists (newer), fall back to no-flag signature (older).
                BEGIN
                PERFORM add_continuous_aggregate_policy(
                    'apirequest_hourly'::regclass,
                    start_offset => INTERVAL '7 days',
                    end_offset => INTERVAL '1 hour',
                    schedule_interval => INTERVAL '15 minutes',
                    if_not_exists => TRUE
                );
                EXCEPTION
                    WHEN undefined_function THEN
                        PERFORM add_continuous_aggregate_policy(
                            'apirequest_hourly'::regclass,
                            start_offset => INTERVAL '7 days',
                            end_offset => INTERVAL '1 hour',
                            schedule_interval => INTERVAL '15 minutes'
                        );
                    WHEN others THEN
                        -- If anything unexpected happens, don't block migration
                        NULL;
                END;
            END;
        END $$;
        """,
    ]

    with schema_editor.connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


def backwards(apps, schema_editor):
    """
    Reverse:
      - Remove refresh policy (if exists)
      - Drop indexes (optional but clean)
      - Drop continuous aggregate materialized view
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    statements = [
        # Remove policy (best-effort across Timescale versions)
        """
        DO $$
        BEGIN
            BEGIN
                PERFORM remove_continuous_aggregate_policy('apirequest_hourly'::regclass, if_exists => TRUE);
            EXCEPTION
                WHEN undefined_function THEN
                    BEGIN
                        PERFORM remove_continuous_aggregate_policy('apirequest_hourly'::regclass, if_not_exists => TRUE);
                    EXCEPTION
                        WHEN undefined_function THEN
                            BEGIN
                                PERFORM remove_continuous_aggregate_policy('apirequest_hourly'::regclass);
                            EXCEPTION
                                WHEN others THEN NULL;
                            END;
                        WHEN others THEN NULL;
                    END;
                WHEN others THEN NULL;
            END;
        END $$;
        """,
        "DROP INDEX IF EXISTS apirequest_hourly_svc_ep_bucket_desc_idx;",
        "DROP INDEX IF EXISTS apirequest_hourly_bucket_desc_idx;",
        "DROP MATERIALIZED VIEW IF EXISTS apirequest_hourly;",
    ]

    with schema_editor.connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0002_timescale"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
