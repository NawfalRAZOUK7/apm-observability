# observability/models.py
from django.db import models
from django.db.models import Q
from pgvector.django import VectorField


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

    # Tenant scope (Phase 5). Nullable + backfilled to a default project; RLS
    # enforcement on this legacy table is deferred to Phase 6 (which reshapes
    # ingestion to always carry a project). db_constraint=False keeps the
    # TimescaleDB hypertable happy, mirroring ApiRequestEmbedding.
    project = models.ForeignKey(
        "tenancy.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="api_requests",
        db_index=True,
        db_constraint=False,
    )

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
        return (
            f"[{self.time}] {self.service} {self.method} {self.endpoint} "
            f"{self.status_code} ({self.latency_ms}ms)"
        )


class ApiRequestEmbedding(models.Model):
    class Source(models.TextChoices):
        ERROR = "error", "error"
        REQUEST = "request", "request"

    request = models.OneToOneField(
        ApiRequest,
        on_delete=models.CASCADE,
        related_name="embedding",
        db_constraint=False,
    )
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.ERROR)
    model = models.CharField(max_length=64, default="text-embedding-004")
    content_hash = models.CharField(max_length=64, db_index=True)
    embedding = VectorField(dimensions=768)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["source", "created_at"], name="api_req_emb_source_time_idx"),
        ]


class Service(models.Model):
    """A service auto-registered from OTLP resource attributes (Phase 6)."""

    project = models.ForeignKey(
        "tenancy.Project",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="services",
        db_constraint=False,
    )
    name = models.CharField(max_length=200, db_index=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="uniq_project_service")
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Span(models.Model):
    """A single OTLP span, stored tenant-aware as a TimescaleDB hypertable.

    ``time`` mirrors the span start and is the hypertable partition column.
    Service-topology (Phase 7) is derived from ``parent_span_id`` edges; HTTP
    attributes are denormalized for fast per-edge rate/error/latency queries.
    """

    class Kind(models.TextChoices):
        UNSPECIFIED = "unspecified", "unspecified"
        INTERNAL = "internal", "internal"
        SERVER = "server", "server"
        CLIENT = "client", "client"
        PRODUCER = "producer", "producer"
        CONSUMER = "consumer", "consumer"

    class StatusCode(models.TextChoices):
        UNSET = "unset", "unset"
        OK = "ok", "ok"
        ERROR = "error", "error"

    time = models.DateTimeField(db_index=True, help_text="Span start (partition column).")
    end_time = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0, db_index=True)

    project = models.ForeignKey(
        "tenancy.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="spans",
        db_index=True,
        db_constraint=False,
    )

    trace_id = models.CharField(max_length=64, db_index=True)
    span_id = models.CharField(max_length=32, db_index=True)
    parent_span_id = models.CharField(max_length=32, blank=True, default="", db_index=True)

    service = models.CharField(max_length=200, db_index=True)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.INTERNAL)
    status_code = models.CharField(
        max_length=8, choices=StatusCode.choices, default=StatusCode.UNSET, db_index=True
    )

    # Denormalized HTTP semantic-convention fields (nullable for non-HTTP spans).
    http_method = models.CharField(max_length=10, blank=True, default="")
    http_route = models.CharField(max_length=255, blank=True, default="")
    http_status_code = models.PositiveSmallIntegerField(null=True, blank=True)

    attributes = models.JSONField(default=dict, blank=True)
    resource = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-time"]
        indexes = [
            models.Index(fields=["trace_id", "time"], name="span_trace_time_idx"),
            models.Index(fields=["parent_span_id"], name="span_parent_idx"),
            models.Index(fields=["service", "-time"], name="span_service_time_idx"),
            models.Index(fields=["project", "-time"], name="span_project_time_idx"),
            models.Index(
                fields=["service", "-time"],
                name="span_err_service_time_idx",
                condition=Q(status_code="error"),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service} {self.name} ({self.kind}) {self.duration_ms}ms"


class MetricPoint(models.Model):
    """A single OTLP metric data point (Phase 11), tenant-aware hypertable.

    Gauges and sums store ``value``; histograms store ``count`` + ``sum_value``
    plus optional bucket detail in ``attributes``. ``time`` is the partition col.
    """

    class Kind(models.TextChoices):
        GAUGE = "gauge", "gauge"
        SUM = "sum", "sum"
        HISTOGRAM = "histogram", "histogram"

    time = models.DateTimeField(db_index=True)
    project = models.ForeignKey(
        "tenancy.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="metric_points",
        db_index=True,
        db_constraint=False,
    )
    service = models.CharField(max_length=200, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.GAUGE)
    unit = models.CharField(max_length=63, blank=True, default="")

    value = models.FloatField(null=True, blank=True)
    count = models.PositiveBigIntegerField(null=True, blank=True)
    sum_value = models.FloatField(null=True, blank=True)

    attributes = models.JSONField(default=dict, blank=True)
    resource = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-time"]
        indexes = [
            models.Index(fields=["service", "name", "-time"], name="metric_svc_name_time_idx"),
            models.Index(fields=["project", "-time"], name="metric_project_time_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.service} {self.name}={self.value} ({self.kind})"


class LogRecord(models.Model):
    """A single OTLP log record (Phase 11), tenant-aware hypertable.

    Correlated to traces via ``trace_id`` / ``span_id`` when present.
    """

    time = models.DateTimeField(db_index=True)
    project = models.ForeignKey(
        "tenancy.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="log_records",
        db_index=True,
        db_constraint=False,
    )
    service = models.CharField(max_length=200, db_index=True)
    severity_text = models.CharField(max_length=32, blank=True, default="", db_index=True)
    severity_number = models.PositiveSmallIntegerField(default=0)
    body = models.TextField(blank=True, default="")

    trace_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    span_id = models.CharField(max_length=32, blank=True, default="")

    attributes = models.JSONField(default=dict, blank=True)
    resource = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-time"]
        indexes = [
            models.Index(fields=["service", "-time"], name="log_service_time_idx"),
            models.Index(fields=["trace_id"], name="log_trace_idx"),
            models.Index(fields=["project", "-time"], name="log_project_time_idx"),
            models.Index(
                fields=["service", "-time"],
                name="log_error_service_time_idx",
                condition=Q(severity_number__gte=17),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service} [{self.severity_text}] {self.body[:60]}"


class Issue(models.Model):
    """A group of similar errors (Phase 13), fingerprinted Sentry-style.

    Signature is a normalized identity (service + method + endpoint + status
    class + normalized message) so repeated occurrences roll up into one issue
    with a count and first/last-seen window.
    """

    project = models.ForeignKey(
        "tenancy.Project",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="issues",
        db_constraint=False,
    )
    signature = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255)
    service = models.CharField(max_length=200, blank=True, default="")
    endpoint = models.CharField(max_length=255, blank=True, default="")
    method = models.CharField(max_length=10, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)

    count = models.PositiveIntegerField(default=0)
    first_seen = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True)
    sample_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-count", "-last_seen"]
        constraints = [
            models.UniqueConstraint(fields=["project", "signature"], name="uniq_project_issue")
        ]

    def __str__(self) -> str:
        return f"{self.title} (×{self.count})"
