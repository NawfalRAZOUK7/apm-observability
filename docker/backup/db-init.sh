#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# docker/backup/db-init.sh
# One-shot initializer used by the `db-init` service.
# - verifies DB is reachable
# - applies safe/idempotent init
# - optionally runs /initdb/*.sql (must be idempotent)
# ============================================================================

echo "db-init: waiting for postgres..."
for i in {1..60}; do
  if pg_isready -h "${PGHOST:-db}" -p "${PGPORT:-5432}" -U "${PGUSER:-apm}" -d "${PGDATABASE:-apm}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "db-init: ERROR: postgres not ready after 60s" >&2
    exit 1
  fi
done

echo "db-init: verifying connectivity..."
psql -v ON_ERROR_STOP=1 -c "SELECT 1;" >/dev/null

echo "db-init: ensuring timescaledb extension exists..."
psql -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >/dev/null

# Optional: re-apply init SQL idempotently
if [ -d "/initdb" ]; then
  shopt -s nullglob
  SQL_FILES=(/initdb/*.sql)
  if [ ${#SQL_FILES[@]} -gt 0 ]; then
    echo "db-init: applying /initdb/*.sql (must be idempotent)..."
    for f in "${SQL_FILES[@]}"; do
      echo "db-init: running ${f}"
      psql -v ON_ERROR_STOP=1 -f "$f"
    done
  else
    echo "db-init: /initdb present but no .sql files found"
  fi
else
  echo "db-init: no /initdb mounted; skipping custom SQL"
fi

echo "db-init: OK"
