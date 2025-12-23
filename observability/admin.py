# observability/admin.py
from django.contrib import admin

from .models import ApiRequest, ApiRequestEmbedding


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
