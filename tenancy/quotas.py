# tenancy/quotas.py
from __future__ import annotations

from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import Throttled

from .models import Project, UsageRecord


def _current_period() -> "timezone.datetime.date":
    today = timezone.now().date()
    return today.replace(day=1)


class QuotaExceeded(Throttled):
    """Raised (HTTP 429) when a project exceeds its monthly ingest quota."""

    default_detail = "Monthly ingest quota exceeded for this project."


def check_and_reserve(project: Project, count: int) -> None:
    """Atomically reserve ``count`` events against the project's monthly quota.

    No-op when the project has an unlimited quota (0). Raises QuotaExceeded if
    the reservation would exceed the limit.
    """
    if count <= 0:
        return
    quota = project.monthly_event_quota
    period = _current_period()

    record, _ = UsageRecord.objects.get_or_create(project=project, period=period)

    if quota and record.event_count + count > quota:
        remaining = max(quota - record.event_count, 0)
        raise QuotaExceeded(
            detail=(
                f"Monthly ingest quota exceeded: {record.event_count}/{quota} used, "
                f"{remaining} remaining, {count} requested."
            )
        )

    # Atomic increment to avoid races under concurrent ingest.
    UsageRecord.objects.filter(pk=record.pk).update(event_count=F("event_count") + count)


def current_usage(project: Project) -> int:
    record = UsageRecord.objects.filter(project=project, period=_current_period()).first()
    return record.event_count if record else 0
