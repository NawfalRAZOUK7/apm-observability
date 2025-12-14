# observability/migrations/0004_daily_cagg.py
from __future__ import annotations

from django.db import migrations


def forwards(apps, schema_editor):
    """
    Step 4: Daily continuous aggregate + refresh policy + realtime.

    Creates continuous aggregate view: apirequest_daily
      bucket = time_bucket('1 day', time)
      group by (bucket, service, endpoint)

    Metrics:
      hits            = COUNT(*)
      errors          = COUNT(*) FILTER (WHERE status_code >= 500)
      avg_latency_ms  = AVG(latency_ms)
      p95_latency_ms  = PERCENTILE_CONT(0.95) ... (best-effort; may fall back to NULL)
      max_latency_ms  = MAX(latency_ms)

    Indexes:
      (bucket DESC)
      (service, endpoint, bucket DESC)

    Realtime:
      timescaledb.materialized_only = false

    Refresh policy:
      start_offset      30 days
      end_offset        1 day
      schedule_interval 1 hour
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    create_with_p95 = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS apirequest_daily
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket(INTERVAL '1 day', time) AS bucket,
        service,
        endpoint,
        COUNT(*)::bigint AS hits,
        COUNT(*) FILTER (WHERE status_code >= 500)::bigint AS errors,
        AVG(latency_ms)::double precision AS avg_latency_ms,
        (percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms))::double precision AS p95_latency_ms,
        MAX(latency_ms)::integer AS max_latency_ms
    FROM observability_apirequest
    GROUP BY 1, 2, 3
    WITH NO DATA;
    """

    # Fallback: some Timescale versions may reject non-rollup aggregates in continuous aggregates.
    # We keep the column for API stability, but set it to NULL if unsupported.
    create_without_p95 = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS apirequest_daily
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket(INTERVAL '1 day', time) AS bucket,
        service,
        endpoint,
        COUNT(*)::bigint AS hits,
        COUNT(*) FILTER (WHERE status_code >= 500)::bigint AS errors,
        AVG(latency_ms)::double precision AS avg_latency_ms,
        NULL::double precision AS p95_latency_ms,
        MAX(latency_ms)::integer AS max_latency_ms
    FROM observability_apirequest
    GROUP BY 1, 2, 3
    WITH NO DATA;
    """

    statements_after_create = [
        # Realtime aggregation (include newest raw rows before refresh)
        "ALTER MATERIALIZED VIEW apirequest_daily SET (timescaledb.materialized_only = false);",
        # Indexes
        "CREATE INDEX IF NOT EXISTS apirequest_daily_bucket_desc_idx ON apirequest_daily (bucket DESC);",
        "CREATE INDEX IF NOT EXISTS apirequest_daily_svc_ep_bucket_desc_idx ON apirequest_daily (service, endpoint, bucket DESC);",
        # Refresh policy (best-effort idempotent across Timescale versions)
        """
        DO $$
        BEGIN
            -- Remove any existing policy first (ignore if not present / unsupported)
            BEGIN
                PERFORM remove_continuous_aggregate_policy('apirequest_daily'::regclass, if_exists => TRUE);
            EXCEPTION
                WHEN undefined_function THEN
                    BEGIN
                        PERFORM remove_continuous_aggregate_policy('apirequest_daily'::regclass, if_not_exists => TRUE);
                    EXCEPTION
                        WHEN undefined_function THEN
                            BEGIN
                                PERFORM remove_continuous_aggregate_policy('apirequest_daily'::regclass);
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
                    'apirequest_daily'::regclass,
                    start_offset => INTERVAL '30 days',
                    end_offset => INTERVAL '1 day',
                    schedule_interval => INTERVAL '1 hour',
                    if_not_exists => TRUE
                );
            EXCEPTION
                WHEN undefined_function THEN
                    PERFORM add_continuous_aggregate_policy(
                        'apirequest_daily'::regclass,
                        start_offset => INTERVAL '30 days',
                        end_offset => INTERVAL '1 day',
                        schedule_interval => INTERVAL '1 hour'
                    );
                WHEN others THEN
                    -- If anything unexpected happens, don't block migration
                    NULL;
            END;
        END $$;
        """,
    ]

    with schema_editor.connection.cursor() as cursor:
        # Create the CAGG (try with p95, fall back to NULL column if unsupported)
        try:
            cursor.execute(create_with_p95)
        except Exception:
            cursor.execute(create_without_p95)

        for sql in statements_after_create:
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
                PERFORM remove_continuous_aggregate_policy('apirequest_daily'::regclass, if_exists => TRUE);
            EXCEPTION
                WHEN undefined_function THEN
                    BEGIN
                        PERFORM remove_continuous_aggregate_policy('apirequest_daily'::regclass, if_not_exists => TRUE);
                    EXCEPTION
                        WHEN undefined_function THEN
                            BEGIN
                                PERFORM remove_continuous_aggregate_policy('apirequest_daily'::regclass);
                            EXCEPTION
                                WHEN others THEN NULL;
                            END;
                        WHEN others THEN NULL;
                    END;
                WHEN others THEN NULL;
            END;
        END $$;
        """,
        "DROP INDEX IF EXISTS apirequest_daily_svc_ep_bucket_desc_idx;",
        "DROP INDEX IF EXISTS apirequest_daily_bucket_desc_idx;",
        "DROP MATERIALIZED VIEW IF EXISTS apirequest_daily;",
    ]

    with schema_editor.connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0003_hourly_cagg"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
