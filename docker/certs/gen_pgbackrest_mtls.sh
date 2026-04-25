#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# docker/certs/gen_pgbackrest_mtls.sh
#
# Generate mTLS material for pgBackRest TLS server (Option 2).
# Robust paths: output is ALWAYS docker/certs/pgbackrest/ relative to this script.
#
# Creates:
#   docker/certs/pgbackrest/
#     - ca.crt, ca.key
#     - server.crt, server.key  (CN/SAN = pgbackrest-server)
#     - client.crt, client.key  (CN = pgbr-client)
#
# SECURITY:
#   - DO NOT COMMIT *.key
# ============================================================================

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${OUT_DIR:-$SCRIPT_DIR/pgbackrest}"

# Names must match your docker-compose services/configs
SERVER_DNS="${SERVER_DNS:-pgbackrest-server}"
CLIENT_CN="${CLIENT_CN:-pgbr-client}"

umask 077
mkdir -p "$OUT_DIR"
cd "$OUT_DIR"

rm -f ca.srl server.ext client.ext server.csr client.csr 2>/dev/null || true

echo "[1/3] Generating CA..."
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 \
  -out ca.crt -subj "/CN=pgbackrest-ca"

echo "[2/3] Generating server cert (CN/SAN = ${SERVER_DNS})..."
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=${SERVER_DNS}"
cat > server.ext <<EOF
subjectAltName=DNS:${SERVER_DNS}
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 825 -sha256 -extfile server.ext

echo "[3/3] Generating client cert (CN = ${CLIENT_CN})..."
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr -subj "/CN=${CLIENT_CN}"
cat > client.ext <<EOF
extendedKeyUsage=clientAuth
EOF
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out client.crt -days 825 -sha256 -extfile client.ext

chmod 600 ca.key server.key client.key || true

echo
echo "OK. Generated pgBackRest mTLS material in: $OUT_DIR"
ls -la

echo
echo "Verify server SAN:"
openssl x509 -in server.crt -noout -subject -ext subjectAltName

echo "Verify client CN:"
openssl x509 -in client.crt -noout -subject
