#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# docker/certs/setup-ssl.sh
#
# Generates a self-signed TLS certificate for LOCAL DEV with proper SANs.
# This is suitable for MinIO when clients connect to: https://minio:9000
#
# Outputs (in docker/certs/):
#   - public.crt
#   - private.key
#
# SECURITY:
#   - DO NOT COMMIT private.key
#   - chmod 600 private.key
# ============================================================================

CERT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CRT_OUT="${CRT_OUT:-$CERT_DIR/public.crt}"
KEY_OUT="${KEY_OUT:-$CERT_DIR/private.key}"
DAYS="${DAYS:-825}"
CN="${CN:-minio}"

# Default SANs (override if needed)
DNS1="${DNS1:-minio}"
DNS2="${DNS2:-localhost}"
IP1="${IP1:-127.0.0.1}"

umask 077

echo "Generating self-signed cert with SANs: DNS:${DNS1}, DNS:${DNS2}, IP:${IP1}"

TMP_CONF="$(mktemp)"
trap 'rm -f "$TMP_CONF"' EXIT

cat >"$TMP_CONF" <<EOF
[req]
prompt = no
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = ${CN}

[v3_req]
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${DNS1}
DNS.2 = ${DNS2}
IP.1  = ${IP1}
EOF

# Key
openssl genrsa -out "$KEY_OUT" 2048

# Cert
openssl req -x509 -new -nodes -key "$KEY_OUT" \
  -sha256 -days "$DAYS" \
  -out "$CRT_OUT" \
  -config "$TMP_CONF"

chmod 600 "$KEY_OUT" || true

echo "OK: wrote: $CRT_OUT"
echo "OK: wrote: $KEY_OUT"

echo
echo "Verify SANs:"
openssl x509 -in "$CRT_OUT" -noout -subject -ext subjectAltName
