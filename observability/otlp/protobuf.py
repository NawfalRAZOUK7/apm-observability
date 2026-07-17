# observability/otlp/protobuf.py
"""Decode OTLP protobuf request bodies into the same dict shape as OTLP JSON.

Uses the opentelemetry-proto generated messages + protobuf's MessageToDict, whose
default lowerCamelCase output matches the OTLP/JSON field names our parsers
already understand (resourceSpans, scopeSpans, startTimeUnixNano, …). Imports are
lazy so the JSON path never requires protobuf/grpc.
"""

from __future__ import annotations

CONTENT_TYPE = "application/x-protobuf"


def decode(signal: str, body: bytes) -> dict:
    from google.protobuf.json_format import MessageToDict

    if signal == "traces":
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
            ExportTraceServiceRequest as Request,
        )
    elif signal == "metrics":
        from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
            ExportMetricsServiceRequest as Request,
        )
    elif signal == "logs":
        from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
            ExportLogsServiceRequest as Request,
        )
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown signal {signal!r}")

    message = Request()
    message.ParseFromString(body)
    # camelCase keys + include defaults so empty repeated fields exist.
    return MessageToDict(message, preserving_proto_field_name=False)
