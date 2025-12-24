# APM Observability (Django + Timescale) — Implementation Plan

This plan is **linear** (no migration branches) and designed to be executed as **one Step per chat**.

---

## Step 0 — Bootstrap & repo

### Objective

* Create a clean repo structure + local dev setup.
* Add Docker services (DB only at this stage) + basic documentation.

### Create/Update

* `README.md` (project goal + run instructions)
* `.gitignore`
* `docker/docker-compose.yml` (TimescaleDB service)
* `docs/PLAN.md` (this file)
* `requirements.txt` (base deps)

### Done when

* `python manage.py runserver` starts locally.
* `docker compose -f docker/docker-compose.yml up -d` starts DB.

### Git

```bash
git add .
git commit -m "chore: bootstrap project structure"
git push
```

---

## Step 1 — Core API (ApiRequest model + CRUD)

### Objective

* Implement `ApiRequest` model + migrations.
* DRF serializer + ViewSet + routes.
* Add basic filtering & ordering.

### Create/Update

* `observability/models.py`
* `observability/serializers.py`
* `observability/views.py`
* `observability/urls.py`
* `apm_platform/urls.py`
* `apm_platform/settings.py` (apps + DRF + DB config)

### Done when

* `POST /api/requests/` works.
* `GET /api/requests/` lists ordered by `-time`.

### Git

```bash
git add .
git commit -m "feat: ApiRequest model + CRUD API"
git push
```

---

## Step 2 — Ingestion endpoint (bulk)

### Objective

* Add `/api/requests/ingest/` to accept a list of events and insert efficiently.
* Validate input, return counts, reject bad payloads cleanly.

### Deliverables

* `/api/requests/ingest/` accepts **either**:

  * raw list payload: `[{...}, {...}]`
  * wrapper payload: `{ "events": [{...}] }`
* Non-strict mode returns counts + error details:

  * `{inserted: X, rejected: Y, errors: [...]}`
* Strict mode: `?strict=true` rejects all on any invalid item (HTTP 400).

### Create/Update

* `observability/serializers.py` (bulk serializer)
* `observability/views.py` (custom action)
* `postman/APM_Observability_Step2.postman_collection.json` (or update)

### Done when

* Can ingest 1000 events in one request.
* Returns `{inserted: X, rejected: Y}` (+ optional errors).

### Git

```bash
git add .
git commit -m "feat: bulk ingestion endpoint"
git push
```

---

## Step 3 — Timescale hypertable + hourly continuous aggregate

### Objective

* Convert `observability_apirequest` table into a hypertable.
* Create `apirequest_hourly` continuous aggregate (grouped by service+endpoint).
* Add refresh policy + optional manual refresh command.
* Add `/api/requests/hourly/` endpoint.

### Create/Update

* `observability/migrations/0002_timescale.py` (or next linear number): hypertable + hourly CAGG SQL
* `observability/management/commands/refresh_apirequest_hourly.py` (optional)
* `observability/views.py` (hourly action)
* `README.md` (hourly usage)

### Done when

* `/api/requests/hourly/` returns hourly rows for a seeded dataset.

### Git

```bash
git add .
git commit -m "feat: timescale hypertable + hourly continuous aggregate"
git push
```

---

## Step 4 — Daily continuous aggregate + endpoint analytics

### Objective

* Add `apirequest_daily` continuous aggregate (day + service + endpoint).
* Add refresh policy + optional manual refresh command.
* Add `/api/requests/daily/` endpoint.

### Create/Update

* `observability/migrations/0003_daily_cagg.py` (or next linear number)
* `observability/management/commands/refresh_apirequest_daily.py` (optional)
* `observability/views.py` (daily action)
* `README.md` (daily usage)

### Done when

* `/api/requests/daily/` returns correct daily buckets.

### Git

```bash
git add .
git commit -m "feat: daily continuous aggregate + daily analytics endpoint"
git push
```

---

## Step 5 — Filters + KPIs (p95, error-rate, top endpoints)

### Objective

* Expand list filters (service, endpoint, method, status codes, time range, latency range, trace_id, user_ref).
* Add dashboard endpoints:

  * `/api/requests/kpis/`
  * `/api/requests/top-endpoints/`
* Implement fast-path via CAGGs when possible and raw fallback when required.
* Compute p95 accurately from raw using `percentile_cont`.

### Create/Update

* `observability/filters.py`
* `observability/views.py`
* `README.md` (params tables + curl examples)

### Done when

* `/api/requests/kpis/` returns hits/errors/error_rate/avg/max/p95.
* `/api/requests/top-endpoints/` supports sorting/limit/with_p95.

### Git

```bash
git add .
git commit -m "feat: kpis + top endpoints analytics"
git push
```

---

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

  * `observability/tests/test_filters.py`

* **Ingestion tests**

  * `observability/tests/test_ingest_valid.py`
  * `observability/tests/test_ingest_mixed_non_strict.py`
  * `observability/tests/test_ingest_strict.py`

* **Analytics tests (auto-skip if not supported)**

  * `observability/tests/test_hourly.py` (skip if not PostgreSQL or hourly view missing)
  * `observability/tests/test_daily.py` (skip if not PostgreSQL or daily view missing)
  * `observability/tests/test_kpis.py` (skip if not PostgreSQL)
  * `observability/tests/test_top_endpoints.py` (skip if not PostgreSQL)

* **Step 6 runner script**

  * `scripts/step6_test.sh`
  * Checks pending migrations (`makemigrations --check`), runs migrations, runs tests, logs to `reports/step6_tests.log`

* **Developer ergonomics**

  * Optional `Makefile` target: `make test` (and optionally `make step6`, `make migrate`)

* **Documentation**

  * `README.md` includes how to run Django tests and Step 6 runner.

### Acceptance criteria

* `python manage.py test` runs and discovers tests.
* `./scripts/step6_test.sh` passes:

  * no pending migrations
  * migrations apply
  * full test suite passes
* Analytics tests skip cleanly when DB is not PostgreSQL/Timescale or views are missing.

### Git

```bash
git add .
git commit -m "test: add test suite + step6 runner"
git push
```

---

## Step 7 — Docker/Deploy + docs

### Objective

* Provide a production-style Docker setup (web + db).
* Add deployment notes and env configuration guidance.
* Improve docs so anyone can run, test, and deploy quickly.

### Deliverables

#### A) Docker (web + db)

* `Dockerfile` (Gunicorn)
* `.dockerignore`
* `docker/docker-compose.yml` (services: `db` + `web`)
* `docker/entrypoint.sh`:

  * wait for DB
  * `python manage.py migrate --noinput`
  * `python manage.py collectstatic --noinput`
  * start `gunicorn apm_platform.wsgi:application`

#### B) Django settings for deploy

* `apm_platform/settings.py` updates:

  * WhiteNoise support (`whitenoise.runserver_nostatic`, middleware)
  * `STATIC_ROOT` + static storage (manifest compressed)
  * `DEBUG` from env (`DJANGO_DEBUG`)
  * `ALLOWED_HOSTS` from env (`DJANGO_ALLOWED_HOSTS`)
  * Postgres from env + optional `DB_SSLMODE`

#### C) Health endpoint

* `GET /api/health/` returns `{status: "ok"}`
* Optional `GET /api/health/?db=1` checks DB connectivity

#### D) Documentation

* `.env.example` (no secrets)
* `README.md` additions:

  * Docker run instructions
  * env vars table
  * health endpoint
  * how to run tests/scripts inside Docker
* `docs/DEPLOY.md`:

  * Local Docker
  * Deploy options (Render / Railway / Fly.io / VM)
  * Required env vars
  * Timescale notes + migrations

#### E) Optional (recommended)

* `.github/workflows/tests.yml` to run tests on push/PR
* `Makefile` shortcuts (`up`, `down`, `logs`, `test`, `migrate`)

### Acceptance criteria

* `docker compose -f docker/docker-compose.yml up --build` starts `db` + `web`.
* Opening `/api/health/` returns OK.
* `docker compose ... exec web python manage.py test` works.

### Git

```bash
git add .
git commit -m "feat: docker deploy setup + docs"
git push
```
