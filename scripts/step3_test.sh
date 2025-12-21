#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://127.0.0.1:8443}"
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

python manage.py migrate --noinput

mkdir -p "$REPORT_DIR"

# Run Postman Step 3 collection (seed + hourly assertions)
# Requires:
#   npm install -g newman newman-reporter-htmlextra
newman run postman/APM_Observability_Step3.postman_collection.json \
  -e postman/APM_Observability.local.postman_environment.json \
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
