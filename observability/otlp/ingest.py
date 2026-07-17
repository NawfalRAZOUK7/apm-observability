# observability/otlp/ingest.py
"""Persist parsed OTLP spans: service registration, span storage, and
conversion of HTTP server spans into the ApiRequest analytics model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from django.db import transaction
from django.utils import timezone

from observability.metrics import (
    apm_logs_ingested_total,
    apm_metric_points_ingested_total,
    apm_spans_ingested_total,
)
from observability.models import ApiRequest, LogRecord, MetricPoint, Service, Span


@dataclass(frozen=True)
class OtlpIngestResult:
    spans: int
    services: int
    analytics_rows: int

    def as_response_data(self) -> dict:
        # Mirror the OTLP ExportTraceServiceResponse shape (empty = full success).
        return {
            "partialSuccess": {},
            "stored": {
                "spans": self.spans,
                "services": self.services,
                "analytics_rows": self.analytics_rows,
            },
        }


def _register_services(project, names: set[str]) -> int:
    now = timezone.now()
    count = 0
    for name in names:
        _obj, created = Service.objects.update_or_create(
            project=project, name=name, defaults={"last_seen": now}
        )
        count += 1 if created else 0
    return len(names)


def _to_api_request(span_dict: dict, project) -> ApiRequest | None:
    """Convert an HTTP SERVER span into an ApiRequest row for KPI continuity."""
    if span_dict["kind"] != Span.Kind.SERVER:
        return None
    method = span_dict.get("http_method")
    status_code = span_dict.get("http_status_code")
    if not method or status_code is None:
        return None
    endpoint = span_dict.get("http_route") or span_dict.get("name") or "/"
    return ApiRequest(
        time=span_dict["time"] or timezone.now(),
        service=span_dict["service"][:100],
        endpoint=str(endpoint)[:255],
        method=method[:10],
        status_code=status_code,
        latency_ms=span_dict["duration_ms"],
        trace_id=span_dict.get("trace_id") or None,
        project=project,
        tags={"source": "otlp"},
    )


@transaction.atomic
def store_spans(span_dicts: list[dict], project) -> OtlpIngestResult:
    if not span_dicts:
        return OtlpIngestResult(0, 0, 0)

    service_names = {s["service"] for s in span_dicts if s.get("service")}
    n_services = _register_services(project, service_names)

    spans: list[Span] = []
    api_requests: list[ApiRequest] = []
    for s in span_dicts:
        spans.append(
            Span(
                time=s["time"] or timezone.now(),
                end_time=s.get("end_time"),
                duration_ms=s.get("duration_ms", 0),
                project=project,
                trace_id=s.get("trace_id", ""),
                span_id=s.get("span_id", ""),
                parent_span_id=s.get("parent_span_id", ""),
                service=s.get("service", "unknown")[:200],
                name=s.get("name", "")[:255],
                kind=s.get("kind", "internal"),
                status_code=s.get("status_code", "unset"),
                http_method=(s.get("http_method") or "")[:10],
                http_route=(s.get("http_route") or "")[:255],
                http_status_code=s.get("http_status_code"),
                attributes=s.get("attributes", {}),
                resource=s.get("resource", {}),
            )
        )
        converted = _to_api_request(s, project)
        if converted is not None:
            api_requests.append(converted)

    Span.objects.bulk_create(spans, batch_size=1000)
    if api_requests:
        ApiRequest.objects.bulk_create(api_requests, batch_size=1000)

    for s in spans:
        status_class = "error" if s.status_code == "error" else "ok"
        apm_spans_ingested_total.labels(service=s.service, status_class=status_class).inc()

    return OtlpIngestResult(
        spans=len(spans), services=n_services, analytics_rows=len(api_requests)
    )


@transaction.atomic
def store_metrics(point_dicts: list[dict], project) -> int:
    if not point_dicts:
        return 0
    _register_services(project, {p["service"] for p in point_dicts if p.get("service")})
    points = [
        MetricPoint(
            time=p["time"] or timezone.now(),
            project=project,
            service=(p.get("service") or "unknown")[:200],
            name=(p.get("name") or "")[:255],
            kind=p.get("kind", "gauge"),
            unit=(p.get("unit") or "")[:63],
            value=p.get("value"),
            count=p.get("count"),
            sum_value=p.get("sum_value"),
            attributes=p.get("attributes", {}),
            resource=p.get("resource", {}),
        )
        for p in point_dicts
    ]
    MetricPoint.objects.bulk_create(points, batch_size=1000)
    for p in points:
        apm_metric_points_ingested_total.labels(service=p.service).inc()
    return len(points)


@transaction.atomic
def store_logs(record_dicts: list[dict], project) -> int:
    if not record_dicts:
        return 0
    _register_services(project, {r["service"] for r in record_dicts if r.get("service")})
    records = [
        LogRecord(
            time=r["time"] or timezone.now(),
            project=project,
            service=(r.get("service") or "unknown")[:200],
            severity_text=(r.get("severity_text") or "")[:32],
            severity_number=r.get("severity_number", 0),
            body=r.get("body", ""),
            trace_id=(r.get("trace_id") or "")[:64],
            span_id=(r.get("span_id") or "")[:32],
            attributes=r.get("attributes", {}),
            resource=r.get("resource", {}),
        )
        for r in record_dicts
    ]
    LogRecord.objects.bulk_create(records, batch_size=1000)
    for r in records:
        apm_logs_ingested_total.labels(
            service=r.service, severity=r.severity_text or "unspecified"
        ).inc()
    return len(records)
