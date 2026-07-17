# observability/migrations/0015_rls_spans_and_force.py
"""Enforce tenant RLS now that ingestion is tenant-aware (Phase 6, PostgreSQL).

- Install the same `tenant_isolation` policy on the spans hypertable.
- Switch both `observability_apirequest` and `observability_span` to
  FORCE ROW LEVEL SECURITY.

Safety: the policy is permissive when `app.current_project` is unset (its USING
expression short-circuits), so FORCE never breaks owner/migration/aggregate
queries that set no tenant — it only scopes sessions that DO set the GUC (OTLP
ingestion via set_current_project). No-op on SQLite.
"""

from __future__ import annotations

from django.db import migrations

POLICY_NAME = "tenant_isolation"


def _policy_sql(table: str) -> str:
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
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    api_request = apps.get_model("observability", "ApiRequest")._meta.db_table
    span = apps.get_model("observability", "Span")._meta.db_table
    with connection.cursor() as cursor:
        # Span: create policy + force.
        cursor.execute(_policy_sql(span))
        # ApiRequest: policy already exists (0012); just force enforcement.
        cursor.execute(f"ALTER TABLE {api_request} FORCE ROW LEVEL SECURITY;")


def backwards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    api_request = apps.get_model("observability", "ApiRequest")._meta.db_table
    span = apps.get_model("observability", "Span")._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {api_request} NO FORCE ROW LEVEL SECURITY;")
        cursor.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {span};")
        cursor.execute(f"ALTER TABLE {span} NO FORCE ROW LEVEL SECURITY;")
        cursor.execute(f"ALTER TABLE {span} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0014_span_hypertable"),
        ("observability", "0012_rls_apirequest"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
