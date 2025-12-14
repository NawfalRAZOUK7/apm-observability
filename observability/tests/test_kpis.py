# observability/tests/test_kpis.py
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from observability.models import ApiRequest


class KpisEndpointTests(APITestCase):
    URL = "/api/requests/kpis/"

    def setUp(self):
        super().setUp()

        # KPI endpoint uses percentile_cont (Postgres), and/or postgres_required decorator.
        if connection.vendor != "postgresql":
            self.skipTest("KPIs endpoint tests require PostgreSQL (percentile_cont).")

        now = timezone.now()

        # Seed: 10 hits total, 2 errors => error_rate = 0.2
        rows: List[ApiRequest] = []

        # 8 OK
        for i in range(8):
            rows.append(
                ApiRequest(
                    time=now - timedelta(minutes=30 - i),
                    service="svc",
                    endpoint="/kpi",
                    method="GET",
                    status_code=200,
                    latency_ms=10 + i * 10,  # 10..80
                    tags={},
                )
            )
        # 2 errors
        rows.append(
            ApiRequest(
                time=now - timedelta(minutes=5),
                service="svc",
                endpoint="/kpi",
                method="GET",
                status_code=500,
                latency_ms=150,
                tags={},
            )
        )
        rows.append(
            ApiRequest(
                time=now - timedelta(minutes=4),
                service="svc",
                endpoint="/kpi",
                method="GET",
                status_code=502,
                latency_ms=250,
                tags={},
            )
        )

        ApiRequest.objects.bulk_create(rows)

    def test_kpis_shape_and_plausible_values(self):
        # method filter typically forces RAW path (so test doesn't depend on caggs existing)
        res = self.client.get(self.URL, {"service": "svc", "method": "GET"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        j: Dict[str, Any] = res.data

        # Required keys (based on your Step 5 behavior)
        required = [
            "hits",
            "errors",
            "error_rate",
            "avg_latency_ms",
            "p95_latency_ms",
            "max_latency_ms",
            "source",
        ]
        for k in required:
            self.assertIn(k, j)

        hits = int(j["hits"])
        errors = int(j["errors"])
        error_rate = float(j["error_rate"])

        self.assertEqual(hits, 10)
        self.assertEqual(errors, 2)
        self.assertAlmostEqual(error_rate, 2.0 / 10.0, places=6)

        # numeric latency fields
        self.assertTrue(isinstance(j["avg_latency_ms"], (int, float)))
        self.assertTrue(isinstance(j["max_latency_ms"], (int, float)))
        self.assertTrue(isinstance(j["p95_latency_ms"], (int, float)))

        # sanity checks
        self.assertGreaterEqual(float(j["max_latency_ms"]), float(j["p95_latency_ms"]))
        self.assertGreaterEqual(float(j["p95_latency_ms"]), 0.0)

        # method filter => raw is expected in your implementation
        self.assertEqual(j["source"], "raw")

    def test_kpis_bad_date_param_returns_400(self):
        res = self.client.get(self.URL, {"start": "not-a-date"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
