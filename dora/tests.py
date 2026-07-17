# dora/tests.py
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.models import Incident

from .metrics import compute_dora
from .models import Deployment


def _deploy(when, status=Deployment.Status.SUCCESS, lead_hours=2, caused_incident=False):
    return Deployment.objects.create(
        environment="production",
        version="v1",
        status=status,
        caused_incident=caused_incident,
        committed_at=when - timedelta(hours=lead_hours),
        deployed_at=when,
    )


class DoraMetricsTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        # 5 successful + 1 failed over the last week.
        for i in range(5):
            _deploy(self.now - timedelta(days=i))
        _deploy(self.now - timedelta(days=1), status=Deployment.Status.ROLLED_BACK)

    def _compute(self):
        return compute_dora(self.now - timedelta(days=7), self.now + timedelta(minutes=1))

    def test_frequency_and_cfr(self):
        m = self._compute()
        self.assertEqual(m["deployment_frequency"]["total_successful"], 5)
        self.assertEqual(m["change_failure_rate"]["failures"], 1)
        self.assertEqual(m["change_failure_rate"]["total"], 6)
        self.assertAlmostEqual(m["change_failure_rate"]["rate"], round(1 / 6, 4))

    def test_lead_time_present(self):
        m = self._compute()
        # committed 2h before deploy => median lead ~7200s.
        self.assertAlmostEqual(m["lead_time_for_changes"]["median_seconds"], 7200.0, delta=1)
        self.assertEqual(m["lead_time_for_changes"]["band"], "Elite")  # < 1 day

    def test_mttr_from_incidents(self):
        inc = Incident.objects.create(dedup_key="k", title="down", severity="critical")
        inc.opened_at = self.now - timedelta(hours=3)
        inc.resolved_at = self.now - timedelta(hours=2)  # 1h MTTR
        inc.status = Incident.Status.RESOLVED
        inc.save()
        m = self._compute()
        self.assertAlmostEqual(m["time_to_recovery"]["mttr_seconds_avg"], 3600.0, delta=5)

    def test_bands_present(self):
        m = self._compute()
        for key in (
            "deployment_frequency",
            "lead_time_for_changes",
            "change_failure_rate",
            "time_to_recovery",
        ):
            self.assertIn(m[key]["band"], {"Elite", "High", "Medium", "Low", "unknown"})


class DoraApiTests(TestCase):
    def test_record_and_metrics_endpoints(self):
        client = APIClient()
        resp = client.post(
            "/api/dora/deployments/",
            {"environment": "production", "version": "v1.2.3", "status": "success"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Deployment.objects.count(), 1)

        metrics = client.get("/api/dora/metrics/")
        self.assertEqual(metrics.status_code, 200)
        self.assertIn("deployment_frequency", metrics.json())
        self.assertIn("change_failure_rate", metrics.json())
