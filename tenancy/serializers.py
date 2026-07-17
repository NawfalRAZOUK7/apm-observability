# tenancy/serializers.py
from rest_framework import serializers

from .models import ApiKey, Environment, Organization, Project


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "created_at"]


class EnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment
        fields = ["id", "kind"]


class ProjectSerializer(serializers.ModelSerializer):
    organization = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    environments = EnvironmentSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "organization",
            "name",
            "slug",
            "monthly_event_quota",
            "environments",
            "created_at",
        ]


class ApiKeySerializer(serializers.ModelSerializer):
    """Read view of a key. Never exposes the plaintext or hash."""

    environment = serializers.CharField(source="environment.kind", read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ApiKey
        fields = [
            "id",
            "name",
            "prefix",
            "environment",
            "can_write",
            "is_active",
            "created_at",
            "last_used_at",
            "expires_at",
            "revoked_at",
        ]


class ApiKeyCreateSerializer(serializers.Serializer):
    environment = serializers.ChoiceField(choices=Environment.Kind.choices)
    name = serializers.CharField(required=False, allow_blank=True, default="")
