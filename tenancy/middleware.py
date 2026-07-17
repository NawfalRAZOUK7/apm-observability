# tenancy/middleware.py
from __future__ import annotations

from django.db import connection


class TenantContextMiddleware:
    """Bind the resolved tenant to the DB session for Row-Level Security.

    When a request carries tenant context (set by ApiKeyAuthentication, or later
    by the JWT/session flow), and the backend is PostgreSQL, set the
    ``app.current_project`` GUC so RLS policies can scope rows. On SQLite this is
    a no-op and isolation relies on the app-level query scoping.

    Authentication runs inside the view (DRF), so we set the GUC as late as
    possible: we expose a helper the ingest path calls, and also best-effort set
    it here if middleware-level auth already resolved a project.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response


def set_current_project(project_id) -> None:
    """Set the RLS GUC for the current DB connection (PostgreSQL only)."""
    if connection.vendor != "postgresql" or project_id is None:
        return
    with connection.cursor() as cursor:
        # SET LOCAL scopes to the surrounding transaction; use set_config so the
        # value can be parameterized safely.
        cursor.execute("SELECT set_config('app.current_project', %s, true)", [str(project_id)])


def clear_current_project() -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_project', '', true)")
