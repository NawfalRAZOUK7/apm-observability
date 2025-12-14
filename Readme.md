# APM Observability (Django + Timescale)

Backend API to store API request logs (service, endpoint, latency, status codes) and expose analytics endpoints later (hourly/daily aggregates with TimescaleDB).

## Stack
- Django
- Django REST Framework
- django-filter
- PostgreSQL / TimescaleDB (later steps)
- Docker Compose (optional for DB)

## Project structure (high level)
- `apm_platform/` — Django project settings + root URLs
- `observability/` — app: model, serializers, views, filters, tests
- `docker/` — docker compose (db services)
- `postman/` — Postman collections + environments
- `scripts/` — test runner scripts (Newman)

---

## Quick start (local)

### 1) Create virtualenv + install deps
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure DB
You can run with a local Postgres, or via Docker (recommended).

#### Option A — Docker DB (recommended)
```bash
docker compose -f docker/docker-compose.yml up -d
```

#### Option B — Local Postgres
Update your `apm_platform/settings.py` database settings accordingly.

### 3) Run migrations + start server
```bash
python manage.py migrate
python manage.py runserver
```

API base: `http://127.0.0.1:8000`

---

## API Endpoints (current)

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
Returns counts and (optionally) per-item validation errors:

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
The endpoint supports these query params:

- `batch_size` (default: `settings.APM_INGEST_BATCH_SIZE`)
  - Controls Django `bulk_create()` batching.
- `max_events` (default: `settings.APM_INGEST_MAX_EVENTS`)
  - Maximum number of events accepted per request.
  - If exceeded, returns **413 Payload Too Large**.
- `max_errors` (default: `settings.APM_INGEST_MAX_ERRORS`)
  - Maximum number of error details returned in response.
  - You can set `max_errors=0` to return only counts.

> Query params are allowed but cannot exceed server defaults defined in settings.

### cURL examples

#### Raw list
```bash
curl -s -X POST "http://127.0.0.1:8000/api/requests/ingest/?batch_size=1000&max_errors=25" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "time": "2025-12-14T12:00:00Z",
      "service": "billing",
      "endpoint": "/api/v1/invoices",
      "method": "GET",
      "status_code": 200,
      "latency_ms": 123,
      "trace_id": "trace-001",
      "user_ref": "user-001",
      "tags": {"env": "test"}
    }
  ]'
```

#### Wrapper
```bash
curl -s -X POST "http://127.0.0.1:8000/api/requests/ingest/?max_events=50000" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "time": "2025-12-14T12:00:00Z",
        "service": "auth",
        "endpoint": "/api/v1/login",
        "method": "POST",
        "status_code": 200,
        "latency_ms": 80,
        "trace_id": "trace-002",
        "user_ref": "user-002",
        "tags": {"env": "test"}
      }
    ]
  }'
```

---

## Running tests

### Django tests
```bash
python manage.py test
```

### Newman (Postman) tests
1) Install:
```bash
npm install -g newman newman-reporter-htmlextra
```

2) Run Step 2 test script:
```bash
chmod +x scripts/step2_test.sh
./scripts/step2_test.sh
```

Reports are generated in `reports/`.

---

## Next steps (planned)
- Step 3: Convert table to Timescale hypertable + hourly continuous aggregate + `/api/requests/hourly/`
- Step 4: Daily continuous aggregate + `/api/requests/daily/`
- Step 5+: KPI endpoints (p95, error rate, top endpoints), filters, and dashboards support

