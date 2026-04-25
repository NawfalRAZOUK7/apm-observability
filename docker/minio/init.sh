#!/bin/sh
set -eu

# ============================================================================
# docker/minio/init.sh
#
# POSIX /bin/sh compatible script (works with minio/mc container).
#
# Purpose:
# - Wait for MinIO to be reachable
# - Configure an mc alias
# - Create the bucket used by pgBackRest (default: pgbackrest)
# - Optionally enable versioning
#
# Env:
#   MINIO_ENDPOINT            (default: https://minio:9000)
#   MINIO_ROOT_USER           (required)
#   MINIO_ROOT_PASSWORD       (required)
#   MINIO_BUCKET              (default: pgbackrest)
#   MINIO_ALIAS               (default: myminio)
#   MINIO_ENABLE_VERSIONING   (default: 1)
#   MINIO_INSECURE            (default: 0)  # 1 disables TLS verify for mc only
#   MINIO_INIT_WAIT_SECONDS   (default: 120)
#   MINIO_INIT_WAIT_INTERVAL  (default: 2)
# ============================================================================

: "${MINIO_ENDPOINT:=https://minio:9000}"
: "${MINIO_BUCKET:=pgbackrest}"
: "${MINIO_BUCKET_COLD:=}"
: "${MINIO_ALIAS:=myminio}"
: "${MINIO_ENABLE_VERSIONING:=1}"
: "${MINIO_INSECURE:=0}"
: "${MINIO_INIT_WAIT_SECONDS:=120}"
: "${MINIO_INIT_WAIT_INTERVAL:=2}"

if [ -z "${MINIO_ROOT_USER:-}" ] || [ -z "${MINIO_ROOT_PASSWORD:-}" ]; then
  echo "ERROR: MINIO_ROOT_USER and MINIO_ROOT_PASSWORD are required" >&2
  exit 1
fi

MC_INSECURE_FLAG=""
if [ "$MINIO_INSECURE" = "1" ]; then
  MC_INSECURE_FLAG="--insecure"
  echo "WARN: MINIO_INSECURE=1 (TLS verification disabled for mc)." >&2
fi

max_attempts=$((MINIO_INIT_WAIT_SECONDS / MINIO_INIT_WAIT_INTERVAL))
if [ "$max_attempts" -lt 1 ]; then
  max_attempts=1
fi

echo "minio-init: waiting for MinIO at ${MINIO_ENDPOINT} (timeout ${MINIO_INIT_WAIT_SECONDS}s) ..."
i=1
while [ "$i" -le "$max_attempts" ]; do
  if mc $MC_INSECURE_FLAG alias set "$MINIO_ALIAS" "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" --api S3v4 >/dev/null 2>&1; then
    break
  fi
  sleep "$MINIO_INIT_WAIT_INTERVAL"
  i=$((i + 1))
done

if [ "$i" -gt "$max_attempts" ]; then
  echo "ERROR: MinIO not reachable after ${MINIO_INIT_WAIT_SECONDS}s" >&2
  exit 1
fi

echo "minio-init: creating bucket '${MINIO_BUCKET}' (idempotent) ..."
mc $MC_INSECURE_FLAG mb --ignore-existing "$MINIO_ALIAS/$MINIO_BUCKET" >/dev/null

if [ "$MINIO_ENABLE_VERSIONING" = "1" ]; then
  echo "minio-init: enabling versioning on '${MINIO_BUCKET}' (idempotent) ..."
  mc $MC_INSECURE_FLAG version enable "$MINIO_ALIAS/$MINIO_BUCKET" >/dev/null 2>&1 || true
fi

if [ -n "$MINIO_BUCKET_COLD" ] && [ "$MINIO_BUCKET_COLD" != "$MINIO_BUCKET" ]; then
  echo "minio-init: creating cold bucket '${MINIO_BUCKET_COLD}' (idempotent) ..."
  mc $MC_INSECURE_FLAG mb --ignore-existing "$MINIO_ALIAS/$MINIO_BUCKET_COLD" >/dev/null
  if [ "$MINIO_ENABLE_VERSIONING" = "1" ]; then
    echo "minio-init: enabling versioning on '${MINIO_BUCKET_COLD}' (idempotent) ..."
    mc $MC_INSECURE_FLAG version enable "$MINIO_ALIAS/$MINIO_BUCKET_COLD" >/dev/null 2>&1 || true
  fi
fi

echo "minio-init: OK"
