from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase


class HealthEndpointTests(APITestCase):
    URL = "/api/health/"

    def test_health_without_db_check_returns_ok(self):
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data, {"status": "ok"})

    def test_health_with_db_check_returns_ok(self):
        res = self.client.get(self.URL, {"db": "1"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data, {"status": "ok", "db": "ok"})
