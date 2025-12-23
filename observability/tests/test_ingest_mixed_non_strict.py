# observability/tests/test_ingest_mixed_non_strict.py
from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from observability.models import ApiRequest
from observability.tests.utils import make_event, make_events, post_ingest


class BulkIngestMixedNonStrictTests(APITestCase):
    INGEST_URL = "/api/requests/ingest/"

    def test_mixed_payload_inserts_valid_rejects_invalid_returns_200(self):
        before = ApiRequest.objects.count()

        valid = make_events(3, trace_id_prefix="ok-")
        invalid_1 = make_event(trace_id="bad-1", status_code=700)  # invalid HTTP status
        invalid_2 = make_event(
            trace_id="bad-2", method="NOPE"
        )  # invalid method (depending on your validation)
        invalid_3 = {"not": "an event"}  # invalid shape

        payload = valid + [invalid_1, invalid_2, invalid_3]

        res = post_ingest(self.client, payload, ingest_url=self.INGEST_URL, strict=False)

        # Non-strict should still be 200 and insert what it can
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        self.assertEqual(res.data["inserted"], 3)
        self.assertEqual(res.data["rejected"], 3)

        # errors should be present and include indexes of the invalid rows
        self.assertTrue(isinstance(res.data.get("errors"), list))
        self.assertGreaterEqual(len(res.data["errors"]), 1)

        # We expect at least one error index in {3,4,5}
        bad_indexes = {e.get("index") for e in res.data["errors"] if isinstance(e, dict)}
        self.assertTrue(any(i in bad_indexes for i in (3, 4, 5)), res.data["errors"])

        after = ApiRequest.objects.count()
        self.assertEqual(after - before, 3)

    def test_mixed_payload_respects_max_errors_cap(self):
        before = ApiRequest.objects.count()

        valid = [make_event(trace_id="ok-1")]
        invalids = [
            make_event(trace_id="bad-1", status_code=700),
            make_event(trace_id="bad-2", status_code=700),
            make_event(trace_id="bad-3", status_code=700),
            make_event(trace_id="bad-4", status_code=700),
        ]
        payload = valid + invalids

        res = post_ingest(self.client, payload, ingest_url=self.INGEST_URL, max_errors=2)

        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["inserted"], 1)
        self.assertEqual(res.data["rejected"], 4)

        # Only 2 detailed errors should be returned
        self.assertEqual(len(res.data.get("errors", [])), 2)

        after = ApiRequest.objects.count()
        self.assertEqual(after - before, 1)
