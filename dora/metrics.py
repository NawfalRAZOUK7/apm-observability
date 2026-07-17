# dora/metrics.py
"""Compute the four DORA metrics + Elite/High/Medium/Low performance bands."""
from __future__ import annotations

from datetime import datetime

from .models import Deployment


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def _band(value, thresholds, *, lower_is_better) -> str:
    """thresholds = (elite, high, medium) cutoffs. Returns the band name."""
    if value is None:
        return "unknown"
    elite, high, medium = thresholds
    if lower_is_better:
        if value < elite:
            return "Elite"
        if value < high:
            return "High"
        if value < medium:
            return "Medium"
        return "Low"
    else:
        if value >= elite:
            return "Elite"
        if value >= high:
            return "High"
        if value >= medium:
            return "Medium"
        return "Low"


def _mttr_seconds(since, until, environment=None, project=None) -> float | None:
    # Reuse the incident model (Phase 9): recovery time of incidents in-window.
    from notifications.models import Incident

    qs = Incident.objects.filter(
        status=Incident.Status.RESOLVED, opened_at__gte=since, opened_at__lt=until
    )
    if project is not None:
        qs = qs.filter(project=project)
    values = [i.mttr_seconds for i in qs if i.mttr_seconds is not None]
    return sum(values) / len(values) if values else None


def compute_dora(since: datetime, until: datetime, *, environment=None, project=None) -> dict:
    qs = Deployment.objects.filter(deployed_at__gte=since, deployed_at__lt=until)
    if environment:
        qs = qs.filter(environment=environment)
    if project is not None:
        qs = qs.filter(project=project)
    deploys = list(qs)

    total = len(deploys)
    successful = [d for d in deploys if d.status == Deployment.Status.SUCCESS]
    failures = [d for d in deploys if d.is_failure]

    days = max((until - since).total_seconds() / 86400.0, 1e-9)
    freq_per_day = len(successful) / days

    lead_times = [d.lead_time_seconds for d in successful if d.lead_time_seconds is not None]
    median_lead = _median(lead_times)

    cfr = (len(failures) / total) if total else None
    mttr = _mttr_seconds(since, until, environment, project)

    return {
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "deployment_frequency": {
            "per_day": round(freq_per_day, 3),
            "total_successful": len(successful),
            "band": _band(freq_per_day, (1.0, 1 / 7, 1 / 30), lower_is_better=False),
        },
        "lead_time_for_changes": {
            "median_seconds": round(median_lead, 1) if median_lead is not None else None,
            "band": _band(median_lead, (86400, 604800, 2592000), lower_is_better=True),
        },
        "change_failure_rate": {
            "rate": round(cfr, 4) if cfr is not None else None,
            "failures": len(failures),
            "total": total,
            "band": _band(cfr, (0.15, 0.30, 0.45), lower_is_better=True),
        },
        "time_to_recovery": {
            "mttr_seconds_avg": round(mttr, 1) if mttr is not None else None,
            "band": _band(mttr, (3600, 86400, 604800), lower_is_better=True),
        },
    }
