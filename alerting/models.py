# alerting/models.py
from __future__ import annotations

from django.db import models


class AlertRule(models.Model):
    """A tenant-owned alert rule, evaluated on a schedule.

    Two kinds:
      - threshold: compare a computed metric against a fixed value.
      - anomaly:   flag when the metric deviates from its robust baseline
                   (reuses the Phase 8 detector).
    """

    class Kind(models.TextChoices):
        THRESHOLD = "threshold", "threshold"
        ANOMALY = "anomaly", "anomaly"

    class Metric(models.TextChoices):
        ERROR_RATE = "error_rate", "error rate"
        LATENCY_AVG = "latency_avg", "avg latency (ms)"
        LATENCY_P95 = "latency_p95", "p95 latency (ms)"
        REQUEST_COUNT = "request_count", "request count"

    class Comparator(models.TextChoices):
        GT = "gt", ">"
        GTE = "gte", ">="
        LT = "lt", "<"
        LTE = "lte", "<="

    class Severity(models.TextChoices):
        CRITICAL = "critical", "critical"
        WARNING = "warning", "warning"
        INFO = "info", "info"

    class State(models.TextChoices):
        OK = "ok", "ok"
        FIRING = "firing", "firing"

    project = models.ForeignKey(
        "tenancy.Project", on_delete=models.CASCADE, related_name="alert_rules", db_constraint=False
    )
    name = models.CharField(max_length=200)
    enabled = models.BooleanField(default=True, db_index=True)

    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.THRESHOLD)
    metric = models.CharField(max_length=20, choices=Metric.choices, default=Metric.ERROR_RATE)

    # Optional narrowing.
    service = models.CharField(max_length=100, blank=True, default="")
    endpoint = models.CharField(max_length=255, blank=True, default="")

    # Threshold parameters.
    comparator = models.CharField(max_length=4, choices=Comparator.choices, default=Comparator.GT)
    threshold = models.FloatField(default=0.0)

    # Anomaly parameters.
    z_threshold = models.FloatField(default=3.0)

    window_minutes = models.PositiveIntegerField(default=5)
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.WARNING
    )
    runbook_url = models.URLField(max_length=1024, blank=True, default="")

    # Evaluation bookkeeping (for state-transition detection + observability).
    state = models.CharField(max_length=8, choices=State.choices, default=State.OK, db_index=True)
    last_value = models.FloatField(null=True, blank=True)
    last_evaluated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project", "name"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="uniq_project_alertrule")
        ]

    def __str__(self) -> str:
        return f"{self.project}:{self.name} [{self.state}]"

    @property
    def alertname(self) -> str:
        # Used as the notification/incident dedup identity.
        return f"rule:{self.project_id}:{self.name}"


class AlertRuleEvaluation(models.Model):
    """Append-only evaluation history for a rule (observability + debugging)."""

    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name="evaluations")
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    value = models.FloatField(null=True, blank=True)
    firing = models.BooleanField(default=False)
    detail = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-at"]

    def __str__(self) -> str:
        return f"{self.rule.name} @ {self.at:%H:%M:%S} firing={self.firing}"
