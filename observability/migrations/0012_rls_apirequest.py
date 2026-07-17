"""Install Row-Level Security scaffolding on ApiRequest (Phase 5, PostgreSQL).

Policy: a session sees rows for its ``app.current_project`` GUC (set by
tenancy.middleware.set_current_project), and — permissively — all rows when the
GUC is unset, so existing/admin queries keep working during the transition.

Enforcement posture is intentionally *deferred*: we ENABLE (not FORCE) RLS, so
the table owner (used by migrations) bypasses it while the non-owner writer/
reader roles are already subject to it. Phase 6 reshapes ingestion to always
carry a project and can then switch to FORCE ROW LEVEL SECURITY.

No-op on SQLite (tests/dev), where isolation relies on app-level scoping.
"""

from django.db import migrations

POLICY_NAME = "tenant_isolation"


def apply_rls(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    table = apps.get_model("observability", "ApiRequest")._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        cursor.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table};")
        cursor.execute(f"""
            CREATE POLICY {POLICY_NAME} ON {table}
            USING (
                current_setting('app.current_project', true) IS NULL
                OR current_setting('app.current_project', true) = ''
                OR project_id = NULLIF(current_setting('app.current_project', true), '')::bigint
            );
            """)


def drop_rls(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    table = apps.get_model("observability", "ApiRequest")._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table};")
        cursor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0011_backfill_default_project"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]
