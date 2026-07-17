# notifications/admin.py
from django.contrib import admin

from .models import Incident, IncidentEvent, Notification


class IncidentEventInline(admin.TabularInline):
    model = IncidentEvent
    extra = 0
    readonly_fields = ("at", "kind", "message", "actor")


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "severity",
        "status",
        "opened_at",
        "acknowledged_at",
        "resolved_at",
    )
    list_filter = ("status", "severity")
    search_fields = ("title", "dedup_key", "trace_id")
    inlines = [IncidentEventInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "received_at",
        "severity",
        "alertname",
        "status",
        "delivered",
        "channels",
    )
    list_filter = ("severity", "status", "delivered")
    search_fields = ("alertname", "summary", "description", "fingerprint")
    readonly_fields = tuple(f.name for f in Notification._meta.fields)
    ordering = ("-received_at",)
