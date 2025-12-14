# observability/serializers.py
from rest_framework import serializers
from .models import ApiRequest


class ApiRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiRequest
        fields = [
            "id",
            "time",
            "service",
            "endpoint",
            "method",
            "status_code",
            "latency_ms",
            "trace_id",
            "user_ref",
            "tags",
        ]
        read_only_fields = ["id"]

    def validate_status_code(self, value: int) -> int:
        if value < 100 or value > 599:
            raise serializers.ValidationError("status_code must be a valid HTTP status (100..599).")
        return value

    def validate_latency_ms(self, value: int) -> int:
        if value < 0:
            raise serializers.ValidationError("latency_ms must be >= 0.")
        return value

    def validate_service(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("service cannot be empty.")
        return value

    def validate_endpoint(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("endpoint cannot be empty.")
        return value

    def validate_tags(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("tags must be a JSON object (dictionary).")
        return value
