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

# Ensure Docker stack is running
# docker compose -f docker/docker-compose.yml up -d

# Clean up any existing test data
echo "Cleaning up existing test data..."
POSTGRES_HOST="$DB_HOST" POSTGRES_PORT="$DB_PORT" POSTGRES_DB="$DB_NAME" POSTGRES_USER="$DB_USER" POSTGRES_PASSWORD="$DB_PASSWORD" \
  python manage.py shell -c "import os; from django.conf import settings; print('Database engine:', settings.DATABASES['default']['ENGINE']); print('Database name:', settings.DATABASES['default'].get('NAME', 'N/A'))"
POSTGRES_HOST="$DB_HOST" POSTGRES_PORT="$DB_PORT" POSTGRES_DB="$DB_NAME" POSTGRES_USER="$DB_USER" POSTGRES_PASSWORD="$DB_PASSWORD" \
  python manage.py shell -c "from observability.models import ApiRequest; count = ApiRequest.objects.count(); ApiRequest.objects.all().delete(); print(f'Deleted {count} existing records')"
POSTGRES_HOST="$DB_HOST" POSTGRES_PORT="$DB_PORT" POSTGRES_DB="$DB_NAME" POSTGRES_USER="$DB_USER" POSTGRES_PASSWORD="$DB_PASSWORD" \
  python manage.py shell -c "from observability.models import ApiRequest; print('Records after cleanup:', ApiRequest.objects.count())"

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

# Set newman SSL flags based on SSL_VERIFY
if [[ "$SSL_VERIFY" == "false" ]]; then
    NEWMAN_SSL_FLAGS="--insecure"
else
    NEWMAN_SSL_FLAGS=""
fi

# Requires:
#   npm install -g newman newman-reporter-htmlextra
newman run postman/APM_Observability_Step1.postman_collection.json \
  -e "$POSTMAN_ENV" \
  --env-var "base_url=$BASE_URL" \
  --env-var "app_host=$APP_HOST" \
  --env-var "app_https_port=$APP_HTTPS_PORT" \
  $NEWMAN_SSL_FLAGS \
  --reporters cli,json,junit,htmlextra \
  --reporter-json-export "$REPORT_DIR/step1-report.json" \
  --reporter-junit-export "$REPORT_DIR/step1-junit.xml" \
  --reporter-htmlextra-export "$REPORT_DIR/step1-report.html" \
  --reporter-htmlextra-title "APM Observability - Step 1" \
  --reporter-htmlextra-logs
