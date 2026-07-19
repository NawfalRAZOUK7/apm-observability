# ADR 0001 — Multi-tenant isolation model

- **Status:** Accepted
- **Date:** 2026-07-14
- **Context phase:** Phase 5 (see `docs/ROADMAP.md`)

## Context

The platform is becoming multi-tenant: `Organization → Project → Environment`,
with per-project ingestion API keys and tenant-scoped queries and dashboards.
The core data (`ApiRequest`, and the Phase 6 span tables) lives in **TimescaleDB
hypertables** with continuous aggregates. We must isolate tenants without
breaking time-series partitioning or aggregation, and the choice is effectively
irreversible once data accumulates.

## Options considered

1. **Database per tenant.** Strongest isolation. But N databases means N sets of
   hypertables, continuous aggregates, retention/compression policies, and
   migrations — operationally heavy, and cross-tenant analytics become painful.
   Overkill for this stage.
2. **Schema per tenant.** Medium isolation. Still multiplies hypertables and
   continuous aggregates per schema; Timescale policies and migrations must be
   replayed per schema. Fights the time-series design.
3. **Shared schema + `project_id` column + Row-Level Security.** One set of
   hypertables and aggregates. `project_id` folds into the existing composite
   indexes so partitioning and query plans are preserved. PostgreSQL RLS
   enforces isolation at the database, not by trusting every query to filter.

## Decision

Adopt **option 3: shared schema with a `project_id` on every tenant row,
enforced by PostgreSQL Row-Level Security**, with app-level scoping as
defense-in-depth.

- The tenant is bound to the DB session via a GUC, `app.current_project`, set by
  `tenancy.middleware.set_current_project()` using `set_config(..., is_local :=
  true)` so it is transaction-scoped.
- RLS policies live in dedicated migrations (`RunPython`).
- **Enforcement is phased.** On `ApiRequest` we `ENABLE` (not `FORCE`) RLS now:
  the owner role used by migrations bypasses it, while the non-owner
  `apm_writer` / `apm_reader` roles are already subject to it. Phase 6 reshapes
  ingestion to always carry a `project` (resolved from the API key) and can then
  switch to `FORCE ROW LEVEL SECURITY`.

## Consequences

**Positive:** single hypertable set and aggregates; indexes preserved; DB-level
isolation; cheap cross-tenant admin analytics.

**Negative / risks:** every tenant table must carry `project_id` and every
policy must be correct — a missing policy is a silent leak, so policies are
tested against Postgres in CI (Phase 6). A forgotten `set_current_project` under
`FORCE` mode fails closed (no rows) rather than leaking — an acceptable failure
mode. Existing rows were backfilled to a `default/default` project
(`observability` migration `0011`).

**Trade-off — no columnar compression.** TimescaleDB refuses native columnar
compression on a table with Row-Level Security enabled (`columnstore cannot be
used on table with row security`). Choosing RLS therefore means dropping the
compression policy that Phase 2 had enabled on `observability_apirequest`;
retention + continuous aggregates are unaffected. Tenant isolation is judged more
valuable than the storage saving. (Migration `0009` was updated to keep retention
and remove compression.)

## References

- `tenancy/models.py`, `tenancy/middleware.py`, `tenancy/authentication.py`
- `observability/migrations/0011_backfill_default_project.py`,
  `observability/migrations/0012_rls_apirequest.py`
