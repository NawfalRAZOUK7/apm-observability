# alerting/tests.py
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.models import Incident, Notification
from observability.models import ApiRequest
from tenancy.models import Environment, Membership, Organization, Project, Role

from .evaluator import evaluate_all, evaluate_rule
from .models import AlertRule

User = get_user_model()


def make_project(slug="acme"):
    org = Organization.objects.create(name=slug.title(), slug=slug)
    project = Project.objects.create(organization=org, name=slug.title(), slug="app")
    Environment.objects.create(project=project, kind="production")
    return org, project


def add_requests(project, *, n, n_errors, latency=100, minutes_ago=1, service="api", endpoint="/x"):
    when = timezone.now() - timedelta(minutes=minutes_ago)
    rows = [
        ApiRequest(
            time=when,
            service=service,
            endpoint=endpoint,
            method="GET",
            status_code=500 if i < n_errors else 200,
            latency_ms=latency,
            project=project,
        )
        for i in range(n)
    ]
    ApiRequest.objects.bulk_create(rows)


class ThresholdRuleTests(TestCase):
    def setUp(self):
        _org, self.project = make_project()
        self.rule = AlertRule.objects.create(
            project=self.project,
            name="High error rate",
            kind=AlertRule.Kind.THRESHOLD,
            metric=AlertRule.Metric.ERROR_RATE,
            comparator=AlertRule.Comparator.GT,
            threshold=0.10,
            window_minutes=10,
            severity=AlertRule.Severity.CRITICAL,
        )

    def test_fires_and_opens_incident_on_transition(self):
        add_requests(self.project, n=10, n_errors=5)  # 50% error rate
        result = evaluate_rule(self.rule)
        self.assertTrue(result["firing"])
        self.assertTrue(result["transitioned"])
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.state, AlertRule.State.FIRING)
        # A firing notification was emitted and an incident opened.
        self.assertEqual(Notification.objects.filter(status="firing").count(), 1)
        self.assertEqual(Incident.objects.filter(status=Incident.Status.OPEN).count(), 1)

    def test_no_duplicate_notification_while_firing(self):
        add_requests(self.project, n=10, n_errors=5)
        evaluate_rule(self.rule)
        evaluate_rule(self.rule)  # still firing -> no transition
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Incident.objects.count(), 1)

    def test_resolves_when_metric_recovers(self):
        add_requests(self.project, n=10, n_errors=5)
        evaluate_rule(self.rule)
        # New window with healthy traffic; old error rows fall outside window.
        ApiRequest.objects.all().delete()
        add_requests(self.project, n=10, n_errors=0)
        result = evaluate_rule(self.rule)
        self.assertFalse(result["firing"])
        self.assertTrue(result["transitioned"])
        incident = Incident.objects.get()
        self.assertEqual(incident.status, Incident.Status.RESOLVED)
        self.assertEqual(Notification.objects.filter(status="resolved").count(), 1)

    def test_evaluate_all_skips_disabled(self):
        self.rule.enabled = False
        self.rule.save(update_fields=["enabled"])
        add_requests(self.project, n=10, n_errors=5)
        self.assertEqual(evaluate_all(), [])


class AnomalyRuleTests(TestCase):
    def setUp(self):
        _org, self.project = make_project(slug="beta")
        self.rule = AlertRule.objects.create(
            project=self.project,
            name="Latency anomaly",
            kind=AlertRule.Kind.ANOMALY,
            metric=AlertRule.Metric.LATENCY_AVG,
            z_threshold=3.0,
            severity=AlertRule.Severity.WARNING,
        )

    def _bucket(self, hours_ago, latency):
        when = (timezone.now() - timedelta(hours=hours_ago)).replace(
            minute=0, second=0, microsecond=0
        )
        ApiRequest.objects.bulk_create(
            [
                ApiRequest(
                    time=when,
                    service="api",
                    endpoint="/x",
                    method="GET",
                    status_code=200,
                    latency_ms=latency,
                    project=self.project,
                )
                for _ in range(5)
            ]
        )

    def test_anomaly_fires_on_latency_spike(self):
        for h, lat in [(6, 100), (5, 101), (4, 99), (3, 100), (2, 102)]:
            self._bucket(h, lat)
        self._bucket(0, 1000)  # spike in the latest bucket
        result = evaluate_rule(self.rule)
        self.assertTrue(result["firing"])
        self.assertEqual(Notification.objects.filter(status="firing").count(), 1)


class AlertRuleApiTests(TestCase):
    def setUp(self):
        self.org, self.project = make_project(slug="gamma")
        self.client = APIClient()

    def _login(self, role):
        user = User.objects.create_user(username=f"u_{role}", password="x")
        Membership.objects.create(user=user, organization=self.org, role=role)
        self.client.force_authenticate(user=user)
        return user

    def _payload(self):
        return {
            "project": self.project.id,
            "name": "err rule",
            "kind": "threshold",
            "metric": "error_rate",
            "comparator": "gt",
            "threshold": 0.05,
            "severity": "warning",
        }

    def test_viewer_cannot_create_developer_can(self):
        self._login(Role.VIEWER)
        self.assertEqual(
            self.client.post("/api/alerting/rules/", self._payload(), format="json").status_code,
            403,
        )

        self.client.force_authenticate(None)
        self._login(Role.DEVELOPER)
        resp = self.client.post("/api/alerting/rules/", self._payload(), format="json")
        self.assertEqual(resp.status_code, 201)

    def test_rules_scoped_to_visible_projects(self):
        # A rule in another org the user cannot see.
        _o, other = make_project(slug="delta")
        AlertRule.objects.create(project=other, name="hidden", threshold=1)
        AlertRule.objects.create(project=self.project, name="visible", threshold=1)

        self._login(Role.VIEWER)
        resp = self.client.get("/api/alerting/rules/")
        self.assertEqual(resp.status_code, 200)
        names = {r["name"] for r in resp.json()["results"]}
        self.assertEqual(names, {"visible"})
