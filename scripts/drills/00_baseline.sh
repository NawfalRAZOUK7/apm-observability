#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

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

DATA_NODE_IP="${DATA_NODE_IP:-$(read_env DATA_NODE_IP)}"
DATA_NODE_IP="${DATA_NODE_IP:-127.0.0.1}"
CONTROL_NODE_IP="${CONTROL_NODE_IP:-$(read_env CONTROL_NODE_IP)}"
CONTROL_NODE_IP="${CONTROL_NODE_IP:-127.0.0.1}"

POSTGRES_DB="${POSTGRES_DB:-$(read_env POSTGRES_DB)}"
POSTGRES_USER="${POSTGRES_USER:-$(read_env POSTGRES_USER)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(read_env POSTGRES_PASSWORD)}"
POSTGRES_APP_USER="${POSTGRES_APP_USER:-$(read_env POSTGRES_APP_USER)}"
POSTGRES_APP_PASSWORD="${POSTGRES_APP_PASSWORD:-$(read_env POSTGRES_APP_PASSWORD)}"
POSTGRES_READONLY_USER="${POSTGRES_READONLY_USER:-$(read_env POSTGRES_READONLY_USER)}"
POSTGRES_READONLY_PASSWORD="${POSTGRES_READONLY_PASSWORD:-$(read_env POSTGRES_READONLY_PASSWORD)}"

POSTGRES_DB="${POSTGRES_DB:-apm}"
POSTGRES_USER="${POSTGRES_USER:-apm}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-apm}"

DB_PORT="${CLUSTER_DATA_DB_HOST_PORT:-$(read_env CLUSTER_DATA_DB_HOST_PORT)}"
DB_PORT="${DB_PORT:-5432}"

export POSTGRES_HOST="$DATA_NODE_IP"
export POSTGRES_PORT="$DB_PORT"
export POSTGRES_DB
export POSTGRES_USER
export POSTGRES_PASSWORD
export POSTGRES_APP_USER
export POSTGRES_APP_PASSWORD
export POSTGRES_READONLY_USER
export POSTGRES_READONLY_PASSWORD
export CLUSTER_DB_PRIMARY_HOST="${DATA_NODE_IP}:${DB_PORT}"

REPORT_DIR="${REPORT_DIR:-reports/task6}"
mkdir -p "$REPORT_DIR"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"

SEED="${SEED:-1}"
if [[ "$SEED" == "1" ]]; then
  SEED_COUNT="${SEED_COUNT:-2000}"
  SEED_DAYS="${SEED_DAYS:-7}"
  SEED_VALUE="${SEED_VALUE:-42}"
  echo "Seeding: count=$SEED_COUNT days=$SEED_DAYS seed=$SEED_VALUE"
  "$PYTHON" manage.py seed_apirequests --count "$SEED_COUNT" --days "$SEED_DAYS" --seed "$SEED_VALUE"
fi

echo "Capturing baseline row count..."
"$PYTHON" - <<'PY' | tee "$REPORT_DIR/apirequest_count_${STAMP}.txt"
import os
import psycopg

conn = psycopg.connect(
    host=os.environ["POSTGRES_HOST"],
    port=os.environ["POSTGRES_PORT"],
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
with conn.cursor() as cur:
    cur.execute("select count(*) from observability_apirequest;")
    print(cur.fetchone()[0])
conn.close()
PY

echo "Capturing pgbackrest info..."
CONTROL_PGBR_IMAGE="${CONTROL_PGBR_IMAGE:-apm-control-pgbackrest}"
CONTROL_PGBR_SPOOL_VOLUME="${CONTROL_PGBR_SPOOL_VOLUME:-apm-control_pgbackrest_spool}"
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

if ! run_with_timeout "${PGBR_TIMEOUT:-60}" "${PGBR_CMD[@]}" \
  | tee "$REPORT_DIR/pgbackrest_info_${STAMP}.txt"; then
  echo "WARN: pgbackrest info failed or timed out."
fi

echo "Capturing replication status..."
"$PYTHON" - <<'PY' | tee "$REPORT_DIR/replication_${STAMP}.txt"
import os
import psycopg

conn = psycopg.connect(
    host=os.environ["POSTGRES_HOST"],
    port=os.environ["POSTGRES_PORT"],
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
with conn.cursor() as cur:
    cur.execute("select application_name, client_addr, state, sync_state from pg_stat_replication;")
    rows = cur.fetchall()
    if not rows:
        print("none")
    else:
        for row in rows:
            print("|".join("" if v is None else str(v) for v in row))
conn.close()
PY

BASE_URL="${BASE_URL:-https://127.0.0.1:18443}"
SSL_VERIFY="${SSL_VERIFY:-false}"
if [[ "$SSL_VERIFY" == "false" ]]; then
  CURL_FLAGS="-k"
else
  CURL_FLAGS=""
fi

echo "Capturing API health..."
curl $CURL_FLAGS -sS "$BASE_URL/api/health/" \
  | tee "$REPORT_DIR/health_${STAMP}.json" >/dev/null
curl $CURL_FLAGS -sS "$BASE_URL/api/requests/kpis/" \
  | tee "$REPORT_DIR/kpis_${STAMP}.json" >/dev/null
curl $CURL_FLAGS -sS "$BASE_URL/api/requests/top-endpoints/?limit=5&sort_by=hits&direction=desc" \
  | tee "$REPORT_DIR/top_endpoints_${STAMP}.json" >/dev/null

echo "Baseline captured in $REPORT_DIR"
