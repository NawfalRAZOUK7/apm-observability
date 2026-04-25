# observability/tests/test_crud.py
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from observability.models import ApiRequest
from observability.tests.utils import make_event


class ApiRequestCrudTests(APITestCase):
    LIST_URL = "/api/requests/"

    def test_post_create_then_get_detail(self):
        payload = make_event(
            time=timezone.now().isoformat(),
            service="svc-a",
            endpoint="/ping",
            method="GET",
            status_code=200,
            latency_ms=12,
            trace_id="trace-create",
            user_ref="u1",
            tags={"env": "test"},
        )

        res = self.client.post(self.LIST_URL, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        created_id = res.data.get("id")
        self.assertIsNotNone(created_id)

        # GET detail
        detail_url = f"{self.LIST_URL}{created_id}/"
        res2 = self.client.get(detail_url)
        self.assertEqual(res2.status_code, status.HTTP_200_OK, res2.data)

        self.assertEqual(res2.data["id"], created_id)
        self.assertEqual(res2.data["service"], "svc-a")
        self.assertEqual(res2.data["endpoint"], "/ping")
        self.assertEqual(res2.data["method"], "GET")
        self.assertEqual(int(res2.data["status_code"]), 200)
        self.assertEqual(int(res2.data["latency_ms"]), 12)
        self.assertEqual(res2.data.get("trace_id"), "trace-create")
        self.assertEqual(res2.data.get("user_ref"), "u1")

    def test_get_list_default_ordering_is_time_desc(self):
        """
        Acceptance: GET /api/requests/ lists ordered by -time (newest first).
        """
        now = timezone.now()

        # Create 3 records with known times: oldest, middle, newest
        a = ApiRequest.objects.create(
            time=now - timedelta(minutes=30),
            service="svc",
            endpoint="/a",
            method="GET",
            status_code=200,
            latency_ms=10,
            tags={},
        )
        b = ApiRequest.objects.create(
            time=now - timedelta(minutes=20),
            service="svc",
            endpoint="/b",
            method="GET",
            status_code=200,
            latency_ms=20,
            tags={},
        )
        c = ApiRequest.objects.create(
            time=now - timedelta(minutes=10),
            service="svc",
            endpoint="/c",
            method="GET",
            status_code=200,
            latency_ms=30,
            tags={},
        )

        res = self.client.get(self.LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        # DRF can return paginated shape or raw list depending on your config.
        data = res.data
        if isinstance(data, dict) and "results" in data:
            rows = data["results"]
        else:
            rows = data

        self.assertGreaterEqual(len(rows), 3)

        # First three should be newest-first: c, b, a
        self.assertEqual(rows[0]["id"], c.id)
        self.assertEqual(rows[1]["id"], b.id)
        self.assertEqual(rows[2]["id"], a.id)

    def test_patch_updates_fields(self):
        obj = ApiRequest.objects.create(
            time=timezone.now(),
            service="svc",
            endpoint="/old",
            method="GET",
            status_code=200,
            latency_ms=50,
            tags={"k": "v"},
        )
        url = f"{self.LIST_URL}{obj.id}/"

        patch = {
            "endpoint": "/new",
            "status_code": 503,
            "latency_ms": 999,
        }
        res = self.client.patch(url, data=patch, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        obj.refresh_from_db()
        self.assertEqual(obj.endpoint, "/new")
        self.assertEqual(obj.status_code, 503)
        self.assertEqual(obj.latency_ms, 999)

    def test_put_replaces_resource(self):
        obj = ApiRequest.objects.create(
            time=timezone.now(),
            service="svc",
            endpoint="/before",
            method="GET",
            status_code=200,
            latency_ms=10,
            tags={},
        )
        url = f"{self.LIST_URL}{obj.id}/"

        # PUT requires full payload for your serializer
        payload = make_event(
            time=timezone.now().isoformat(),
            service="svc-put",
            endpoint="/after",
            method="POST",
            status_code=201,
            latency_ms=77,
            trace_id="trace-put",
            user_ref="u-put",
            tags={"x": 1},
        )

        res = self.client.put(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        obj.refresh_from_db()
        self.assertEqual(obj.service, "svc-put")
        self.assertEqual(obj.endpoint, "/after")
        self.assertEqual(obj.method, "POST")
        self.assertEqual(obj.status_code, 201)
        self.assertEqual(obj.latency_ms, 77)
        self.assertEqual(obj.trace_id, "trace-put")
        self.assertEqual(obj.user_ref, "u-put")

    def test_delete_removes_resource(self):
        obj = ApiRequest.objects.create(
            time=timezone.now(),
            service="svc",
            endpoint="/to-delete",
            method="GET",
            status_code=200,
            latency_ms=1,
            tags={},
        )
        url = f"{self.LIST_URL}{obj.id}/"

        res = self.client.delete(url)
        self.assertIn(res.status_code, (status.HTTP_204_NO_CONTENT, status.HTTP_200_OK), res.data)

        self.assertFalse(ApiRequest.objects.filter(id=obj.id).exists())
