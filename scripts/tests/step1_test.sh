#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$ROOT_DIR/scripts/lib/common.sh"
cd_repo_root
configure_step_environment

# Ensure Docker stack is running
# docker compose --env-file .env.docker -f docker/docker-compose.yml up -d

# Clean up any existing test data
echo "Cleaning up existing test data..."
POSTGRES_HOST="$DB_HOST" POSTGRES_PORT="$DB_PORT" POSTGRES_DB="$DB_NAME" POSTGRES_USER="$DB_USER" POSTGRES_PASSWORD="$DB_PASSWORD" \
  python manage.py shell -c "import os; from django.conf import settings; print('Database engine:', settings.DATABASES['default']['ENGINE']); print('Database name:', settings.DATABASES['default'].get('NAME', 'N/A'))"
POSTGRES_HOST="$DB_HOST" POSTGRES_PORT="$DB_PORT" POSTGRES_DB="$DB_NAME" POSTGRES_USER="$DB_USER" POSTGRES_PASSWORD="$DB_PASSWORD" \
  python manage.py shell -c "from observability.models import ApiRequest; count = ApiRequest.objects.count(); ApiRequest.objects.all().delete(); print(f'Deleted {count} existing records')"
POSTGRES_HOST="$DB_HOST" POSTGRES_PORT="$DB_PORT" POSTGRES_DB="$DB_NAME" POSTGRES_USER="$DB_USER" POSTGRES_PASSWORD="$DB_PASSWORD" \
  python manage.py shell -c "from observability.models import ApiRequest; print('Records after cleanup:', ApiRequest.objects.count())"

wait_for_django_api

mkdir -p "$REPORT_DIR"

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
