# APM Observability (Django + Timescale)

Backend API to store API request logs (service, endpoint, latency, status codes) and expose analytics endpoints (hourly/daily aggregates with TimescaleDB).

## Stack

* Django
* Django REST Framework
* django-filter
* PostgreSQL + TimescaleDB (hypertable + continuous aggregates)
* Docker Compose (optional for DB)
* Postman + Newman (smoke tests)

## Project structure (high level)

* `apm_platform/` — Django project settings + root URLs
* `observability/` — app: model, serializers, views, filters, tests, migrations
* `docker/` — docker compose (db services)
* `postman/` — Postman collections + environments
* `scripts/` — test runner scripts (Newman)
* `reports/` — generated test reports (Newman)

---

## Quick start (local)

### 1) Create virtualenv + install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure DB

#### Option A — Docker DB (recommended)

```bash
docker compose -f docker/docker-compose.yml up -d
```

#### Option B — Local Postgres

Update your `apm_platform/settings.py` database settings accordingly.

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

## API Endpoints

### CRUD (Step 1)

Base endpoint:

* `GET /api/requests/` list (default ordered by `-time`)
* `POST /api/requests/` create
* `GET /api/requests/{id}/` retrieve
* `PUT/PATCH /api/requests/{id}/` update
* `DELETE /api/requests/{id}/` delete

Filtering (examples):

* `?service=billing`
* `?endpoint=/api/v1/invoices`
* `?method=GET`
* `?status_code=200`
* `?status_code__in=200,201,204`
* `?time_after=2025-12-01T00:00:00Z&time_before=2025-12-31T23:59:59Z`
* `?latency_min=0&latency_max=250`
* `?trace_id=abc123`
* `?user_ref=user-001`

Ordering:

* `?ordering=-time`
* `?ordering=latency_ms`

Search:

* `?search=billing`

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
    "tags": {"env": "prod"}
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
      "tags": {"env": "prod"}
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
    { "index": 3, "errors": { "status_code": ["status_code must be a valid HTTP status (100..599)."] } }
  ]
}
```

### Limits & query params

* `batch_size` (default: `settings.APM_INGEST_BATCH_SIZE`)
* `max_events` (default: `settings.APM_INGEST_MAX_EVENTS`) → returns **413** if exceeded
* `max_errors` (default: `settings.APM_INGEST_MAX_ERRORS`) → use `max_errors=0` for counts only
* `strict=true` (optional) → if payload has invalid items, returns **400** and inserts **nothing**

---

## Step 3 — Hourly analytics (Timescale CAGG)

### Endpoint

`GET /api/requests/hourly/`

### Query params

* `start` (ISO datetime/date) optional (default: `end - 24h`)
* `end` (ISO datetime/date) optional (default: `now`)
* `service` optional
* `endpoint` optional
* `limit` optional (default 500, max 5000)

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

* `start` (ISO datetime OR ISO date) optional
  Examples: `2025-12-01T00:00:00Z` or `2025-12-01`
* `end` (ISO datetime OR ISO date) optional
  Examples: `2025-12-14T23:59:59Z` or `2025-12-14`
* `service` (string) optional
* `endpoint` (string) optional
* `limit` (int) optional (default 500, max 5000)

**Defaults**

* If `end` missing → now (UTC)
* If `start` missing → `end - 7 days`

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

## Running tests

### Django tests

```bash
python manage.py test
```

### Newman (Postman) tests

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

Reports are generated in `reports/`.

---

## Troubleshooting

### Why do I see vendor=sqlite but later vendor=postgresql?

Usually because **the Django server process** was started **without** your Postgres env loaded, so it connected to SQLite.
Even if your *current shell* has Postgres env, the already-running server may still be using SQLite.

Fix:

1. Stop any running server (Ctrl+C), then:

```bash
set -a
source .env
set +a
python manage.py runserver
```

### Daily endpoint returns 501

That means analytics are not available because you’re not using Postgres/Timescale (often SQLite).
Load `.env` and restart the server (see above).

### Daily endpoint returns 503 (relation/view missing)

That usually means the Timescale view does not exist yet. Ensure:

* You are connected to Postgres
* Step 4 migration is applied:

```bash
python manage.py migrate
```

---

## Roadmap

* Step 5+: KPI endpoints (p95, error rate, top endpoints), filters, and dashboards support
