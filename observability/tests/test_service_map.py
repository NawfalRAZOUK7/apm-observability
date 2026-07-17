"""Service-map derivation tests (Phase 7)."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from observability.analytics.service_map import build_service_map
from observability.models import Span


def _span(span_id, service, kind, *, parent="", dur=10, error=False, http=None, when=None):
    return Span.objects.create(
        time=when or timezone.now(),
        end_time=(when or timezone.now()),
        duration_ms=dur,
        trace_id="T1",
        span_id=span_id,
        parent_span_id=parent,
        service=service,
        name=f"{service}:{span_id}",
        kind=kind,
        status_code=Span.StatusCode.ERROR if error else Span.StatusCode.OK,
        http_status_code=http,
    )


class ServiceMapTests(TestCase):
    def setUp(self):
        # frontend -> api -> postgres, with the api->postgres call failing.
        _span("f1", "frontend", Span.Kind.SERVER, dur=200)
        _span("f2", "frontend", Span.Kind.CLIENT, parent="f1", dur=180)
        _span("a1", "api", Span.Kind.SERVER, parent="f2", dur=150)
        _span("a2", "api", Span.Kind.CLIENT, parent="a1", dur=40)
        _span("p1", "postgres", Span.Kind.SERVER, parent="a2", dur=30, error=True, http=500)

    def _map(self):
        now = timezone.now()
        return build_service_map(now - timedelta(hours=1), now + timedelta(minutes=1))

    def test_nodes_and_edges(self):
        m = self._map()
        services = {n["service"] for n in m["nodes"]}
        self.assertEqual(services, {"frontend", "api", "postgres"})

        edges = {(e["from"], e["to"]): e for e in m["edges"]}
        self.assertIn(("frontend", "api"), edges)
        self.assertIn(("api", "postgres"), edges)
        # The failing dependency is flagged unhealthy.
        self.assertEqual(edges[("api", "postgres")]["error_rate"], 1.0)
        self.assertTrue(edges[("api", "postgres")]["unhealthy"])
        self.assertFalse(edges[("frontend", "api")]["unhealthy"])

    def test_edge_latency(self):
        edges = {(e["from"], e["to"]): e for e in self._map()["edges"]}
        # api->postgres latency is the child (p1) duration.
        self.assertEqual(edges[("api", "postgres")]["avg_latency_ms"], 30.0)

    def test_critical_path_starts_at_slowest_root(self):
        path = self._map()["critical_path"]
        self.assertEqual(path[0]["service"], "frontend")
        # Follows the slowest child chain down to postgres.
        self.assertEqual(path[-1]["service"], "postgres")
        self.assertTrue(path[-1]["error"])

    def test_unhealthy_services_list(self):
        # postgres server span errored -> node unhealthy.
        self.assertIn("postgres", self._map()["unhealthy_services"])

    def test_empty_window(self):
        future = timezone.now() + timedelta(days=2)
        m = build_service_map(future, future + timedelta(hours=1))
        self.assertEqual(m["nodes"], [])
        self.assertEqual(m["edges"], [])
        self.assertEqual(m["critical_path"], [])
