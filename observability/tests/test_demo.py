"""Demo tooling tests: OTLP payload builder + seed_tenant command."""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from observability.management.commands.demo_e2e import _alert_payload, _otlp_payload
from observability.otlp.ingest import store_spans
from observability.otlp.parser import parse_traces
from tenancy.models import ApiKey, Organization, Project


class DemoPayloadTests(TestCase):
    def test_otlp_payload_parses_and_stores(self):
        payload = _otlp_payload(3)
        spans = parse_traces(payload)
        # 3 traces x (2 frontend + 2 api + 1 postgres) = 15 spans.
        self.assertEqual(len(spans), 15)
        services = {s["service"] for s in spans}
        self.assertEqual(services, {"frontend", "api", "postgres"})

        org = Organization.objects.create(name="Demo", slug="demo")
        project = Project.objects.create(organization=org, name="Demo", slug="demo")
        result = store_spans(spans, project)
        self.assertEqual(result.spans, 15)
        self.assertEqual(result.services, 3)

    def test_alert_payload_shape(self):
        alert = _alert_payload()["alerts"][0]
        self.assertEqual(alert["labels"]["severity"], "critical")
        self.assertIn("runbook_url", alert["annotations"])


class SeedTenantCommandTests(TestCase):
    def test_quiet_prints_only_key(self):
        out = StringIO()
        call_command("seed_tenant", "--quiet", stdout=out)
        key = out.getvalue().strip()
        self.assertTrue(key.startswith("apm_pro_"))
        self.assertIsNotNone(ApiKey.verify(key))

    def test_idempotent_org_project(self):
        call_command("seed_tenant", "--quiet", stdout=StringIO())
        call_command("seed_tenant", "--quiet", stdout=StringIO())
        # Org/project reused; two keys minted.
        self.assertEqual(Organization.objects.filter(slug="demo").count(), 1)
        self.assertEqual(Project.objects.filter(slug="demo").count(), 1)
        self.assertEqual(ApiKey.objects.count(), 2)
