"""Statistical anomaly detection tests (Phase 8)."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from observability.analytics.anomaly import detect_anomalies
from observability.models import ApiRequest


def _bucket(hours_ago, *, n=10, latency=100, n_errors=0):
    when = (timezone.now() - timedelta(hours=hours_ago)).replace(minute=0, second=0, microsecond=0)
    rows = []
    for i in range(n):
        rows.append(
            ApiRequest(
                time=when,
                service="api",
                endpoint="/checkout",
                method="GET",
                status_code=500 if i < n_errors else 200,
                latency_ms=latency,
            )
        )
    ApiRequest.objects.bulk_create(rows)


class AnomalyTests(TestCase):
    def _detect(self, **kw):
        now = timezone.now()
        return detect_anomalies(now - timedelta(hours=48), now + timedelta(minutes=1), **kw)

    def test_latency_and_error_spike_flagged(self):
        # Stable-ish history...
        for h, lat, err in [(6, 100, 0), (5, 101, 1), (4, 99, 0), (3, 100, 1), (2, 102, 0)]:
            _bucket(h, latency=lat, n_errors=err)
        # ...then a latest bucket that spikes both latency and error rate.
        _bucket(0, latency=1000, n_errors=5)

        flagged = [a for a in self._detect() if a["is_anomaly"]]
        metrics = {a["metric"] for a in flagged}
        self.assertIn("latency_ms", metrics)
        self.assertIn("error_rate", metrics)
        latency = next(a for a in flagged if a["metric"] == "latency_ms")
        self.assertGreater(latency["z_score"], 3)
        self.assertEqual(latency["current"], 1000.0)

    def test_stable_series_not_flagged(self):
        for h in range(6, -1, -1):
            _bucket(h, latency=100, n_errors=0)
        self.assertEqual([a for a in self._detect() if a["is_anomaly"]], [])

    def test_needs_minimum_history(self):
        _bucket(1, latency=100)
        _bucket(0, latency=1000)
        self.assertEqual(self._detect(), [])  # < 3 buckets -> nothing to say
