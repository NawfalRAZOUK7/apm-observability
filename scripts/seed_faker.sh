#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Auto-load .env if present (so Django uses Postgres in scripts)
if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

has_flag() {
  local name="$1"
  shift
  for arg in "$@"; do
    if [[ "$arg" == "$name" || "$arg" == "$name="* ]]; then
      return 0
    fi
  done
  return 1
}

ARGS=("$@")

if ! has_flag "--count" "${ARGS[@]}"; then
  ARGS+=(--count "${COUNT:-1000}")
fi

if ! has_flag "--days" "${ARGS[@]}"; then
  ARGS+=(--days "${DAYS:-7}")
fi

if ! has_flag "--batch-size" "${ARGS[@]}"; then
  ARGS+=(--batch-size "${BATCH_SIZE:-1000}")
fi

python manage.py seed_apirequests "${ARGS[@]}"

# Optional: refresh Timescale CAGGs after seeding (set REFRESH_CAGG=0 to skip)
if [[ "${REFRESH_CAGG:-1}" == "1" ]]; then
  python manage.py refresh_apirequest_hourly || true
  python manage.py refresh_apirequest_daily || true
fi
