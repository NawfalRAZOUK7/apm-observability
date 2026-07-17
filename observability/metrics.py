from __future__ import annotations

from prometheus_client import Counter, Histogram

apm_ingested_requests_total = Counter(
    "apm_ingested_requests_total",
    "Number of APM requests ingested by the API.",
    ["service", "status_class"],
)

apm_ingest_latency_seconds = Histogram(
    "apm_ingest_latency_seconds",
    "Latency of the APM ingestion endpoint.",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

apm_spans_ingested_total = Counter(
    "apm_spans_ingested_total",
    "Number of OTLP spans ingested via /v1/traces.",
    ["service", "status_class"],
)

apm_metric_points_ingested_total = Counter(
    "apm_metric_points_ingested_total",
    "Number of OTLP metric data points ingested via /v1/metrics.",
    ["service"],
)

apm_logs_ingested_total = Counter(
    "apm_logs_ingested_total",
    "Number of OTLP log records ingested via /v1/logs.",
    ["service", "severity"],
)

apm_spans_dropped_total = Counter(
    "apm_spans_dropped_total",
    "Number of spans dropped by tail sampling.",
    ["service"],
)
