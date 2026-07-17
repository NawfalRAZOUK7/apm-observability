"""Multi-tenancy: organizations, projects, environments, API keys, RBAC.

Isolation model (see docs/ROADMAP.md, Phase 5 + the ADR): shared schema
with a ``project_id`` on every tenant row, enforced by app-level scoping and,
on PostgreSQL, Row-Level Security. SQLite (tests/dev) relies on the app-level
path; RLS policies are installed by a Postgres-only migration.
"""
