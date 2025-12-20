# APM Observability (Django + Timescale)

Backend API to store API request logs (service, endpoint, latency, status codes) and expose analytics endpoints (hourly/daily aggregates with TimescaleDB) + KPI endpoints for dashboards.

## Stack

- Django
- Django REST Framework
- django-filter
- PostgreSQL + TimescaleDB (hypertable + continuous aggregates)
- Docker Compose (web + DB)
- Postman + Newman (smoke tests)

## Project structure (high level)

- `apm_platform/` — Django project settings + root URLs
- `observability/` — app: model, serializers, views, filters, tests, migrations
- `docker/` — Docker + docker compose
- `postman/` — Postman collections + environments
- `scripts/` — test runner scripts
- `reports/` — generated test reports (Newman / Step 6 logs)

---

## Quick start (local, without Docker)

### 1) Create virtualenv + install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure DB

#### Option A — Docker DB only

```bash
docker compose -f docker/docker-compose.yml up -d db
```

#### Option B — Local Postgres

Update your Postgres env vars (see below) or update your `apm_platform/settings.py` accordingly.

### 3) Load env (important for Postgres/Timescale)

If your project uses a `.env` for Postgres credentials, load it before running Django commands:

```bash
set -a
source .env
set +a
```

### 4) Run migrations + start server

```bash
python manage.py migrate
python manage.py runserver
```

API base: `http://127.0.0.1:8000`

---

## Docker (recommended)

This project ships with a production-style Docker setup:

- **TimescaleDB** container (`db`)
- **Django + Gunicorn + WhiteNoise** container (`web`)

### 1) Create `.env`

Copy the example and edit as needed:

```bash
cp .env.example .env
```

### 2) Build + run

```bash
docker compose -f docker/docker-compose.yml up --build
```

Open:

- API: `http://127.0.0.1:8000/api/`
- Health: `http://127.0.0.1:8000/api/health/`

### 3) Useful Docker commands

```bash
# Stop
docker compose -f docker/docker-compose.yml down

# Rebuild
docker compose -f docker/docker-compose.yml up --build

# Tail logs
docker compose -f docker/docker-compose.yml logs -f web

# Run a Django command inside the container
docker compose -f docker/docker-compose.yml exec web python manage.py migrate
```

## Dependencies & rebuild (Docker)

- **If a runtime binary is missing in the `web` container (example: `gunicorn: not found`)**:
  - Ensure the dependency is listed in `requirements.txt` (e.g. add `gunicorn`).
  - Rebuild the `web` image and restart the service:

```bash
docker compose -f docker/docker-compose.yml up -d --build web
```

This installs Python deps into the image layers so the entrypoint can `exec` the server process.

## Troubleshooting (quick checks)

- If `curl http://127.0.0.1:8000/api/health/` fails locally:
  - Run `docker compose -f docker/docker-compose.yml ps` to see container statuses.
  - Inspect `web` logs for startup errors:

```bash
docker compose -f docker/docker-compose.yml logs web --tail 200
```

- Common startup error: `exec: gunicorn: not found` — fix by adding `gunicorn` to `requirements.txt` and rebuilding the image (see above).

---

## Environment variables

The settings are **env-first**. If the following are set, Django will use PostgreSQL:

| Variable               |               Example | Required | Notes                                             |
| ---------------------- | --------------------: | :------: | ------------------------------------------------- |
| `DJANGO_DEBUG`         |                   `0` |    ✅    | `1` enables debug mode                            |
| `DJANGO_SECRET_KEY`    |           `change-me` |    ✅    | Must be secret in production                      |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` |    ✅    | Comma-separated                                   |
| `POSTGRES_HOST`        |                  `db` |    ✅    | In Docker, use `db`                               |
| `POSTGRES_PORT`        |                `5432` |    ✅    |                                                   |
| `POSTGRES_DB`          |                 `apm` |    ✅    |                                                   |
| `POSTGRES_USER`        |                 `apm` |    ✅    |                                                   |
| `POSTGRES_PASSWORD`    |                 `apm` |    ✅    |                                                   |
| `DB_SSLMODE`           |             `disable` |    ❌    | For hosted Postgres: `require`, `verify-ca`, etc. |
| `FORCE_SQLITE`         |                   `0` |    ❌    | `1` forces SQLite even if Postgres vars exist     |
| `DRF_PAGE_SIZE`        |                  `50` |    ❌    | Default list page size                            |
| `WEB_PORT`             |                `8000` |    ❌    | Host port when using Docker compose               |

---

## Health endpoint

### `GET /api/health/`

Returns:

```json
{ "status": "ok" }
```

### Optional DB check

```bash
curl -s "http://127.0.0.1:8000/api/health/?db=1"
```

Returns:

```json
{ "status": "ok", "db": "ok" }
```

If DB is down, returns **503**.

---

## Database notes (Postgres / Timescale)

This project supports:

- **PostgreSQL + TimescaleDB** (recommended) — enables hypertables, continuous aggregates (`hourly`, `daily`) and fast analytics.
- **Plain PostgreSQL** — KPI endpoints still work (raw queries + `percentile_cont`), but Timescale-specific features are unavailable.
- **SQLite** — supported as a **fallback** for local dev and basic CRUD/ingest tests. Analytics endpoints that require Postgres/Timescale may return 501/503 or be skipped in tests.

Optional:

- `POSTGRES_TEST_DB` (defaults to `${POSTGRES_DB}_test`)

---

## API Endpoints

### CRUD (Step 1)

Base endpoint:

- `GET /api/requests/` list (default ordered by `-time`)
- `POST /api/requests/` create
- `GET /api/requests/{id}/` retrieve
- `PUT/PATCH /api/requests/{id}/` update
- `DELETE /api/requests/{id}/` delete

Filtering (examples):

- `?service=billing`
- `?endpoint=/api/v1/invoices`
- `?method=GET`
- `?status_code=200`
- `?status_code__in=200,201,204`
- `?time_after=2025-12-01T00:00:00Z&time_before=2025-12-31T23:59:59Z`
- `?latency_min=0&latency_max=250`
- `?trace_id=abc123`
- `?user_ref=user-001`

Ordering:

- `?ordering=-time`
- `?ordering=latency_ms`

Search:

- `?search=billing`

---

## Step 2 — Bulk ingestion

### Endpoint

`POST /api/requests/ingest/`

Accepts **either**:

#### 1) Raw list payload

```json
[
  {
    "time": "2025-12-14T12:00:00Z",
    "service": "billing",
    "endpoint": "/api/v1/invoices",
    "method": "GET",
    "status_code": 200,
    "latency_ms": 123,
    "trace_id": "trace-001",
    "user_ref": "user-001",
    "tags": { "env": "prod" }
  }
]
```

#### 2) Wrapper payload

```json
{
  "events": [
    {
      "time": "2025-12-14T12:00:00Z",
      "service": "billing",
      "endpoint": "/api/v1/invoices",
      "method": "GET",
      "status_code": 200,
      "latency_ms": 123,
      "trace_id": "trace-001",
      "user_ref": "user-001",
      "tags": { "env": "prod" }
    }
  ]
}
```

### Response

```json
{
  "inserted": 10,
  "rejected": 2,
  "errors": [
    {
      "index": 3,
      "errors": {
        "status_code": ["status_code must be a valid HTTP status (100..599)."]
      }
    }
  ]
}
```

### Limits & query params

- `batch_size` (default: `settings.APM_INGEST_BATCH_SIZE`)
- `max_events` (default: `settings.APM_INGEST_MAX_EVENTS`) → returns **413** if exceeded
- `max_errors` (default: `settings.APM_INGEST_MAX_ERRORS`) → use `max_errors=0` for counts only
- `strict=true` (optional) → if payload has invalid items, returns **400** and inserts **nothing**

---

## Step 3 — Hourly analytics (Timescale CAGG)

### Endpoint

`GET /api/requests/hourly/`

### Query params

- `start` (ISO datetime/date) optional (default: `end - 24h`)
- `end` (ISO datetime/date) optional (default: `now`)
- `service` optional
- `endpoint` optional
- `limit` optional (default 500, max 5000)

### cURL examples

Last 24 hours:

```bash
curl -s "http://127.0.0.1:8000/api/requests/hourly/?limit=50"
```

With time window:

```bash
curl -s "http://127.0.0.1:8000/api/requests/hourly/?start=2025-12-10&end=2025-12-14&limit=200"
```

---

## Step 4 — Daily analytics (Timescale CAGG)

### Endpoint

`GET /api/requests/daily/`

### Query params

- `start` (ISO datetime OR ISO date) optional
  Examples: `2025-12-01T00:00:00Z` or `2025-12-01`
- `end` (ISO datetime OR ISO date) optional
  Examples: `2025-12-14T23:59:59Z` or `2025-12-14`
- `service` (string) optional
- `endpoint` (string) optional
- `limit` (int) optional (default 500, max 5000)

**Defaults**

- If `end` missing → now (UTC)
- If `start` missing → `end - 7 days`

### cURL examples

Daily — last 7 days:

```bash
curl -s "http://127.0.0.1:8000/api/requests/daily/?limit=50"
```

Daily — date-only range:

```bash
curl -s "http://127.0.0.1:8000/api/requests/daily/?start=2025-12-01&end=2025-12-14&limit=200"
```

Daily — filtered:

```bash
curl -s "http://127.0.0.1:8000/api/requests/daily/?service=api&endpoint=/health&limit=100"
```

---

## Step 5 — KPIs + Top endpoints (dashboards)

These endpoints are designed for dashboard widgets.

- They use **Timescale CAGGs** (hourly/daily) when possible for fast totals.
- They **fallback to raw** when needed (e.g. `method` filter or custom `error_from`).
- `p95` is computed from **raw** using `percentile_cont` for correctness.

> **Requires PostgreSQL.** TimescaleDB is recommended (for fast-path), but raw fallback still works on plain PostgreSQL.

### 5.1) `GET /api/requests/kpis/`

Returns overall KPIs over a time window.

#### Response

```json
{
  "hits": 123,
  "errors": 7,
  "error_rate": 0.0569,
  "avg_latency_ms": 42.7,
  "p95_latency_ms": 120.0,
  "max_latency_ms": 411,
  "source": "hourly"
}
```

`source` is one of: `hourly`, `daily`, `raw`.

#### Query params

| Param         | Type              | Default     | Notes                                             |
| ------------- | ----------------- | ----------- | ------------------------------------------------- | ------ | --------------------------------------------------- |
| `start`       | ISO datetime/date | `end - 24h` | Examples: `2025-12-14T10:00:00Z` or `2025-12-14`  |
| `end`         | ISO datetime/date | `now`       | Date-only end uses end-of-day                     |
| `service`     | string            | —           | Exact match                                       |
| `endpoint`    | string            | —           | Exact match                                       |
| `method`      | string            | —           | **Forces raw path** (CAGGs do not include method) |
| `error_from`  | int               | `500`       | If not 500, **forces raw path**                   |
| `granularity` | `auto`            | `hourly`    | `daily`                                           | `auto` | When `auto`: small ranges → hourly, otherwise daily |

#### cURL examples

Default (last 24h):

```bash
curl -s "http://127.0.0.1:8000/api/requests/kpis/" | python -m json.tool
```

Filtered by service + endpoint:

```bash
curl -s "http://127.0.0.1:8000/api/requests/kpis/?service=api&endpoint=/orders" | python -m json.tool
```

Force hourly totals:

```bash
curl -s "http://127.0.0.1:8000/api/requests/kpis/?granularity=hourly" | python -m json.tool
```

Raw path (method filter):

```bash
curl -s "http://127.0.0.1:8000/api/requests/kpis/?service=api&method=GET" | python -m json.tool
```

Custom error threshold (raw path):

```bash
curl -s "http://127.0.0.1:8000/api/requests/kpis/?error_from=400" | python -m json.tool
```

---

### 5.2) `GET /api/requests/top-endpoints/`

Returns ranked endpoints with metrics.

#### Response (list)

```json
[
  {
    "service": "api",
    "endpoint": "/orders",
    "hits": 900,
    "errors": 12,
    "error_rate": 0.0133,
    "avg_latency_ms": 35.2,
    "p95_latency_ms": 120.0,
    "max_latency_ms": 410
  }
]
```

#### Query params

| Param         | Type              | Default     | Notes                                                                                |
| ------------- | ----------------- | ----------- | ------------------------------------------------------------------------------------ | -------------- | ------------------------------ |
| `start`       | ISO datetime/date | `end - 24h` | Time window                                                                          |
| `end`         | ISO datetime/date | `now`       | Time window                                                                          |
| `service`     | string            | —           | Filter rows                                                                          |
| `endpoint`    | string            | —           | Filter rows                                                                          |
| `method`      | string            | —           | **Forces raw**                                                                       |
| `error_from`  | int               | `500`       | If not 500, **forces raw**                                                           |
| `granularity` | `auto`            | `hourly`    | `daily`                                                                              | `auto`         | Used when fast-path is allowed |
| `limit`       | int               | `20`        | Max `200`                                                                            |
| `sort_by`     | string            | `hits`      | `hits`, `errors`, `error_rate`, `avg_latency_ms`, `max_latency_ms`, `p95_latency_ms` |
| `direction`   | `asc`             | `desc`      | `desc`                                                                               | Sort direction |
| `with_p95`    | bool              | `false`     | If true: computes p95 per returned endpoint (raw query)                              |

#### Notes

- Sorting by `p95_latency_ms` requires raw mode (heavier).
- When using CAGG fast-path, `with_p95=true` computes p95 only for the returned endpoints (not for the whole table).

#### cURL examples

Top endpoints by hits:

```bash
curl -s "http://127.0.0.1:8000/api/requests/top-endpoints/?limit=10&sort_by=hits&direction=desc" | python -m json.tool
```

Top endpoints by error rate:

```bash
curl -s "http://127.0.0.1:8000/api/requests/top-endpoints/?limit=10&sort_by=error_rate&direction=desc" | python -m json.tool
```

Include p95 per endpoint:

```bash
curl -s "http://127.0.0.1:8000/api/requests/top-endpoints/?limit=10&with_p95=true" | python -m json.tool
```

Force raw (method filter):

```bash
curl -s "http://127.0.0.1:8000/api/requests/top-endpoints/?method=GET&limit=10" | python -m json.tool
```

---

## Management commands

### Refresh daily CAGG manually (Step 4)

```bash
python manage.py refresh_apirequest_daily
```

Optional window:

```bash
python manage.py refresh_apirequest_daily --start 2025-12-01 --end 2025-12-14
```

> This requires PostgreSQL + TimescaleDB and the `apirequest_daily` view to exist (Step 4 migrations applied).

---

## Running tests (Step 6)

### Without Docker

Run the whole test suite:

```bash
python manage.py test
```

Or using Makefile (if you add it):

```bash
make test
```

Step 6 strict runner (writes logs to `reports/step6_tests.log`):

```bash
chmod +x scripts/step6_test.sh
./scripts/step6_test.sh
```

### Lint / format (optional)

```bash
# Ruff (lint)
ruff check .

# Ruff autofix + import sort
ruff check . --fix

# Black (format)
black .
```

### In Docker

```bash
# Run Django tests inside the container
docker compose -f docker/docker-compose.yml exec web python manage.py test

# Run the Step 6 runner inside the container
docker compose -f docker/docker-compose.yml exec web bash -lc "chmod +x scripts/step6_test.sh && ./scripts/step6_test.sh"

# Run any Step script (example: Step 4)
docker compose -f docker/docker-compose.yml exec web bash -lc "chmod +x scripts/step4_test.sh && ./scripts/step4_test.sh"
```

### Notes about database support in tests

- Tests that require PostgreSQL / Timescale (e.g. p95 via `percentile_cont`, or caggs/views) will **auto-skip** when the DB is not PostgreSQL.
- Hourly/Daily endpoint tests will also auto-skip if the underlying Timescale views are missing.

---

## Newman (Postman) tests

1. Install:

```bash
npm install -g newman newman-reporter-htmlextra
```

2. Run scripts:

Step 2:

```bash
chmod +x scripts/step2_test.sh
./scripts/step2_test.sh
```

Step 3:

```bash
chmod +x scripts/step3_test.sh
./scripts/step3_test.sh
```

Step 4 (daily):

```bash
set -a
source .env
set +a

chmod +x scripts/step4_test.sh
./scripts/step4_test.sh
```

Step 5 (KPIs + Top endpoints):

```bash
set -a
source .env
set +a

chmod +x scripts/step5_test.sh
./scripts/step5_test.sh
```

Reports are generated in `reports/`.

---

## Troubleshooting

### Why do I see vendor=sqlite but later vendor=postgresql?

Usually because **the Django server process** was started **without** your Postgres env loaded, so it connected to SQLite.
Even if your _current shell_ has Postgres env, the already-running server may still be using SQLite.

Fix:

1. Stop any running server (Ctrl+C), then:

```bash
set -a
source .env
set +a
python manage.py runserver
```

### Daily/KPIs/Top endpoints return 501

That means analytics are not available because you’re not using Postgres/Timescale (often SQLite).
Load `.env` and restart the server (see above).

### Daily/Hourly endpoints return 503 (relation/view missing)

That usually means the Timescale view does not exist yet. Ensure:

- You are connected to Postgres
- Step migrations are applied:

```bash
python manage.py migrate
```

---

## Roadmap

- Step 6+: more tests + CI
- Step 7+: deploy docs + Docker improvements
