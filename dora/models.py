# dora/models.py
from __future__ import annotations

from django.db import models


class Deployment(models.Model):
    """A recorded deployment, fed by the CD pipeline (Phase 18).

    Change-failure = status in (failed, rolled_back) OR caused_incident.
    Lead time = deployed_at - committed_at (when the commit time is provided).
    """

    class Environment(models.TextChoices):
        PRODUCTION = "production", "production"
        STAGING = "staging", "staging"
        DEVELOPMENT = "development", "development"

    class Status(models.TextChoices):
        SUCCESS = "success", "success"
        FAILED = "failed", "failed"
        ROLLED_BACK = "rolled_back", "rolled_back"

    environment = models.CharField(
        max_length=16, choices=Environment.choices, default=Environment.PRODUCTION, db_index=True
    )
    version = models.CharField(max_length=100, help_text="Image tag / release version.")
    commit_sha = models.CharField(max_length=64, blank=True, default="")
    service = models.CharField(max_length=200, blank=True, default="")

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUCCESS, db_index=True
    )
    caused_incident = models.BooleanField(default=False)

    committed_at = models.DateTimeField(
        null=True, blank=True, help_text="Commit time (for lead time)."
    )
    deployed_at = models.DateTimeField(db_index=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    project = models.ForeignKey(
        "tenancy.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deployments",
        db_constraint=False,
    )
    triggered_by = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-deployed_at"]
        indexes = [
            models.Index(fields=["environment", "-deployed_at"], name="deploy_env_time_idx"),
            models.Index(fields=["status", "-deployed_at"], name="deploy_status_time_idx"),
        ]

    def __str__(self) -> str:
        return (
            f"{self.environment} {self.version} [{self.status}] @ {self.deployed_at:%Y-%m-%d %H:%M}"
        )

    @property
    def is_failure(self) -> bool:
        return self.status != self.Status.SUCCESS or self.caused_incident

    @property
    def lead_time_seconds(self) -> float | None:
        if self.committed_at is None:
            return None
        return (self.deployed_at - self.committed_at).total_seconds()
