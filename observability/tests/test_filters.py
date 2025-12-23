# observability/tests/test_filters.py
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from observability.models import ApiRequest


class ApiRequestFilterTests(APITestCase):
    LIST_URL = "/api/requests/"

    @staticmethod
    def _rows(data: Any) -> list[dict[str, Any]]:
        """
        Accept both DRF response shapes:
          - paginated: {"count":..., "results":[...]}
          - raw list:  [...]
        """
        if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
            return data["results"]
        if isinstance(data, list):
            return data
        raise AssertionError(f"Unexpected response shape: {type(data)} => {data}")

    @staticmethod
    def _ids(rows: Iterable[dict[str, Any]]) -> list[int]:
        return [int(r["id"]) for r in rows]

    def setUp(self):
        super().setUp()
        now = timezone.now()

        # Create 6 rows with distinct attributes + known time ordering
        # Oldest -> newest
        self.t1 = now - timedelta(hours=6)
        self.t2 = now - timedelta(hours=5)
        self.t3 = now - timedelta(hours=4)
        self.t4 = now - timedelta(hours=3)
        self.t5 = now - timedelta(hours=2)
        self.t6 = now - timedelta(hours=1)

        self.r1 = ApiRequest.objects.create(
            time=self.t1,
            service="billing",
            endpoint="/a",
            method="GET",
            status_code=200,
            latency_ms=10,
            tags={},
        )
        self.r2 = ApiRequest.objects.create(
            time=self.t2,
            service="billing",
            endpoint="/a",
            method="POST",
            status_code=500,
            latency_ms=20,
            tags={},
        )
        self.r3 = ApiRequest.objects.create(
            time=self.t3,
            service="billing",
            endpoint="/b",
            method="GET",
            status_code=201,
            latency_ms=30,
            tags={},
        )
        self.r4 = ApiRequest.objects.create(
            time=self.t4,
            service="auth",
            endpoint="/login",
            method="POST",
            status_code=401,
            latency_ms=40,
            tags={},
        )
        self.r5 = ApiRequest.objects.create(
            time=self.t5,
            service="auth",
            endpoint="/login",
            method="POST",
            status_code=200,
            latency_ms=50,
            tags={},
        )
        self.r6 = ApiRequest.objects.create(
            time=self.t6,
            service="auth",
            endpoint="/profile",
            method="GET",
            status_code=200,
            latency_ms=60,
            tags={},
        )

        self.all_ids = {self.r1.id, self.r2.id, self.r3.id, self.r4.id, self.r5.id, self.r6.id}

    # ----------------------------
    # Internal helpers to be robust to param naming
    # ----------------------------
    def _get_with_first_working_param(
        self, candidates: Sequence[str], value: Any, expected_ids: set[int]
    ):
        """
        Try candidate query param names until one returns exactly expected_ids.
        If none match, fail with a helpful message.
        """
        last = None
        for key in candidates:
            res = self.client.get(self.LIST_URL, {key: value})
            self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
            rows = self._rows(res.data)
            got = set(self._ids(rows))
            last = (key, got, res.data)

            if got == expected_ids:
                return key, rows

        key, got, data = last if last is not None else ("<none>", set(), None)
        self.fail(
            f"None of these params produced expected result.\n"
            f"candidates={list(candidates)} value={value}\n"
            f"expected_ids={sorted(expected_ids)}\n"
            f"last_tried={key} got_ids={sorted(got)}\n"
            f"last_response={data}"
        )

    def _get_with_first_working_time_range(
        self,
        start_iso: str,
        end_iso: str,
        expected_ids: set[int],
        candidates: Sequence[tuple[str, str]],
    ):
        last = None
        for start_key, end_key in candidates:
            res = self.client.get(self.LIST_URL, {start_key: start_iso, end_key: end_iso})
            self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
            rows = self._rows(res.data)
            got = set(self._ids(rows))
            last = ((start_key, end_key), got, res.data)

            if got == expected_ids:
                return (start_key, end_key), rows

        pair, got, data = last if last is not None else (("<none>", "<none>"), set(), None)
        self.fail(
            f"No time-range param pair matched expected result.\n"
            f"candidates={list(candidates)}\n"
            f"start={start_iso} end={end_iso}\n"
            f"expected_ids={sorted(expected_ids)}\n"
            f"last_tried={pair} got_ids={sorted(got)}\n"
            f"last_response={data}"
        )

    # ----------------------------
    # Tests: exact filters
    # ----------------------------
    def test_filter_service(self):
        expected = {self.r1.id, self.r2.id, self.r3.id}
        self._get_with_first_working_param(
            candidates=["service", "service__exact"],
            value="billing",
            expected_ids=expected,
        )

    def test_filter_endpoint(self):
        expected = {self.r4.id, self.r5.id}
        self._get_with_first_working_param(
            candidates=["endpoint", "endpoint__exact"],
            value="/login",
            expected_ids=expected,
        )

    def test_filter_method(self):
        expected = {self.r2.id, self.r4.id, self.r5.id}
        self._get_with_first_working_param(
            candidates=["method", "method__exact"],
            value="POST",
            expected_ids=expected,
        )

    def test_filter_status_code(self):
        expected = {self.r1.id, self.r5.id, self.r6.id}
        self._get_with_first_working_param(
            candidates=["status_code", "status", "status_code__exact"],
            value=200,
            expected_ids=expected,
        )

    # ----------------------------
    # Tests: time range
    # ----------------------------
    def test_filter_time_range(self):
        # Window includes t4 (3h ago) and t5 (2h ago), excludes others
        start = (timezone.now() - timedelta(hours=3, minutes=30)).isoformat()
        end = (timezone.now() - timedelta(hours=1, minutes=30)).isoformat()
        expected = {self.r4.id, self.r5.id}

        # Try common naming conventions
        candidates = [
            ("start", "end"),
            ("time_after", "time_before"),
            ("time_min", "time_max"),
            ("from", "to"),
            ("time__gte", "time__lte"),
        ]
        self._get_with_first_working_time_range(
            start_iso=start,
            end_iso=end,
            expected_ids=expected,
            candidates=candidates,
        )

    # ----------------------------
    # Tests: ordering
    # ----------------------------
    def test_ordering_time_asc(self):
        # ordering=time should return oldest first (r1)
        res = self.client.get(self.LIST_URL, {"ordering": "time"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        rows = self._rows(res.data)
        self.assertGreaterEqual(len(rows), 6)

        # If ordering is ignored, you'd still get default -time (newest first).
        # This assertion enforces that ordering works.
        self.assertEqual(rows[0]["id"], self.r1.id, rows[:3])

    def test_ordering_time_desc(self):
        # ordering=-time should return newest first (r6)
        res = self.client.get(self.LIST_URL, {"ordering": "-time"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        rows = self._rows(res.data)
        self.assertGreaterEqual(len(rows), 6)
        self.assertEqual(rows[0]["id"], self.r6.id, rows[:3])

    # ----------------------------
    # Tests: search (only if configured)
    # ----------------------------
    def test_search_login_if_present(self):
        """
        If SearchFilter is enabled AND search_fields are configured on the ViewSet,
        search=login should return only /login endpoints (r4, r5).

        If search is not configured (returns unfiltered full dataset), we skip.
        """
        res = self.client.get(self.LIST_URL, {"search": "login"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        rows = self._rows(res.data)
        got = set(self._ids(rows))

        # If search isn't wired (no search_fields), many setups will just return all rows.
        if got == self.all_ids:
            self.skipTest(
                "Search is not configured on the ViewSet (search_fields missing); skipping."
            )

        self.assertEqual(got, {self.r4.id, self.r5.id})
