# observability/otlp/grpc_server.py
"""Native OTLP/gRPC receiver on :4317 (Phase 11).

Implements the three OTLP collector services (trace/metrics/logs) by converting
the protobuf request to the OTLP-JSON dict shape and reusing the same parsers,
tail sampling, rate limiting, and store functions as the HTTP path. Tenant is
resolved from the gRPC ``authorization`` metadata (``Api-Key <key>``), falling
back to the default project.

Runs as its own process (``manage.py otlp_grpc_server``) since it needs a
long-lived gRPC server, separate from the WSGI app. Imports of grpc/proto are
done here so the rest of the app never depends on them.
"""

from __future__ import annotations

from concurrent import futures

from . import ratelimit
from .ingest import store_logs, store_metrics, store_spans
from .parser import parse_logs, parse_metrics, parse_traces
from .sampling import tail_sample


def _resolve_project(context):
    from tenancy.models import ApiKey, Project

    metadata = dict(context.invocation_metadata() or [])
    auth = metadata.get("authorization", "")
    if auth.lower().startswith("api-key "):
        key = ApiKey.verify(auth.split(None, 1)[1].strip())
        if key is not None:
            return key.project
    return Project.objects.filter(slug="default", organization__slug="default").first()


def _rate_ok(project, cost):
    return project is not None and ratelimit.allow(project.id, max(cost, 1))


def build_server(port: int = 4317):
    import grpc
    from google.protobuf.json_format import MessageToDict
    from opentelemetry.proto.collector.logs.v1 import logs_service_pb2, logs_service_pb2_grpc
    from opentelemetry.proto.collector.metrics.v1 import (
        metrics_service_pb2,
        metrics_service_pb2_grpc,
    )
    from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc

    from tenancy.middleware import set_current_project

    def _prepare(request, context, cost_of):
        payload = MessageToDict(request, preserving_proto_field_name=False)
        project = _resolve_project(context)
        return payload, project

    class TraceService(trace_service_pb2_grpc.TraceServiceServicer):
        def Export(self, request, context):
            payload, project = _prepare(request, context, None)
            spans = parse_traces(payload)
            if not _rate_ok(project, len(spans)):
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "rate limit exceeded")
            set_current_project(project.id)
            kept, _dropped = tail_sample(spans)
            store_spans(kept, project)
            return trace_service_pb2.ExportTraceServiceResponse()

    class MetricsService(metrics_service_pb2_grpc.MetricsServiceServicer):
        def Export(self, request, context):
            payload, project = _prepare(request, context, None)
            points = parse_metrics(payload)
            if not _rate_ok(project, len(points)):
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "rate limit exceeded")
            set_current_project(project.id)
            store_metrics(points, project)
            return metrics_service_pb2.ExportMetricsServiceResponse()

    class LogsService(logs_service_pb2_grpc.LogsServiceServicer):
        def Export(self, request, context):
            payload, project = _prepare(request, context, None)
            records = parse_logs(payload)
            if not _rate_ok(project, len(records)):
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "rate limit exceeded")
            set_current_project(project.id)
            store_logs(records, project)
            return logs_service_pb2.ExportLogsServiceResponse()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(TraceService(), server)
    metrics_service_pb2_grpc.add_MetricsServiceServicer_to_server(MetricsService(), server)
    logs_service_pb2_grpc.add_LogsServiceServicer_to_server(LogsService(), server)
    server.add_insecure_port(f"[::]:{port}")
    return server


def serve(port: int = 4317):
    server = build_server(port)
    server.start()
    server.wait_for_termination()
