# Case study: building a multi-tenant, OTel-native observability platform

A walkthrough of the problem, the key architectural decisions, the trade-offs
behind them, and the results — verified end-to-end on a real Kubernetes cluster.
For the component map see [ARCHITECTURE](ARCHITECTURE.md); for the decision
records see [`adr/`](adr); for the build history see [ROADMAP](ROADMAP.md).

## The problem

Application-performance monitoring is usually assembled from several SaaS
products (Datadog, New Relic, Sentry, PagerDuty) that are expensive, opaque, and
hard to reason about as a system. I wanted to build the core of such a platform
from first principles — ingestion, storage, analytics, alerting, incidents, and
delivery — as **one coherent system**, with two constraints:

1. **Runs at $0 by default.** Every external dependency (LLM, object store,
   notifier, embedder) sits behind a provider interface with a free/local driver,
   selectable by environment variable. Nothing is required to be paid to run it.
2. **Production-shaped, not a toy.** Multi-tenant isolation, a real delivery
   chain (IaC, GitOps, policy, progressive delivery), and evidence it works.

## Key decisions and trade-offs

### 1. Multi-tenancy: shared schema + PostgreSQL Row-Level Security

The choice was between schema-per-tenant, database-per-tenant, and a shared
schema with a `project_id` on every row. Shared-schema won because the workload
is time-series analytics: a single set of hypertables and continuous aggregates
keeps cross-tenant admin queries cheap and avoids an explosion of objects.

Isolation is enforced at the **database** layer, not just the application: every
tenant row carries `project_id`, and PostgreSQL **Row-Level Security** policies
filter on a per-session GUC (`app.current_project`) bound by middleware in a
transaction-scoped `set_config(...)`. Application scoping is defense-in-depth on
top. See [ADR 0001](adr/0001-multi-tenant-isolation.md).

**The trade-off that bit:** enabling RLS on the raw hypertable makes TimescaleDB
**refuse native columnar compression** (`columnstore cannot be used on table with
row security`). I chose tenant isolation over the storage saving and dropped the
compression policy — retention and continuous aggregates are unaffected. This is
exactly the kind of non-obvious interaction that only surfaces when you build the
real thing, and it's documented rather than hidden.

### 2. One database: PostgreSQL + TimescaleDB (+ pgvector)

The platform standardizes on a single engine — PostgreSQL with the TimescaleDB
and pgvector extensions — for **every** environment (dev, CI, production). An
earlier SQLite "fast path" was removed: it created a second code path, forced
Postgres-only tests to skip, and let bugs pass on SQLite that would fail in
production. Consolidating means tests exercise the real engine and behaviour is
identical everywhere. The cost — you need Docker/Postgres to run anything — was
worth the fidelity.

### 3. Native OTLP, with analytics projection

Rather than only a custom ingest API, the platform speaks **native OTLP** —
HTTP (JSON + protobuf) and gRPC on `:4317`, for traces, metrics, and logs — so
any stock OpenTelemetry SDK or Collector can point at it unchanged. Tenant is
resolved from the ingestion API key; tail sampling and per-tenant rate limiting
run before storage. Server spans are also projected into the analytics model so
the existing KPI/aggregate machinery keeps working — new ingestion path, same
analytics.

### 4. Progressive delivery with real metric analysis

Deploys go out as an **Argo Rollouts canary** that promotes or rolls back based
on a Prometheus **AnalysisTemplate**, not a timer. Getting this right surfaced
several real bugs: the Prometheus query returns a vector (`result[0]`, not
`result`), the canary must be selected by the `rollouts-pod-template-hash` label
(a `PodMonitor` with `podTargetLabels`), and Argo's `{{args}}` templating has to
be escaped through Helm's own `{{ }}`.

### 5. Supply chain: sign, attest, and verify at admission

CI builds the image, scans it (Trivy), produces a CycloneDX **SBOM** and a
**SLSA build-provenance** attestation, and **signs it with Cosign** (keyless
OIDC). The cluster then **verifies that signature at admission** via a Kyverno
policy — an unsigned image is denied. A subtle version pin matters here: Cosign
2.x writes the legacy `sha256-<digest>.sig` tag that Kyverno 1.18 reads; Cosign
3.x defaults to the OCI 1.1 referrers format the policy can't find — so Cosign is
pinned to 2.4.3.

## Results (verified on a real kind cluster)

This wasn't validated only in unit tests. A full run on a local Kubernetes
cluster exercised the delivery chain end to end:

- **Canary auto-rollback fired correctly.** With a bad build injected, the
  Prometheus analysis measured a **0.98 service-wide error rate against a 0.16
  canary** threshold and Argo Rollouts aborted the promotion automatically —
  no human in the loop.
- **Signature enforcement works both ways.** A signed image is admitted; an
  unsigned image is **denied** by the Kyverno `verifyImages` policy (asserted by
  an integration test in CI).
- **Disaster recovery is measured, not assumed.** pgBackRest backups are restored
  by an automated drill that emits `apm_backup_restore_success` plus RPO/RTO
  metrics — recovery is a number, not a hope.
- **Policy engine is honest about edge cases.** The `require-probes` Kyverno rule
  correctly *skips* run-to-completion Job pods (the chart's migration hook) via an
  `ownerReferences` precondition — probes are for long-running workloads.

## What I'd do next

- A hosted public demo so the dashboard is one click away.
- SLO-as-code with error-budget burn dashboards generated from the alert rules.
- An OpenTelemetry Collector reference pipeline in front of ingestion.
- Contract testing (schemathesis) driven by the generated OpenAPI schema.

## What this demonstrates

End-to-end ownership of a system: data modelling on a time-series database,
multi-tenant security at the database layer, an OTel-native ingestion pipeline,
and a complete platform-engineering delivery chain — built with explicit
trade-offs, and verified with evidence rather than claims.
