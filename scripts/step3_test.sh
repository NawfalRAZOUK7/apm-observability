#!/usr/bin/env bash
set -euo pipefail

STACK="${STACK:-main}"
APP_HOST="${APP_HOST:-127.0.0.1}"

# Load port registry for consistent host ports (main/cluster).
for env_file in docker/.env.ports docker/.env.ports.localdev; do
    if [[ -f "$env_file" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$env_file"
        set +a
    fi
done

if [[ "$STACK" == "cluster" ]]; then
    APP_HTTPS_PORT="${APP_HTTPS_PORT:-${CLUSTER_APP_NGINX_HTTPS_HOST_PORT:-18443}}"
    POSTMAN_ENV_DEFAULT="postman/APM_Observability.cluster.postman_environment.json"
    DB_PORT_DEFAULT="${CLUSTER_DATA_DB_HOST_PORT:-5432}"
else
    APP_HTTPS_PORT="${APP_HTTPS_PORT:-${MAIN_NGINX_HTTPS_HOST_PORT:-8443}}"
    POSTMAN_ENV_DEFAULT="postman/APM_Observability.main.postman_environment.json"
    DB_PORT_DEFAULT="${MAIN_DB_HOST_PORT:-5432}"
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

# Run Postman Step 3 collection (seed + hourly assertions)
# Requires:
#   npm install -g newman newman-reporter-htmlextra
newman run postman/APM_Observability_Step3.postman_collection.json \
  -e "$POSTMAN_ENV" \
  --env-var "base_url=$BASE_URL" \
  --env-var "app_host=$APP_HOST" \
  --env-var "app_https_port=$APP_HTTPS_PORT" \
  $NEWMAN_SSL_FLAGS \
  --reporters cli,json,junit,htmlextra \
  --reporter-json-export "$REPORT_DIR/step3-report.json" \
  --reporter-junit-export "$REPORT_DIR/step3-junit.xml" \
  --reporter-htmlextra-export "$REPORT_DIR/step3-report.html" \
  --reporter-htmlextra-title "APM Observability - Step 3" \
  --reporter-htmlextra-logs

echo ""
echo "---- Basic curl smoke check: /api/requests/hourly/ ----"

# Build a last-4-hours window (works on macOS date)
START="$(date -u -v-4H +"%Y-%m-%dT%H:%M:%SZ")"
END="$(date -u -v+5M +"%Y-%m-%dT%H:%M:%SZ")"

HTTP_CODE="$(
  curl $CURL_SSL_FLAGS -s -o /tmp/apm_step3_hourly.json -w "%{http_code}" \
    "$BASE_URL/api/requests/hourly/?start=$START&end=$END&limit=50"
)"

cat /tmp/apm_step3_hourly.json | head -c 2000 || true
echo ""
echo "HTTP $HTTP_CODE"

if [[ "$HTTP_CODE" == "200" ]]; then
  # Basic JSON shape checks without jq (grep-based, minimal)
  grep -q '"bucket"' /tmp/apm_step3_hourly.json
  grep -q '"hits"' /tmp/apm_step3_hourly.json
  grep -q '"errors"' /tmp/apm_step3_hourly.json
  echo "✅ Hourly endpoint returned expected fields."
elif [[ "$HTTP_CODE" == "501" ]]; then
  echo "ℹ️ Hourly endpoint returned 501 (SQLite/Non-Postgres). This is expected if POSTGRES_* env vars are not loaded."
else
  echo "❌ Unexpected hourly response code: $HTTP_CODE"
  exit 1
fi

echo ""
echo "Done. Reports are in: $REPORT_DIR/"
