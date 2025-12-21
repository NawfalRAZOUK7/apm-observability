#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost:8443}"
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
POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=apm POSTGRES_USER=apm POSTGRES_PASSWORD=apm python manage.py shell -c "import os; from django.conf import settings; print('Database engine:', settings.DATABASES['default']['ENGINE']); print('Database name:', settings.DATABASES['default'].get('NAME', 'N/A'))"
POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=apm POSTGRES_USER=apm POSTGRES_PASSWORD=apm python manage.py shell -c "from observability.models import ApiRequest; count = ApiRequest.objects.count(); ApiRequest.objects.all().delete(); print(f'Deleted {count} existing records')"
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
  -e postman/APM_Observability.local.postman_environment.json \
  $NEWMAN_SSL_FLAGS \
  --reporters cli,json,junit,htmlextra \
  --reporter-json-export "$REPORT_DIR/step1-report.json" \
  --reporter-junit-export "$REPORT_DIR/step1-junit.xml" \
  --reporter-htmlextra-export "$REPORT_DIR/step1-report.html" \
  --reporter-htmlextra-title "APM Observability - Step 1" \
  --reporter-htmlextra-logs
