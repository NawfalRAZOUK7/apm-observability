"""Native OTLP trace ingestion (Phase 6).

Accepts OTLP/HTTP JSON at ``/v1/traces``, parses OpenTelemetry semantic
conventions, auto-registers services, stores spans in a tenant-aware hypertable,
and converts HTTP server spans into the existing ApiRequest analytics model so
KPIs keep working. See docs/ROADMAP.md, Phase 6.
"""
