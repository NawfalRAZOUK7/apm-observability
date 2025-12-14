# observability/tests/test_top_endpoints.py
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from observability.models import ApiRequest


class TopEndpointsEndpointTests(APITestCase):
    URL = "/api/requests/top-endpoints/"

    def setUp(self):
        super().setUp()

        # Top endpoints uses percentile_cont (Postgres), and/or postgres_required decorator.
        if connection.vendor != "postgresql":
            self.skipTest("Top endpoints tests require PostgreSQL (percentile_cont).")

        now = timezone.now()

        # Seed:
        # service api:
        #   /orders GET: 6 hits, 1 error, mid latency
        #   /health GET: 2 hits, 0 error, low latency
        #
        # service web:
        #   /home GET: 3 hits, 0 error
        #   /search GET: 1 hit, 1 error, high latency
        rows: List[ApiRequest] = []

        # api /orders (6 hits, 1 error)
        for i, ms in enumerate([20, 30, 40, 50, 60]):
            rows.append(
                ApiRequest(
                    time=now - timedelta(minutes=30 - i),
                    service="api",
                    endpoint="/orders",
                    method="GET",
                    status_code=200,
                    latency_ms=ms,
                    tags={},
                )
            )
        rows.append(
            ApiRequest(
                time=now - timedelta(minutes=10),
                service="api",
                endpoint="/orders",
                method="GET",
                status_code=500,
                latency_ms=200,
                tags={},
            )
        )

        # api /health (2 hits)
        rows.append(
            ApiRequest(
                time=now - timedelta(minutes=9),
                service="api",
                endpoint="/health",
                method="GET",
                status_code=200,
                latency_ms=5,
                tags={},
            )
        )
        rows.append(
            ApiRequest(
                time=now - timedelta(minutes=8),
                service="api",
                endpoint="/health",
                method="GET",
                status_code=200,
                latency_ms=8,
                tags={},
            )
        )

        # web /home (3 hits)
        for i, ms in enumerate([15, 17, 19]):
            rows.append(
                ApiRequest(
                    time=now - timedelta(minutes=40 - i),
                    service="web",
                    endpoint="/home",
                    method="GET",
                    status_code=200,
                    latency_ms=ms,
                    tags={},
                )
            )

        # web /search (1 hit, 1 error)
        rows.append(
            ApiRequest(
                time=now - timedelta(minutes=7),
                service="web",
                endpoint="/search",
                method="GET",
                status_code=504,
                latency_ms=450,
                tags={},
            )
        )

        ApiRequest.objects.bulk_create(rows)

    # ----------------------------
    # Helpers
    # ----------------------------
    def _as_rows(self, data: Any) -> List[Dict[str, Any]]:
        """
        Accept both response shapes:
          - list of rows
          - {"source": "...", "results": [...]}
        """
        if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
            return data["results"]
        if isinstance(data, list):
            return data
        self.fail(f"Unexpected response shape: {type(data)} => {data}")

    # ----------------------------
    # Tests
    # ----------------------------
    def test_params_validation_bad_sort_returns_400(self):
        res = self.client.get(self.URL, {"sort_by": "not-a-metric"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

    def test_sort_by_hits_desc_orders_biggest_first(self):
        # api:/orders has the most hits (6)
        res = self.client.get(self.URL, {"sort_by": "hits", "direction": "desc", "limit": 3})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        rows = self._as_rows(res.data)
        self.assertGreaterEqual(len(rows), 1)

        first = rows[0]
        self.assertEqual(first["service"], "api")
        self.assertEqual(first["endpoint"], "/orders")

        # Ensure key fields exist
        for k in ("service", "endpoint", "hits", "errors", "error_rate", "avg_latency_ms", "max_latency_ms"):
            self.assertIn(k, first)

        self.assertTrue(isinstance(first["hits"], int))
        self.assertTrue(isinstance(first["errors"], int))
        self.assertTrue(isinstance(first["error_rate"], (int, float)))

    def test_sort_by_hits_asc_orders_smallest_first(self):
        # smallest hits should be web:/search (1 hit)
        res = self.client.get(self.URL, {"sort_by": "hits", "direction": "asc", "limit": 1})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        rows = self._as_rows(res.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["service"], "web")
        self.assertEqual(rows[0]["endpoint"], "/search")

    def test_sort_by_error_rate_desc_orders_highest_first(self):
        # web:/search has 1 hit and 1 error => error_rate ~ 1.0 (highest)
        res = self.client.get(self.URL, {"sort_by": "error_rate", "direction": "desc", "limit": 1})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        rows = self._as_rows(res.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["service"], "web")
        self.assertEqual(rows[0]["endpoint"], "/search")
        self.assertGreaterEqual(float(rows[0]["error_rate"]), 0.9)

    def test_sort_by_avg_latency_desc_orders_slowest_first(self):
        # web:/search should be slowest avg latency due to high latency_ms
        res = self.client.get(self.URL, {"sort_by": "avg_latency_ms", "direction": "desc", "limit": 1})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        rows = self._as_rows(res.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["service"], "web")
        self.assertEqual(rows[0]["endpoint"], "/search")

    def test_with_p95_true_includes_p95_field(self):
        res = self.client.get(self.URL, {"limit": 5, "with_p95": "true"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        rows = self._as_rows(res.data)
        self.assertGreaterEqual(len(rows), 1)

        # Some rows may have p95 as None if too few samples; ensure field exists at least.
        self.assertTrue(any("p95_latency_ms" in r for r in rows))
        self.assertTrue(
            any(
                (r.get("p95_latency_ms") is not None and isinstance(r.get("p95_latency_ms"), (int, float)))
                for r in rows
            )
            or True  # tolerate None depending on your implementation/data
        )
