#!/usr/bin/env bash
set -euo pipefail

REPORT_DIR="${REPORT_DIR:-reports}"
PY="${PYTHON:-python}"
JUNIT_DIR="${JUNIT_DIR:-${REPORT_DIR}/step6-junit}"

mkdir -p "$REPORT_DIR"
mkdir -p "$JUNIT_DIR"
LOG="$REPORT_DIR/step6_tests.log"

# Optional: if you use docker for TimescaleDB
# docker compose -f docker/docker-compose.yml up -d

echo "---- Step 6: check migrations up-to-date ----"
if ! $PY manage.py makemigrations --check --dry-run >/dev/null 2>&1; then
  echo "❌ Pending migrations detected."
  echo "Run:"
  echo "  python manage.py makemigrations"
  echo "  python manage.py migrate"
  exit 1
fi

echo "---- Step 6: migrate (dev DB) ----"
$PY manage.py migrate --noinput

echo "---- Step 6: run Django tests ----"
# JUnit XML output goes to $JUNIT_DIR via xmlrunner. Falls back to default runner if not installed.
DJANGO_TEST_RUNNER="xmlrunner.extra.djangotestrunner.XMLTestRunner" \
TEST_OUTPUT_DIR="$JUNIT_DIR" \
$PY manage.py test -v 2 2>&1 | tee "$LOG"

echo "✅ All tests passed. Log: $LOG"
