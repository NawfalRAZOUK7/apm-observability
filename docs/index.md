# APM Observability Platform

A **multi-tenant, OpenTelemetry-native observability platform** — metrics, logs,
and traces on TimescaleDB, with per-tenant API keys and RBAC, real alerting and
incident management, a first-party dashboard, an AI assist layer, and a full
platform-engineering delivery chain: Infrastructure as Code, secrets management,
a policy-enforced supply chain, progressive delivery, and DORA metrics.

Built as a Django/DRF service on PostgreSQL + TimescaleDB + pgvector. Every
feature runs at **$0 by default** through a provider pattern (each external
dependency has a free/local driver selectable by environment variable).

## Start here

- [Architecture](ARCHITECTURE.md) — components, data model, telemetry paths, and delivery.
- [Roadmap](ROADMAP.md) — the full phase-by-phase build history (Phases 1–18).
- [Progressive delivery](PROGRESSIVE_DELIVERY.md) — Argo Rollouts canary + metric analysis.
- [Architecture Decision Records](adr/0001-multi-tenant-isolation.md) — the decisions and their trade-offs.
- Runbooks — operational procedures (TargetDown, DR restore, secret rotation).

## Quick demo

```bash
make demo            # full stack (TimescaleDB + metrics/logs/traces) + seed + URLs
make demo-features   # seed a tenant + API key, send OTLP traces, fire a test alert
# open http://localhost:8000/dashboard/   ← the first-party UI
```

> This site is generated from the Markdown in [`docs/`](https://github.com/NawfalRAZOUK7/apm-observability/tree/main/docs)
> with MkDocs Material and published on every push to `main`.
