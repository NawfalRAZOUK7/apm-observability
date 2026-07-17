# alerting/views.py
from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tenancy.permissions import HasMinimumRole
from tenancy.views import _visible_projects

from .evaluator import evaluate_rule
from .models import AlertRule
from .serializers import AlertRuleSerializer


class AlertRuleViewSet(viewsets.ModelViewSet):
    """Tenant-scoped CRUD for alert rules.

    Reads require viewer+, writes require developer+ (HasMinimumRole default).
    Rules are visible/editable only within the caller's organizations.
    """

    serializer_class = AlertRuleSerializer
    permission_classes = [IsAuthenticated, HasMinimumRole]
    filterset_fields = ["project", "enabled", "kind", "severity", "state"]

    def get_queryset(self):
        projects = _visible_projects(self.request.user)
        return AlertRule.objects.filter(project__in=projects).select_related("project")

    def _assert_visible(self, project):
        if not _visible_projects(self.request.user).filter(pk=project.pk).exists():
            raise PermissionDenied("You do not have access to that project.")

    def perform_create(self, serializer):
        self._assert_visible(serializer.validated_data["project"])
        serializer.save()

    def perform_update(self, serializer):
        project = serializer.validated_data.get("project", serializer.instance.project)
        self._assert_visible(project)
        serializer.save()

    @action(detail=True, methods=["post"])
    def evaluate(self, request, pk=None):
        """Evaluate this rule immediately (useful for testing a rule)."""
        rule = self.get_object()
        result = evaluate_rule(rule)
        return Response(result)
