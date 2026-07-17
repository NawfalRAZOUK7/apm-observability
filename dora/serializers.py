# dora/serializers.py
from django.utils import timezone
from rest_framework import serializers

from .models import Deployment


class DeploymentSerializer(serializers.ModelSerializer):
    lead_time_seconds = serializers.FloatField(read_only=True)
    is_failure = serializers.BooleanField(read_only=True)

    class Meta:
        model = Deployment
        fields = [
            "id",
            "environment",
            "version",
            "commit_sha",
            "service",
            "status",
            "caused_incident",
            "committed_at",
            "deployed_at",
            "duration_seconds",
            "triggered_by",
            "lead_time_seconds",
            "is_failure",
        ]
        extra_kwargs = {"deployed_at": {"required": False}}

    def validate(self, attrs):
        # Default the deploy time to now if the caller didn't provide one.
        attrs.setdefault("deployed_at", timezone.now())
        return attrs
