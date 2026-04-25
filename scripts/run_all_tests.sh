#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Load port registry for consistent host ports (main/cluster).
for env_file in "$ROOT_DIR/docker/.env.ports" "$ROOT_DIR/docker/.env.ports.localdev"; do
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi
done

STACK="${STACK:-main}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_HTTPS_PORT="${APP_HTTPS_PORT:-}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-}"
REPORT_DIR="${REPORT_DIR:-}"
SKIP_STEP6="${SKIP_STEP6:-}"
AUTO_SKIP_STEP6="false"

usage() {
  cat <<USAGE
Usage: $0 [--stack main|cluster] [--app-host HOST] [--app-https-port PORT] \
          [--db-host HOST] [--db-port PORT] [--report-dir DIR] [--skip-step6]

Examples:
  $0
  $0 --stack cluster
  STACK=cluster APP_HTTPS_PORT=18443 $0
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack)
      STACK="$2"
      shift 2
      ;;
    --app-host)
      APP_HOST="$2"
      shift 2
      ;;
    --app-https-port)
      APP_HTTPS_PORT="$2"
      shift 2
      ;;
    --db-host)
      DB_HOST="$2"
      shift 2
      ;;
    --db-port)
      DB_PORT="$2"
      shift 2
      ;;
    --report-dir)
      REPORT_DIR="$2"
      shift 2
      ;;
    --skip-step6)
      SKIP_STEP6="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "$STACK" != "main" && "$STACK" != "cluster" ]]; then
  echo "STACK must be 'main' or 'cluster'."
  exit 1
fi

if [[ -z "$APP_HTTPS_PORT" ]]; then
  if [[ "$STACK" == "cluster" ]]; then
    APP_HTTPS_PORT="${CLUSTER_APP_NGINX_HTTPS_HOST_PORT:-18443}"
  else
    APP_HTTPS_PORT="${MAIN_NGINX_HTTPS_HOST_PORT:-8443}"
  fi
fi

if [[ -z "$DB_PORT" ]]; then
  if [[ "$STACK" == "cluster" ]]; then
    DB_PORT="${CLUSTER_DATA_DB_HOST_PORT:-5432}"
  else
    DB_PORT="${MAIN_DB_HOST_PORT:-5432}"
  fi
fi

if [[ -z "$REPORT_DIR" ]]; then
  REPORT_DIR="reports/all_tests_$(date -u +"%Y%m%d_%H%M%S")"
fi

if [[ -z "$SKIP_STEP6" ]]; then
  AUTO_SKIP_STEP6="true"
  if [[ "$STACK" == "cluster" ]]; then
    SKIP_STEP6="true"
  else
    SKIP_STEP6="false"
  fi
fi

if ! command -v newman >/dev/null 2>&1; then
  echo "newman not found. Install with: npm install -g newman newman-reporter-htmlextra"
  exit 1
fi

export STACK
export APP_HOST
export APP_HTTPS_PORT
export DB_HOST
export DB_PORT
export REPORT_DIR

export BASE_URL="https://${APP_HOST}:${APP_HTTPS_PORT}"

echo "---- APM Observability test suite ----"
echo "STACK=$STACK"
echo "BASE_URL=$BASE_URL"
echo "DB_HOST=$DB_HOST"
echo "DB_PORT=$DB_PORT"
echo "REPORT_DIR=$REPORT_DIR"
if [[ "$AUTO_SKIP_STEP6" == "true" && "$SKIP_STEP6" == "true" ]]; then
  echo "NOTE: Step 6 auto-skipped for cluster runs. Set SKIP_STEP6=false to force it."
fi
mkdir -p "$REPORT_DIR"

scripts/step1_test.sh
scripts/step2_test.sh
scripts/step3_test.sh
scripts/step4_test.sh
scripts/step5_test.sh

if [[ "$SKIP_STEP6" == "true" ]]; then
  echo "---- Step 6 skipped ----"
else
  REPORT_DIR="$REPORT_DIR" scripts/step6_test.sh
fi

echo ""
echo "✅ All steps completed. Reports: $REPORT_DIR"
