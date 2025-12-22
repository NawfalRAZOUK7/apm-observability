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
# ============================================================================

: "${MINIO_ENDPOINT:=https://minio:9000}"
: "${MINIO_BUCKET:=pgbackrest}"
: "${MINIO_ALIAS:=myminio}"
: "${MINIO_ENABLE_VERSIONING:=1}"
: "${MINIO_INSECURE:=0}"

if [ -z "${MINIO_ROOT_USER:-}" ] || [ -z "${MINIO_ROOT_PASSWORD:-}" ]; then
  echo "ERROR: MINIO_ROOT_USER and MINIO_ROOT_PASSWORD are required" >&2
  exit 1
fi

MC_INSECURE_FLAG=""
if [ "$MINIO_INSECURE" = "1" ]; then
  MC_INSECURE_FLAG="--insecure"
  echo "WARN: MINIO_INSECURE=1 (TLS verification disabled for mc)." >&2
fi

echo "minio-init: waiting for MinIO at ${MINIO_ENDPOINT} ..."
i=1
while [ "$i" -le 60 ]; do
  if mc $MC_INSECURE_FLAG alias set "$MINIO_ALIAS" "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" --api S3v4 >/dev/null 2>&1; then
    break
  fi
  sleep 1
  i=$((i + 1))
done

if [ "$i" -gt 60 ]; then
  echo "ERROR: MinIO not reachable after 60s" >&2
  exit 1
fi

echo "minio-init: creating bucket '${MINIO_BUCKET}' (idempotent) ..."
mc $MC_INSECURE_FLAG mb --ignore-existing "$MINIO_ALIAS/$MINIO_BUCKET" >/dev/null

if [ "$MINIO_ENABLE_VERSIONING" = "1" ]; then
  echo "minio-init: enabling versioning on '${MINIO_BUCKET}' (idempotent) ..."
  mc $MC_INSECURE_FLAG version enable "$MINIO_ALIAS/$MINIO_BUCKET" >/dev/null 2>&1 || true
fi

echo "minio-init: OK"
