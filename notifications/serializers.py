# notifications/serializers.py
from rest_framework import serializers

from .models import Incident, IncidentEvent, Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "received_at",
            "fingerprint",
            "status",
            "severity",
            "alertname",
            "summary",
            "description",
            "runbook_url",
            "labels",
            "annotations",
            "starts_at",
            "ends_at",
            "channels",
            "delivered",
            "delivery_error",
        ]
        read_only_fields = fields


class IncidentEventSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()

    class Meta:
        model = IncidentEvent
        fields = ["id", "at", "kind", "message", "actor"]


class IncidentSerializer(serializers.ModelSerializer):
    mtta_seconds = serializers.FloatField(read_only=True)
    mttr_seconds = serializers.FloatField(read_only=True)
    owner = serializers.StringRelatedField()
    acknowledged_by = serializers.StringRelatedField()

    class Meta:
        model = Incident
        fields = [
            "id",
            "dedup_key",
            "title",
            "severity",
            "status",
            "description",
            "runbook_url",
            "grafana_url",
            "trace_id",
            "opened_at",
            "acknowledged_at",
            "resolved_at",
            "acknowledged_by",
            "owner",
            "mtta_seconds",
            "mttr_seconds",
        ]


class IncidentDetailSerializer(IncidentSerializer):
    events = IncidentEventSerializer(many=True, read_only=True)

    class Meta(IncidentSerializer.Meta):
        fields = IncidentSerializer.Meta.fields + ["events"]
