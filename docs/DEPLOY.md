# Deploy guide — APM Observability (Django + Timescale)

This document explains how to run the project with Docker locally and how to deploy it to common platforms.

> Scope: backend API only (Django + DRF) with PostgreSQL/TimescaleDB.

---

## 1) Local Docker (recommended)

### 1.1 Prerequisites

* Docker + Docker Compose
* A `.env` file at the project root

### 1.2 Create `.env`

```bash
cp .env.example .env
```

Minimum recommended values:

```dotenv
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=apm
POSTGRES_USER=apm
POSTGRES_PASSWORD=apm

DB_SSLMODE=disable
WEB_PORT=8000
```

### 1.3 Build & run

```bash
docker compose -f docker/docker-compose.yml up --build
```

What happens on startup:

* `docker/entrypoint.sh` waits for DB, runs `migrate`, runs `collectstatic`, then starts Gunicorn.

### 1.4 Useful commands

```bash
# Stop and remove containers (keep DB volume)
docker compose -f docker/docker-compose.yml down

# Stop and remove containers + delete DB data (DANGEROUS)
docker compose -f docker/docker-compose.yml down -v

# Tail API logs
docker compose -f docker/docker-compose.yml logs -f web

# Run Django command inside web container
docker compose -f docker/docker-compose.yml exec web python manage.py migrate
```

Health check:

* `GET /api/health/` returns `{ "status": "ok" }`
* `GET /api/health/?db=1` checks DB connectivity

---

## 2) Required environment variables

These are the variables expected by `apm_platform/settings.py` (env-first).

### 2.1 Django

| Variable               |           Example | Required | Notes                 |
| ---------------------- | ----------------: | :------: | --------------------- |
| `DJANGO_DEBUG`         |               `0` |     ✅    | Use `0` in production |
| `DJANGO_SECRET_KEY`    |     `long-random` |     ✅    | Must be secret        |
| `DJANGO_ALLOWED_HOSTS` | `your-domain.com` |     ✅    | Comma-separated       |
| `DJANGO_TIME_ZONE`     |             `UTC` |     ❌    | Defaults to `UTC`     |

### 2.2 Database (Postgres/Timescale)

| Variable            |                 Example | Required | Notes                                          |
| ------------------- | ----------------------: | :------: | ---------------------------------------------- |
| `POSTGRES_HOST`     | `db` or hosted hostname |     ✅    | In Docker compose: `db`                        |
| `POSTGRES_PORT`     |                  `5432` |     ✅    |                                                |
| `POSTGRES_DB`       |                   `apm` |     ✅    |                                                |
| `POSTGRES_USER`     |                   `apm` |     ✅    |                                                |
| `POSTGRES_PASSWORD` |                   `...` |     ✅    |                                                |
| `DB_SSLMODE`        |   `disable` / `require` |     ❌    | Useful for hosted Postgres                     |
| `DB_CONN_MAX_AGE`   |                    `60` |     ❌    | Connection reuse (seconds)                     |
| `FORCE_SQLITE`      |                     `0` |     ❌    | `1` forces SQLite (not recommended for deploy) |

### 2.3 Optional runtime

| Variable           |        Example | Required | Notes                          |
| ------------------ | -------------: | :------: | ------------------------------ |
| `WEB_PORT`         |         `8000` |     ❌    | Used by Docker compose         |
| `GUNICORN_WORKERS` |            `3` |     ❌    | Used by `docker/entrypoint.sh` |
| `GUNICORN_TIMEOUT` |           `60` |     ❌    | Used by `docker/entrypoint.sh` |
| `GUNICORN_BIND`    | `0.0.0.0:8000` |     ❌    | Used by `docker/entrypoint.sh` |

---

## 3) TimescaleDB notes (hypertables + continuous aggregates)

### 3.1 What Timescale is used for

* Convert the raw table into a **hypertable** for time-based partitioning.
* Create **continuous aggregates (CAGGs)**:

  * `apirequest_hourly` — hourly buckets
  * `apirequest_daily` — daily buckets

### 3.2 Migrations

Your project creates Timescale objects using Django migrations (SQL via `RunSQL`).

Important notes:

* You must deploy against **PostgreSQL + TimescaleDB** if you want hourly/daily endpoints to work.
* If you deploy on plain Postgres (no Timescale extension), the CAGG migrations may fail.

Recommended approach:

* For production: use a DB that supports TimescaleDB.
* For non-Timescale Postgres: keep CRUD/ingest/KPIs (raw) working, but expect `/hourly/` and `/daily/` to be unavailable.

### 3.3 Refresh policies

Continuous aggregates can be refreshed automatically if your migrations created policies.

If you need to refresh manually (debug):

```bash
python manage.py refresh_apirequest_hourly
python manage.py refresh_apirequest_daily
```

---

## 4) Deploy options

Below are common deployment strategies. Pick the one that matches your constraints.

### Option A — Render (simple web service)

**Best when:** you want an easy deploy pipeline and don’t mind platform constraints.

High-level steps:

1. Create a **Web Service** from your GitHub repo.
2. Set the Docker build to use the project’s `Dockerfile`.
3. Add environment variables (see section 2).
4. Attach a PostgreSQL database:

   * If Render Postgres is used, it may not include TimescaleDB by default.
   * If Timescale is required, use a Timescale-capable hosted DB.

Start command:

* Not needed if you use Dockerfile + entrypoint (already starts Gunicorn).

Check:

* `/api/health/?db=1`

### Option B — Railway

**Best when:** fast setup + managed services.

High-level steps:

1. Create a Railway project from GitHub.
2. Add a Postgres database.
3. Configure env vars.
4. Deploy using Dockerfile.

Notes:

* Verify Timescale extension support. If Timescale is not available, you may need to disable Timescale migrations or use an external Timescale DB.

### Option C — Fly.io

**Best when:** you want more control, near-VM behavior.

High-level steps:

1. Build and deploy the Docker image.
2. Provide secrets (env vars).
3. Connect to a Postgres cluster.

Notes:

* Ensure your Postgres is Timescale-capable if you need caggs.

### Option D — VPS/VM (DigitalOcean / OVH / Hetzner / bare VM)

**Best when:** you want maximum control.

Recommended setup:

1. Install Docker + Docker Compose on the VM.
2. Clone the repo.
3. Create `.env`.
4. Run:

```bash
docker compose -f docker/docker-compose.yml up --build -d
```

Production hardening suggestions:

* Put Nginx/Caddy in front for HTTPS (reverse proxy to `web:8000`).
* Store DB data in a persistent volume.
* Use a managed Timescale DB if you don’t want to manage Postgres on the VM.

---

## 5) First deploy checklist

1. ✅ `DJANGO_DEBUG=0`
2. ✅ Strong `DJANGO_SECRET_KEY`
3. ✅ Correct `DJANGO_ALLOWED_HOSTS` (domain + IP if needed)
4. ✅ Database env vars set
5. ✅ Migrations succeed
6. ✅ `/api/health/?db=1` returns OK
7. ✅ If using Timescale: hourly/daily endpoints return data

---

## 6) Common issues

### 6.1 503 on `/hourly/` or `/daily/`

Usually means the Timescale views don’t exist:

* Confirm Timescale migrations ran successfully.
* Confirm DB is TimescaleDB and `CREATE EXTENSION timescaledb` worked.

### 6.2 Running on Postgres without Timescale

If your DB is plain Postgres, Timescale-specific migrations may fail.

Options:

* Use a Timescale-capable DB.
* Or (advanced) split Timescale migrations into optional migrations and only apply them in Timescale environments.

### 6.3 Static files not served

With Docker + WhiteNoise:

* `collectstatic` runs in `entrypoint.sh`
* WhiteNoise serves from `STATIC_ROOT` (`staticfiles/`)

If you disable the entrypoint, ensure you run:

```bash
python manage.py collectstatic --noinput
```
