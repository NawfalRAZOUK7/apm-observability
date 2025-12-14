# observability/tests.py
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ApiRequest


class ApiRequestIngestionTests(APITestCase):
    INGEST_URL = "/api/requests/ingest/"

    def _event(self, **overrides):
        """
        Build a valid ingestion event (one item).
        """
        base = {
            "time": timezone.now().isoformat(),
            "service": "billing",
            "endpoint": "/api/v1/invoices",
            "method": "GET",
            "status_code": 200,
            "latency_ms": 123,
            "trace_id": "trace-001",
            "user_ref": "user-001",
            "tags": {"env": "test"},
        }
        base.update(overrides)
        return base

    def test_raw_list_success_all_valid(self):
        payload = [
            self._event(trace_id="t1"),
            self._event(trace_id="t2", status_code=201, latency_ms=10),
        ]

        res = self.client.post(self.INGEST_URL, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["inserted"], 2)
        self.assertEqual(res.data["rejected"], 0)
        self.assertEqual(res.data["errors"], [])
        self.assertEqual(ApiRequest.objects.count(), 2)

    def test_mixed_valid_invalid_partial_insert(self):
        valid = self._event(trace_id="ok-1")
        invalid = self._event(trace_id="bad-1", status_code=700)  # invalid HTTP status (100..599)

        payload = [valid, invalid]

        res = self.client.post(self.INGEST_URL, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        self.assertEqual(res.data["inserted"], 1)
        self.assertEqual(res.data["rejected"], 1)
        self.assertTrue(isinstance(res.data["errors"], list))
        self.assertGreaterEqual(len(res.data["errors"]), 1)
        self.assertEqual(res.data["errors"][0]["index"], 1)

        self.assertEqual(ApiRequest.objects.count(), 1)
        row = ApiRequest.objects.first()
        self.assertEqual(row.trace_id, "ok-1")

    def test_wrapper_events_payload_works(self):
        payload = {
            "events": [
                self._event(trace_id="w1"),
                self._event(trace_id="w2", status_code=204, latency_ms=5),
            ]
        }

        res = self.client.post(self.INGEST_URL, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["inserted"], 2)
        self.assertEqual(res.data["rejected"], 0)
        self.assertEqual(ApiRequest.objects.count(), 2)

    def test_non_list_payload_returns_400(self):
        # dict without "events" is invalid shape
        payload = {"foo": "bar"}

        res = self.client.post(self.INGEST_URL, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
        self.assertIn("detail", res.data)

    def test_too_many_events_returns_413(self):
        # override guardrail via query param max_events=2
        payload = [
            self._event(trace_id="a"),
            self._event(trace_id="b"),
            self._event(trace_id="c"),
        ]

        res = self.client.post(f"{self.INGEST_URL}?max_events=2", data=payload, format="json")
        self.assertEqual(res.status_code, 413, res.data)
        # Should not insert anything because it fails before validation loop
        self.assertEqual(ApiRequest.objects.count(), 0)

    def test_max_errors_caps_error_details_but_counts_all_rejected(self):
        # 1 valid + 5 invalid => inserted=1, rejected=5
        valid = self._event(trace_id="ok")

        invalids = [
            self._event(trace_id="bad1", status_code=700),
            self._event(trace_id="bad2", status_code=700),
            self._event(trace_id="bad3", status_code=700),
            self._event(trace_id="bad4", status_code=700),
            self._event(trace_id="bad5", status_code=700),
        ]

        payload = [valid] + invalids

        res = self.client.post(
            f"{self.INGEST_URL}?max_errors=2",
            data=payload,
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        self.assertEqual(res.data["inserted"], 1)
        self.assertEqual(res.data["rejected"], 5)

        # Only 2 detailed error entries should be returned
        self.assertEqual(len(res.data["errors"]), 2)

        # DB should contain only the valid one
        self.assertEqual(ApiRequest.objects.count(), 1)
        self.assertEqual(ApiRequest.objects.first().trace_id, "ok")

    def test_strict_mode_rejects_all_if_any_invalid(self):
        # strict=true + any invalid item => 400 and NOTHING inserted
        valid = self._event(trace_id="s-ok")
        invalid = self._event(trace_id="s-bad", status_code=700)

        payload = [valid, invalid]

        res = self.client.post(f"{self.INGEST_URL}?strict=true", data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

        # Strict response should indicate nothing inserted
        self.assertEqual(res.data.get("inserted"), 0)
        self.assertEqual(res.data.get("rejected"), 2)

        # Ensure DB stays empty
        self.assertEqual(ApiRequest.objects.count(), 0)

    def test_strict_mode_rejects_all_if_any_item_not_dict(self):
        # strict=true + a non-dict item => 400 and NOTHING inserted
        valid = self._event(trace_id="s-ok-2")

        payload = [valid, "oops"]

        res = self.client.post(f"{self.INGEST_URL}?strict=true", data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

        self.assertEqual(res.data.get("inserted"), 0)
        self.assertEqual(res.data.get("rejected"), 2)

        # Should return at least one error (index 1)
        self.assertTrue(isinstance(res.data.get("errors"), list))
        self.assertGreaterEqual(len(res.data["errors"]), 1)
        self.assertEqual(res.data["errors"][0]["index"], 1)

        # Ensure DB stays empty
        self.assertEqual(ApiRequest.objects.count(), 0)


# ============================================================
# Step 5: API tests (KPIs + Top Endpoints)
# ============================================================
class Step5AnalyticsApiTests(APITestCase):
    """
    Step 5 tests (KPIs + Top Endpoints).

    These endpoints require PostgreSQL (percentile_cont) and are decorated with postgres_required,
    so we auto-skip on SQLite to keep local/CI flexible.
    """

    KPIS_URL = "/api/requests/kpis/"
    TOP_URL = "/api/requests/top-endpoints/"

    def setUp(self):
        super().setUp()
        if connection.vendor != "postgresql":
            self.skipTest(
                "Step 5 analytics tests require PostgreSQL (percentile_cont + postgres_required)."
            )

        now = timezone.now()

        # Seed data (all within last 24h so default KPI window includes them)
        #
        # Service api:
        #   /orders GET: 7 hits, 1 error
        #   /health GET: 3 hits, 0 error
        #   /orders POST: 2 hits, 1 error (to ensure method filter impacts totals)
        #
        # Service web:
        #   /home GET: 2 hits, 0 error
        #   /search GET: 1 hit, 1 error
        api_rows = [
            # /orders GET (7 hits, 1 error)
            ApiRequest(
                time=now - timedelta(minutes=10),
                service="api",
                endpoint="/orders",
                method="GET",
                status_code=200,
                latency_ms=10,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=9),
                service="api",
                endpoint="/orders",
                method="GET",
                status_code=200,
                latency_ms=20,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=8),
                service="api",
                endpoint="/orders",
                method="GET",
                status_code=200,
                latency_ms=30,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=7),
                service="api",
                endpoint="/orders",
                method="GET",
                status_code=200,
                latency_ms=40,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=6),
                service="api",
                endpoint="/orders",
                method="GET",
                status_code=200,
                latency_ms=50,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=5),
                service="api",
                endpoint="/orders",
                method="GET",
                status_code=200,
                latency_ms=60,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=4),
                service="api",
                endpoint="/orders",
                method="GET",
                status_code=500,
                latency_ms=70,
                tags={},
            ),
            # /health GET (3 hits)
            ApiRequest(
                time=now - timedelta(minutes=3),
                service="api",
                endpoint="/health",
                method="GET",
                status_code=200,
                latency_ms=15,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=2),
                service="api",
                endpoint="/health",
                method="GET",
                status_code=200,
                latency_ms=18,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=1),
                service="api",
                endpoint="/health",
                method="GET",
                status_code=200,
                latency_ms=12,
                tags={},
            ),
            # /orders POST (2 hits, 1 error)
            ApiRequest(
                time=now - timedelta(minutes=11),
                service="api",
                endpoint="/orders",
                method="POST",
                status_code=201,
                latency_ms=120,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=12),
                service="api",
                endpoint="/orders",
                method="POST",
                status_code=502,
                latency_ms=220,
                tags={},
            ),
        ]

        web_rows = [
            ApiRequest(
                time=now - timedelta(minutes=20),
                service="web",
                endpoint="/home",
                method="GET",
                status_code=200,
                latency_ms=33,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=19),
                service="web",
                endpoint="/home",
                method="GET",
                status_code=200,
                latency_ms=35,
                tags={},
            ),
            ApiRequest(
                time=now - timedelta(minutes=18),
                service="web",
                endpoint="/search",
                method="GET",
                status_code=504,
                latency_ms=410,
                tags={},
            ),
        ]

        ApiRequest.objects.bulk_create(api_rows + web_rows)

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
    # Tests: params validation
    # ----------------------------
    def test_kpis_params_validation_bad_date_returns_400(self):
        res = self.client.get(self.KPIS_URL, {"start": "not-a-date"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

    def test_top_endpoints_params_validation_bad_sort_returns_400(self):
        res = self.client.get(self.TOP_URL, {"sort_by": "not-a-metric"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

    # ----------------------------
    # Tests: KPI correctness
    # ----------------------------
    def test_kpis_error_rate_correct_and_p95_numeric(self):
        # method=GET forces RAW path (so tests don't depend on caggs existing)
        res = self.client.get(self.KPIS_URL, {"service": "api", "method": "GET"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        j = res.data
        for k in (
            "hits",
            "errors",
            "error_rate",
            "avg_latency_ms",
            "p95_latency_ms",
            "max_latency_ms",
            "source",
        ):
            self.assertIn(k, j)

        # For api + GET:
        # /orders GET = 7 hits (1 error), /health GET = 3 hits (0 error) => hits=10 errors=1
        self.assertEqual(int(j["hits"]), 10)
        self.assertEqual(int(j["errors"]), 1)

        expected = 1.0 / 10.0
        self.assertAlmostEqual(float(j["error_rate"]), expected, places=6)

        # p95 must exist and be numeric for seeded rows
        self.assertIsNotNone(j["p95_latency_ms"])
        self.assertTrue(isinstance(j["p95_latency_ms"], (float, int)))

        # method filter => raw
        self.assertEqual(j["source"], "raw")

    # ----------------------------
    # Tests: Top endpoints sorting + limit
    # ----------------------------
    def test_top_endpoints_sorting_respects_direction_and_limit(self):
        # Desc by hits: expect api:/orders first (GET 7 + POST 2 => 9 total)
        res = self.client.get(self.TOP_URL, {"sort_by": "hits", "direction": "desc", "limit": 2})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        rows = self._as_rows(res.data)
        self.assertEqual(len(rows), 2)

        self.assertEqual(rows[0]["service"], "api")
        self.assertEqual(rows[0]["endpoint"], "/orders")

        # Asc by hits: smallest endpoint should be web:/search (1 hit)
        res2 = self.client.get(self.TOP_URL, {"sort_by": "hits", "direction": "asc", "limit": 1})
        self.assertEqual(res2.status_code, status.HTTP_200_OK, res2.data)

        rows2 = self._as_rows(res2.data)
        self.assertEqual(len(rows2), 1)

        self.assertEqual(rows2[0]["service"], "web")
        self.assertEqual(rows2[0]["endpoint"], "/search")

    # ----------------------------
    # Tests: p95 per endpoint
    # ----------------------------
    def test_top_endpoints_with_p95_returns_numeric_for_at_least_one_row(self):
        res = self.client.get(self.TOP_URL, {"limit": 5, "with_p95": "true"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        rows = self._as_rows(res.data)
        self.assertGreaterEqual(len(rows), 1)

        # Field exists, and at least one row should have numeric p95 (not None)
        self.assertTrue(any(("p95_latency_ms" in r) for r in rows))
        self.assertTrue(
            any(
                (r.get("p95_latency_ms") is not None and isinstance(r.get("p95_latency_ms"), (float, int)))
                for r in rows
            )
        )
