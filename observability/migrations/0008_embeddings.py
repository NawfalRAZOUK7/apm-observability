from __future__ import annotations

from django.db import migrations, models
import pgvector.django


def create_vector_extension(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0007_task7_indexes"),
    ]

    operations = [
        migrations.RunPython(create_vector_extension, migrations.RunPython.noop),
        migrations.CreateModel(
            name="ApiRequestEmbedding",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[("error", "error"), ("request", "request")],
                        default="error",
                        max_length=16,
                    ),
                ),
                ("model", models.CharField(default="text-embedding-004", max_length=64)),
                ("content_hash", models.CharField(db_index=True, max_length=64)),
                ("embedding", pgvector.django.VectorField(dimensions=768)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "request",
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=models.deletion.CASCADE,
                        related_name="embedding",
                        to="observability.apirequest",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["source", "created_at"],
                        name="api_req_emb_source_time_idx",
                    ),
                ],
            },
        ),
    ]
