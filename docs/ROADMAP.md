# Roadmap — APM Observability Platform

This roadmap turns the project into a portfolio piece that credibly speaks to
three profiles at once, without becoming a pile of unrelated buzzwords:

- **SRE / DevOps / Platform** — the platform is an observability system by nature.
- **Backend / Software Engineer** — the core is a Django/DRF service.
- **Data / Data Engineer** — the heart is time-series + analytics on TimescaleDB + pgvector.

**Unifying narrative:** *"A complete observability platform — the three pillars
(metrics, logs, traces) — shipped through a secure CI/CD supply chain."*
Every item below is chosen to reinforce that story.

Each item is tagged with the profile(s) it strengthens and a rough effort
(`S` = hours, `M` = 1-2 days, `L` = 3+ days).

## Implementation status

- **Phase 1 — done.** k6 load test (`loadtest/`), OpenAPI/Swagger
  (`drf-spectacular`, `/api/docs/`), one-command `make demo` + README polish.
- **Phase 2 — done.** OpenTelemetry tracing + Tempo (2a), structured JSON logs +
  Loki (2b), SLO burn-rate alerts (2c), TimescaleDB retention/compression +
  `check_data_quality` (2d), Trivy + CodeQL CI (2e). The three observability
  pillars (metrics/logs/traces) are complete.
- **Phase 3 — done.** Helm chart (`deploy/helm/apm-observability`) + ArgoCD
  Application (`deploy/argocd`) for Kubernetes GitOps.

Everything below is the original plan, kept for reference.

---

## Where the project stands today

Already implemented (strong baseline):

- Django/DRF APM ingestion + analytics API (batch ingest, KPIs, top-endpoints,
  hourly/daily continuous aggregates, semantic search).
- TimescaleDB hypertables + continuous aggregates; primary/replica read routing.
- pgvector + Gemini embeddings (semantic search over errors).
- Monitoring: Prometheus + Grafana (provisioned) + Alertmanager + node/postgres
  exporters + **custom application metrics** (`apm_ingested_requests_total`,
  `apm_ingest_latency_seconds`).
- Backups: pgBackRest hot/cold to MinIO (S3-compatible).
- Ansible deployment; single-node and multi-node cluster topologies.
- CI (lint, format, tests on SQLite + TimescaleDB, compose smoke, pip-audit) and
  CD (`release.yml`: GHCR build/push + SBOM + provenance + Cosign signing).

**Observability pillar status:** metrics ✅, logs ⚠️ (unstructured), traces ❌.
The single biggest coherence gain is completing the three pillars.

---

## Phase 1 — Make it visible and prove it works

Highest return on image for the least effort. Do this first and in full.

### 1a. Load testing with k6 `[SRE + Backend + Data]` — effort `M`
**Goal:** a documented load test that actually drives latency and error rate up,
fires the alerts, and fills the dashboards — the demo that closes the loop for an
APM project and gives concrete numbers to discuss.

- Files: `loadtest/ingest_and_read.js`, `loadtest/README.md`.
- Ramp VUs against `/api/requests/ingest/` (valid batches) and read endpoints
  (`/api/requests/`, `/api/requests/kpis/`); inject a share of 5xx-labelled events
  so `HighErrorRate` can trigger.
- Add k6 `thresholds` (p95 latency, error rate) so the test doubles as a
  performance gate.
- Document the "watch this happen" flow: run test → Grafana panels move →
  Prometheus alert goes `PENDING`/`FIRING`.

### 1b. OpenAPI / Swagger docs `[Backend]` — effort `S`
**Goal:** self-served, auto-generated API documentation — a strong, cheap
professionalism signal, and it makes the API explorable in a browser.

- Dependency: `drf-spectacular`.
- `settings.py`: add to `INSTALLED_APPS`, set
  `REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"]`, add `SPECTACULAR_SETTINGS`.
- `apm_platform/urls.py`: `/api/schema/`, `/api/docs/` (Swagger UI),
  `/api/redoc/`.

### 1c. One-command demo + README polish `[all]` — effort `S`
**Goal:** the thing that decides whether a reviewer looks at the rest.

- `make demo`: bring up the single-node stack, migrate, seed, print the URLs
  (API, Swagger, Grafana, Prometheus).
- README: CI badge, "Live API docs" section, "Load testing" section, and a
  one-command demo block near the top.

---

## Phase 2 — Deepen each pillar (this is where mastery shows)

### 2a. Distributed tracing with OpenTelemetry + Grafana Tempo `[SRE + Backend]` — effort `L`
**Goal:** the most important addition. Completes the three pillars and matches the
exact vocabulary of SRE teams.

- Instrument Django with `opentelemetry-instrumentation-django` +
  OTLP exporter; run an OpenTelemetry Collector + Tempo service in compose.
- Add Tempo as a Grafana datasource; enable trace-to-logs / trace-to-metrics
  correlation (exemplars).
- Propagate `trace_id` (the model already has a `trace_id` column — wire it to the
  real span context for a clean story).

### 2b. Structured logs in Loki `[SRE]` — effort `M`
**Goal:** the logs pillar; with Prometheus + Tempo + Loki, Grafana becomes a single
pane of glass (the "LGTM" stack).

- JSON logging (e.g. `python-json-logger`) with `trace_id` in every log line.
- Run Loki + Promtail (or Grafana Alloy) in compose; add Loki datasource.

### 2c. SLO / SLI with burn-rate alerts `[SRE]` — effort `M`
**Goal:** turns "CPU > 85%" into real SRE practice.

- Define SLIs (availability, latency) and SLOs (e.g. 99.5% / p95 < 300ms).
- Multi-window multi-burn-rate alert rules (fast + slow burn) in
  `alert.rules.yml`; a dedicated "SLO" Grafana dashboard with error budget.

### 2d. Data-layer depth `[Data]` — effort `M`
**Goal:** strengthen the Data profile on top of the existing aggregates.

- TimescaleDB retention + compression policies (native, very time-series-idiomatic).
- Data-quality checks (null/range/uniqueness) as a management command or CI step.
- Surface the pgvector semantic search better (documented examples, a small
  evaluation of result quality).

### 2e. Supply-chain / security hardening in CI `[DevOps/security]` — effort `S`
**Goal:** completes a "secure SDLC" story (already have Cosign, SBOM, pip-audit,
Dependabot).

- Trivy image scan on the built image; CodeQL static analysis workflow.
- Optional: `pre-commit` hooks (ruff, black, detect-secrets).

---

## Phase 3 — Ambitious, Platform-oriented (only with real time budget)

### 3a. Kubernetes + Helm `[Platform]` — effort `L`
**Goal:** justified since Platform roles are a target; but honest about effort —
Ansible + Compose already prove orchestration.

- Minimal Helm chart (Deployment, Service, Ingress, ConfigMap/Secret) for the web
  app + DB + monitoring.
- Local deploy on `kind`/`minikube`; document `helm install`.

### 3b. GitOps with ArgoCD `[Platform]` — effort `L` — optional
**Goal:** the "declarative delivery" capstone if you want to go all-in on Platform.

---

## Recommended order

1. **Phase 1 in full** — 2-3 days, biggest image return.
2. **Phase 2a (tracing) first** within Phase 2 — it legitimizes the word
   "observability" and serves all three profiles. Pick the rest of Phase 2 by
   available time.
3. **Phase 3 only** with a real time budget, after Phases 1-2 are solid.

> Guiding principle: do not do everything. Depth and proof beat breadth. Each
> addition must reinforce the observability narrative, not dilute it.
