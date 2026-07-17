"""OTLP/HTTP JSON trace ingestion tests (Phase 6)."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from observability.models import ApiRequest, Service, Span
from observability.otlp.ingest import store_spans
from observability.otlp.parser import parse_traces
from tenancy.models import Environment, Organization, Project


def _otlp_payload():
    # Two spans in one trace: an HTTP SERVER span (api) and a CLIENT child (db).
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [{"key": "service.name", "value": {"stringValue": "api"}}]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "abcd1234",
                                "spanId": "1111",
                                "name": "GET /users/{id}",
                                "kind": 2,  # SERVER
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000000120000000",  # +120ms
                                "attributes": [
                                    {"key": "http.request.method", "value": {"stringValue": "GET"}},
                                    {"key": "http.route", "value": {"stringValue": "/users/{id}"}},
                                    {
                                        "key": "http.response.status_code",
                                        "value": {"intValue": "200"},
                                    },
                                ],
                                "status": {"code": 1},  # OK
                            },
                            {
                                "traceId": "abcd1234",
                                "spanId": "2222",
                                "parentSpanId": "1111",
                                "name": "SELECT users",
                                "kind": 3,  # CLIENT
                                "startTimeUnixNano": "1700000000010000000",
                                "endTimeUnixNano": "1700000000050000000",  # +40ms
                                "attributes": [
                                    {"key": "db.system", "value": {"stringValue": "postgresql"}}
                                ],
                                "status": {"code": 2},  # ERROR
                            },
                        ]
                    }
                ],
            }
        ]
    }


class OtlpParserTests(TestCase):
    def test_parse_extracts_semantics(self):
        spans = parse_traces(_otlp_payload())
        self.assertEqual(len(spans), 2)
        server = next(s for s in spans if s["kind"] == "server")
        self.assertEqual(server["service"], "api")
        self.assertEqual(server["http_method"], "GET")
        self.assertEqual(server["http_route"], "/users/{id}")
        self.assertEqual(server["http_status_code"], 200)
        self.assertEqual(server["duration_ms"], 120)
        self.assertEqual(server["status_code"], "ok")

        client = next(s for s in spans if s["kind"] == "client")
        self.assertEqual(client["parent_span_id"], "1111")
        self.assertEqual(client["duration_ms"], 40)
        self.assertEqual(client["status_code"], "error")

    def test_empty_payload(self):
        self.assertEqual(parse_traces({}), [])


class OtlpStoreTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Acme", slug="acme")
        self.project = Project.objects.create(organization=org, name="App", slug="app")
        Environment.objects.create(project=self.project, kind="production")

    def test_store_creates_spans_services_and_analytics(self):
        spans = parse_traces(_otlp_payload())
        result = store_spans(spans, self.project)

        self.assertEqual(result.spans, 2)
        self.assertEqual(Span.objects.count(), 2)
        # One service registered (api).
        self.assertEqual(Service.objects.filter(project=self.project).count(), 1)
        # The HTTP SERVER span becomes an ApiRequest analytics row.
        self.assertEqual(result.analytics_rows, 1)
        req = ApiRequest.objects.get(tags__source="otlp")
        self.assertEqual(req.service, "api")
        self.assertEqual(req.endpoint, "/users/{id}")
        self.assertEqual(req.status_code, 200)
        self.assertEqual(req.latency_ms, 120)
        self.assertEqual(req.project_id, self.project.id)

    def test_spans_are_tenant_scoped(self):
        store_spans(parse_traces(_otlp_payload()), self.project)
        self.assertTrue(all(s.project_id == self.project.id for s in Span.objects.all()))


class OtlpViewTests(TestCase):
    def setUp(self):
        # The backfill migration (0011) already seeds default/default, which the
        # keyless local ingestion fallback resolves to.
        org, _ = Organization.objects.get_or_create(slug="default", defaults={"name": "Default"})
        self.project, _ = Project.objects.get_or_create(
            organization=org, slug="default", defaults={"name": "Default"}
        )

    def test_post_traces_endpoint(self):
        client = APIClient()
        resp = client.post("/v1/traces", _otlp_payload(), format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("partialSuccess", resp.json())
        self.assertEqual(Span.objects.count(), 2)
        self.assertEqual(ApiRequest.objects.filter(tags__source="otlp").count(), 1)
