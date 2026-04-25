#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

DATA_DB_CONTAINER="${DATA_DB_CONTAINER:-apm-data-db-1}"
CONTROL_MINIO_CONTAINER="${CONTROL_MINIO_CONTAINER:-apm-control-minio-1}"

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

run_with_timeout() {
  local timeout="$1"
  shift
  "$PYTHON" - "$timeout" "$@" <<'PY'
import subprocess
import sys

timeout = float(sys.argv[1])
cmd = sys.argv[2:]
try:
    subprocess.run(cmd, check=True, timeout=timeout)
except subprocess.TimeoutExpired:
    print(f"Timeout after {timeout}s: {' '.join(cmd)}", file=sys.stderr)
    sys.exit(124)
except subprocess.CalledProcessError as exc:
    sys.exit(exc.returncode)
PY
}

POSTGRES_DB="${POSTGRES_DB:-$(read_env POSTGRES_DB)}"
POSTGRES_USER="${POSTGRES_USER:-$(read_env POSTGRES_USER)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(read_env POSTGRES_PASSWORD)}"
POSTGRES_DB="${POSTGRES_DB:-apm}"
POSTGRES_USER="${POSTGRES_USER:-apm}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-apm}"

DATA_NODE_IP="${DATA_NODE_IP:-$(read_env DATA_NODE_IP)}"
DATA_NODE_IP="${DATA_NODE_IP:-127.0.0.1}"
DB_PORT="${CLUSTER_DATA_DB_HOST_PORT:-$(read_env CLUSTER_DATA_DB_HOST_PORT)}"
DB_PORT="${DB_PORT:-5432}"

CONTROL_NODE_IP="${CONTROL_NODE_IP:-$(read_env CONTROL_NODE_IP)}"
CONTROL_NODE_IP="${CONTROL_NODE_IP:-127.0.0.1}"
MINIO_PORT="${CLUSTER_CONTROL_MINIO_API_HOST_PORT:-$(read_env CLUSTER_CONTROL_MINIO_API_HOST_PORT)}"
MINIO_PORT="${MINIO_PORT:-9000}"
PGBR_CIPHER_PASS="${PGBACKREST_CIPHER_PASS:-$(read_env PGBACKREST_CIPHER_PASS)}"

MINIO_HEALTH_URL="${MINIO_HEALTH_URL:-https://127.0.0.1:19000/minio/health/ready}"

echo "Stopping MinIO..."
docker stop "$CONTROL_MINIO_CONTAINER"

echo "DB should remain up (pg_isready)..."
"$PYTHON" - <<PY
import psycopg

conn = psycopg.connect(
    host="${DATA_NODE_IP}",
    port="${DB_PORT}",
    dbname="${POSTGRES_DB}",
    user="${POSTGRES_USER}",
    password="${POSTGRES_PASSWORD}",
)
conn.close()
PY

echo "Running pgbackrest check (expected to fail while MinIO is down)..."
DB_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$DATA_DB_CONTAINER" 2>/dev/null || true)"
DB_IMAGE="${DB_IMAGE:-apm-data-db}"

PGBR_CHECK_CMD=(
  docker run --rm
  --network "container:${DATA_DB_CONTAINER}"
  --volumes-from "$DATA_DB_CONTAINER"
  -e PGBACKREST_CONFIG=/etc/pgbackrest/pgbackrest.conf
  -e PGBACKREST_REPO1_CIPHER_PASS="${PGBR_CIPHER_PASS}"
  -e PGBACKREST_REPO1_S3_ENDPOINT="https://${CONTROL_NODE_IP}:${MINIO_PORT}"
  -e PGBACKREST_REPO1_STORAGE_VERIFY_TLS=n
  "$DB_IMAGE"
  pgbackrest --stanza=apm check
)

if run_with_timeout "${PGBR_TIMEOUT:-60}" "${PGBR_CHECK_CMD[@]}"; then
  echo "WARN: pgbackrest check unexpectedly succeeded with MinIO down."
else
  echo "Expected failure recorded."
fi

echo "Starting MinIO..."
docker start "$CONTROL_MINIO_CONTAINER"

echo "Waiting for MinIO readiness..."
for _ in $(seq 1 30); do
  if curl -k -sS "$MINIO_HEALTH_URL" >/dev/null 2>&1; then
    echo "MinIO is ready."
    break
  fi
  sleep 2
done

echo "Re-running pgbackrest check (should pass)..."
run_with_timeout "${PGBR_TIMEOUT:-60}" "${PGBR_CHECK_CMD[@]}"

echo "MinIO outage drill complete."
