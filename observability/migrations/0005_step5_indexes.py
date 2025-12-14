from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0004_daily_cagg"),
    ]

    operations = [
        # Helps raw fallback queries that scan/filter by time range + order by time desc
        migrations.AddIndex(
            model_name="apirequest",
            index=models.Index(fields=["-time"], name="api_req_time_desc_idx"),
        ),
    ]
