# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — Platform evolution (Phases 4–18)

Product & observability:
- Multi-tenancy: `Organization → Project → Environment`, hashed/rotatable API
  keys, JWT auth, RBAC, per-project quotas, and PostgreSQL Row-Level Security
  ([ADR 0001](docs/adr/0001-multi-tenant-isolation.md)).
- Native OTLP ingestion for traces, metrics, and logs over HTTP **and gRPC**
  (`:4317`), JSON **and protobuf**; tail sampling + per-tenant rate limiting.
- Service dependency maps (`/api/service-map/`) and trace waterfalls
  (`/api/traces/`) derived from spans.
- Statistical anomaly detection (`/api/anomalies/`) with a pluggable embedder
  (free local Ollama or Gemini).
- Real alert delivery (Slack/Discord/ntfy/email via a provider sink),
  tenant-defined alert rules + scheduler, and an incident workflow with
  MTTA/MTTR, runbooks, and postmortems.
- First-party dashboard at `/dashboard/` (service map, incidents, anomalies,
  traces, issues, NL query, DORA).
- LLM assist: AI-drafted postmortems, embeddings error grouping (`/api/issues/`),
  natural-language telemetry queries (`/api/nl-query/`) — all with $0 fallbacks.

Platform engineering & delivery:
- Infrastructure as Code (Terraform/OpenTofu): local `kind` + reference AWS
  (VPC/EKS/RDS/S3); fmt/validate/tflint/tfsec in CI.
- Secrets management: External Secrets Operator, Sealed Secrets, and SOPS+age;
  chart hardened (no committed secrets); gitleaks secret-scanning CI.
- Policy-as-code (Kyverno) incl. Cosign image-signature verification at
  admission; restricted Pod Security Standard + NetworkPolicy in the chart.
- Progressive delivery via Argo Rollouts canary with Prometheus metric analysis.
- DORA metrics (`/api/dora/`): deployment frequency, lead time, change-failure
  rate, MTTR, with Elite/High/Medium/Low bands + Grafana dashboard.
- Reliability/DR: automated restore verification with RPO/RTO metrics + chaos
  drills.

### Added
- OpenAPI 3 schema with Swagger UI and ReDoc (`drf-spectacular`) at `/api/docs/`,
  `/api/redoc/`, `/api/schema/`.
- k6 load-test suite (`loadtest/`) that drives metrics and fires alerts, with
  performance thresholds.
- Distributed tracing via OpenTelemetry exported to Grafana Tempo (opt-in
  `OTEL_ENABLED`).
- Structured JSON logs correlated with traces (`trace_id`/`span_id`) shipped to
  Loki via Promtail.
- SLO availability alerts with multi-window burn-rate rules.
- TimescaleDB retention policy (`0009_retention_compression`). Columnar
  compression is intentionally left off — TimescaleDB rejects it on tables with
  row-level security, which tenant isolation depends on.
- `check_data_quality` management command, wired into CI as a gate.
- CI security workflows: CodeQL and Trivy image scanning.
- Kubernetes delivery: Helm chart (`deploy/helm`) and ArgoCD Application
  (`deploy/argocd`).
- One-command demo (`make demo`) and community health files (LICENSE,
  CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue/PR templates).

### Changed
- Repository structure tidied: `scripts/tests/`, `scripts/deploy/`, monitoring
  configs grouped under `docker/monitoring/{prometheus,alertmanager,grafana}`.
- CI settings de-duplicated to a committed `apm_platform/ci_settings.py`.

### Fixed
- Grafana TimescaleDB datasource now resolves in the single-node stack.

## [0.1.0] - 2026

Initial platform: Django/DRF APM API, TimescaleDB hypertables and continuous
aggregates, primary/replica routing, pgBackRest backups to MinIO, Prometheus +
Grafana monitoring, Ansible deployment, and CI/CD.
