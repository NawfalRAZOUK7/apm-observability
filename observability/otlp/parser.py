# observability/otlp/parser.py
"""Parse OTLP/HTTP JSON trace payloads into normalized span dicts.

Implements the JSON encoding of the OTLP trace protocol (ExportTraceServiceRequest)
and the subset of OpenTelemetry semantic conventions we denormalize. No protobuf
dependency: OTLP defines a stable JSON mapping, and stock SDK exporters can emit
it (OTEL_EXPORTER_OTLP_PROTOCOL=http/json).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# OTLP SpanKind enum (int) -> our TextChoices value.
_KIND = {
    0: "unspecified",
    1: "internal",
    2: "server",
    3: "client",
    4: "producer",
    5: "consumer",
}
# OTLP StatusCode enum (int) -> our value.
_STATUS = {0: "unset", 1: "ok", 2: "error"}


def _attr_value(value: dict) -> Any:
    """Unwrap a single OTLP AnyValue."""
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        # OTLP encodes int64 as a string in JSON.
        try:
            return int(value["intValue"])
        except (TypeError, ValueError):
            return value["intValue"]
    if "doubleValue" in value:
        return value["doubleValue"]
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "arrayValue" in value:
        return [_attr_value(v) for v in value["arrayValue"].get("values", [])]
    if "kvlistValue" in value:
        return _attributes_to_dict(value["kvlistValue"].get("values", []))
    return None


def _attributes_to_dict(attributes: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for attr in attributes or []:
        key = attr.get("key")
        if key is None:
            continue
        out[key] = _attr_value(attr.get("value", {}) or {})
    return out


def _nano_to_dt(nanos: Any) -> datetime | None:
    if nanos in (None, "", 0, "0"):
        return None
    try:
        seconds = int(nanos) / 1_000_000_000
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=UTC)


def _first(attrs: dict, *keys: str, default=None):
    for key in keys:
        if key in attrs and attrs[key] not in (None, ""):
            return attrs[key]
    return default


def parse_traces(payload: dict) -> list[dict[str, Any]]:
    """Return a flat list of normalized span dicts from an OTLP request body."""
    spans: list[dict[str, Any]] = []
    for resource_span in payload.get("resourceSpans", []) or []:
        resource_attrs = _attributes_to_dict(
            (resource_span.get("resource") or {}).get("attributes", [])
        )
        service_name = resource_attrs.get("service.name", "unknown")

        for scope_span in resource_span.get("scopeSpans", []) or []:
            for span in scope_span.get("spans", []) or []:
                attrs = _attributes_to_dict(span.get("attributes", []))
                start = _nano_to_dt(span.get("startTimeUnixNano"))
                end = _nano_to_dt(span.get("endTimeUnixNano"))
                duration_ms = 0
                if start and end:
                    duration_ms = max(int((end - start).total_seconds() * 1000), 0)

                http_status = _first(
                    attrs, "http.response.status_code", "http.status_code"
                )
                try:
                    http_status = int(http_status) if http_status is not None else None
                except (TypeError, ValueError):
                    http_status = None

                spans.append(
                    {
                        "trace_id": span.get("traceId", ""),
                        "span_id": span.get("spanId", ""),
                        "parent_span_id": span.get("parentSpanId", "") or "",
                        "service": service_name,
                        "name": span.get("name", ""),
                        "kind": _KIND.get(span.get("kind", 0), "internal"),
                        "status_code": _STATUS.get(
                            (span.get("status") or {}).get("code", 0), "unset"
                        ),
                        "time": start,
                        "end_time": end,
                        "duration_ms": duration_ms,
                        "http_method": _first(
                            attrs, "http.request.method", "http.method", default=""
                        )
                        or "",
                        "http_route": _first(
                            attrs, "http.route", "url.path", "http.target", default=""
                        )
                        or "",
                        "http_status_code": http_status,
                        "attributes": attrs,
                        "resource": resource_attrs,
                    }
                )
    return spans


def _dp_value(dp: dict):
    if "asDouble" in dp:
        return float(dp["asDouble"])
    if "asInt" in dp:
        try:
            return float(int(dp["asInt"]))
        except (TypeError, ValueError):
            return None
    return None


def parse_metrics(payload: dict) -> list[dict[str, Any]]:
    """Flatten an OTLP metrics request into normalized metric-point dicts."""
    points: list[dict[str, Any]] = []
    for resource_metric in payload.get("resourceMetrics", []) or []:
        resource_attrs = _attributes_to_dict(
            (resource_metric.get("resource") or {}).get("attributes", [])
        )
        service_name = resource_attrs.get("service.name", "unknown")
        for scope_metric in resource_metric.get("scopeMetrics", []) or []:
            for metric in scope_metric.get("metrics", []) or []:
                name = metric.get("name", "")
                unit = metric.get("unit", "")
                for kind in ("gauge", "sum", "histogram"):
                    block = metric.get(kind)
                    if not block:
                        continue
                    for dp in block.get("dataPoints", []) or []:
                        common = {
                            "service": service_name,
                            "name": name,
                            "kind": kind,
                            "unit": unit,
                            "time": _nano_to_dt(dp.get("timeUnixNano")),
                            "attributes": _attributes_to_dict(dp.get("attributes", [])),
                            "resource": resource_attrs,
                            "value": None,
                            "count": None,
                            "sum_value": None,
                        }
                        if kind == "histogram":
                            common["count"] = int(dp.get("count", 0) or 0)
                            common["sum_value"] = float(dp.get("sum", 0) or 0)
                            common["attributes"] = {
                                **common["attributes"],
                                "bucketCounts": dp.get("bucketCounts", []),
                                "explicitBounds": dp.get("explicitBounds", []),
                            }
                        else:
                            common["value"] = _dp_value(dp)
                        points.append(common)
    return points


def parse_logs(payload: dict) -> list[dict[str, Any]]:
    """Flatten an OTLP logs request into normalized log-record dicts."""
    records: list[dict[str, Any]] = []
    for resource_log in payload.get("resourceLogs", []) or []:
        resource_attrs = _attributes_to_dict(
            (resource_log.get("resource") or {}).get("attributes", [])
        )
        service_name = resource_attrs.get("service.name", "unknown")
        for scope_log in resource_log.get("scopeLogs", []) or []:
            for record in scope_log.get("logRecords", []) or []:
                body = record.get("body") or {}
                body_text = _attr_value(body) if body else ""
                records.append(
                    {
                        "service": service_name,
                        "time": _nano_to_dt(record.get("timeUnixNano"))
                        or _nano_to_dt(record.get("observedTimeUnixNano")),
                        "severity_text": record.get("severityText", ""),
                        "severity_number": int(record.get("severityNumber", 0) or 0),
                        "body": body_text if isinstance(body_text, str) else str(body_text),
                        "trace_id": record.get("traceId", "") or "",
                        "span_id": record.get("spanId", "") or "",
                        "attributes": _attributes_to_dict(record.get("attributes", [])),
                        "resource": resource_attrs,
                    }
                )
    return records
