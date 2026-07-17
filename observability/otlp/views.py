# observability/otlp/views.py
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from observability.metrics import apm_spans_dropped_total
from tenancy.middleware import set_current_project

from . import ratelimit
from .ingest import store_logs, store_metrics, store_spans
from .parser import parse_logs, parse_metrics, parse_traces
from .sampling import tail_sample


class _OTLPBaseView(APIView):
    """Shared tenant resolution + rate limiting for OTLP receivers."""

    authentication_classes: list = []  # DEFAULT_AUTHENTICATION_CLASSES apply
    permission_classes = [AllowAny]
    signal = "otlp"

    def resolve_project(self, request):
        project = getattr(request, "tenant_project", None)
        if project is not None:
            return project
        from tenancy.models import Project

        return Project.objects.filter(slug="default", organization__slug="default").first()

    def payload(self, request) -> dict:
        """Return the request as an OTLP dict, decoding protobuf when needed."""
        from .protobuf import CONTENT_TYPE, decode

        content_type = (request.content_type or "").split(";")[0].strip().lower()
        if content_type == CONTENT_TYPE:
            return decode(self.signal, request.body)
        return request.data or {}

    def guard(self, request, cost: int):
        project = self.resolve_project(request)
        if project is None:
            return None, Response(
                {"detail": "No tenant resolved. Provide an Api-Key or create a default project."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not ratelimit.allow(project.id, cost):
            return None, Response(
                {"detail": "Ingest rate limit exceeded for this project."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        set_current_project(project.id)
        return project, None


class OTLPTracesView(_OTLPBaseView):
    """OTLP/HTTP JSON trace receiver (``POST /v1/traces``) with tail sampling."""

    signal = "traces"

    @extend_schema(request=None, responses={200: None}, description="OTLP trace ingestion.")
    def post(self, request):
        spans = parse_traces(self.payload(request))
        project, err = self.guard(request, cost=max(len(spans), 1))
        if err:
            return err
        kept, dropped = tail_sample(spans)
        if dropped:
            apm_spans_dropped_total.labels(service="_all").inc(dropped)
        result = store_spans(kept, project)
        data = result.as_response_data()
        data["stored"]["dropped_by_sampling"] = dropped
        return Response(data, status=status.HTTP_200_OK)


class OTLPMetricsView(_OTLPBaseView):
    """OTLP/HTTP JSON metrics receiver (``POST /v1/metrics``)."""

    signal = "metrics"

    @extend_schema(request=None, responses={200: None}, description="OTLP metrics ingestion.")
    def post(self, request):
        points = parse_metrics(self.payload(request))
        project, err = self.guard(request, cost=max(len(points), 1))
        if err:
            return err
        stored = store_metrics(points, project)
        return Response({"partialSuccess": {}, "stored": {"metric_points": stored}})


class OTLPLogsView(_OTLPBaseView):
    """OTLP/HTTP JSON logs receiver (``POST /v1/logs``)."""

    signal = "logs"

    @extend_schema(request=None, responses={200: None}, description="OTLP logs ingestion.")
    def post(self, request):
        records = parse_logs(self.payload(request))
        project, err = self.guard(request, cost=max(len(records), 1))
        if err:
            return err
        stored = store_logs(records, project)
        return Response({"partialSuccess": {}, "stored": {"log_records": stored}})
