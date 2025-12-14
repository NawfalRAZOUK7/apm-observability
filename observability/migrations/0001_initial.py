from __future__ import annotations

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ApiRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("time", models.DateTimeField(db_index=True)),
                ("service", models.CharField(db_index=True, max_length=100)),
                ("endpoint", models.CharField(db_index=True, max_length=255)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("GET", "GET"),
                            ("POST", "POST"),
                            ("PUT", "PUT"),
                            ("PATCH", "PATCH"),
                            ("DELETE", "DELETE"),
                            ("HEAD", "HEAD"),
                            ("OPTIONS", "OPTIONS"),
                        ],
                        db_index=True,
                        max_length=10,
                    ),
                ),
                ("status_code", models.PositiveSmallIntegerField(db_index=True)),
                ("latency_ms", models.PositiveIntegerField(db_index=True)),
                ("trace_id", models.CharField(blank=True, db_index=True, max_length=128, null=True)),
                ("user_ref", models.CharField(blank=True, db_index=True, max_length=128, null=True)),
                ("tags", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["-time"],
            },
        ),
        migrations.AddIndex(
            model_name="apirequest",
            index=models.Index(fields=["service", "endpoint", "-time"], name="api_req_svc_ep_time_idx"),
        ),
        migrations.AddIndex(
            model_name="apirequest",
            index=models.Index(fields=["service", "-time"], name="api_req_svc_time_idx"),
        ),
        migrations.AddIndex(
            model_name="apirequest",
            index=models.Index(fields=["endpoint", "-time"], name="api_req_ep_time_idx"),
        ),
        migrations.AddIndex(
            model_name="apirequest",
            index=models.Index(fields=["status_code", "-time"], name="api_req_status_time_idx"),
        ),
        migrations.AddConstraint(
            model_name="apirequest",
            constraint=models.CheckConstraint(condition=Q(("latency_ms__gte", 0)), name="api_req_latency_ms_gte_0"),
        ),
        migrations.AddConstraint(
            model_name="apirequest",
            constraint=models.CheckConstraint(
                condition=Q(("status_code__gte", 100), ("status_code__lte", 599)),
                name="api_req_status_code_valid_http",
            ),
        ),
    ]
