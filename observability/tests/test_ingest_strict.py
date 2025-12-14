# observability/tests/test_ingest_strict.py
from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from observability.models import ApiRequest
from observability.tests.utils import make_event, make_events, post_ingest


class BulkIngestStrictModeTests(APITestCase):
    INGEST_URL = "/api/requests/ingest/"

    def test_strict_mode_mixed_invalid_returns_400_inserts_0(self):
        before = ApiRequest.objects.count()

        valid = make_events(2, trace_id_prefix="s-ok-")
        invalid = make_event(trace_id="s-bad-1", status_code=700)  # invalid HTTP status
        payload = valid + [invalid]

        res = post_ingest(self.client, payload, ingest_url=self.INGEST_URL, strict=True)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

        # strict response should indicate nothing inserted
        self.assertEqual(int(res.data.get("inserted", 0)), 0)
        self.assertGreaterEqual(int(res.data.get("rejected", 0)), 1)

        # DB unchanged
        after = ApiRequest.objects.count()
        self.assertEqual(after, before)

    def test_strict_mode_non_dict_item_rejects_all(self):
        before = ApiRequest.objects.count()

        valid = make_event(trace_id="s-ok-x")
        payload = [valid, "oops"]  # invalid item type

        res = post_ingest(self.client, payload, ingest_url=self.INGEST_URL, strict=True)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
        self.assertEqual(int(res.data.get("inserted", 0)), 0)
        self.assertGreaterEqual(int(res.data.get("rejected", 0)), 1)

        # should return at least one error pointing to index 1
        errors = res.data.get("errors", [])
        self.assertTrue(isinstance(errors, list))
        self.assertGreaterEqual(len(errors), 1)
        self.assertEqual(errors[0].get("index"), 1)

        after = ApiRequest.objects.count()
        self.assertEqual(after, before)

    def test_strict_mode_all_valid_still_inserts(self):
        before = ApiRequest.objects.count()

        payload = make_events(3, trace_id_prefix="s-all-ok-")
        res = post_ingest(self.client, payload, ingest_url=self.INGEST_URL, strict=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["inserted"], 3)
        self.assertEqual(res.data["rejected"], 0)

        after = ApiRequest.objects.count()
        self.assertEqual(after - before, 3)
