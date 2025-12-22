#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# docker/minio/gen-minio-cert.sh
#
# Generates the MinIO TLS certificate + key in docker/certs/ using the shared
# SAN-capable script docker/certs/setup-ssl.sh.
#
# This ensures the cert includes SANs for:
#   - DNS:minio   (containers connect to https://minio:9000)
#   - DNS:localhost
#   - IP:127.0.0.1
#
# Output files:
#   docker/certs/public.crt
#   docker/certs/private.key
#
# Run from repo root:
#   bash docker/minio/gen-minio-cert.sh
# ============================================================================

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}" )" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

SETUP_SSL="$REPO_ROOT/docker/certs/setup-ssl.sh"

if [[ ! -f "$SETUP_SSL" ]]; then
  echo "ERROR: Missing $SETUP_SSL" >&2
  exit 1
fi

# You can override SANs via env if needed
export CN="${CN:-minio}"
export DNS1="${DNS1:-minio}"
export DNS2="${DNS2:-localhost}"
export IP1="${IP1:-127.0.0.1}"

bash "$SETUP_SSL"

echo
echo "MinIO TLS cert generated. Files:" 
ls -la "$REPO_ROOT/docker/certs/public.crt" "$REPO_ROOT/docker/certs/private.key"
