# alerting/admin.py
from django.contrib import admin

from .models import AlertRule, AlertRuleEvaluation


class AlertRuleEvaluationInline(admin.TabularInline):
    model = AlertRuleEvaluation
    extra = 0
    readonly_fields = ("at", "value", "firing", "detail")
    can_delete = False
    max_num = 20


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "kind",
        "metric",
        "severity",
        "enabled",
        "state",
        "last_value",
        "last_evaluated_at",
    )
    list_filter = ("kind", "severity", "enabled", "state", "project")
    search_fields = ("name", "service", "endpoint")
    inlines = [AlertRuleEvaluationInline]
