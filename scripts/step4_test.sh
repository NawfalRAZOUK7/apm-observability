#!/usr/bin/env bash
set -euo pipefail

# Run from repo root no matter where script is called from
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Auto-load .env if present (so Django uses Postgres in scripts)
if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

STACK="${STACK:-main}"
APP_HOST="${APP_HOST:-127.0.0.1}"

if [[ "$STACK" == "cluster" ]]; then
  APP_HTTPS_PORT="${APP_HTTPS_PORT:-18443}"
  POSTMAN_ENV_DEFAULT="postman/APM_Observability.cluster.postman_environment.json"
  DB_PORT_DEFAULT="25432"
else
  APP_HTTPS_PORT="${APP_HTTPS_PORT:-8443}"
  POSTMAN_ENV_DEFAULT="postman/APM_Observability.main.postman_environment.json"
  DB_PORT_DEFAULT="5432"
fi

POSTMAN_ENV="${POSTMAN_ENV:-$POSTMAN_ENV_DEFAULT}"
BASE_URL="${BASE_URL:-https://${APP_HOST}:${APP_HTTPS_PORT}}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-$DB_PORT_DEFAULT}"
DB_NAME="${DB_NAME:-apm}"
DB_USER="${DB_USER:-apm}"
DB_PASSWORD="${DB_PASSWORD:-apm}"
REPORT_DIR="${REPORT_DIR:-reports}"
SSL_VERIFY="${SSL_VERIFY:-false}"
LOG_FILE="${LOG_FILE:-}"

# Set curl SSL flags based on SSL_VERIFY
if [[ "$SSL_VERIFY" == "false" ]]; then
    CURL_SSL_FLAGS="-k"
else
    CURL_SSL_FLAGS=""
fi

# Set newman SSL flags based on SSL_VERIFY
if [[ "$SSL_VERIFY" == "false" ]]; then
    NEWMAN_SSL_FLAGS="--insecure"
else
    NEWMAN_SSL_FLAGS=""
fi

# Optional: if you use docker for TimescaleDB
# docker compose -f docker/docker-compose.yml up -d

POSTGRES_HOST="$DB_HOST" POSTGRES_PORT="$DB_PORT" POSTGRES_DB="$DB_NAME" POSTGRES_USER="$DB_USER" POSTGRES_PASSWORD="$DB_PASSWORD" \
  python manage.py migrate --noinput

mkdir -p "$REPORT_DIR"

# ----------------------------
# Seed data spanning multiple days
# ----------------------------
echo ""
echo "---- Seeding sample events across multiple days via /api/requests/ingest/ ----"

NOW_ISO="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
DAY1_ISO="$(date -u -v-1d +"%Y-%m-%dT%H:%M:%SZ")"
DAY2_ISO="$(date -u -v-2d +"%Y-%m-%dT%H:%M:%SZ")"
DAY3_ISO="$(date -u -v-3d +"%Y-%m-%dT%H:%M:%SZ")"

INGEST_PAYLOAD="$(cat <<JSON
{
  "events": [
    {"time":"$DAY3_ISO","service":"api","endpoint":"/health","method":"GET","status_code":200,"latency_ms":12,"trace_id":"t-1","user_ref":"u-1","tags":{"step":4}},
    {"time":"$DAY3_ISO","service":"api","endpoint":"/health","method":"GET","status_code":500,"latency_ms":120,"trace_id":"t-2","user_ref":"u-2","tags":{"step":4}},

    {"time":"$DAY2_ISO","service":"api","endpoint":"/login","method":"POST","status_code":200,"latency_ms":80,"trace_id":"t-3","user_ref":"u-1","tags":{"step":4}},
    {"time":"$DAY2_ISO","service":"api","endpoint":"/login","method":"POST","status_code":503,"latency_ms":220,"trace_id":"t-4","user_ref":"u-3","tags":{"step":4}},
    {"time":"$DAY2_ISO","service":"api","endpoint":"/login","method":"POST","status_code":200,"latency_ms":60,"trace_id":"t-5","user_ref":"u-4","tags":{"step":4}},

    {"time":"$DAY1_ISO","service":"web","endpoint":"/home","method":"GET","status_code":200,"latency_ms":35,"trace_id":"t-6","user_ref":"u-5","tags":{"step":4}},
    {"time":"$DAY1_ISO","service":"web","endpoint":"/home","method":"GET","status_code":200,"latency_ms":40,"trace_id":"t-7","user_ref":"u-6","tags":{"step":4}},

    {"time":"$NOW_ISO","service":"api","endpoint":"/health","method":"GET","status_code":200,"latency_ms":15,"trace_id":"t-8","user_ref":"u-7","tags":{"step":4}}
  ]
}
JSON
)"

HTTP_CODE_INGEST="$(
  curl $CURL_SSL_FLAGS -sS --connect-timeout 2 --max-time 20 \
    -o /tmp/apm_step4_ingest.json -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$BASE_URL/api/requests/ingest/?strict=false" \
    --data "$INGEST_PAYLOAD"
)"

cat /tmp/apm_step4_ingest.json | head -c 2000 || true
echo ""
echo "HTTP $HTTP_CODE_INGEST"

if [[ "$HTTP_CODE_INGEST" != "200" ]]; then
  echo "❌ Ingest failed (HTTP $HTTP_CODE_INGEST)"
  if [[ -n "$LOG_FILE" && -f "$LOG_FILE" ]]; then
    echo "---- Last 80 lines of server log ($LOG_FILE) ----"
    tail -n 80 "$LOG_FILE" || true
  fi
  exit 1
fi

# ----------------------------
# Run Postman Step 4 collection
# ----------------------------
echo ""
echo "---- Running Postman Step 4 collection (daily) ----"
newman run postman/APM_Observability_Step4.postman_collection.json \
  -e "$POSTMAN_ENV" \
  --env-var "base_url=$BASE_URL" \
  --env-var "app_host=$APP_HOST" \
  --env-var "app_https_port=$APP_HTTPS_PORT" \
  $NEWMAN_SSL_FLAGS \
  --reporters cli,json,junit,htmlextra \
  --reporter-json-export "$REPORT_DIR/step4-report.json" \
  --reporter-junit-export "$REPORT_DIR/step4-junit.xml" \
  --reporter-htmlextra-export "$REPORT_DIR/step4-report.html" \
  --reporter-htmlextra-title "APM Observability - Step 4" \
  --reporter-htmlextra-logs

# ----------------------------
# Basic curl smoke check: daily endpoint
# ----------------------------
echo ""
echo "---- Basic curl smoke check: /api/requests/daily/ ----"

START="$(date -u -v-7d +"%Y-%m-%dT%H:%M:%SZ")"
END="$(date -u -v+5M +"%Y-%m-%dT%H:%M:%SZ")"

HTTP_CODE_DAILY="$(
  curl $CURL_SSL_FLAGS -sS --connect-timeout 2 --max-time 20 \
    -o /tmp/apm_step4_daily.json -w "%{http_code}" \
    "$BASE_URL/api/requests/daily/?start=$START&end=$END&limit=50"
)"

cat /tmp/apm_step4_daily.json | head -c 4000 || true
echo ""
echo "HTTP $HTTP_CODE_DAILY"

if [[ "$HTTP_CODE_DAILY" == "200" ]]; then
  grep -q '"bucket"' /tmp/apm_step4_daily.json || (echo "Missing bucket" && exit 1)
  grep -q '"hits"' /tmp/apm_step4_daily.json || (echo "Missing hits" && exit 1)
  grep -q '"errors"' /tmp/apm_step4_daily.json || (echo "Missing errors" && exit 1)
  grep -q '"avg_latency_ms"' /tmp/apm_step4_daily.json || (echo "Missing avg_latency_ms" && exit 1)
  echo "✅ Daily endpoint returned expected fields."
else
  echo "❌ Daily endpoint returned HTTP $HTTP_CODE_DAILY"
  if [[ -n "$LOG_FILE" && -f "$LOG_FILE" ]]; then
    echo "---- Last 80 lines of server log ($LOG_FILE) ----"
    tail -n 80 "$LOG_FILE" || true
  fi
  exit 1
fi

echo ""
echo "Done. Reports are in: $REPORT_DIR/"
