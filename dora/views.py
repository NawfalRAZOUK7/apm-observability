# dora/views.py
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from observability.api.query_params import get_datetime_or_date_query_param
from tenancy.models import Project

from .metrics import compute_dora
from .models import Deployment
from .serializers import DeploymentSerializer


class DeploymentListCreateView(ListCreateAPIView):
    """Record a deployment (POST, called by CD) or list recent ones (GET).

    Unauthenticated for internal pipeline use; protect with an ingest key or
    network policy in production.
    """

    serializer_class = DeploymentSerializer
    permission_classes = [AllowAny]
    queryset = Deployment.objects.all()
    filterset_fields = ["environment", "status"]
    ordering_fields = ["deployed_at"]
    ordering = ["-deployed_at"]


class DoraMetricsView(APIView):
    """The four DORA metrics + Elite/High/Medium/Low bands over a window."""

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("since", str, description="ISO datetime/date (default 30d ago)."),
            OpenApiParameter("until", str),
            OpenApiParameter("environment", str, description="production|staging|development."),
            OpenApiParameter("project", str, description="Project slug."),
        ],
        responses={200: None},
    )
    def get(self, request):
        now = timezone.now()
        until = get_datetime_or_date_query_param(request, "until", end_of_day=True) or now
        since = get_datetime_or_date_query_param(request, "since") or (until - timedelta(days=30))

        project = None
        slug = request.query_params.get("project")
        if slug:
            project = Project.objects.filter(slug=slug).first()

        return Response(
            compute_dora(
                since,
                until,
                environment=request.query_params.get("environment"),
                project=project,
            )
        )
