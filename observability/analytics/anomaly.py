# observability/analytics/anomaly.py
"""Statistical anomaly detection over API request time series (Phase 8).

Robust baselines (median + MAD) per service+endpoint on time buckets, for both
latency and error rate. Robust statistics resist the very spikes we want to
detect, unlike mean/stddev. Start here before any ML (see docs/ROADMAP.md).

Pure-ORM/Python so it runs on SQLite (tests/dev) and PostgreSQL alike; the
TimescaleDB `time_bucket` + continuous-aggregate version is the scale optimization.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from observability.models import ApiRequest

_ERROR_STATUS = 500
_MAD_SCALE = 0.6745  # makes MAD a consistent estimator of stddev for normals


def _floor(dt: datetime, bucket: str) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    if bucket == "minute":
        return dt
    if bucket == "day":
        return dt.replace(hour=0, minute=0)
    return dt.replace(minute=0)  # hour (default)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def _robust_z(current: float, history: list[float]) -> tuple[float, float, float]:
    """Return (z_score, baseline_median, spread). Falls back to std if MAD==0."""
    if len(history) < 2:
        return 0.0, (history[0] if history else current), 0.0
    med = _median(history)
    mad = _median([abs(x - med) for x in history])
    if mad > 0:
        return _MAD_SCALE * (current - med) / mad, med, mad
    # Degenerate MAD (many identical values): fall back to standard deviation.
    mean = sum(history) / len(history)
    var = sum((x - mean) ** 2 for x in history) / len(history)
    std = var**0.5
    if std == 0:
        return 0.0, med, 0.0
    return (current - mean) / std, med, std


@dataclass
class Anomaly:
    service: str
    endpoint: str
    metric: str  # "latency_ms" | "error_rate"
    current: float
    baseline: float
    z_score: float
    is_anomaly: bool
    buckets: int

    def as_dict(self) -> dict:
        return asdict(self)


def _bucketed(rows, bucket: str):
    """{(service, endpoint): {bucket_start: [rows...]}}"""
    grouped: dict[tuple[str, str], dict[datetime, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        grouped[(r.service, r.endpoint)][_floor(r.time, bucket)].append(r)
    return grouped


def detect_anomalies(
    since: datetime,
    until: datetime,
    *,
    project=None,
    service: str | None = None,
    endpoint: str | None = None,
    bucket: str = "hour",
    z_threshold: float = 3.0,
) -> list[dict]:
    """Flag the latest bucket per service+endpoint whose latency or error rate
    deviates from its own robust baseline by >= ``z_threshold``."""
    qs = ApiRequest.objects.filter(time__gte=since, time__lt=until)
    if project is not None:
        qs = qs.filter(project=project)
    if service:
        qs = qs.filter(service=service)
    if endpoint:
        qs = qs.filter(endpoint=endpoint)

    grouped = _bucketed(list(qs.only("service", "endpoint", "time", "status_code", "latency_ms")), bucket)

    results: list[dict] = []
    for (svc, ep), buckets in grouped.items():
        if len(buckets) < 3:
            continue  # need history + a current bucket to say anything
        ordered_keys = sorted(buckets)
        history_keys, current_key = ordered_keys[:-1], ordered_keys[-1]

        for metric in ("latency_ms", "error_rate"):
            def bucket_value(rows) -> float:
                if metric == "latency_ms":
                    return sum(r.latency_ms for r in rows) / len(rows)
                errors = sum(1 for r in rows if r.status_code >= _ERROR_STATUS)
                return errors / len(rows)

            history = [bucket_value(buckets[k]) for k in history_keys]
            current = bucket_value(buckets[current_key])
            z, baseline, _spread = _robust_z(current, history)
            results.append(
                Anomaly(
                    service=svc,
                    endpoint=ep,
                    metric=metric,
                    current=round(current, 4),
                    baseline=round(baseline, 4),
                    z_score=round(z, 3),
                    is_anomaly=abs(z) >= z_threshold,
                    buckets=len(ordered_keys),
                ).as_dict()
            )

    results.sort(key=lambda a: abs(a["z_score"]), reverse=True)
    return results
