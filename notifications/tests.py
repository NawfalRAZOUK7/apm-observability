# notifications/tests.py
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from . import providers
from .incidents import incident_metrics
from .models import Incident, Notification
from .providers import SEVERITY_POLICY, dispatch
from .views import AlertmanagerWebhookView

User = get_user_model()


class _RecordingProvider(providers.BaseProvider):
    name = "recording"

    def __init__(self):
        self.sent: list = []

    def send(self, notification):
        self.sent.append(notification.alertname)


class _FailingProvider(providers.BaseProvider):
    name = "failing"

    def send(self, notification):
        raise OSError("channel unreachable")


class SeverityPolicyTests(TestCase):
    def test_info_is_dashboard_only(self):
        n = Notification(severity="info", alertname="Noise")
        dispatch(n)
        self.assertEqual(n.channels, [])
        self.assertTrue(n.delivered)
        self.assertEqual(n.delivery_error, "")

    def test_critical_routes_to_pager_and_chat(self):
        chat, pager = _RecordingProvider(), _RecordingProvider()
        self.settings()  # no-op, keep symmetry
        orig_chat, orig_pager = providers.get_chat_provider, providers.get_pager_provider
        providers.get_chat_provider = lambda: chat
        providers.get_pager_provider = lambda: pager
        try:
            n = Notification(severity="critical", alertname="TargetDown")
            dispatch(n)
        finally:
            providers.get_chat_provider, providers.get_pager_provider = orig_chat, orig_pager
        self.assertEqual(set(n.channels), {"pager", "chat"})
        self.assertEqual(chat.sent, ["TargetDown"])
        self.assertEqual(pager.sent, ["TargetDown"])
        self.assertTrue(n.delivered)

    def test_delivery_failure_is_recorded(self):
        orig_chat = providers.get_chat_provider
        providers.get_chat_provider = lambda: _FailingProvider()
        try:
            n = Notification(severity="warning", alertname="HighErrorRate")
            dispatch(n)
        finally:
            providers.get_chat_provider = orig_chat
        self.assertFalse(n.delivered)
        self.assertIn("channel unreachable", n.delivery_error)

    def test_policy_covers_all_severities(self):
        for sev in ("critical", "warning", "info", "unknown"):
            self.assertIn(sev, SEVERITY_POLICY)


class WebhookViewTests(TestCase):
    def _payload(self):
        return {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "fingerprint": "abc123",
                    "labels": {"alertname": "TargetDown", "severity": "critical"},
                    "annotations": {
                        "summary": "Target db is down",
                        "runbook_url": "https://runbooks.example/targetdown",
                    },
                    "startsAt": "2026-07-14T10:00:00Z",
                },
                {
                    "status": "resolved",
                    "fingerprint": "def456",
                    "labels": {"alertname": "HighErrorRate", "severity": "warning"},
                    "annotations": {"summary": "5xx back to normal"},
                    "startsAt": "2026-07-14T09:00:00Z",
                    "endsAt": "2026-07-14T10:05:00Z",
                },
            ],
        }

    def test_webhook_stores_and_routes(self):
        # Default providers are console (no network) -> safe in tests.
        request = APIRequestFactory().post("/sink/notify", self._payload(), format="json")
        response = AlertmanagerWebhookView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Notification.objects.count(), 2)

        critical = Notification.objects.get(alertname="TargetDown")
        self.assertEqual(critical.severity, "critical")
        self.assertEqual(critical.status, "firing")
        self.assertEqual(critical.runbook_url, "https://runbooks.example/targetdown")
        self.assertEqual(set(critical.channels), {"pager", "chat"})
        self.assertIsNotNone(critical.starts_at)

        resolved = Notification.objects.get(alertname="HighErrorRate")
        self.assertEqual(resolved.status, "resolved")
        self.assertTrue(resolved.delivered)  # resolved is recorded, not re-paged
        self.assertIsNotNone(resolved.ends_at)

    def test_unknown_severity_is_normalized(self):
        payload = {
            "alerts": [{"status": "firing", "labels": {"alertname": "Weird", "severity": "bogus"}}]
        }
        request = APIRequestFactory().post("/sink/notify", payload, format="json")
        response = AlertmanagerWebhookView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Notification.objects.get(alertname="Weird").severity, "unknown")


class IncidentWorkflowTests(TestCase):
    def _post(self, status_, severity, alertname="TargetDown", fingerprint="fp1"):
        payload = {
            "alerts": [
                {
                    "status": status_,
                    "fingerprint": fingerprint,
                    "labels": {"alertname": alertname, "severity": severity},
                    "annotations": {
                        "summary": f"{alertname} summary",
                        "runbook_url": "https://runbooks.example/x",
                    },
                }
            ]
        }
        request = APIRequestFactory().post("/sink/notify", payload, format="json")
        return AlertmanagerWebhookView.as_view()(request)

    def test_firing_opens_incident_with_timeline(self):
        self._post("firing", "critical")
        incident = Incident.objects.get()
        self.assertEqual(incident.status, Incident.Status.OPEN)
        self.assertEqual(incident.runbook_url, "https://runbooks.example/x")
        self.assertTrue(incident.events.filter(kind="opened").exists())

    def test_refire_does_not_duplicate(self):
        self._post("firing", "critical")
        self._post("firing", "critical")
        self.assertEqual(Incident.objects.count(), 1)
        incident = Incident.objects.get()
        self.assertTrue(incident.events.filter(kind="notification").exists())

    def test_resolved_alert_resolves_incident(self):
        self._post("firing", "critical")
        self._post("resolved", "critical")
        incident = Incident.objects.get()
        self.assertEqual(incident.status, Incident.Status.RESOLVED)
        self.assertIsNotNone(incident.resolved_at)
        self.assertIsNotNone(incident.mttr_seconds)

    def test_info_does_not_open_incident(self):
        self._post("firing", "info", alertname="Noise", fingerprint="fp-info")
        self.assertEqual(Incident.objects.count(), 0)

    def test_ack_and_resolve_endpoints_and_metrics(self):
        self._post("firing", "critical")
        incident = Incident.objects.get()
        client = APIClientLite()

        ack = client.post(f"/sink/incidents/{incident.id}/ack/")
        self.assertEqual(ack.status_code, 200)
        incident.refresh_from_db()
        self.assertIsNotNone(incident.acknowledged_at)
        self.assertEqual(incident.status, Incident.Status.ACKNOWLEDGED)

        res = client.post(f"/sink/incidents/{incident.id}/resolve/")
        self.assertEqual(res.status_code, 200)

        metrics = incident_metrics()
        self.assertEqual(metrics["resolved"], 1)
        self.assertIsNotNone(metrics["mtta_seconds_avg"])

    def test_postmortem_markdown(self):
        self._post("firing", "critical")
        incident = Incident.objects.get()
        resp = APIClientLite().get(f"/sink/incidents/{incident.id}/postmortem/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("# Postmortem", resp.content.decode())
        self.assertIn("## Timeline", resp.content.decode())


# Small wrapper so incident tests use the URL router (exercises urls + views).
from rest_framework.test import APIClient as APIClientLite  # noqa: E402
