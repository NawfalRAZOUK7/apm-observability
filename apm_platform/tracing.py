"""
OpenTelemetry tracing bootstrap.

Tracing is fully optional and disabled by default. It only activates when
``OTEL_ENABLED`` is truthy, so tests, CI, and environments without a collector
are never affected. When enabled, spans are exported over OTLP/HTTP to an
OpenTelemetry Collector (which forwards them to Tempo).

Configuration (environment variables):
    OTEL_ENABLED                  "1" to turn tracing on (default off)
    OTEL_SERVICE_NAME             logical service name (default "apm-observability")
    OTEL_EXPORTER_OTLP_ENDPOINT   collector base URL (default http://otel-collector:4318)
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_CONFIGURED = False


def configure_tracing() -> bool:
    """Initialise OpenTelemetry tracing. Returns True if tracing was enabled.

    Safe to call multiple times; instrumentation runs at most once. Any import
    or setup error is logged and swallowed so it can never break the app.
    """
    global _CONFIGURED

    if os.environ.get("OTEL_ENABLED", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    if _CONFIGURED:
        return True

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        service_name = os.environ.get("OTEL_SERVICE_NAME", "apm-observability")
        endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318"
        ).rstrip("/")

        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
        )
        trace.set_tracer_provider(provider)

        # Instrument the Django request/response cycle.
        DjangoInstrumentor().instrument()

        # Best-effort DB span instrumentation (psycopg 3). Never fatal.
        try:
            from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

            PsycopgInstrumentor().instrument(enable_commenter=True)
        except Exception as exc:  # pragma: no cover - optional
            logger.warning("psycopg tracing instrumentation skipped: %s", exc)

        _CONFIGURED = True
        logger.info("OpenTelemetry tracing enabled (service=%s, otlp=%s)", service_name, endpoint)
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("OpenTelemetry tracing could not be configured: %s", exc)
        return False
