# observability/traces_views.py
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from tenancy.models import Project

from .api.query_params import get_datetime_or_date_query_param, get_int_query_param
from .models import Span


def _resolve_project(request):
    slug = request.query_params.get("project")
    if slug:
        return Project.objects.filter(slug=slug).first()
    return getattr(request, "tenant_project", None)


def _is_error(span: Span) -> bool:
    return span.status_code == Span.StatusCode.ERROR or (
        span.http_status_code is not None and span.http_status_code >= 500
    )


class TraceListView(APIView):
    """Recent trace summaries (Phase 12) for the UI trace list."""

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("since", str), OpenApiParameter("until", str),
            OpenApiParameter("project", str), OpenApiParameter("limit", int),
        ],
        responses={200: None},
    )
    def get(self, request):
        now = timezone.now()
        until = get_datetime_or_date_query_param(request, "until", end_of_day=True) or now
        since = get_datetime_or_date_query_param(request, "since") or (until - timedelta(hours=1))
        limit = get_int_query_param(request, "limit", 50, min_value=1, max_value=500)

        qs = Span.objects.filter(time__gte=since, time__lt=until)
        project = _resolve_project(request)
        if project is not None:
            qs = qs.filter(project=project)

        traces: dict[str, list[Span]] = {}
        for span in qs.only(
            "trace_id", "parent_span_id", "service", "name", "time", "end_time",
            "duration_ms", "status_code", "http_status_code",
        )[:5000]:
            traces.setdefault(span.trace_id, []).append(span)

        summaries = []
        for trace_id, spans in traces.items():
            roots = [s for s in spans if not s.parent_span_id] or spans
            root = min(roots, key=lambda s: s.time)
            start = min(s.time for s in spans)
            summaries.append(
                {
                    "trace_id": trace_id,
                    "root_service": root.service,
                    "root_name": root.name,
                    "span_count": len(spans),
                    "duration_ms": max(s.duration_ms for s in spans),
                    "error": any(_is_error(s) for s in spans),
                    "start": start.isoformat(),
                }
            )
        summaries.sort(key=lambda t: t["start"], reverse=True)
        return Response({"count": len(summaries), "traces": summaries[:limit]})


class TraceDetailView(APIView):
    """All spans of one trace with waterfall offsets (Phase 12)."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request, trace_id):
        qs = Span.objects.filter(trace_id=trace_id)
        project = _resolve_project(request)
        if project is not None:
            qs = qs.filter(project=project)
        spans = list(qs)
        if not spans:
            return Response({"trace_id": trace_id, "spans": []})

        trace_start = min(s.time for s in spans)
        rows = [
            {
                "span_id": s.span_id,
                "parent_span_id": s.parent_span_id,
                "service": s.service,
                "name": s.name,
                "kind": s.kind,
                "start_offset_ms": int((s.time - trace_start).total_seconds() * 1000),
                "duration_ms": s.duration_ms,
                "status": s.status_code,
                "error": _is_error(s),
                "http_status_code": s.http_status_code,
            }
            for s in sorted(spans, key=lambda s: s.time)
        ]
        return Response(
            {
                "trace_id": trace_id,
                "start": trace_start.isoformat(),
                "total_ms": max(r["start_offset_ms"] + r["duration_ms"] for r in rows),
                "span_count": len(rows),
                "spans": rows,
            }
        )
