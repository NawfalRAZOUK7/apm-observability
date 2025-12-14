#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
REPORT_DIR="${REPORT_DIR:-reports}"

# ensure db up if you use docker (optional)
# docker compose -f docker/docker-compose.yml up -d

python manage.py migrate --noinput

# Start server only if it's not already running
if ! curl -sf "$BASE_URL/api/requests/" >/dev/null 2>&1; then
  python manage.py runserver 127.0.0.1:8000 >/tmp/apm_step2_server.log 2>&1 &
  PID=$!
  trap 'kill $PID >/dev/null 2>&1 || true' EXIT

  for i in {1..40}; do
    curl -sf "$BASE_URL/api/requests/" >/dev/null 2>&1 && break
    sleep 0.25
  done
fi

mkdir -p "$REPORT_DIR"

# Requires:
#   npm install -g newman newman-reporter-htmlextra
newman run postman/APM_Observability_Step2.postman_collection.json \
  -e postman/APM_Observability.local.postman_environment.json \
  --reporters cli,json,junit,htmlextra \
  --reporter-json-export "$REPORT_DIR/step2-report.json" \
  --reporter-junit-export "$REPORT_DIR/step2-junit.xml" \
  --reporter-htmlextra-export "$REPORT_DIR/step2-report.html" \
  --reporter-htmlextra-title "APM Observability - Step 2" \
  --reporter-htmlextra-logs
