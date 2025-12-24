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
else
    APP_HTTPS_PORT="${APP_HTTPS_PORT:-${MAIN_NGINX_HTTPS_HOST_PORT:-8443}}"
    POSTMAN_ENV_DEFAULT="postman/APM_Observability.main.postman_environment.json"
fi

POSTMAN_ENV="${POSTMAN_ENV:-$POSTMAN_ENV_DEFAULT}"
BASE_URL="${BASE_URL:-https://${APP_HOST}:${APP_HTTPS_PORT}}"
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

# Ensure Docker stack is running
# docker compose -f docker/docker-compose.yml up -d

# Wait for Django to be ready (via Nginx proxy with SSL)
echo "Waiting for Django API to be ready..."
for i in {1..40}; do
    if curl $CURL_SSL_FLAGS -sf "$BASE_URL/api/requests/" >/dev/null 2>&1; then
        echo "Django API is ready."
        break
    fi
    echo "Django API not ready yet. Waiting ($i/40)..."
    sleep 0.25
done

mkdir -p "$REPORT_DIR"

# Requires:
#   npm install -g newman newman-reporter-htmlextra
newman run postman/APM_Observability_Step2.postman_collection.json \
  -e "$POSTMAN_ENV" \
  --env-var "base_url=$BASE_URL" \
  --env-var "app_host=$APP_HOST" \
  --env-var "app_https_port=$APP_HTTPS_PORT" \
  $NEWMAN_SSL_FLAGS \
  --reporters cli,json,junit,htmlextra \
  --reporter-json-export "$REPORT_DIR/step2-report.json" \
  --reporter-junit-export "$REPORT_DIR/step2-junit.xml" \
  --reporter-htmlextra-export "$REPORT_DIR/step2-report.html" \
  --reporter-htmlextra-title "APM Observability - Step 2" \
  --reporter-htmlextra-logs
