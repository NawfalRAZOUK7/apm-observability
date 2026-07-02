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
