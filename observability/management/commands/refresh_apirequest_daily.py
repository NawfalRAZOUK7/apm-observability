from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def _parse_dt_or_date(value: str, *, end_of_day: bool) -> datetime:
    """
    Accepts ISO datetime or ISO date.
    Returns aware datetime in UTC.
    """
    value = (value or "").strip()
    if not value:
        raise CommandError("Empty datetime/date value.")

    dt = parse_datetime(value)
    if dt is not None:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=UTC)
        return dt.astimezone(UTC)

    d = parse_date(value)
    if d is not None:
        if end_of_day:
            dt2 = datetime.combine(d, time(23, 59, 59, 999999))
        else:
            dt2 = datetime.combine(d, time(0, 0, 0))
        dt2 = timezone.make_aware(dt2, timezone=UTC)
        return dt2.astimezone(UTC)

    raise CommandError(
        "Invalid format. Use ISO datetime (2025-12-14T10:00:00Z) or date (2025-12-14)."
    )


class Command(BaseCommand):
    help = (
        "Manually refresh Timescale continuous aggregate: apirequest_daily. "
        "Example: python manage.py refresh_apirequest_daily --start 2025-12-01 --end 2025-12-14"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            required=False,
            help="ISO datetime or date. Default: end - 7 days.",
        )
        parser.add_argument(
            "--end",
            required=False,
            help="ISO datetime or date. Default: now.",
        )

    def handle(self, *args, **options):
        # Defaults: last 7 days
        now = timezone.now().astimezone(UTC)
        end_raw = options.get("end")
        start_raw = options.get("start")

        end = _parse_dt_or_date(end_raw, end_of_day=True) if end_raw else now
        start = (
            _parse_dt_or_date(start_raw, end_of_day=False)
            if start_raw
            else (end - timedelta(days=7))
        )

        if start > end:
            raise CommandError("`--start` must be <= `--end`.")

        if connection.vendor != "postgresql":
            raise CommandError("This command requires PostgreSQL (TimescaleDB).")

        sql = "CALL refresh_continuous_aggregate('apirequest_daily', %s, %s);"

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, [start, end])
        except Exception as exc:
            raise CommandError(f"Failed to refresh apirequest_daily: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Refreshed apirequest_daily from {start.isoformat()} to {end.isoformat()}"
            )
        )
