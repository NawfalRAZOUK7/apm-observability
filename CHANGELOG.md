# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
- TimescaleDB compression + retention policies (`0009_retention_compression`).
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
