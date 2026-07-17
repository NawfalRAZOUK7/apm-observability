# tenancy/models.py
from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    ADMIN = "admin", "admin"
    OPERATOR = "operator", "operator"
    DEVELOPER = "developer", "developer"
    VIEWER = "viewer", "viewer"


# Higher rank => more privilege. Used by permission checks (see permissions.py).
ROLE_RANK: dict[str, int] = {
    Role.VIEWER: 1,
    Role.DEVELOPER: 2,
    Role.OPERATOR: 3,
    Role.ADMIN: 4,
}


class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    """A user's role within an organization."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"], name="uniq_user_org_membership"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"


class Project(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    # Per-project monthly ingest quota; 0 = unlimited.
    monthly_event_quota = models.PositiveBigIntegerField(default=1_000_000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization", "name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "slug"], name="uniq_org_project_slug")
        ]

    def __str__(self) -> str:
        return f"{self.organization.slug}/{self.slug}"


class Environment(models.Model):
    class Kind(models.TextChoices):
        PRODUCTION = "production", "production"
        STAGING = "staging", "staging"
        DEVELOPMENT = "development", "development"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="environments")
    kind = models.CharField(max_length=16, choices=Kind.choices)

    class Meta:
        ordering = ["project", "kind"]
        constraints = [
            models.UniqueConstraint(fields=["project", "kind"], name="uniq_project_environment")
        ]

    def __str__(self) -> str:
        return f"{self.project}:{self.kind}"


def _hash_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


class ApiKey(models.Model):
    """Ingestion API key scoped to a project + environment.

    Stored hashed (SHA-256) with a short lookup prefix. The plaintext is shown
    exactly once, at creation. Supports expiry, revocation, and rotation.
    """

    PREFIX_LEN = 12

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="api_keys")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=200, blank=True, default="")

    prefix = models.CharField(max_length=32, db_index=True)
    hashed_key = models.CharField(max_length=64, unique=True)
    can_write = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_keys",
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        state = "revoked" if self.revoked_at else ("expired" if self.is_expired else "active")
        return f"{self.prefix}… ({self.project}:{self.environment.kind}) [{state}]"

    # --- lifecycle -------------------------------------------------------
    @classmethod
    def generate(cls, *, project, environment, name="", created_by=None):
        """Create a key and return (instance, plaintext). Plaintext is not stored."""
        token = secrets.token_urlsafe(32)
        full_key = f"apm_{environment.kind[:3]}_{token}"
        instance = cls.objects.create(
            project=project,
            environment=environment,
            name=name,
            prefix=full_key[: cls.PREFIX_LEN],
            hashed_key=_hash_key(full_key),
            created_by=created_by,
        )
        return instance, full_key

    def rotate(self):
        """Revoke this key and issue a replacement for the same scope."""
        self.revoke()
        return type(self).generate(
            project=self.project,
            environment=self.environment,
            name=self.name,
            created_by=self.created_by,
        )

    def revoke(self):
        if not self.revoked_at:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    # --- state -----------------------------------------------------------
    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and not self.is_expired

    @classmethod
    def verify(cls, full_key: str):
        """Return the active ApiKey for a presented plaintext, or None."""
        if not full_key:
            return None
        prefix = full_key[: cls.PREFIX_LEN]
        candidate = (
            cls.objects.filter(prefix=prefix, hashed_key=_hash_key(full_key))
            .select_related("project", "environment", "project__organization")
            .first()
        )
        if candidate is None or not candidate.is_active:
            return None
        return candidate

    def touch(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])


class UsageRecord(models.Model):
    """Per-project, per-month ingest counter backing quota enforcement."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="usage")
    period = models.DateField(help_text="First day of the month this counts.")
    event_count = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "period"], name="uniq_project_period_usage")
        ]

    def __str__(self) -> str:
        return f"{self.project} {self.period:%Y-%m}: {self.event_count}"
