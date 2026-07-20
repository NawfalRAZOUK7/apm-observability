# Academic report (archive)

This folder is the **original academic submission** for the APM Observability
project (IDATA 3A, 2025/2026), written in French and kept here for provenance. It
describes the project at its **Phase 1–3** stage (the Django/DRF + TimescaleDB
core, backups, and the monitoring stack).

> For the **current platform** — Phases 4–18: multi-tenancy, native OTLP,
> alerting/incidents, the dashboard, IaC, policy, and delivery — see the
> up-to-date docs one level up:
> [`../ARCHITECTURE.md`](../ARCHITECTURE.md), [`../ROADMAP.md`](../ROADMAP.md),
> and the [top-level README](../../README.md).

## Contents

- `PRISE_EN_MAIN.md` — step-by-step setup/runbook (French).
- `TRACEABILITY.md` — note on the public vs. private (internal-evidence) repo split.
- `sections/` — write-ups mapped to the assignment sections (01–04).
- `latex/` — LaTeX sources for the report, its `images/` and `diagrams/`, and the
  compiled `main.pdf`.

> **Note:** the LaTeX sources were corrected to match the current code (the
> data-lifecycle section no longer claims columnar compression — it was dropped
> because TimescaleDB refuses it on Row-Level-Security tables; see
> [ADR 0001](../adr/0001-multi-tenant-isolation.md)). Recompile the PDF to pick
> this up: `cd latex && latexmk -pdf main.tex`.
