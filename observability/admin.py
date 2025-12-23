# observability/admin.py
from django.contrib import admin

from .models import ApiRequest


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
