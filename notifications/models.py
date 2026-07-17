# notifications/models.py
from django.conf import settings
from django.db import models


class Notification(models.Model):
    """A single alert notification received from Alertmanager.

    One row per received alert event (firing or resolved), which gives a natural
    delivery timeline and doubles as the incident intake in Phase 9.
    """

    class Status(models.TextChoices):
        FIRING = "firing", "firing"
        RESOLVED = "resolved", "resolved"

    class Severity(models.TextChoices):
        CRITICAL = "critical", "critical"
        WARNING = "warning", "warning"
        INFO = "info", "info"
        UNKNOWN = "unknown", "unknown"

    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Alertmanager per-alert fingerprint (stable across firing/resolved).
    fingerprint = models.CharField(max_length=128, db_index=True, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.FIRING, db_index=True
    )
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.UNKNOWN, db_index=True
    )
    alertname = models.CharField(max_length=255, db_index=True, blank=True, default="")

    summary = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    runbook_url = models.URLField(max_length=1024, blank=True, default="")

    labels = models.JSONField(default=dict, blank=True)
    annotations = models.JSONField(default=dict, blank=True)

    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    # Channels this notification was routed to (e.g. ["chat", "pager"]).
    channels = models.JSONField(default=list, blank=True)
    delivered = models.BooleanField(default=False, db_index=True)
    delivery_error = models.TextField(blank=True, default="")

    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["severity", "-received_at"], name="notif_sev_time_idx"),
            models.Index(fields=["status", "-received_at"], name="notif_status_time_idx"),
            models.Index(fields=["alertname", "-received_at"], name="notif_alert_time_idx"),
        ]

    def __str__(self) -> str:
        return f"[{self.received_at:%Y-%m-%d %H:%M:%S}] {self.severity} {self.alertname} ({self.status})"


class Incident(models.Model):
    """An actionable incident opened from firing alerts (Phase 9).

    Deduplicated by ``dedup_key`` while open, so repeated firings update one
    incident instead of spawning many. Tracks acknowledgement, ownership, and
    the MTTA/MTTR clocks.
    """

    class Status(models.TextChoices):
        OPEN = "open", "open"
        ACKNOWLEDGED = "acknowledged", "acknowledged"
        RESOLVED = "resolved", "resolved"

    dedup_key = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255)
    severity = models.CharField(
        max_length=16, choices=Notification.Severity.choices, default=Notification.Severity.UNKNOWN
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True
    )

    description = models.TextField(blank=True, default="")
    runbook_url = models.URLField(max_length=1024, blank=True, default="")
    grafana_url = models.URLField(max_length=1024, blank=True, default="")
    trace_id = models.CharField(max_length=128, blank=True, default="")

    project = models.ForeignKey(
        "tenancy.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incidents",
        db_constraint=False,
    )

    opened_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="acknowledged_incidents",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_incidents",
    )

    class Meta:
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["status", "-opened_at"], name="incident_status_time_idx"),
            models.Index(fields=["dedup_key", "status"], name="incident_dedup_status_idx"),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.title} [{self.status}]"

    @property
    def mtta_seconds(self) -> float | None:
        if self.acknowledged_at is None:
            return None
        return (self.acknowledged_at - self.opened_at).total_seconds()

    @property
    def mttr_seconds(self) -> float | None:
        if self.resolved_at is None:
            return None
        return (self.resolved_at - self.opened_at).total_seconds()

    @property
    def is_open(self) -> bool:
        return self.status != self.Status.RESOLVED


class IncidentEvent(models.Model):
    """A single entry in an incident's timeline."""

    class Kind(models.TextChoices):
        OPENED = "opened", "opened"
        NOTIFICATION = "notification", "notification"
        ACKNOWLEDGED = "acknowledged", "acknowledged"
        ASSIGNED = "assigned", "assigned"
        COMMENT = "comment", "comment"
        RESOLVED = "resolved", "resolved"

    incident = models.ForeignKey(
        Incident, on_delete=models.CASCADE, related_name="events"
    )
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    message = models.TextField(blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incident_events",
    )

    class Meta:
        ordering = ["at"]

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M:%S} {self.kind}"
