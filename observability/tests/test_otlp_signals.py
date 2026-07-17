"""OTLP metrics + logs ingestion, tail sampling, and rate limiting (Phase 11)."""

from __future__ import annotations

import os

from django.test import TestCase
from rest_framework.test import APIClient

from observability.models import LogRecord, MetricPoint
from observability.otlp import ratelimit
from observability.otlp.parser import parse_logs, parse_metrics
from observability.otlp.sampling import tail_sample
from tenancy.models import Organization, Project


def _metrics_payload():
    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [{"key": "service.name", "value": {"stringValue": "api"}}]
                },
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "http.server.active_requests",
                                "unit": "1",
                                "gauge": {
                                    "dataPoints": [
                                        {"asInt": "5", "timeUnixNano": "1700000000000000000"}
                                    ]
                                },
                            },
                            {
                                "name": "http.server.duration",
                                "unit": "ms",
                                "histogram": {
                                    "dataPoints": [
                                        {
                                            "count": "10",
                                            "sum": 1234.5,
                                            "bucketCounts": ["3", "7"],
                                            "explicitBounds": [100],
                                            "timeUnixNano": "1700000000000000000",
                                        }
                                    ]
                                },
                            },
                        ]
                    }
                ],
            }
        ]
    }


def _logs_payload():
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [{"key": "service.name", "value": {"stringValue": "api"}}]
                },
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": "1700000000000000000",
                                "severityNumber": 17,
                                "severityText": "ERROR",
                                "body": {"stringValue": "boom"},
                                "traceId": "abcd",
                                "spanId": "1111",
                            }
                        ]
                    }
                ],
            }
        ]
    }


class MetricsLogsParseTests(TestCase):
    def test_parse_metrics(self):
        points = parse_metrics(_metrics_payload())
        self.assertEqual(len(points), 2)
        gauge = next(p for p in points if p["kind"] == "gauge")
        self.assertEqual(gauge["value"], 5.0)
        hist = next(p for p in points if p["kind"] == "histogram")
        self.assertEqual(hist["count"], 10)
        self.assertEqual(hist["sum_value"], 1234.5)

    def test_parse_logs(self):
        recs = parse_logs(_logs_payload())
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["severity_text"], "ERROR")
        self.assertEqual(recs[0]["body"], "boom")
        self.assertEqual(recs[0]["trace_id"], "abcd")


class SignalEndpointTests(TestCase):
    def setUp(self):
        org, _ = Organization.objects.get_or_create(slug="default", defaults={"name": "Default"})
        Project.objects.get_or_create(
            organization=org, slug="default", defaults={"name": "Default"}
        )
        ratelimit.reset()

    def test_metrics_endpoint(self):
        resp = APIClient().post("/v1/metrics", _metrics_payload(), format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(MetricPoint.objects.count(), 2)

    def test_logs_endpoint(self):
        resp = APIClient().post("/v1/logs", _logs_payload(), format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LogRecord.objects.count(), 1)


class TailSamplingTests(TestCase):
    def _spans(self, trace_id, error=False, dur=10):
        return [
            {"trace_id": trace_id, "status_code": "error" if error else "ok", "duration_ms": dur},
            {"trace_id": trace_id, "status_code": "ok", "duration_ms": dur},
        ]

    def test_rate_one_keeps_all(self):
        os.environ.pop("OTLP_TAIL_SAMPLE_RATE", None)
        kept, dropped = tail_sample(self._spans("t1"))
        self.assertEqual(dropped, 0)
        self.assertEqual(len(kept), 2)

    def test_rate_zero_keeps_only_interesting(self):
        os.environ["OTLP_TAIL_SAMPLE_RATE"] = "0"
        os.environ["OTLP_SLOW_MS"] = "500"
        try:
            spans = (
                self._spans("t-normal")
                + self._spans("t-error", error=True)
                + self._spans("t-slow", dur=999)
            )
            kept, dropped = tail_sample(spans)
        finally:
            os.environ.pop("OTLP_TAIL_SAMPLE_RATE", None)
            os.environ.pop("OTLP_SLOW_MS", None)
        kept_traces = {s["trace_id"] for s in kept}
        self.assertEqual(kept_traces, {"t-error", "t-slow"})
        self.assertEqual(dropped, 2)  # the normal trace's 2 spans


class RateLimitTests(TestCase):
    def setUp(self):
        ratelimit.reset()

    def test_unlimited_when_rate_zero(self):
        os.environ.pop("OTLP_RATE_LIMIT_PER_SEC", None)
        self.assertTrue(all(ratelimit.allow(1) for _ in range(100)))

    def test_bucket_limits_then_denies(self):
        os.environ["OTLP_RATE_LIMIT_PER_SEC"] = "10"
        os.environ["OTLP_RATE_LIMIT_BURST"] = "3"
        try:
            ratelimit.reset()
            now = 1000.0
            allowed = [ratelimit.allow(1, now=now) for _ in range(5)]
        finally:
            os.environ.pop("OTLP_RATE_LIMIT_PER_SEC", None)
            os.environ.pop("OTLP_RATE_LIMIT_BURST", None)
            ratelimit.reset()
        self.assertEqual(allowed, [True, True, True, False, False])  # burst=3
