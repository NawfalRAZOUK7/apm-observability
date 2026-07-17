"""LLM intelligence: provider, AI postmortems, error grouping, NL queries (Phase 13)."""
from __future__ import annotations

import os
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.incidents import generate_ai_postmortem
from notifications.models import Incident, IncidentEvent
from observability.ai import llm
from observability.analytics.issues import group_error_rows, normalize, rebuild_issues
from observability.analytics.nlquery import answer_question, execute, heuristic_parse
from observability.models import ApiRequest, Issue
from tenancy.models import Organization, Project


def _error_request(service="api", endpoint="/checkout", status=500, message="timeout after 30s", when=None):
    return ApiRequest.objects.create(
        time=when or timezone.now(),
        service=service, endpoint=endpoint, method="GET",
        status_code=status, latency_ms=100, tags={"error": message},
    )


class LLMProviderTests(TestCase):
    def test_defaults_to_none_and_unavailable(self):
        os.environ.pop("LLM_PROVIDER", None)
        self.assertEqual(llm.active_provider(), "none")
        self.assertFalse(llm.is_available())
        with self.assertRaises(llm.LLMUnavailable):
            llm.complete("hi")


class AiPostmortemTests(TestCase):
    def _incident(self):
        inc = Incident.objects.create(dedup_key="k", title="DB down", severity="critical")
        IncidentEvent.objects.create(incident=inc, kind="opened", message="opened from TargetDown")
        return inc

    def test_falls_back_to_template_without_llm(self):
        os.environ.pop("LLM_PROVIDER", None)
        md = generate_ai_postmortem(self._incident())
        self.assertIn("# Postmortem", md)
        self.assertIn("## Timeline", md)

    def test_uses_llm_when_available(self):
        inc = self._incident()
        orig_avail, orig_complete = llm.is_available, llm.complete
        llm.is_available = lambda: True
        llm.complete = lambda prompt, system=None, timeout=30.0: "# Postmortem (AI)\n\nDrafted."
        try:
            md = generate_ai_postmortem(inc)
        finally:
            llm.is_available, llm.complete = orig_avail, orig_complete
        self.assertIn("(AI)", md)


class ErrorGroupingTests(TestCase):
    def test_normalize_collapses_volatile_tokens(self):
        self.assertEqual(normalize("Timeout after 30s"), "timeout after Ns")
        self.assertEqual(
            normalize("user 550e8400-e29b-41d4-a716-446655440000 failed"),
            "user <uuid> failed",
        )

    def test_similar_errors_group_together(self):
        rows = [
            _error_request(message="timeout after 30s"),
            _error_request(message="timeout after 45s"),  # same signature after normalize
            _error_request(endpoint="/pay", message="null pointer"),  # different
        ]
        groups = group_error_rows(rows)
        self.assertEqual(len(groups), 2)
        biggest = max(groups.values(), key=lambda g: g["count"])
        self.assertEqual(biggest["count"], 2)

    def test_rebuild_and_endpoint(self):
        _error_request(message="timeout after 1s")
        _error_request(message="timeout after 2s")
        n = rebuild_issues(since=timezone.now() - timedelta(hours=1))
        self.assertEqual(n, 1)
        self.assertEqual(Issue.objects.get().count, 2)

        resp = APIClient().get("/api/issues/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)


class NLQueryTests(TestCase):
    def setUp(self):
        for _ in range(8):
            _error_request(service="checkout")
        for _ in range(2):
            ApiRequest.objects.create(
                time=timezone.now(), service="checkout", endpoint="/checkout",
                method="GET", status_code=200, latency_ms=50,
            )

    def test_heuristic_parse(self):
        p = heuristic_parse("what's the error rate for checkout in the last 6 hours")
        self.assertEqual(p["metric"], "error_rate")
        self.assertEqual(p["service"], "checkout")
        self.assertEqual(p["window_hours"], 6)

    def test_execute_error_rate(self):
        p = {"metric": "error_rate", "service": "checkout", "endpoint": None, "window_hours": 1}
        result = execute(p)
        self.assertEqual(result["sample_size"], 10)
        self.assertEqual(result["value"], 0.8)  # 8 of 10 are 5xx

    def test_answer_endpoint(self):
        os.environ.pop("LLM_PROVIDER", None)
        resp = APIClient().get("/api/nl-query/", {"q": "latency for checkout last 2 hours"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["source"], "heuristic")
        self.assertIn("interpretation", body)

    def test_answer_requires_question(self):
        self.assertEqual(APIClient().get("/api/nl-query/").status_code, 400)
