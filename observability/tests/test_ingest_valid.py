# observability/tests/test_ingest_valid.py
from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from observability.models import ApiRequest
from observability.tests.utils import make_events, post_ingest


class BulkIngestValidTests(APITestCase):
    INGEST_URL = "/api/requests/ingest/"

    def test_bulk_ingest_valid_list_inserts_all(self):
        before = ApiRequest.objects.count()

        payload = make_events(10, trace_id_prefix="valid-")
        res = post_ingest(self.client, payload, ingest_url=self.INGEST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["inserted"], 10)
        self.assertEqual(res.data["rejected"], 0)
        self.assertEqual(res.data.get("errors", []), [])

        after = ApiRequest.objects.count()
        self.assertEqual(after - before, 10)

    def test_bulk_ingest_valid_wrapper_shape_inserts_all(self):
        before = ApiRequest.objects.count()

        payload = {"events": make_events(5, trace_id_prefix="wrap-")}
        res = post_ingest(self.client, payload, ingest_url=self.INGEST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["inserted"], 5)
        self.assertEqual(res.data["rejected"], 0)
        self.assertEqual(res.data.get("errors", []), [])

        after = ApiRequest.objects.count()
        self.assertEqual(after - before, 5)
