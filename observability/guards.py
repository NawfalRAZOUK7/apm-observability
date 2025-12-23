# observability/guards.py
from functools import wraps

from django.db import connection
from rest_framework import status
from rest_framework.response import Response


def postgres_required(reason: str = "This endpoint requires PostgreSQL + TimescaleDB."):
    """
    Use on analytics endpoints (hourly/daily) so local SQLite runs don't crash.
    Returns HTTP 501 when not running on PostgreSQL.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            if connection.vendor != "postgresql":
                return Response(
                    {
                        "detail": reason,
                        "db_vendor": connection.vendor,
                        "hint": (
                            "Set POSTGRES_* env vars (POSTGRES_DB/USER/PASSWORD/HOST/PORT) "
                            "and run Timescale via docker-compose."
                        ),
                    },
                    status=status.HTTP_501_NOT_IMPLEMENTED,
                )
            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator
