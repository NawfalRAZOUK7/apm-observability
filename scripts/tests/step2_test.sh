#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$ROOT_DIR/scripts/lib/common.sh"
cd_repo_root
configure_step_environment

# Ensure Docker stack is running
# docker compose --env-file .env.docker -f docker/docker-compose.yml up -d

wait_for_django_api

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
