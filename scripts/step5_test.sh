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

PORT="${PORT:-8443}"
BASE_URL="https://127.0.0.1:${PORT}"
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

fail() {
  echo "❌ $*"
  echo "---- Last 120 lines of server log ($LOG_FILE) ----"
  tail -n 120 "$LOG_FILE" || true
  exit 1
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

# Cross-platform "days ago" ISO8601 (macOS date -v, GNU date -d fallback)
iso_days_ago() {
  local days="$1"
  if date -u -v-"${days}"d +"%Y-%m-%dT%H:%M:%SZ" >/dev/null 2>&1; then
    date -u -v-"${days}"d +"%Y-%m-%dT%H:%M:%SZ"
  else
    date -u -d "${days} days ago" +"%Y-%m-%dT%H:%M:%SZ"
  fi
}

iso_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

mkdir -p "$REPORT_DIR"

echo "---- Step 5 smoke test ----"
echo "BASE_URL=$BASE_URL"
echo "REPORT_DIR=$REPORT_DIR"
echo ""

python manage.py migrate --noinput

# ----------------------------
# Seed data spanning multiple days/services/endpoints via ingest
# ----------------------------
echo "---- Seeding sample events via /api/requests/ingest/ ----"

NOW_ISO="$(iso_now)"
D1_ISO="$(iso_days_ago 1)"
D2_ISO="$(iso_days_ago 2)"
D3_ISO="$(iso_days_ago 3)"
D5_ISO="$(iso_days_ago 5)"

INGEST_PAYLOAD="$(cat <<JSON
{
  "events": [
    {"time":"$D5_ISO","service":"api","endpoint":"/health","method":"GET","status_code":200,"latency_ms":12,"trace_id":"t-01","user_ref":"u-1","tags":{"step":5}},
    {"time":"$D5_ISO","service":"api","endpoint":"/health","method":"GET","status_code":500,"latency_ms":180,"trace_id":"t-02","user_ref":"u-2","tags":{"step":5}},

    {"time":"$D3_ISO","service":"auth","endpoint":"/login","method":"POST","status_code":200,"latency_ms":85,"trace_id":"t-03","user_ref":"u-3","tags":{"step":5}},
    {"time":"$D3_ISO","service":"auth","endpoint":"/login","method":"POST","status_code":503,"latency_ms":240,"trace_id":"t-04","user_ref":"u-4","tags":{"step":5}},
    {"time":"$D3_ISO","service":"auth","endpoint":"/login","method":"POST","status_code":200,"latency_ms":70,"trace_id":"t-05","user_ref":"u-5","tags":{"step":5}},

    {"time":"$D2_ISO","service":"web","endpoint":"/home","method":"GET","status_code":200,"latency_ms":35,"trace_id":"t-06","user_ref":"u-6","tags":{"step":5}},
    {"time":"$D2_ISO","service":"web","endpoint":"/home","method":"GET","status_code":200,"latency_ms":42,"trace_id":"t-07","user_ref":"u-7","tags":{"step":5}},
    {"time":"$D2_ISO","service":"web","endpoint":"/search","method":"GET","status_code":200,"latency_ms":90,"trace_id":"t-08","user_ref":"u-8","tags":{"step":5}},
    {"time":"$D2_ISO","service":"web","endpoint":"/search","method":"GET","status_code":504,"latency_ms":410,"trace_id":"t-09","user_ref":"u-9","tags":{"step":5}},

    {"time":"$D1_ISO","service":"api","endpoint":"/orders","method":"GET","status_code":200,"latency_ms":110,"trace_id":"t-10","user_ref":"u-10","tags":{"step":5}},
    {"time":"$D1_ISO","service":"api","endpoint":"/orders","method":"GET","status_code":200,"latency_ms":95,"trace_id":"t-11","user_ref":"u-11","tags":{"step":5}},
    {"time":"$D1_ISO","service":"api","endpoint":"/orders","method":"GET","status_code":502,"latency_ms":350,"trace_id":"t-12","user_ref":"u-12","tags":{"step":5}},
    {"time":"$D1_ISO","service":"api","endpoint":"/orders","method":"POST","status_code":201,"latency_ms":160,"trace_id":"t-13","user_ref":"u-13","tags":{"step":5}},

    {"time":"$NOW_ISO","service":"api","endpoint":"/health","method":"GET","status_code":200,"latency_ms":15,"trace_id":"t-14","user_ref":"u-14","tags":{"step":5}},
    {"time":"$NOW_ISO","service":"api","endpoint":"/orders","method":"GET","status_code":200,"latency_ms":105,"trace_id":"t-15","user_ref":"u-15","tags":{"step":5}},
    {"time":"$NOW_ISO","service":"web","endpoint":"/home","method":"GET","status_code":200,"latency_ms":33,"trace_id":"t-16","user_ref":"u-16","tags":{"step":5}}
  ]
}
JSON
)"

HTTP_CODE_INGEST="$(
  curl $CURL_SSL_FLAGS -sS --connect-timeout 2 --max-time 30 \
    -o "$REPORT_DIR/step5_ingest.json" -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$BASE_URL/api/requests/ingest/?strict=false" \
    --data "$INGEST_PAYLOAD"
)"

echo "HTTP $HTTP_CODE_INGEST"
cat "$REPORT_DIR/step5_ingest.json" | head -c 2000 || true
echo ""
[[ "$HTTP_CODE_INGEST" == "200" ]] || fail "Ingest failed (HTTP $HTTP_CODE_INGEST)."

# ----------------------------
# Smoke check: /kpis/
# ----------------------------
echo "---- Smoke check: /api/requests/kpis/ ----"
HTTP_CODE_KPIS="$(
  curl $CURL_SSL_FLAGS -sS --connect-timeout 2 --max-time 20 \
    -o "$REPORT_DIR/step5_kpis.json" -w "%{http_code}" \
    "$BASE_URL/api/requests/kpis/"
)"
echo "HTTP $HTTP_CODE_KPIS"
cat "$REPORT_DIR/step5_kpis.json" | head -c 2000 || true
echo ""
[[ "$HTTP_CODE_KPIS" == "200" ]] || fail "KPIs failed (HTTP $HTTP_CODE_KPIS)."

# Basic content checks (don’t assume exact numbers)
grep -q '"hits"' "$REPORT_DIR/step5_kpis.json" || fail "KPIs response missing 'hits'."
grep -q '"errors"' "$REPORT_DIR/step5_kpis.json" || fail "KPIs response missing 'errors'."
grep -q '"source"' "$REPORT_DIR/step5_kpis.json" || fail "KPIs response missing 'source'."

# Optional filtered KPIs
echo "---- KPIs filtered: service=api ----"
HTTP_CODE_KPIS2="$(
  curl $CURL_SSL_FLAGS -sS --connect-timeout 2 --max-time 20 \
    -o "$REPORT_DIR/step5_kpis_service_api.json" -w "%{http_code}" \
    "$BASE_URL/api/requests/kpis/?service=api"
)"
echo "HTTP $HTTP_CODE_KPIS2"
cat "$REPORT_DIR/step5_kpis_service_api.json" | head -c 2000 || true
echo ""
[[ "$HTTP_CODE_KPIS2" == "200" ]] || fail "Filtered KPIs failed (HTTP $HTTP_CODE_KPIS2)."

# ----------------------------
# Smoke check: /top-endpoints/
# ----------------------------
echo "---- Smoke check: /api/requests/top-endpoints/ ----"
HTTP_CODE_TOP="$(
  curl $CURL_SSL_FLAGS -sS --connect-timeout 2 --max-time 30 \
    -o "$REPORT_DIR/step5_top_endpoints_hits.json" -w "%{http_code}" \
    "$BASE_URL/api/requests/top-endpoints/?limit=10&sort_by=hits&direction=desc"
)"
echo "HTTP $HTTP_CODE_TOP"
cat "$REPORT_DIR/step5_top_endpoints_hits.json" | head -c 3000 || true
echo ""
[[ "$HTTP_CODE_TOP" == "200" ]] || fail "Top endpoints (hits) failed (HTTP $HTTP_CODE_TOP)."

# Works whether response is a list OR {"results":[...]}
grep -q '"service"' "$REPORT_DIR/step5_top_endpoints_hits.json" || fail "Top endpoints missing 'service'."
grep -q '"endpoint"' "$REPORT_DIR/step5_top_endpoints_hits.json" || fail "Top endpoints missing 'endpoint'."
grep -q '"hits"' "$REPORT_DIR/step5_top_endpoints_hits.json" || fail "Top endpoints missing 'hits'."

echo "---- Top endpoints: sort_by=error_rate ----"
HTTP_CODE_TOP2="$(
  curl $CURL_SSL_FLAGS -sS --connect-timeout 2 --max-time 30 \
    -o "$REPORT_DIR/step5_top_endpoints_error_rate.json" -w "%{http_code}" \
    "$BASE_URL/api/requests/top-endpoints/?limit=10&sort_by=error_rate&direction=desc"
)"
echo "HTTP $HTTP_CODE_TOP2"
cat "$REPORT_DIR/step5_top_endpoints_error_rate.json" | head -c 3000 || true
echo ""
[[ "$HTTP_CODE_TOP2" == "200" ]] || fail "Top endpoints (error_rate) failed (HTTP $HTTP_CODE_TOP2)."

# ----------------------------
# Optional: Newman run (if installed + collection exists)
# ----------------------------
STEP5_COLLECTION="postman/APM_Observability_Step5.postman_collection.json"
STEP5_ENV="postman/APM_Observability.local.postman_environment.json"

if have_cmd newman && [[ -f "$STEP5_COLLECTION" ]]; then
  echo "---- Running Newman: Step 5 collection ----"
  # Env file is optional; we also pass base_url directly
  NEWMAN_ARGS=(
    run "$STEP5_COLLECTION"
    --env-var "base_url=$BASE_URL"
    $NEWMAN_SSL_FLAGS
    --reporters cli,json,junit,htmlextra
    --reporter-json-export "$REPORT_DIR/step5-report.json"
    --reporter-junit-export "$REPORT_DIR/step5-junit.xml"
    --reporter-htmlextra-export "$REPORT_DIR/step5-report.html"
    --reporter-htmlextra-title "APM Observability - Step 5"
    --reporter-htmlextra-logs
  )
  if [[ -f "$STEP5_ENV" ]]; then
    NEWMAN_ARGS+=( -e "$STEP5_ENV" )
  fi
  newman "${NEWMAN_ARGS[@]}"
else
  echo "---- Newman skipped ----"
  if ! have_cmd newman; then
    echo "newman not found in PATH."
  fi
  if [[ ! -f "$STEP5_COLLECTION" ]]; then
    echo "Missing collection: $STEP5_COLLECTION"
  fi
fi

echo ""
echo "✅ Step 5 smoke test OK."
echo "Reports / responses are in: $REPORT_DIR/"
