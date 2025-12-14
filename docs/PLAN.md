# APM Observability (Django + Timescale) — Implementation Plan

## Step 0 — Bootstrap & repo

* Clean repo structure, venv, dependencies
* Docker Compose: TimescaleDB
* Base settings and run instructions

## Step 1 — Core API (ApiRequest model + CRUD)

* ApiRequest model + migrations
* DRF serializer + ViewSet + routes
* Basic filtering & ordering

## Step 2 — Ingestion endpoint (bulk)

* `/api/requests/ingest/` accepts a list of events (raw list or `{events: [...]}` wrapper)
* Validate + insert efficiently using `bulk_create`
* Returns `{inserted: X, rejected: Y, errors: [...]}`
* Strict mode: `?strict=true` rejects all if any invalid

## Step 3 — Timescale hypertable + hourly continuous aggregate

* Convert `observability_apirequest` table to hypertable (Timescale)
* Create hourly continuous aggregate (service + endpoint)
* Add refresh policy (and optional manual refresh command)
* `/api/requests/hourly/` endpoint

## Step 4 — Daily continuous aggregate + endpoint analytics

* Create daily continuous aggregate (service + endpoint)
* Add refresh policy (and optional manual refresh command)
* `/api/requests/daily/` endpoint

## Step 5 — Filters + KPIs

* Expand list filters (service, endpoint, method, status codes, time range, latency range, trace_id, user_ref)
* KPI endpoint: `/api/requests/kpis/` (hits, errors, error_rate, avg, max, p95)
* Top endpoints endpoint: `/api/requests/top-endpoints/` (sorting, limit, optional p95)
* Fast-path via caggs when possible, raw fallback when required

## Step 6 — Tests + quality

### Objective

* Add a reliable automated test suite for CRUD, filters, ingestion, and analytics.
* Ensure migrations stay clean and linear (no drift between `models.py` and migrations).
* Keep the project easy to verify for anyone cloning the repo.

### Deliverables

* **Tests package structure**

  * `observability/tests/__init__.py`
  * Move legacy tests into `observability/tests/`

* **Shared test helpers**

  * `observability/tests/utils.py` with helpers like `make_event()`, `make_events(n)`, `post_ingest(...)`

* **CRUD tests**

  * `observability/tests/test_crud.py` (POST/GET list/GET detail/PATCH/PUT/DELETE)
  * Includes default ordering assertion (`-time`)

* **Filters + search tests**

  * `observability/tests/test_filters.py` (service/endpoint/method/status_code/time range/ordering/search if enabled)

* **Ingestion tests**

  * `observability/tests/test_ingest_valid.py`
  * `observability/tests/test_ingest_mixed_non_strict.py`
  * `observability/tests/test_ingest_strict.py`

* **Analytics tests (auto-skip if not supported)**

  * `observability/tests/test_hourly.py` (skip if not PostgreSQL or if hourly view missing)
  * `observability/tests/test_daily.py` (skip if not PostgreSQL or if daily view missing)
  * `observability/tests/test_kpis.py` (skip if not PostgreSQL)
  * `observability/tests/test_top_endpoints.py` (skip if not PostgreSQL)

* **Step 6 runner script**

  * `scripts/step6_test.sh`
  * Checks pending migrations (`makemigrations --check`), runs migrations, runs tests, logs to `reports/step6_tests.log`

* **Developer ergonomics**

  * `Makefile`: add `make test` (and optionally `make step6`, `make migrate`, etc.)

* **Documentation**

  * `README.md`: explain how to run Django tests, Step 6 runner, and Postgres/Timescale notes
  * `docs/PLAN.md`: document Step 6 objective and deliverables (this section)

### Acceptance criteria

* `python manage.py test` runs and discovers tests.
* `./scripts/step6_test.sh` passes:

  * no pending migrations
  * migrations apply
  * test suite passes
* Analytics tests auto-skip cleanly when DB is not PostgreSQL/Timescale or views are missing.

## Step 7 — Docker/Deploy + docs

* Production Dockerfile + Compose (app + db)
* Deployment notes (env vars, migrations, Timescale requirements)
* Docs cleanup + Postman collection finalized
