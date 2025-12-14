#!/usr/bin/env bash
set -euo pipefail

echo "==> APM Observability entrypoint starting..."

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:=apm}"
: "${POSTGRES_USER:=apm}"
: "${POSTGRES_PASSWORD:=apm}"

: "${GUNICORN_WORKERS:=3}"
: "${GUNICORN_TIMEOUT:=60}"
: "${GUNICORN_BIND:=0.0.0.0:8000}"

# Wait for DB (requires 'curl' + 'psql' or 'pg_isready'. We use pg_isready from postgres client in DB image,
# but web image doesn't have it. So we do a TCP check + Django migrate retry.
echo "==> Waiting for database at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
for i in $(seq 1 60); do
  if (echo >"/dev/tcp/${POSTGRES_HOST}/${POSTGRES_PORT}") >/dev/null 2>&1; then
    echo "==> DB port is reachable."
    break
  fi
  sleep 1
done

# Run migrations (retry a few times in case DB is up but not ready)
echo "==> Running migrations..."
for i in $(seq 1 10); do
  if python manage.py migrate --noinput; then
    echo "==> Migrations applied."
    break
  fi
  echo "==> Migrate failed, retrying in 2s... ($i/10)"
  sleep 2
done

# Collect static for WhiteNoise
echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Starting Gunicorn..."
exec gunicorn apm_platform.wsgi:application \
  --bind "${GUNICORN_BIND}" \
  --workers "${GUNICORN_WORKERS}" \
  --timeout "${GUNICORN_TIMEOUT}"
