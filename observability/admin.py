# observability/admin.py
from django.contrib import admin

from .models import (
    ApiRequest,
    ApiRequestEmbedding,
    Issue,
    LogRecord,
    MetricPoint,
    Service,
    Span,
)


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("title", "service", "status_code", "count", "last_seen", "project")
    list_filter = ("service", "status_code")
    search_fields = ("title", "signature", "sample_message")


@admin.register(MetricPoint)
class MetricPointAdmin(admin.ModelAdmin):
    list_display = ("time", "service", "name", "kind", "value", "unit", "project")
    list_filter = ("kind", "service")
    search_fields = ("name", "service")


@admin.register(LogRecord)
class LogRecordAdmin(admin.ModelAdmin):
    list_display = ("time", "service", "severity_text", "trace_id", "project")
    list_filter = ("severity_text", "service")
    search_fields = ("body", "trace_id", "service")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "first_seen", "last_seen")
    list_filter = ("project",)
    search_fields = ("name",)


@admin.register(Span)
class SpanAdmin(admin.ModelAdmin):
    list_display = (
        "time",
        "service",
        "name",
        "kind",
        "status_code",
        "duration_ms",
        "trace_id",
    )
    list_filter = ("kind", "status_code", "service")
    search_fields = ("trace_id", "span_id", "name", "service")


@admin.register(ApiRequest)
class ApiRequestAdmin(admin.ModelAdmin):
    list_display = (
        "time",
        "service",
        "method",
        "endpoint",
        "status_code",
        "latency_ms",
        "trace_id",
        "user_ref",
    )
    list_filter = (
        "service",
        "method",
        "status_code",
        ("time", admin.DateFieldListFilter),
    )
    search_fields = (
        "service",
        "endpoint",
        "trace_id",
        "user_ref",
    )
    ordering = ("-time",)
    date_hierarchy = "time"

    # Performance on big tables
    list_select_related = ()
    list_per_page = 50


@admin.register(ApiRequestEmbedding)
class ApiRequestEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("request", "source", "model", "created_at")
    list_filter = ("source", "model", ("created_at", admin.DateFieldListFilter))
    search_fields = ("request__service", "request__endpoint")
    ordering = ("-created_at",)
