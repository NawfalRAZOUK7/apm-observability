# alerting/serializers.py
from rest_framework import serializers

from tenancy.models import Project

from .models import AlertRule


class AlertRuleSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_slug = serializers.CharField(source="project.slug", read_only=True)

    class Meta:
        model = AlertRule
        fields = [
            "id",
            "project",
            "project_slug",
            "name",
            "enabled",
            "kind",
            "metric",
            "service",
            "endpoint",
            "comparator",
            "threshold",
            "z_threshold",
            "window_minutes",
            "severity",
            "runbook_url",
            "state",
            "last_value",
            "last_evaluated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["state", "last_value", "last_evaluated_at", "created_at", "updated_at"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", AlertRule.Kind.THRESHOLD))
        metric = attrs.get("metric", getattr(self.instance, "metric", None))
        if kind == AlertRule.Kind.ANOMALY and metric == AlertRule.Metric.REQUEST_COUNT:
            raise serializers.ValidationError(
                {"metric": "request_count is not supported for anomaly rules."}
            )
        return attrs
