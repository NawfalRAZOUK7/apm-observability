#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# docker/entrypoint.sh
# Review notes:
# - This script is executed by the web service entrypoint.
# - Ensure your web image has bash installed.
# - Keeps your existing behavior: wait for DB, migrate, collectstatic, start gunicorn.
# ============================================================================

: "${DB_HOST:=${POSTGRES_HOST:-db}}"
: "${DB_PORT:=${POSTGRES_PORT:-5432}}"
: "${DB_CONNECT_RETRIES:=60}"
: "${DB_CONNECT_DELAY:=1}"

wait_for_db() {
  echo "Waiting for DB at ${DB_HOST}:${DB_PORT} ..."
  for i in $(seq 1 "${DB_CONNECT_RETRIES}"); do
    # TCP-level check (fast)
    if (echo >"/dev/tcp/${DB_HOST}/${DB_PORT}") >/dev/null 2>&1; then
      echo "DB is reachable."
      return 0
    fi
    sleep "${DB_CONNECT_DELAY}"
  done
  echo "ERROR: DB not reachable after ${DB_CONNECT_RETRIES} attempts" >&2
  return 1
}

wait_for_db

if [[ "${SKIP_MIGRATE:-0}" != "1" ]]; then
  echo "Running migrations..."
  python manage.py migrate --noinput
fi

if [[ "${SKIP_COLLECTSTATIC:-0}" != "1" ]]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

echo "Starting Gunicorn..."
exec gunicorn apm_platform.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
