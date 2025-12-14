from __future__ import annotations

from datetime import timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class Command(BaseCommand):
    help = "Manually refresh the Timescale continuous aggregate: apirequest_hourly"

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            type=str,
            default=None,
            help="ISO datetime (UTC recommended). Default: now-7d",
        )
        parser.add_argument(
            "--end",
            type=str,
            default=None,
            help="ISO datetime (UTC recommended). Default: now-1h",
        )

    def _parse_dt(self, raw: str | None, name: str):
        if not raw:
            return None
        dt = parse_datetime(raw)
        if dt is None:
            raise CommandError(f"{name} must be an ISO datetime (e.g. 2025-12-14T10:00:00Z).")
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=dt_timezone.utc)
        return dt.astimezone(dt_timezone.utc)

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("This command requires PostgreSQL + TimescaleDB (not SQLite).")

        start = self._parse_dt(options.get("start"), "start")
        end = self._parse_dt(options.get("end"), "end")

        now = timezone.now().astimezone(dt_timezone.utc)

        # Safe defaults matching policy window:
        # start_offset = 7 days, end_offset = 1 hour
        if end is None:
            end = now - timedelta(hours=1)
        if start is None:
            start = now - timedelta(days=7)

        if start > end:
            raise CommandError("start must be <= end")

        # Timescale refresh function
        sql = "CALL refresh_continuous_aggregate('apirequest_hourly'::regclass, %s, %s);"

        self.stdout.write(
            f"Refreshing apirequest_hourly from {start.isoformat()} to {end.isoformat()} ..."
        )

        with connection.cursor() as cursor:
            cursor.execute(sql, [start, end])

        self.stdout.write(self.style.SUCCESS("Refresh completed."))
