# observability/models.py
from django.db import models
from django.db.models import Q


class ApiRequest(models.Model):
    class HttpMethod(models.TextChoices):
        GET = "GET", "GET"
        POST = "POST", "POST"
        PUT = "PUT", "PUT"
        PATCH = "PATCH", "PATCH"
        DELETE = "DELETE", "DELETE"
        HEAD = "HEAD", "HEAD"
        OPTIONS = "OPTIONS", "OPTIONS"

    time = models.DateTimeField(db_index=True)
    service = models.CharField(max_length=100, db_index=True)
    endpoint = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=10, choices=HttpMethod.choices, db_index=True)

    status_code = models.PositiveSmallIntegerField(db_index=True)
    latency_ms = models.PositiveIntegerField(db_index=True)

    trace_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    user_ref = models.CharField(max_length=128, null=True, blank=True, db_index=True)

    tags = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-time"]
        indexes = [
            models.Index(fields=["service", "endpoint", "-time"], name="api_req_svc_ep_time_idx"),
            models.Index(
                fields=["service", "endpoint", "method", "-time"],
                name="api_req_svc_ep_method_time_idx",
            ),
            models.Index(fields=["service", "-time"], name="api_req_svc_time_idx"),
            models.Index(fields=["endpoint", "-time"], name="api_req_ep_time_idx"),
            models.Index(fields=["status_code", "-time"], name="api_req_status_time_idx"),
            models.Index(
                fields=["service", "endpoint", "-time"],
                name="api_req_err_svc_ep_time_idx",
                condition=Q(status_code__gte=500),
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(latency_ms__gte=0),
                name="api_req_latency_ms_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(status_code__gte=100) & Q(status_code__lte=599),
                name="api_req_status_code_valid_http",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.time}] {self.service} {self.method} {self.endpoint} {self.status_code} ({self.latency_ms}ms)"
