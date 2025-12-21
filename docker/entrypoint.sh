#!/usr/bin/env bash
# entrypoint.sh - Main entrypoint for the APM Observability Django application container.
# Handles DB connection checks, migrations, static file collection, and Gunicorn startup.
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

: "${SKIP_MIGRATE:=0}"
: "${SKIP_COLLECTSTATIC:=0}"

echo "==> DB: ${POSTGRES_HOST}:${POSTGRES_PORT} (db=${POSTGRES_DB}, user=${POSTGRES_USER})"
echo "==> Gunicorn: bind=${GUNICORN_BIND}, workers=${GUNICORN_WORKERS}, timeout=${GUNICORN_TIMEOUT}"

# Safety net (compose already waits for db health, but keep this to avoid race conditions)
echo "==> Checking DB port..."
for i in $(seq 1 30); do
  if (echo >"/dev/tcp/${POSTGRES_HOST}/${POSTGRES_PORT}") >/dev/null 2>&1; then
    echo "==> DB port reachable."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "!! DB not reachable after 30s (${POSTGRES_HOST}:${POSTGRES_PORT})"
    exit 1
  fi
  sleep 1
done

if [ "${SKIP_MIGRATE}" = "1" ]; then
  echo "==> SKIP_MIGRATE=1, skipping migrations."
else
  echo "==> Running migrations..."
  for i in $(seq 1 10); do
    if python manage.py migrate --noinput; then
      echo "==> Migrations applied."
      break
    fi
    if [ "$i" -eq 10 ]; then
      echo "!! Migrations failed after 10 attempts."
      exit 1
    fi
    echo "==> Migrate failed, retrying in 2s... ($i/10)"
    sleep 2
  done
fi

if [ "${SKIP_COLLECTSTATIC}" = "1" ]; then
  echo "==> SKIP_COLLECTSTATIC=1, skipping collectstatic."
else
  echo "==> Collecting static files..."
  python manage.py collectstatic --noinput
fi

echo "==> Starting Gunicorn..."
exec gunicorn apm_platform.wsgi:application \
  --bind "${GUNICORN_BIND}" \
  --workers "${GUNICORN_WORKERS}" \
  --timeout "${GUNICORN_TIMEOUT}"
