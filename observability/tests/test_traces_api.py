"""Trace list + waterfall detail endpoints (Phase 12)."""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from observability.models import Span


def _span(trace, span_id, service, *, parent="", dur=10, offset_s=0, error=False):
    base = timezone.now() - timedelta(minutes=5)
    return Span.objects.create(
        time=base + timedelta(seconds=offset_s),
        end_time=base + timedelta(seconds=offset_s, milliseconds=dur),
        duration_ms=dur,
        trace_id=trace,
        span_id=span_id,
        parent_span_id=parent,
        service=service,
        name=f"{service}:{span_id}",
        kind=Span.Kind.SERVER,
        status_code=Span.StatusCode.ERROR if error else Span.StatusCode.OK,
    )


class TraceApiTests(TestCase):
    def setUp(self):
        _span("t1", "a", "frontend", dur=200)
        _span("t1", "b", "api", parent="a", dur=150, offset_s=0, error=True)
        _span("t2", "c", "frontend", dur=50)
        self.client = APIClient()

    def test_trace_list(self):
        resp = self.client.get("/api/traces/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["count"], 2)
        t1 = next(t for t in body["traces"] if t["trace_id"] == "t1")
        self.assertEqual(t1["span_count"], 2)
        self.assertTrue(t1["error"])
        self.assertEqual(t1["root_service"], "frontend")

    def test_trace_detail_waterfall(self):
        resp = self.client.get("/api/traces/t1/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["span_count"], 2)
        self.assertIn("total_ms", body)
        spans = {s["span_id"]: s for s in body["spans"]}
        self.assertEqual(spans["b"]["parent_span_id"], "a")
        self.assertTrue(spans["b"]["error"])
        self.assertIn("start_offset_ms", spans["a"])

    def test_trace_detail_unknown(self):
        resp = self.client.get("/api/traces/nope/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["spans"], [])
