# observability/tests.py
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

