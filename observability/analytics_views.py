# observability/analytics_views.py
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from tenancy.models import Project

from .analytics.anomaly import detect_anomalies
from .analytics.nlquery import answer_question
from .analytics.service_map import build_service_map
from .api.query_params import get_datetime_or_date_query_param
from .models import Issue


class IssueListView(APIView):
    """Grouped errors ("issues"), most frequent first (Phase 13)."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None}, description="Grouped errors ranked by count.")
    def get(self, request):
        qs = Issue.objects.all()
        project = _resolve_project(request)
        if project is not None:
            qs = qs.filter(project=project)
        issues = [
            {
                "id": i.id,
                "title": i.title,
                "signature": i.signature,
                "service": i.service,
                "endpoint": i.endpoint,
                "method": i.method,
                "status_code": i.status_code,
                "count": i.count,
                "first_seen": i.first_seen.isoformat() if i.first_seen else None,
                "last_seen": i.last_seen.isoformat() if i.last_seen else None,
                "sample_message": i.sample_message,
            }
            for i in qs[:200]
        ]
        return Response({"count": len(issues), "issues": issues})


class NLQueryView(APIView):
    """Natural-language telemetry query (Phase 13).

    ``?q=error rate for checkout in the last 6 hours`` -> parsed params + result.
    Uses an LLM when configured, otherwise a keyword heuristic (both $0-capable).
    """

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="Natural-language question.")],
        responses={200: None},
    )
    def get(self, request):
        question = request.query_params.get("q", "")
        if not question.strip():
            return Response({"detail": "Provide a ?q= question."}, status=400)
        return Response(answer_question(question, project=_resolve_project(request)))


class ServiceMapView(APIView):
    """Service dependency topology derived from span edges (Phase 7).

    Query params: ``since``/``until`` (ISO datetime or date; default last 1h),
    optional ``project`` (slug) to scope to one tenant.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("since", str, description="ISO datetime/date (default: 1h ago)."),
            OpenApiParameter("until", str, description="ISO datetime/date (default: now)."),
            OpenApiParameter("project", str, description="Project slug to scope to."),
        ],
        responses={200: None},
        description="Service map: nodes, dependency edges with rate/error/latency, "
        "critical path, and period-over-period deltas.",
    )
    def get(self, request):
        now = timezone.now()
        until = get_datetime_or_date_query_param(request, "until", end_of_day=True) or now
        since = get_datetime_or_date_query_param(request, "since") or (until - timedelta(hours=1))

        project = _resolve_project(request)
        return Response(build_service_map(since, until, project))


def _resolve_project(request):
    slug = request.query_params.get("project")
    if slug:
        return Project.objects.filter(slug=slug).first()
    return getattr(request, "tenant_project", None)


class AnomalyView(APIView):
    """Statistical anomalies (latency + error rate) per service+endpoint (Phase 8).

    Query params: ``since``/``until`` (default last 24h), optional ``service``,
    ``endpoint``, ``project``, ``bucket`` (minute|hour|day), ``threshold`` (z).
    """

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("since", str, description="ISO datetime/date (default: 24h ago)."),
            OpenApiParameter("until", str, description="ISO datetime/date (default: now)."),
            OpenApiParameter("service", str),
            OpenApiParameter("endpoint", str),
            OpenApiParameter("project", str, description="Project slug."),
            OpenApiParameter("bucket", str, description="minute | hour | day (default hour)."),
        ],
        responses={200: None},
        description="Robust (median/MAD) anomaly detection over API request "
        "latency and error rate, per service+endpoint.",
    )
    def get(self, request):
        now = timezone.now()
        until = get_datetime_or_date_query_param(request, "until", end_of_day=True) or now
        since = get_datetime_or_date_query_param(request, "since") or (until - timedelta(hours=24))
        bucket = request.query_params.get("bucket", "hour")
        if bucket not in ("minute", "hour", "day"):
            bucket = "hour"
        threshold = float(request.query_params.get("threshold", "3") or 3)

        anomalies = detect_anomalies(
            since,
            until,
            project=_resolve_project(request),
            service=request.query_params.get("service"),
            endpoint=request.query_params.get("endpoint"),
            bucket=bucket,
            z_threshold=threshold,
        )
        flagged = [a for a in anomalies if a["is_anomaly"]]
        return Response(
            {
                "window": {"since": since.isoformat(), "until": until.isoformat()},
                "bucket": bucket,
                "z_threshold": threshold,
                "anomaly_count": len(flagged),
                "anomalies": flagged,
                "series": anomalies,
            }
        )
