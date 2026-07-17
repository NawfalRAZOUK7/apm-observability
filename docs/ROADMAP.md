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
  Loki (2b), SLO burn-rate alerts (2c), TimescaleDB retention +
  `check_data_quality` (2d), Trivy + CodeQL CI (2e). The three observability
  pillars (metrics/logs/traces) are complete. (Native columnar compression was
  later removed — TimescaleDB refuses it on tables with Row-Level Security, added
  in Phase 5; see [ADR 0001](adr/0001-multi-tenant-isolation.md).)
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


---

# Continued — Platform evolution (Phases 4–18)

# Roadmap (Next) — Free-First Platform Evolution

Companion to [`ROADMAP.md`](./ROADMAP.md), which covers Phases 1–3 (all done:
the three observability pillars + secure CI/CD + Helm/ArgoCD). This document is
the **next chapter — Phases 4–9 plus two parallel infrastructure tracks** — that
turns the project from a monitoring app into a **secure, multi-tenant,
OpenTelemetry-compatible observability platform** with actionable alerts,
automated releases, and demonstrated reliability.

**Goal profile:** real product / SaaS **and** learning vehicle. Sequencing
optimizes for correctness and avoiding rework, not demo flash.

Tags per item: profile(s) it strengthens `[SRE | Backend | Data | Platform]`
and rough effort (`S` = hours, `M` = 1–2 days, `L` = 3+ days).

## Implementation status

- **Phase 4 — done.** `notifications` app (provider-pattern sink): Alertmanager
  webhook receiver, `Notification` model + migration, severity-based fan-out
  (`console`/`slack`/`discord`/`ntfy`, free by default), dashboard/audit API at
  `/sink/`. Alertmanager rewritten with severity routing + inhibition (secrets
  kept out of the config); `TargetDown` runbook added. 6 unit tests, full suite
  green (52 passed).
- **Phase 5 — done.** `tenancy` app: `Organization/Project/Environment/Membership`,
  hashed+rotatable `ApiKey` (scoped to project+env, expiry/revocation), RBAC
  (`admin/operator/developer/viewer`), JWT auth (simplejwt), per-project monthly
  quotas (429), management API at `/api/tenancy/`. Isolation = shared-schema +
  `project_id` + PostgreSQL RLS (see [ADR 0001](./adr/0001-multi-tenant-isolation.md));
  RLS installed on `ApiRequest` (ENABLE, deferred to FORCE in Phase 6), existing
  rows backfilled to `default/default`. 13 unit tests, full suite green (65 passed).
- **Phase 6 — done.** Native OTLP/HTTP JSON trace ingestion at `/v1/traces`
  (stock OTel exporters, `OTEL_EXPORTER_OTLP_PROTOCOL=http/json`), **zero new
  deps**. New `Span` hypertable + `Service` auto-registration, tenant resolved
  from the API key. OTLP parser handles semantic conventions; HTTP SERVER spans
  convert to `ApiRequest` rows so KPIs keep working. RLS switched to **FORCE** on
  `ApiRequest` + `Span` (permissive-when-unset policy makes this safe). 5 unit
  tests, full suite green (70 passed).
- **Phase 7 — done.** Service map at `/api/service-map/`: dependency topology
  from `parent_span_id` edges, per-edge call volume / error rate / avg+p95
  latency, per-node health, critical-path of the slowest trace, and
  period-over-period deltas. Tenant-scoped, pure-ORM (runs on SQLite + PG). 5
  unit tests, full suite green (75 passed).
- **Phase 8 — done.** Statistical anomaly detection at `/api/anomalies/`: robust
  median/MAD baselines per service+endpoint over time buckets, for latency and
  error rate, with a minimum-history guard. Pluggable embedder (`EMBED_PROVIDER`)
  defaulting to free/offline **Ollama `nomic-embed-text`** (768-dim, no schema
  change) with Gemini as the hosted option; optional profile-gated `ollama`
  compose service. 7 unit tests, full suite green (82 passed).
- **Phase 9 — done.** Incident workflow on the sink: firing alerts open/dedupe
  `Incident`s (info stays dashboard-only), resolved alerts auto-resolve them,
  with a full `IncidentEvent` timeline, ack/assign/resolve endpoints, MTTA/MTTR
  metrics, Grafana deep-link, and markdown postmortem generation at
  `/sink/incidents/`. 6 unit tests, full suite green (88 passed). App phases
  (4–9) complete.
- **Track A — done.** CD pipeline `.github/workflows/deploy.yml`: tag → staging →
  smoke → **GitHub Environment approval** → production → smoke, with
  `helm upgrade --atomic` auto-rollback and optional Grafana deploy annotations.
  Per-env values (`values-staging.yaml`/`values-production.yaml`), ArgoCD apps
  for both namespaces, and local k3d scripts (`scripts/deploy/`) — staging + prod
  as two namespaces on one free local cluster.
- **Track B — done.** Automated restore verification (`scripts/drills/verify_restore.sh`):
  checks the pgBackRest repo, times a real restore (RTO), measures backup age
  (RPO), verifies cluster consistency, and emits Prometheus metrics via the
  node-exporter textfile collector. Weekly `dr-verify.yml` workflow publishes
  results as an artifact; RPO/RTO Grafana dashboard + DR alert rules
  (`BackupRestoreVerificationFailing`, `BackupTooOld`, `BackupVerificationStale`)
  + runbook. Chaos drills already existed in `scripts/drills/`.

- **Phase 10 — done.** `alerting` app: tenant-owned `AlertRule`s (threshold +
  anomaly kinds, per service/endpoint), evaluated by a scheduler
  (`evaluate_alert_rules --loop`, optional `rule-scheduler` compose sidecar) that
  computes metrics over `ApiRequest` / the Phase 8 detector and routes state
  transitions through the notification sink into incidents. CRUD API at
  `/api/alerting/rules/` (RBAC-gated, tenant-scoped) with an on-demand
  `evaluate` action. This unifies Phases 4/8/9 into automatic alerting. 7 unit
  tests, full suite green (99 passed).

Original phases (4–9) + infra tracks were completed earlier. Verification runs
on the Python 3.10 sandbox with a `datetime.UTC` shim (project targets 3.11+);
nothing was committed.

## Next chapter (planned order)

Recommended sequence for the follow-on features (foundations → presentation →
intelligence, to avoid rework):

1. **Phase 10 — alert rules + scheduler.** ✅ done.
2. **Phase 11 — complete native OTLP.** ✅ done. OTLP **metrics** (`/v1/metrics`)
   and **logs** (`/v1/logs`) signals as tenant-aware hypertables; **protobuf**
   accepted on the HTTP endpoints (`application/x-protobuf`) alongside JSON;
   native **gRPC** receiver on :4317 (`manage.py otlp_grpc_server`, opt-in
   `otlp-grpc` compose sidecar) reusing the same parse/store path; **tail
   sampling** (keep errors/slow, hash-deterministic otherwise) and per-project
   **token-bucket rate limiting** on ingest. `grpcio` + `opentelemetry-proto`
   added to the lock. 10 unit tests (incl. a real protobuf round-trip + gRPC
   server build), full suite green (109 passed).
3. **Phase 12 — first-party UI.** ✅ done. Single-file React dashboard served by
   Django at `/dashboard/` (CDN React + Cytoscape, **no Node build step**): a
   visual **service-map graph** (unhealthy nodes/edges in red, critical path),
   an **incident board** (ack/resolve/postmortem, MTTA/MTTR KPIs), an **anomaly
   explorer**, and a **trace waterfall**. Backed by two new read endpoints
   (`/api/traces/`, `/api/traces/<id>/`). Same-origin, so no CORS. 4 unit tests,
   full suite green (113 passed).
4. **Phase 13 — LLM incident intelligence.** ✅ done. Pluggable `llm.py`
   text-generation provider (`gemini`/`ollama`/`none`, default `none` so every
   feature degrades to a $0 path): **AI-drafted postmortems** from the incident
   timeline (`/sink/incidents/<id>/postmortem/?ai=1`, falls back to the
   template), **error grouping into Issues** via Sentry-style fingerprinting
   (`/api/issues/`, `manage.py group_errors`), and **natural-language telemetry
   queries** (`/api/nl-query/?q=…`, LLM parse with a keyword-heuristic fallback).
   Dashboard gains **Issues** + **Ask** tabs. 10 unit tests, full suite green
   (123 passed).

**The full next-chapter roadmap (Phases 10–13) is now implemented**, on top of
Phases 4–9 + the two infra tracks. Every LLM/embedding feature has a free,
offline default; verification runs on the Python 3.10 sandbox with a
`datetime.UTC` shim (project targets 3.11+); nothing was committed.

## Advanced-DevOps track (planned order)

Elevating the platform from "app with CI/CD" to a platform-engineering showcase.
Foundations-first: provision declaratively, secure it, gate it, then get fancy.

1. **Phase 14 — Infrastructure as Code (Terraform/OpenTofu).** ✅ done. Reusable
   modules (`apm_platform` deploys the Helm chart with **secrets injected from
   Terraform**, not `values.yaml`; `monitoring` = kube-prometheus-stack + Loki +
   Tempo) and two environments: **`local`** (kind cluster + app, fully $0) and a
   reference **`aws`** (VPC + EKS + Multi-AZ RDS + encrypted S3 backups, remote
   S3/DynamoDB state). CI `terraform.yml` runs fmt/validate/tflint + a `trivy
   config` scan; `make tf-*` targets. 19 HCL files validated structurally.
2. **Phase 15 — Secrets management.** ✅ done. Chart hardened: **no `change-me`
   defaults**, empty secrets skipped, and an `existingSecret` hook to consume an
   externally-managed Secret. Three integrations under `infra/secrets/`:
   **External Secrets Operator** (TF module + AWS/k8s `SecretStore` +
   `ExternalSecret`), **Sealed Secrets** (TF module + workflow), and **SOPS+age**
   (`.sops.yaml` + `make secrets-*`). A **gitleaks** CI job blocks any plaintext
   secret from being committed; a secret-rotation runbook covers API keys +
   infra secrets. Structurally validated (YAML/HCL); app suite still green (123).
3. **Phase 16 — Policy-as-code + supply-chain enforcement.** ✅ done. **Kyverno**
   admission policies (`infra/policy/kyverno/`): **Cosign keyless signature
   verification** (enforces at admit what release.yml signs), registry allowlist,
   no `:latest`, non-root + drop-ALL-caps, requests/limits, and probes — all
   `Enforce`. The app chart was hardened to comply (pod/container
   `securityContext`, optional default-deny **NetworkPolicy**). Kyverno TF module
   + `kyverno test` fixtures (good/bad pods) + a **Policy CI** workflow. 9 policy
   manifests validated; app suite still green (123).
4. **Phase 17 — Progressive delivery.** ✅ done. **Argo Rollouts** canary
   (`rollout.enabled=true` renders a `Rollout` + `AnalysisTemplate` instead of a
   Deployment): traffic shifts 20→50→80→100% with a Prometheus **AnalysisTemplate**
   between steps (success-rate ≥95%, p95 ≤1s — the same SLIs as the burn-rate
   alerts) that **auto-aborts + rolls back** on breach. Argo Rollouts TF module;
   `deploy-k8s.sh` is rollout-aware (`ROLLOUT=1`, watches status, undoes on
   failure); `docs/PROGRESSIVE_DELIVERY.md`. Chart templates balance-checked;
   app suite green (123).
5. **Phase 18 — DORA metrics.** ✅ done. `dora` app records deployments (fed by
   the CD pipeline) and computes the **four DORA metrics** — deployment
   frequency, lead time for changes, change-failure rate, and time-to-recovery
   (MTTR reused from incidents) — each classified **Elite/High/Medium/Low**.
   API at `/api/dora/` (record + scorecard), a **DORA tab** in the dashboard, a
   Grafana DORA dashboard, and `deploy-k8s.sh` posts a record on every
   deploy/rollback (`DORA_ENDPOINT`). 5 unit tests, full suite green (128).

**The advanced-DevOps track (Phases 14–18) is complete**: declarative IaC,
managed secrets, enforced supply-chain policy, progressive delivery, and the
DORA delivery scorecard. Combined with Phases 4–13, the platform is a full
platform-engineering showcase.

**Verified end-to-end on a `kind` cluster** (not just structurally): Kyverno
admits the hardened app *and* the migrate Job while rejecting non-compliant
pods; the Argo Rollouts canary promotes on healthy metrics and **auto-aborts +
rolls back on a real SLI breach**, with the analysis scoped to the canary pods
(0.16 canary error-rate caught where the Service-wide average of 0.98 would have
shipped it); migrations run as a pre-upgrade Job against the correct revision's
config; RLS + hypertables apply on TimescaleDB; and the Terraform `local`
environment stands the whole thing up. Cosign signing/verification is proven at
release time (the policy needs a real signed image).

---

## Guiding principle: everything runs at $0 via the provider pattern

The single rule that makes this whole roadmap free without faking the
engineering:

> **Every external dependency ships two drivers — a real one and a
> free/local one — chosen by an environment variable. The default is the free
> driver. The real driver is one env change away.**

This is not a hack to dodge cost; it is the correct design (dependency
inversion) and it is where a lot of the *learning* lives. You build the real
integration code once, point it at a local mock or self-hosted equivalent for
$0 during development and demos, and flip a single env var to go live on a paid
service later. Nothing in the codebase is throwaway.

### Paid dependency → free / local replacement

| Feature area | Would normally cost | Free / local replacement | Switch |
|---|---|---|---|
| Paging (Critical alerts) | PagerDuty / Opsgenie | **Mock pager sink** (local webhook receiver that records "pages") + optional self-hosted **[ntfy.sh](https://ntfy.sh)** for real phone push | `PAGER_PROVIDER=sink\|ntfy\|pagerduty` |
| Chat alerts | Slack / Teams paid | Slack **incoming webhook** (free) · **Discord webhook** (free) · self-hosted **Mattermost** (Slack-compatible) · mock sink | `CHAT_PROVIDER=sink\|slack\|discord` |
| Email alerts | Hosted SMTP / SendGrid | **Mailpit** (or MailHog) local SMTP catcher with a web UI; Gmail app-password / Brevo free tier for real send | `EMAIL_BACKEND` + `EMAIL_HOST=mailpit:1025` |
| Staging + prod clusters | Managed EKS/GKE/AKS | **k3d** (or kind) — one local cluster, two namespaces = `staging` + `production` | ArgoCD targets both; local by default |
| Production approval gate | Paid CD platform | **GitHub Environments** required reviewers (free on public repos) | native to Actions |
| Embeddings (error similarity) | Gemini / OpenAI API | **Ollama `nomic-embed-text`** — 768-dim, *exactly matches* your `VectorField(dimensions=768)` — or `sentence-transformers` all-MiniLM (384-dim) | `EMBED_PROVIDER=local\|gemini` |
| CI minutes | Actions private-repo minutes | Keep repo **public** (unlimited) or a **self-hosted runner** | repo setting |
| Grafana / Prometheus / Loki / Tempo | Grafana Cloud | Self-hosted OSS — **already in your stack** | n/a |
| Managed TimescaleDB | Timescale Cloud | Your **TimescaleDB container** — already running | n/a |

Net result: the platform is demonstrable end-to-end, alerts fire and get
"paged", incidents open, deploys promote staging→prod with an approval gate —
all on a laptop, for **$0**. See the [$0 cost ledger](#0-cost-ledger) at the end.

---

## Phase 4 — Real alert delivery + notification sink `[SRE]` — effort `S–M`

**Why first:** your `docker/monitoring/alertmanager/alertmanager.yml` ships with
every receiver commented out — it is the one truly stubbed thing in the repo.
Highest credibility-per-hour, and it establishes the provider pattern the rest of
the roadmap reuses.

**Scope**
- Real Alertmanager routing by severity:
  `Critical → pager + chat`, `Warning → chat`, `Info → dashboard only`.
- Alert **inhibition** (suppress dependent alerts when a parent is firing) and
  **maintenance silences**.
- Secrets injected via env / secret files — never committed into
  `alertmanager.yml` (use `${SLACK_WEBHOOK_URL}` style + an entrypoint that
  templates the file, or Alertmanager's `*_file` options).

**Free / mock strategy**
- Build a tiny **notification-sink** service (see
  [Appendix A](#appendix-a-notification-sink)) — a webhook receiver that records
  every notification into a table and renders them in a page/Grafana panel. Point
  Alertmanager's `webhook_configs` at it. This proves the full alert→delivery
  path with no external account.
- For a "real" free channel, add a Slack **or** Discord incoming webhook.
- For paging, the sink doubles as a mock PagerDuty; optionally self-host `ntfy`
  for genuine phone push.

**Learning notes:** Alertmanager routing trees, inhibition rules, secret
templating, webhook contract design.

**Acceptance**
- k6 load test (`loadtest/`) drives error rate up → `HighErrorRate` fires →
  a record lands in the sink and a message hits Slack/Discord within the group
  interval.
- Silences and inhibition demonstrably suppress noise.

---

## Phase 5 — Multi-tenancy, API keys, RBAC `[Backend + Platform]` — effort `L`

**Why here (before OTLP):** tenancy touches ingestion, every query, and every
dashboard. Build OTLP ingestion first and you write the ingestion path twice.
This is the spine of the SaaS story and the deepest backend-learning block.

**Scope**
- Hierarchy: `Organization → Project → Environment (prod/staging/dev)`.
- **Ingestion API keys** scoped to a project+environment: stored **hashed**
  (e.g. SHA-256) with a short lookup **prefix**; support rotation + expiry.
- Auth for the dashboard/API: **JWT** (`djangorestframework-simplejwt`) and/or
  OAuth (`authlib`) — all free/OSS.
- **RBAC** roles: `admin`, `operator`, `developer`, `viewer`.
- Tenant-isolated queries, dashboards, and per-tenant usage quotas.

**The one load-bearing decision — isolation model.** Recommended: **shared
schema with a `project_id` on every row + PostgreSQL Row-Level Security (RLS)**.
Rationale: schema-per-tenant and db-per-tenant fight TimescaleDB hypertables and
continuous aggregates; a `project_id` folded into your composite indexes keeps
partitioning and aggregates intact, and RLS enforces isolation at the database
rather than trusting every query to filter correctly. (Worth its own ADR — I can
write it.)

**Free / mock strategy:** entirely your own code + OSS — no paid dependency at
any tier. Quotas enforced in-app against Timescale counts.

**Learning notes:** RLS policies + session `SET app.current_project`, API-key
hashing/rotation, DRF permission classes, JWT lifecycle, retrofitting a
`project_id` across hypertables + continuous aggregates via migration.

**Acceptance**
- Two projects cannot read each other's rows even with a crafted query (RLS
  proven by test).
- Ingest rejects unknown/expired/rotated keys; a `viewer` cannot mutate; a
  quota breach returns `429`.

---

## Phase 6 — Native OTLP ingestion + span data model `[SRE + Backend + Data]` — effort `L`

**Why:** turns a custom REST monitor into an interoperable observability
platform. This is genuinely new data modeling, not a reshuffle — your current
`ApiRequest` is flat (one row, a `trace_id` string, no span hierarchy).

**Scope**
- Accept **OTLP over HTTP and gRPC**; honor OpenTelemetry **semantic
  conventions**; automatic service registration from resource attributes.
- New **span model**: `trace_id`, `span_id`, `parent_span_id`, `service`,
  `kind`, `start/end`, `status`, `attributes (JSONB)` — as a Timescale hypertable,
  **tenant-aware from day one** (carries `project_id`, resolved from the ingest
  API key / OTEL resource attributes → project).
- Trace / metric / log correlation via `trace_id` (you already thread `trace_id`
  through logs).
- Conversion layer OTLP spans → your existing analytics model so KPIs keep
  working.

**Free / mock strategy**
- OpenTelemetry SDK + Collector are CNCF/OSS — you already have
  `otel-collector-config.yaml`. Decision to make: **native OTLP receiver in
  Django** (chosen — more real, more learning) vs. the Collector translating
  OTLP→REST (cheaper, but no spans, less learning).
- Generate load with the OTel demo app or your k6 test emitting OTLP — no cost.

**Learning notes:** OTLP protobuf/gRPC, semantic conventions, span→analytics
ETL, hypertable design for spans.

**Acceptance**
- An app instrumented with a stock OTel SDK (no custom code) sends traces that
  appear correlated with logs/metrics, scoped to the right project.

---

## Phase 7 — Service maps + dependency intelligence `[SRE + Platform]` — effort `M–L`

**Why after Phase 6:** a topology graph needs span parent/child relationships —
it literally cannot exist before spans land. Falls almost entirely out of the
Phase 6 model.

**Scope**
- Build topology from `parent_span_id` edges:
  `Frontend → API gateway → Django API → PostgreSQL / Gemini`.
- Per-edge request rate, error rate, latency; **critical-path** detection;
  unhealthy-dependency highlighting; period-over-period change.

**Free / mock strategy:** pure derivation over your own span data — no paid
dependency. Render with a free JS graph lib or a Grafana Node Graph panel.

**Acceptance:** killing a downstream dependency in a demo turns its edge red and
surfaces it on the critical path.

---

## Phase 8 — Anomaly detection (statistical first) `[Data]` — effort `M`

**Why:** cheap, high-signal, and partly pre-built — your `ApiRequestEmbedding`
(pgvector) already scaffolds error-similarity grouping.

**Scope**
- **Statistical baselines first:** rolling z-score / MAD on latency and
  error-rate per `service+endpoint` via Timescale `time_bucket` — hours of work,
  no ML. Per-tenant baselines.
- Seasonal traffic awareness; sudden cardinality-growth detection.
- Error grouping via embeddings; later, capacity forecasting.

**Free / mock strategy:** statistical layer needs nothing external. For
embeddings, swap Gemini for **Ollama `nomic-embed-text` (768-dim — drop-in for
your existing `VectorField(dimensions=768)`)** behind an `EMBED_PROVIDER` switch
(see [Appendix B](#appendix-b-local-embedder)). Runs fully offline, $0.

**Learning notes:** robust statistics for monitoring, seasonality, pluggable
embedder interface, keeping vector dims stable across providers.

**Acceptance:** an injected latency regression flags within a bucket or two;
similar errors cluster together regardless of embedding provider.

---

## Phase 9 — Incident-management workflow `[SRE]` — effort `M`

**Why here:** it consumes Phase 4 (delivery) and Phase 6–7 (traces/maps). Turns
alerts into tracked incidents.

**Scope**
- Runbook URL on every alert (e.g. `TargetDown` → recovery doc).
- Incident timeline, acknowledgement + ownership, **MTTA / MTTR** metrics.
- Postmortem template; auto Grafana snapshot/link; related logs+traces attached
  to the incident.

**Free / mock strategy:** the notification-sink from Phase 4 becomes the
incident intake — an Alertmanager webhook opens an incident row; ack/assign via
your own API; snapshots via Grafana OSS. No paid tool.

**Acceptance:** a firing alert auto-opens an incident with a runbook link; ack
stops MTTA; resolve computes MTTR; postmortem generated from the timeline.

---

## Parallel Track A — Continuous deployment (staging → prod) `[Platform]` — effort `M`

Not blocked by the app phases; interleave anytime. You already scaffolded Helm +
ArgoCD, so this is mostly wiring.

**Scope:** extend `release.yml` — Tag → Test → Scan → Publish → Sign →
**deploy staging** → smoke/integration tests → **manual approval** → deploy prod
→ smoke tests → **auto-rollback on failed health check**; Grafana deployment
annotations.

**Free / mock strategy**
- Staging + production are two **namespaces on one local `k3d`/kind cluster** —
  no cloud bill. ArgoCD (already present) syncs both; Helm updates the image tag.
- Production gate = **GitHub Environments** required reviewers (free).
- Smoke tests = your existing compose smoke + k6 thresholds.

**Acceptance:** a tag deploys to staging automatically, waits for approval,
promotes to prod, and rolls back if `/health/` degrades.

---

## Parallel Track B — Reliability & DR proof `[SRE + Data]` — effort `M`

Independent; strongest "this is real" narrative. You already have pgBackRest +
MinIO and a `scripts/drills/` folder.

**Scope:** scheduled **restore-verification** (restore latest backup into a
throwaway container, run integrity checks, emit pass/fail); backup-age +
integrity metrics to Prometheus; **RPO/RTO dashboards**; automated failover
drills; chaos tests for PostgreSQL, MinIO, and app nodes; published DR results.

**Free / mock strategy:** all local — restore into an ephemeral container,
chaos via `docker kill` / `pumba` (free) or `tc` netem. No paid chaos platform.

**Acceptance:** a scheduled job restores last night's backup, verifies row
counts/checksums, and pushes `backup_verify_success` + age to Prometheus; a
killed DB triggers a drill that measures real RTO.

---

## Appendix A — Notification sink (the universal free mock)

A ~100-line Django app (or tiny FastAPI service) that is the free stand-in for
Slack/PagerDuty/email all at once, and later the incident intake:

- `POST /sink/notify` — accepts an Alertmanager webhook payload, stores
  `{received_at, severity, alertname, labels, channel, payload}`.
- `GET /sink` — renders recent notifications (and a Grafana table panel via the
  Postgres datasource).
- Alertmanager `webhook_configs.url` points here for every channel during
  dev/demo. Flip `CHAT_PROVIDER`/`PAGER_PROVIDER` to hit real Slack/ntfy when
  wanted.

The delivery code (payload shaping, retries, severity routing) is identical
whether the target is the sink or a real provider — that is the point.

## Appendix B — Local embedder

Provider interface `embed(texts) -> list[vector768]` with two drivers:

- `gemini` — existing `text-embedding-004` path (768-dim).
- `local` — **Ollama `nomic-embed-text`** (768-dim, matches your
  `VectorField(dimensions=768)` with zero migration) running in a container, or
  `sentence-transformers` in-process (would need a 384-dim column variant).

Selected by `EMBED_PROVIDER`. Default `local` for $0 offline dev; `gemini` for
production quality. No schema change when using Ollama.

---

## $0 cost ledger

| Layer | Chosen free option | Ongoing cost |
|---|---|---|
| Compute (dev/demo) | Laptop / local k3d | $0 |
| Data + vectors | TimescaleDB + pgvector containers | $0 |
| Metrics/logs/traces UI | Prometheus + Grafana + Loki + Tempo OSS | $0 |
| Alerts + paging | Notification sink (+ Slack/Discord webhook, ntfy) | $0 |
| Email | Mailpit local catcher | $0 |
| Embeddings | Ollama `nomic-embed-text` | $0 |
| Auth / tenancy / RBAC | Django + simplejwt + Postgres RLS | $0 |
| OTLP ingestion | OpenTelemetry OSS | $0 |
| CI/CD | GitHub Actions (public repo) + ArgoCD + Helm | $0 |
| Backups / DR | pgBackRest + MinIO local | $0 |

**Cost only appears when** you want a persistent cloud staging/prod running 24/7,
or you switch a provider from its free driver to a paid tier (real PagerDuty
seats, Gemini volume, private-repo Actions minutes). Every one of those is a
single env/flag change, not a rewrite.

---

## Recommended order

1. **Phase 4** — real alert delivery + sink (establishes the provider pattern).
2. **Phase 5** — multi-tenancy / API keys / RBAC (the spine; do before OTLP).
3. **Phase 6** — native OTLP ingestion + span model (tenant-aware from day one).
4. **Phase 7** — service maps (falls out of Phase 6).
5. **Phase 8** — statistical anomaly detection (+ local embeddings).
6. **Phase 9** — incident-management workflow.
- **Track A (CD)** and **Track B (Reliability/DR)** run in parallel whenever
  there's slack — neither blocks the app phases.

> Guiding principle, unchanged from the original roadmap: depth and proof beat
> breadth. Each item reinforces the "secure, multi-tenant, OTel-compatible
> platform" story — and every one of them runs at $0 by default.
