# tenancy/views.py
from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ApiKey, Environment, Membership, Project
from .permissions import IsOperator, IsViewer, user_max_role
from .quotas import current_usage
from .serializers import (
    ApiKeyCreateSerializer,
    ApiKeySerializer,
    ProjectSerializer,
)


def _visible_projects(user):
    """Projects in organizations the user belongs to (superuser sees all)."""
    if getattr(user, "is_superuser", False):
        return Project.objects.all().select_related("organization")
    org_ids = Membership.objects.filter(user=user).values_list("organization_id", flat=True)
    return Project.objects.filter(organization_id__in=org_ids).select_related("organization")


class ProjectListView(ListAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsViewer]

    def get_queryset(self):
        return _visible_projects(self.request.user).prefetch_related("environments")


class ApiKeyListCreateView(APIView):
    """List keys for a project, or mint a new one (returned in plaintext once)."""

    permission_classes = [IsAuthenticated, IsViewer]

    def _get_project(self, request, project_id):
        return get_object_or_404(_visible_projects(request.user), pk=project_id)

    @extend_schema(responses=ApiKeySerializer(many=True))
    def get(self, request, project_id):
        project = self._get_project(request, project_id)
        keys = project.api_keys.select_related("environment").all()
        return Response(ApiKeySerializer(keys, many=True).data)

    @extend_schema(request=ApiKeyCreateSerializer, responses={201: None})
    def post(self, request, project_id):
        # Minting keys requires operator+.
        if not IsOperator().has_permission(request, self):
            return Response({"detail": "operator role required."}, status=403)
        project = self._get_project(request, project_id)
        payload = ApiKeyCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        environment, _ = Environment.objects.get_or_create(
            project=project, kind=payload.validated_data["environment"]
        )
        api_key, plaintext = ApiKey.generate(
            project=project,
            environment=environment,
            name=payload.validated_data.get("name", ""),
            created_by=request.user if request.user.is_authenticated else None,
        )
        data = ApiKeySerializer(api_key).data
        # Plaintext is shown exactly once and never stored.
        data["key"] = plaintext
        data["warning"] = "Store this key now; it will not be shown again."
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyRotateView(APIView):
    permission_classes = [IsAuthenticated, IsOperator]

    def post(self, request, project_id, key_id):
        project = get_object_or_404(_visible_projects(request.user), pk=project_id)
        old = get_object_or_404(project.api_keys, pk=key_id)
        _new_key, plaintext = old.rotate()
        return Response(
            {
                "detail": "Key rotated. Old key revoked.",
                "key": plaintext,
                "warning": "Store this key now; it will not be shown again.",
            },
            status=status.HTTP_201_CREATED,
        )


class ApiKeyRevokeView(APIView):
    permission_classes = [IsAuthenticated, IsOperator]

    def post(self, request, project_id, key_id):
        project = get_object_or_404(_visible_projects(request.user), pk=project_id)
        key = get_object_or_404(project.api_keys, pk=key_id)
        key.revoke()
        return Response({"detail": "Key revoked."}, status=status.HTTP_200_OK)


class ProjectUsageView(APIView):
    permission_classes = [IsAuthenticated, IsViewer]

    def get(self, request, project_id):
        project = get_object_or_404(_visible_projects(request.user), pk=project_id)
        used = current_usage(project)
        quota = project.monthly_event_quota
        return Response(
            {
                "project": project.slug,
                "monthly_event_quota": quota,
                "used_this_month": used,
                "remaining": (max(quota - used, 0) if quota else None),
                "role": user_max_role(request.user),
            }
        )
