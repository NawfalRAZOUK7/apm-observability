# Load testing (k6)

A [k6](https://k6.io/) load test that exercises the APM API end-to-end and makes
the observability stack react in real time. It is both a **performance gate**
(thresholds fail the run on regression) and a **demo** (watch the dashboards and
alerts move while it runs).

## What it does

`ingest_and_read.js` ramps virtual users up to 40 over ~3 minutes and, per
iteration:

1. `POST /api/requests/ingest/` — a batch of realistic events (default 50).
2. `GET /api/requests/` — paginated reads.
3. `GET /api/requests/kpis/` — analytics read (200 on TimescaleDB stacks, 501 on
   the SQLite dev DB).

A configurable share of ingested events carry a `5xx` status (`ERROR_RATIO`,
default `0.1`), so the **application error rate rises** and the `HighErrorRate`
alert in `docker/monitoring/prometheus/alert.rules.yml` can move to
`PENDING` → `FIRING`.

## Prerequisites

- A running stack. The quickest path: `make demo` (single-node) which exposes the
  API on `http://localhost:8000`.
- k6 installed: `brew install k6` (macOS) or see https://k6.io/docs/get-started/installation/.

## Run

```bash
# Default: BASE_URL=http://localhost:8000, BATCH=50, ERROR_RATIO=0.1
k6 run loadtest/ingest_and_read.js

# Custom target / heavier load / more errors
BASE_URL=http://localhost:8000 BATCH=100 ERROR_RATIO=0.2 k6 run loadtest/ingest_and_read.js
```

Or via the Makefile:

```bash
make loadtest                     # uses defaults
make loadtest BASE_URL=http://localhost:8000 BATCH=100 ERROR_RATIO=0.2
```

## What to watch while it runs

- **Grafana** (`http://localhost:33000`, single-node): the *APM Timescale SQL*
  and *APM Custom Metrics* dashboards fill up — request rate climbs, error rate
  and P95 latency rise.
- **Prometheus** (`http://localhost:9090/alerts`): `HighErrorRate` and
  `HighRequestLatencyP95` transition to `PENDING`, then `FIRING` if the load is
  sustained.
- **k6 summary** (end of run): p95 latency, failure rate, and the custom
  `apm_events_ingested` counter. The run exits non-zero if any threshold is
  breached — useful as a CI performance gate.

## Thresholds (performance gate)

| Metric | Gate |
| --- | --- |
| `http_req_failed` | rate < 5% |
| `http_req_duration` | p95 < 800 ms |
| `checks` | pass rate > 95% |

Tune the stages and thresholds at the top of `ingest_and_read.js`.
