"""Dashboard page is served (Phase 12)."""
from django.test import TestCase


class DashboardTests(TestCase):
    def test_dashboard_served(self):
        resp = self.client.get("/dashboard/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("APM Observability", body)
        # Sanity: the tabs and API calls the UI relies on are present.
        for marker in ["/api/service-map/", "/sink/incidents/", "/api/anomalies/", "/api/traces/"]:
            self.assertIn(marker, body)
