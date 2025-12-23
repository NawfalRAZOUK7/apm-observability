#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM:-}" != "YES" ]]; then
  echo "ERROR: This drill deletes the primary DB volume."
  echo "Set CONFIRM=YES to proceed."
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

DATA_PROJECT="${DATA_PROJECT:-apm-data}"
APP_WEB_CONTAINER="${APP_WEB_CONTAINER:-apm-app-web-1}"
DATA_DB_CONTAINER="${DATA_DB_CONTAINER:-apm-data-db-1}"

VOLUME_NAME="${DATA_PROJECT}_data_db"
SPOOL_VOLUME="${DATA_PROJECT}_pgbackrest_spool"
SOCKET_VOLUME="${DATA_PROJECT}_pg_socket"

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

export POSTGRES_HOST="$DATA_NODE_IP"
export POSTGRES_PORT="$DB_PORT"
export POSTGRES_DB
export POSTGRES_USER
export POSTGRES_PASSWORD

echo "Checking backup status (pgbackrest info)..."
CONTROL_PGBR_IMAGE="${CONTROL_PGBR_IMAGE:-apm-control-pgbackrest}"
CONTROL_PGBR_SPOOL_VOLUME="${CONTROL_PGBR_SPOOL_VOLUME:-apm-control_pgbackrest_spool}"
CONTROL_NODE_IP="${CONTROL_NODE_IP:-$(read_env CONTROL_NODE_IP)}"
CONTROL_NODE_IP="${CONTROL_NODE_IP:-127.0.0.1}"
MINIO_PORT="${CLUSTER_CONTROL_MINIO_API_HOST_PORT:-$(read_env CLUSTER_CONTROL_MINIO_API_HOST_PORT)}"
MINIO_PORT="${MINIO_PORT:-9000}"
PGBR_CIPHER_PASS="${PGBACKREST_CIPHER_PASS:-$(read_env PGBACKREST_CIPHER_PASS)}"

PGBR_CMD=(
  docker run --rm
  --add-host "pgbackrest-server:${DATA_NODE_IP}"
  --add-host "minio:${CONTROL_NODE_IP}"
  -v "${CONTROL_PGBR_SPOOL_VOLUME}:/var/lib/pgbackrest"
  -v "${ROOT_DIR}/docker/backup/pgbackrest-client.conf:/etc/pgbackrest/pgbackrest.conf:ro"
  -v "${ROOT_DIR}/docker/certs:/certs:ro"
  -e PGBACKREST_CONFIG=/etc/pgbackrest/pgbackrest.conf
  -e PGBACKREST_REPO1_CIPHER_PASS="${PGBR_CIPHER_PASS}"
  -e PGBACKREST_REPO2_CIPHER_PASS="${PGBR_CIPHER_PASS}"
  -e PGBACKREST_REPO1_S3_ENDPOINT="https://minio:${MINIO_PORT}"
  -e PGBACKREST_REPO2_S3_ENDPOINT="https://minio:${MINIO_PORT}"
  "$CONTROL_PGBR_IMAGE"
  pgbackrest --stanza=apm info
)

if ! run_with_timeout "${PGBR_TIMEOUT:-60}" "${PGBR_CMD[@]}" >/dev/null; then
  echo "WARN: pgbackrest info failed or timed out."
fi

echo "Stopping app web to avoid writes..."
docker stop "$APP_WEB_CONTAINER" >/dev/null 2>&1 || true

echo "Stopping primary DB..."
docker stop "$DATA_DB_CONTAINER"

if ! docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
  echo "ERROR: volume not found: $VOLUME_NAME"
  exit 1
fi

echo "Wiping primary data volume contents: $VOLUME_NAME"
WIPE_CMD=(
  docker run --rm --name apm-data-wipe
  -v "${VOLUME_NAME}:/var/lib/postgresql/data"
  alpine:3.20
  sh -lc "rm -rf /var/lib/postgresql/data/*"
)
if ! run_with_timeout "${WIPE_TIMEOUT:-60}" "${WIPE_CMD[@]}"; then
  docker rm -f apm-data-wipe >/dev/null 2>&1 || true
  echo "ERROR: volume wipe timed out."
  exit 1
fi

DB_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$DATA_DB_CONTAINER" 2>/dev/null || true)"
DB_IMAGE="${DB_IMAGE:-apm-data-db}"

echo "Restoring from repo1 using image: $DB_IMAGE"
RESTORE_CMD=(
  docker run --rm --name apm-data-restore
  --add-host "minio:${CONTROL_NODE_IP}"
  -v "${VOLUME_NAME}:/var/lib/postgresql/data"
  -v "${SPOOL_VOLUME}:/var/lib/pgbackrest"
  -v "${SOCKET_VOLUME}:/var/run/postgresql"
  -v "${ROOT_DIR}/docker/cluster/pgbackrest-db.conf:/etc/pgbackrest/pgbackrest.conf:ro"
  -v "${ROOT_DIR}/docker/certs/pgbackrest:/certs/pgbackrest:ro"
  -v "${ROOT_DIR}/docker/certs/public.crt:/certs/public.crt:ro"
  -e PGBACKREST_CONFIG=/etc/pgbackrest/pgbackrest.conf
  -e PGBACKREST_REPO1_CIPHER_PASS="${PGBR_CIPHER_PASS}"
  -e PGBACKREST_REPO1_S3_ENDPOINT="https://minio:${MINIO_PORT}"
  "$DB_IMAGE"
  pgbackrest --stanza=apm --repo=1 restore
)
if ! run_with_timeout "${RESTORE_TIMEOUT:-300}" "${RESTORE_CMD[@]}"; then
  docker rm -f apm-data-restore >/dev/null 2>&1 || true
  echo "ERROR: pgbackrest restore timed out."
  exit 1
fi

echo "Starting primary DB..."
docker start "$DATA_DB_CONTAINER"

echo "Waiting for DB readiness..."
for _ in $(seq 1 30); do
  if "$PYTHON" - <<'PY'
import os
import psycopg
import sys

try:
    conn = psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=2,
    )
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
  then
    echo "DB is ready."
    break
  fi
  sleep 2
done

echo "Starting app web..."
docker start "$APP_WEB_CONTAINER"

BASE_URL="${BASE_URL:-https://127.0.0.1:18443}"
SSL_VERIFY="${SSL_VERIFY:-false}"
if [[ "$SSL_VERIFY" == "false" ]]; then
  CURL_FLAGS="-k"
else
  CURL_FLAGS=""
fi

echo "Health check..."
curl $CURL_FLAGS -sS "$BASE_URL/api/health/" >/dev/null
curl $CURL_FLAGS -sS "$BASE_URL/api/requests/kpis/" >/dev/null

echo "Primary restore drill complete."
