"""
Logging helpers for structured JSON logs correlated with traces.

``TraceContextFilter`` injects the active OpenTelemetry ``trace_id`` and
``span_id`` (when present) into every log record, so logs shipped to Loki can be
correlated with traces in Tempo. It degrades gracefully when OpenTelemetry is not
installed or no span is active.
"""

from __future__ import annotations

import logging


class TraceContextFilter(logging.Filter):
    """Attach ``trace_id`` / ``span_id`` from the current span to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = ""
        span_id = ""
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and getattr(ctx, "is_valid", False):
                trace_id = format(ctx.trace_id, "032x")
                span_id = format(ctx.span_id, "016x")
        except Exception:
            # OpenTelemetry not installed or no active span: leave fields empty.
            pass

        record.trace_id = trace_id
        record.span_id = span_id
        return True
