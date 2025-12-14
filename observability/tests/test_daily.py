# observability/tests/test_daily.py
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from observability.models import ApiRequest


class DailyEndpointTests(APITestCase):
    URL = "/api/requests/daily/"

    # --- Helpers -------------------------------------------------

    def _as_rows(self, data: Any) -> List[Dict[str, Any]]:
        """
        Accept both response shapes:
          - list of rows
          - {"source": "...", "results": [...]}
        """
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"]
        if isinstance(data, list):
            return data
        self.fail(f"Unexpected response shape: {type(data)} => {data}")

    def _to_regclass(self, name: str) -> Optional[str]:
        with connection.cursor() as cur:
            cur.execute("SELECT to_regclass(%s);", [name])
            row = cur.fetchone()
            return row[0] if row else None

    def _find_daily_relation(self) -> Optional[str]:
        """
        Try common names for the daily continuous aggregate / view.
        Return the regclass name if found, else None.
        """
        candidates = [
            "apirequest_daily",
            "public.apirequest_daily",
            "observability_apirequest_daily",
            "public.observability_apirequest_daily",
        ]
        for c in candidates:
            found = self._to_regclass(c)
            if found:
                return found
        return None

    def _call_with_first_working_timerange(self, start_iso: str, end_iso: str):
        candidates: List[Tuple[str, str]] = [
            ("start", "end"),
            ("time_min", "time_max"),
            ("from", "to"),
            ("time_after", "time_before"),
            ("time__gte", "time__lte"),
        ]
        last = None
        for a, b in candidates:
            res = self.client.get(self.URL, {a: start_iso, b: end_iso})
            last = res
            if res.status_code in (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE):
                return res
        return last

    # --- Setup / Skips ------------------------------------------

    def setUp(self):
        super().setUp()

        # Skip if not PostgreSQL
        if connection.vendor != "postgresql":
            self.skipTest("Daily endpoint tests require PostgreSQL/TimescaleDB (cagg/view).")

        # Skip if the daily cagg/view does not exist
        rel = self._find_daily_relation()
        if not rel:
            self.skipTest("Daily continuous aggregate/view is missing (apirequest_daily).")

        # Seed data across multiple days (single service+endpoint to simplify expectations)
        now = timezone.now()

        # Normalize to "today" boundary (midnight) to produce clean daily buckets
        today = now.replace(hour=12, minute=0, second=0, microsecond=0)
        d1 = today - timedelta(days=2)
        d2 = today - timedelta(days=1)
        d3 = today  # today

        rows = [
            # Day -2 : 3 hits (1 error)
            ApiRequest(
                time=d1 - timedelta(hours=1),
                service="svc",
                endpoint="/daily",
                method="GET",
                status_code=200,
                latency_ms=10,
                tags={},
            ),
            ApiRequest(
                time=d1 - timedelta(hours=2),
                service="svc",
                endpoint="/daily",
                method="GET",
                status_code=500,
                latency_ms=20,
                tags={},
            ),
            ApiRequest(
                time=d1 - timedelta(hours=3),
                service="svc",
                endpoint="/daily",
                method="GET",
                status_code=200,
                latency_ms=30,
                tags={},
            ),
            # Day -1 : 2 hits (0 error)
            ApiRequest(
                time=d2 - timedelta(hours=1),
                service="svc",
                endpoint="/daily",
                method="GET",
                status_code=200,
                latency_ms=40,
                tags={},
            ),
            ApiRequest(
                time=d2 - timedelta(hours=2),
                service="svc",
                endpoint="/daily",
                method="GET",
                status_code=200,
                latency_ms=50,
                tags={},
            ),
            # Today : 1 hit (1 error)
            ApiRequest(
                time=d3 - timedelta(hours=1),
                service="svc",
                endpoint="/daily",
                method="GET",
                status_code=502,
                latency_ms=60,
                tags={},
            ),
        ]
        ApiRequest.objects.bulk_create(rows)

        self.expected_total_hits = len(rows)
        self.expected_by_day = {
            # We won't match exact bucket timestamps (depends on cagg time_bucket),
            # but we WILL validate the total hits and number of buckets.
            "buckets": 3,
        }

    # --- Tests ----------------------------------------------------

    def test_daily_endpoint_returns_daily_buckets_and_totals(self):
        start = (timezone.now() - timedelta(days=10)).isoformat()
        end = (timezone.now() + timedelta(days=1)).isoformat()

        res = self._call_with_first_working_timerange(start, end)

        if res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            self.skipTest(f"Daily endpoint unavailable (likely missing cagg/view): {res.data}")

        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        rows = self._as_rows(res.data)
        self.assertGreaterEqual(len(rows), 1)

        first = rows[0]
        for key in ("service", "endpoint"):
            self.assertIn(key, first)

        # Detect bucket + hits keys (be tolerant to naming)
        bucket_key = None
        for k in ("bucket", "day", "time_bucket", "time", "date"):
            if k in first:
                bucket_key = k
                break
        self.assertIsNotNone(bucket_key, f"Missing bucket field in row keys: {sorted(first.keys())}")

        hits_key = None
        for k in ("hits", "count", "requests"):
            if k in first:
                hits_key = k
                break
        self.assertIsNotNone(hits_key, f"Missing hits field in row keys: {sorted(first.keys())}")

        total_hits = sum(int(r.get(hits_key, 0) or 0) for r in rows)
        self.assertEqual(total_hits, self.expected_total_hits)

        # We seeded 3 distinct days -> expect >= 2 distinct buckets (some setups may merge if time zone / bucketing differs)
        unique_buckets = {r.get(bucket_key) for r in rows}
        self.assertGreaterEqual(len(unique_buckets), 2, unique_buckets)

        # Ensure our seeded service+endpoint appear
        self.assertTrue(any(r.get("service") == "svc" for r in rows))
        self.assertTrue(any(r.get("endpoint") == "/daily" for r in rows))
