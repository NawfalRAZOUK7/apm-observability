from __future__ import annotations

from django.db import migrations, models
from django.db.models import Q


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    sql = """
    DO $$
    BEGIN
        IF to_regclass('apirequest_hourly') IS NOT NULL THEN
            CREATE INDEX IF NOT EXISTS apirequest_hourly_ep_bucket_desc_idx
                ON apirequest_hourly (endpoint, bucket DESC);
            CREATE INDEX IF NOT EXISTS apirequest_hourly_svc_bucket_desc_idx
                ON apirequest_hourly (service, bucket DESC);
        END IF;

        IF to_regclass('apirequest_daily') IS NOT NULL THEN
            CREATE INDEX IF NOT EXISTS apirequest_daily_ep_bucket_desc_idx
                ON apirequest_daily (endpoint, bucket DESC);
            CREATE INDEX IF NOT EXISTS apirequest_daily_svc_bucket_desc_idx
                ON apirequest_daily (service, bucket DESC);
        END IF;
    END $$;
    """

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    statements = [
        "DROP INDEX IF EXISTS apirequest_hourly_ep_bucket_desc_idx;",
        "DROP INDEX IF EXISTS apirequest_hourly_svc_bucket_desc_idx;",
        "DROP INDEX IF EXISTS apirequest_daily_ep_bucket_desc_idx;",
        "DROP INDEX IF EXISTS apirequest_daily_svc_bucket_desc_idx;",
    ]

    with schema_editor.connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0006_remove_apirequest_api_req_time_desc_idx"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="apirequest",
            index=models.Index(
                fields=["service", "endpoint", "method", "-time"],
                name="api_req_svc_ep_method_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="apirequest",
            index=models.Index(
                fields=["service", "endpoint", "-time"],
                name="api_req_err_svc_ep_time_idx",
                condition=Q(status_code__gte=500),
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
