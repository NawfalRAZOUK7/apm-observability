"""OTLP protobuf-over-HTTP and gRPC server tests (Phase 11).

Skipped automatically when the optional grpc/proto deps are not installed.
"""

from __future__ import annotations

import unittest

from django.test import TestCase
from rest_framework.test import APIClient

from observability.models import Span
from tenancy.models import Organization, Project

try:  # optional dependencies
    import grpc  # noqa: F401
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
    from opentelemetry.proto.resource.v1.resource_pb2 import Resource
    from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans
    from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan

    HAVE_GRPC = True
except Exception:  # pragma: no cover
    HAVE_GRPC = False


def _build_trace_request_bytes() -> bytes:
    span = PbSpan(
        trace_id=b"\x01" * 16,
        span_id=b"\x02" * 8,
        name="GET /pb",
        kind=PbSpan.SpanKind.SPAN_KIND_SERVER,
        start_time_unix_nano=1_700_000_000_000_000_000,
        end_time_unix_nano=1_700_000_000_050_000_000,
    )
    scope = ScopeSpans(spans=[span])
    resource = Resource(
        attributes=[KeyValue(key="service.name", value=AnyValue(string_value="pbservice"))]
    )
    rs = ResourceSpans(resource=resource, scope_spans=[scope])
    return ExportTraceServiceRequest(resource_spans=[rs]).SerializeToString()


@unittest.skipUnless(HAVE_GRPC, "grpcio/opentelemetry-proto not installed")
class ProtobufHttpTests(TestCase):
    def setUp(self):
        org, _ = Organization.objects.get_or_create(slug="default", defaults={"name": "Default"})
        Project.objects.get_or_create(
            organization=org, slug="default", defaults={"name": "Default"}
        )

    def test_protobuf_traces_over_http(self):
        body = _build_trace_request_bytes()
        resp = APIClient().post("/v1/traces", data=body, content_type="application/x-protobuf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Span.objects.count(), 1)
        self.assertEqual(Span.objects.get().service, "pbservice")


@unittest.skipUnless(HAVE_GRPC, "grpcio/opentelemetry-proto not installed")
class GrpcServerBuildTests(TestCase):
    def test_build_server_registers_services(self):
        from observability.otlp.grpc_server import build_server

        server = build_server(0)  # port 0 = ephemeral; we don't start it
        self.assertIsNotNone(server)
