#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM:-}" != "YES" ]]; then
  echo "ERROR: This drill stops the primary DB and promotes a replica."
  echo "Set CONFIRM=YES to proceed."
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

DATA_DB_CONTAINER="${DATA_DB_CONTAINER:-apm-data-db-1}"

ENV_FILES=(
  "docker/.env.ports.localdev"
  "docker/.env.ports"
  "docker/cluster/.env.cluster"
  ".env"
)

read_env() {
  local key="$1"
  local file
  local line
  for file in "${ENV_FILES[@]}"; do
    [[ -f "$file" ]] || continue
    line="$(grep -E "^${key}=" "$file" | tail -n 1 || true)"
    if [[ -n "$line" ]]; then
      echo "${line#*=}"
      return 0
    fi
  done
  return 1
}

PYTHON="${PYTHON:-python}"
if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
fi

REPLICA_INDEX="${REPLICA_INDEX:-1}"
if [[ "$REPLICA_INDEX" == "2" ]]; then
  REPLICA_SERVICE="${REPLICA_CONTAINER:-apm-data-db-replica-2-1}"
  REPLICA_PORT="${REPLICA_PORT:-$(read_env CLUSTER_DATA_DB_REPLICA2_HOST_PORT)}"
  REPLICA_PORT="${REPLICA_PORT:-25434}"
else
  REPLICA_SERVICE="${REPLICA_CONTAINER:-apm-data-db-replica-1}"
  REPLICA_PORT="${REPLICA_PORT:-$(read_env CLUSTER_DATA_DB_REPLICA1_HOST_PORT)}"
  REPLICA_PORT="${REPLICA_PORT:-25433}"
fi

DATA_NODE_IP="${DATA_NODE_IP:-$(read_env DATA_NODE_IP)}"
DATA_NODE_IP="${DATA_NODE_IP:-127.0.0.1}"
REPLICA_HOST="${REPLICA_HOST:-$DATA_NODE_IP}"

POSTGRES_DB="${POSTGRES_DB:-$(read_env POSTGRES_DB)}"
POSTGRES_USER="${POSTGRES_USER:-$(read_env POSTGRES_USER)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(read_env POSTGRES_PASSWORD)}"
POSTGRES_DB="${POSTGRES_DB:-apm}"
POSTGRES_USER="${POSTGRES_USER:-apm}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-apm}"

echo "Stopping primary DB..."
docker stop "$DATA_DB_CONTAINER"

echo "Promoting replica: $REPLICA_SERVICE"
"$PYTHON" - <<PY
import psycopg

conn = psycopg.connect(
    host="${REPLICA_HOST}",
    port="${REPLICA_PORT}",
    dbname="${POSTGRES_DB}",
    user="${POSTGRES_USER}",
    password="${POSTGRES_PASSWORD}",
)
with conn.cursor() as cur:
    cur.execute("select pg_promote();")
conn.commit()
conn.close()
PY

if [[ "${APPLY_APP_SWITCH:-0}" == "1" ]]; then
  echo "Running check_cluster_dbs..."
  CLUSTER_DB_PRIMARY_HOST="${REPLICA_HOST}:${REPLICA_PORT}" \
  CLUSTER_DB_REPLICA_HOSTS="" \
  POSTGRES_HOST="${REPLICA_HOST}" \
  POSTGRES_PORT="${REPLICA_PORT}" \
  POSTGRES_DB="${POSTGRES_DB}" \
  POSTGRES_USER="${POSTGRES_USER}" \
  POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  "$PYTHON" manage.py check_cluster_dbs
else
  echo "Manual step required:"
  echo "  Set CLUSTER_DB_PRIMARY_HOST=${REPLICA_HOST}:${REPLICA_PORT}"
  echo "  Restart app web container"
fi

echo "Failover drill complete."
