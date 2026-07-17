# observability/management/commands/demo_e2e.py
"""End-to-end feature demo for Phases 4-9.

Seeds a demo tenant + ingestion API key, sends sample OTLP traces to /v1/traces
(exercising span storage, service auto-registration, and the service map), then
fires a test Alertmanager webhook at /sink/notify (exercising the notification
sink and incident workflow). Prints the feature URLs at the end.

Runs against the live server over HTTP so it is a true end-to-end path. Intended
to be invoked inside the web container (localhost:8000) via `make demo-features`.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand

from tenancy.models import ApiKey, Environment, Organization, Project


def _post(url: str, payload: dict, headers: dict | None = None) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    # We talk to Gunicorn directly on the loopback, bypassing the TLS-terminating
    # nginx in front of it. With DJANGO_SECURE_SSL_REDIRECT=1 (the .env.docker
    # default) Django would 301 these POSTs to https:// on the same port, where
    # nothing speaks TLS -- the request then hangs until the handshake times out.
    # Presenting the same X-Forwarded-Proto that nginx sets satisfies
    # SECURE_PROXY_SSL_HEADER, so the request is treated as already-secure.
    req.add_header("X-Forwarded-Proto", "https")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "ignore")


def _otlp_payload(n_traces: int) -> dict:
    """Build an OTLP/HTTP JSON payload: frontend -> api -> postgres, now-ish,
    with a share of errors and a latency spike so the service map lights up."""
    now_ns = time.time_ns()
    resource_spans = []
    for i in range(n_traces):
        trace_id = f"{i:032x}"
        base = now_ns - (i * 1_000_000_000)  # stagger traces over recent seconds
        is_error = i % 7 == 0
        slow = 400 if i % 5 == 0 else 90  # occasional slow request (ms)

        def span(
            service,
            span_id,
            parent,
            kind,
            name,
            dur_ms,
            attrs=None,
            err=False,
            base=base,
            trace_id=trace_id,
        ):
            start = base
            end = base + dur_ms * 1_000_000
            s = {
                "traceId": trace_id,
                "spanId": span_id,
                "name": name,
                "kind": kind,
                "startTimeUnixNano": str(start),
                "endTimeUnixNano": str(end),
                "attributes": attrs or [],
                "status": {"code": 2 if err else 1},
            }
            if parent:
                s["parentSpanId"] = parent
            return service, s

        def res(service, spans):
            return {
                "resource": {
                    "attributes": [{"key": "service.name", "value": {"stringValue": service}}]
                },
                "scopeSpans": [{"spans": [s for _, s in spans]}],
            }

        frontend = [
            span(
                "frontend",
                "f1",
                "",
                2,
                "GET /",
                slow + 60,
                [
                    {"key": "http.request.method", "value": {"stringValue": "GET"}},
                    {"key": "http.route", "value": {"stringValue": "/"}},
                    {"key": "http.response.status_code", "value": {"intValue": "200"}},
                ],
            ),
            span("frontend", "f2", "f1", 3, "call api", slow + 40),
        ]
        api = [
            span(
                "api",
                "a1",
                "f2",
                2,
                "GET /checkout",
                slow,
                [
                    {"key": "http.request.method", "value": {"stringValue": "GET"}},
                    {"key": "http.route", "value": {"stringValue": "/checkout"}},
                    {
                        "key": "http.response.status_code",
                        "value": {"intValue": "500" if is_error else "200"},
                    },
                ],
                err=is_error,
            ),
            span("api", "a2", "a1", 3, "SELECT orders", 30),
        ]
        postgres = [
            span("postgres", "p1", "a2", 2, "query orders", 25, err=is_error),
        ]
        resource_spans.append(res("frontend", frontend))
        resource_spans.append(res("api", api))
        resource_spans.append(res("postgres", postgres))
    return {"resourceSpans": resource_spans}


def _alert_payload() -> dict:
    return {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "fingerprint": "demo-targetdown",
                "labels": {
                    "alertname": "TargetDown",
                    "severity": "critical",
                    "instance": "db:5432",
                },
                "annotations": {
                    "summary": "Target db is down (demo)",
                    "description": "Synthetic alert fired by make demo-features.",
                    "runbook_url": "https://github.com/NawfalRAZOUK7/apm-observability/blob/main/docs/runbooks/TargetDown.md",
                },
                "startsAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ],
    }


class Command(BaseCommand):
    help = "Seed a tenant, send OTLP traces, and fire a test alert end-to-end."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="http://localhost:8000")
        parser.add_argument("--traces", type=int, default=25)
        parser.add_argument("--org", default="demo")
        parser.add_argument("--project", default="demo")

    def handle(self, *args, **opts):
        base = opts["base_url"].rstrip("/")

        # 1) Seed tenant + API key.
        org, _ = Organization.objects.get_or_create(
            slug=opts["org"], defaults={"name": opts["org"].title()}
        )
        project, _ = Project.objects.get_or_create(
            organization=org, slug=opts["project"], defaults={"name": opts["project"].title()}
        )
        env, _ = Environment.objects.get_or_create(project=project, kind="production")
        api_key, plaintext = ApiKey.generate(project=project, environment=env, name="demo-e2e")
        self.stdout.write(
            self.style.SUCCESS(
                f"[1/3] Seeded tenant {org.slug}/{project.slug} + API key {api_key.prefix}…"
            )
        )

        # 2) Send OTLP traces.
        status, body = _post(
            f"{base}/v1/traces",
            _otlp_payload(opts["traces"]),
            {"Authorization": f"Api-Key {plaintext}"},
        )
        self.stdout.write(self.style.SUCCESS(f"[2/3] OTLP /v1/traces -> {status}: {body[:200]}"))

        # 3) Fire a test alert into the sink (opens an incident).
        status, body = _post(f"{base}/sink/notify", _alert_payload())
        self.stdout.write(self.style.SUCCESS(f"[3/3] Alert /sink/notify -> {status}: {body[:200]}"))

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("Explore the results:"))
        for label, path in [
            ("Service map", "/api/service-map/"),
            ("Anomalies", "/api/anomalies/"),
            ("Notifications", "/sink/"),
            ("Incidents", "/sink/incidents/"),
            ("Incident metrics (MTTA/MTTR)", "/sink/incidents/metrics/"),
            ("Projects (needs JWT/login)", "/api/tenancy/projects/"),
        ]:
            self.stdout.write(f"  {label:32s}: {base}{path}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(f"Demo API key (shown once): {plaintext}"))
