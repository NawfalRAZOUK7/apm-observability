#!/bin/bash
# gen-minio-cert.sh - Generates a self-signed SSL certificate for MinIO using OpenSSL and a custom SAN config.
# NOTE: This script is for development certificate generation only. Certificates are generated in ../certs/
set -e

# Generate certificates in the centralized certs directory
CERT_DIR="../certs"
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

CONF="../minio/minio-san-openssl.cnf"
KEY="private.key"
CSR="minio.csr"
CRT="public.crt"

# Generate private key
echo "Generating private key..."
openssl genrsa -out "$KEY" 2048

# Generate CSR
echo "Generating CSR..."
openssl req -new -key "$KEY" -out "$CSR" -config "$CONF"

# Generate self-signed certificate with SANs
echo "Generating self-signed certificate with SANs..."
openssl x509 -req -in "$CSR" -signkey "$KEY" -out "$CRT" -days 365 -extensions v3_req -extfile "$CONF"

echo "Certificate and key generated: $CRT, $KEY"
echo "Certificates placed in: $CERT_DIR"
echo "These are development certificates for local SSL testing."
