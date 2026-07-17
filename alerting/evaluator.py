# alerting/evaluator.py
"""Evaluate alert rules and route firings through the notification pipeline.

On an OK->firing transition we emit a firing Notification (which dispatches to
channels and opens an incident); on firing->OK we emit a resolved Notification
(which auto-resolves the incident). Only transitions notify, so a rule that
stays firing does not re-page every tick.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from observability.analytics.anomaly import detect_anomalies
from observability.models import ApiRequest

from .models import AlertRule, AlertRuleEvaluation

_ERROR_STATUS = 500

# Rule metric -> the metric name the anomaly detector emits.
_ANOMALY_METRIC = {
    AlertRule.Metric.ERROR_RATE: "error_rate",
    AlertRule.Metric.LATENCY_AVG: "latency_ms",
    AlertRule.Metric.LATENCY_P95: "latency_ms",
}


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(int(round((pct / 100.0) * (len(ordered) - 1))), 0)
    return float(ordered[k])


def _scoped_rows(rule: AlertRule, since, until):
    qs = ApiRequest.objects.filter(project=rule.project, time__gte=since, time__lt=until)
    if rule.service:
        qs = qs.filter(service=rule.service)
    if rule.endpoint:
        qs = qs.filter(endpoint=rule.endpoint)
    return qs


def _threshold_value(rule: AlertRule, since, until) -> float:
    rows = list(_scoped_rows(rule, since, until).only("status_code", "latency_ms"))
    count = len(rows)
    if rule.metric == AlertRule.Metric.REQUEST_COUNT:
        return float(count)
    if count == 0:
        return 0.0
    if rule.metric == AlertRule.Metric.ERROR_RATE:
        errors = sum(1 for r in rows if r.status_code >= _ERROR_STATUS)
        return errors / count
    latencies = [r.latency_ms for r in rows]
    if rule.metric == AlertRule.Metric.LATENCY_AVG:
        return sum(latencies) / count
    if rule.metric == AlertRule.Metric.LATENCY_P95:
        return _percentile(latencies, 95)
    return 0.0


def _compare(value: float, comparator: str, threshold: float) -> bool:
    return {
        AlertRule.Comparator.GT: value > threshold,
        AlertRule.Comparator.GTE: value >= threshold,
        AlertRule.Comparator.LT: value < threshold,
        AlertRule.Comparator.LTE: value <= threshold,
    }.get(comparator, False)


def _anomaly_result(rule: AlertRule, until) -> tuple[bool, float, str]:
    """Return (firing, z_value, detail) from the robust detector."""
    metric = _ANOMALY_METRIC.get(rule.metric)
    if metric is None:
        return False, 0.0, "metric not supported for anomaly rules"
    # Anomaly detection needs history; use a day of hourly buckets regardless of
    # window_minutes (which governs threshold rules).
    since = until - timedelta(hours=24)
    anomalies = detect_anomalies(
        since,
        until,
        project=rule.project,
        service=rule.service or None,
        endpoint=rule.endpoint or None,
        bucket="hour",
        z_threshold=rule.z_threshold,
    )
    relevant = [a for a in anomalies if a["metric"] == metric]
    if not relevant:
        return False, 0.0, "insufficient history or no signal"
    worst = max(relevant, key=lambda a: abs(a["z_score"]))
    return bool(worst["is_anomaly"]), float(worst["z_score"]), f"z={worst['z_score']}"


def _emit(rule: AlertRule, *, firing: bool, value: float):
    """Build a Notification and run the standard sink pipeline."""
    # Imported lazily to avoid a hard app-load ordering dependency.
    from notifications.incidents import open_or_update_from_notification
    from notifications.models import Notification
    from notifications.providers import dispatch

    status = Notification.Status.FIRING if firing else Notification.Status.RESOLVED
    summary = f"{rule.name}: {rule.get_metric_display()} = {round(value, 4)}"
    notification = Notification(
        fingerprint=rule.alertname,
        status=status,
        severity=rule.severity,
        alertname=rule.alertname,
        summary=summary,
        description=f"Alert rule '{rule.name}' ({rule.kind}) on project {rule.project}.",
        runbook_url=rule.runbook_url,
        labels={
            "alertname": rule.alertname,
            "severity": rule.severity,
            "service": rule.service,
            "endpoint": rule.endpoint,
            "rule_id": str(rule.id),
        },
        starts_at=timezone.now(),
    )
    if firing:
        dispatch(notification)
    else:
        notification.delivered = True
    notification.save()
    open_or_update_from_notification(notification)


def evaluate_rule(rule: AlertRule, *, now=None) -> dict:
    """Evaluate one rule, record history, and notify on state transitions."""
    now = now or timezone.now()
    since = now - timedelta(minutes=rule.window_minutes)

    if rule.kind == AlertRule.Kind.ANOMALY:
        firing, value, detail = _anomaly_result(rule, now)
    else:
        value = _threshold_value(rule, since, now)
        firing = _compare(value, rule.comparator, rule.threshold)
        detail = f"{value} {rule.comparator} {rule.threshold}"

    AlertRuleEvaluation.objects.create(rule=rule, value=value, firing=firing, detail=detail)

    previous = rule.state
    new_state = AlertRule.State.FIRING if firing else AlertRule.State.OK
    transitioned = new_state != previous

    if transitioned:
        # The sink applies the severity policy: info is recorded dashboard-only
        # and never opens an incident (see providers.SEVERITY_POLICY).
        _emit(rule, firing=firing, value=value)

    rule.state = new_state
    rule.last_value = value
    rule.last_evaluated_at = now
    rule.save(update_fields=["state", "last_value", "last_evaluated_at"])

    return {
        "rule": rule.name,
        "project": rule.project.slug,
        "value": value,
        "firing": firing,
        "transitioned": transitioned,
        "state": new_state,
    }


def evaluate_all(*, now=None) -> list[dict]:
    now = now or timezone.now()
    results = []
    for rule in AlertRule.objects.filter(enabled=True).select_related("project"):
        results.append(evaluate_rule(rule, now=now))
    return results
