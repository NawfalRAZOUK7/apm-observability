# SSL/HTTPS Post-Implementation Updates Checklist

This document outlines the necessary updates to scripts and configurations following the SSL/TLS and HTTPS enablement for all Docker services.

## 1. Test Scripts Updates

### Overview

The test scripts (`scripts/step*_test.sh`) currently test against the local Django development server. After enabling HTTPS with Nginx reverse proxy, they need to be updated to test against the Docker stack.

### Required Changes

- [x] Change `BASE_URL` from `http://127.0.0.1:8000` to `https://localhost:8443`
- [x] Add `-k` flag to all `curl` commands to accept self-signed certificates
- [x] Add `--insecure` flag to all `newman` commands to accept self-signed certificates
- [x] Remove local Django server startup (`python manage.py runserver`)
- [x] Update comments and documentation to reflect Docker-based testing

### Files to Update

- [x] `scripts/step1_test.sh`
- [x] `scripts/step2_test.sh`
- [x] `scripts/step3_test.sh`
- [x] `scripts/step4_test.sh`
- [x] `scripts/step5_test.sh`

### Example Changes for step1_test.sh

```bash
# Before
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

# After
BASE_URL="${BASE_URL:-https://localhost:8443}"

# Before
curl -sf "$BASE_URL/api/requests/" >/dev/null 2>&1

# After
curl -k -sf "$BASE_URL/api/requests/" >/dev/null 2>&1

# Before
newman run postman/APM_Observability_Step1.postman_collection.json \
  -e postman/APM_Observability.local.postman_environment.json \
  --reporters cli,json,junit,htmlextra

# After
newman run postman/APM_Observability_Step1.postman_collection.json \
  -e postman/APM_Observability.local.postman_environment.json \
  --insecure \
  --reporters cli,json,junit,htmlextra
```

## 2. MinIO Certificate Generation Script

### Overview

The `gen-minio-cert.sh` script generates certificates in the `docker/minio/` directory, but certificates are now centralized in `docker/certs/`.

### Required Changes

- [x] Update output directory from current directory to `../certs/`
- [x] Update certificate filenames to match existing convention (`public.crt`, `private.key`)
- [x] Add note that script is for development certificate generation only

### File to Update

- [x] `docker/minio/gen-minio-cert.sh`

### Example Changes

```bash
# Before
cd "$(dirname "$0")"
KEY="minio.key"
CSR="minio.csr"
CRT="minio.crt"

# After
CERT_DIR="../certs"
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"
KEY="private.key"
CSR="minio.csr"
CRT="public.crt"
```

## 3. Backup and Restore Scripts Verification

### Overview

Backup scripts use HTTPS endpoints and mounted CA certificates. Verify they work with SSL.

### Verification Steps

- [x] Confirm `docker/backup/pgbackrest.conf` uses `repo1-s3-ca-file = /tmp/ca/public.crt`
- [x] Confirm `repo1-s3-endpoint = https://minio:9000`
- [x] Test backup functionality with SSL-enabled MinIO
- [x] Test restore functionality with SSL-enabled MinIO

### Files to Check

- [x] `docker/backup/pgbackrest.conf`
- [x] `docker/backup/backup.sh`
- [x] `docker/backup/restore.sh`

## 4. Docker Compose Files Verification

### Overview

Ensure all Docker Compose files use correct certificate paths and SSL configurations.

### Verification Steps

- [x] Confirm `docker/docker-compose.yml` mounts `../docker/certs` to Nginx
- [x] Confirm `docker/docker-compose.backup.yml` mounts `./certs` to MinIO and other services
- [x] Confirm MinIO uses `--certs-dir /root/.minio/certs`
- [x] Confirm Nginx listens on 443 with SSL certificates

### Files to Check

- [x] `docker/docker-compose.yml`
- [x] `docker/docker-compose.backup.yml`

## 5. Documentation Updates

### Overview

Update README and documentation to reflect HTTPS setup.

### Required Changes

- [x] Update API endpoint examples to use `https://localhost:8443`
- [x] Add SSL certificate acceptance instructions for development
- [x] Document certificate renewal process for production
- [x] Update deployment instructions to include SSL setup

### Files to Update

- [x] `README.md`
- [x] `docs/DEPLOY.md`
- [x] `SSL_SETUP_CHECKLIST.md` (mark as completed)

## 6. Environment Variables

### Overview

Ensure environment variables support HTTPS configuration.

### Verification Steps

- [x] Check if `BASE_URL` environment variable is used in scripts
- [x] Consider adding `SSL_VERIFY=false` for development testing
- [x] Ensure production environment supports trusted certificates

## 7. Testing the Updates

### Test Plan

- [x] Run updated test scripts against Docker stack
- [x] Verify MinIO SSL connectivity works (HTTPS response confirmed)
- [x] Full backup/restore workflow testing (comprehensive checklist created in BACKUP_RESTORE_TESTING_CHECKLIST.md)
- [x] Test Django API endpoints over HTTPS
- [x] Verify certificate validation (should accept self-signed in dev)

### Commands to Test

```bash
# Test Django API over HTTPS
curl -k https://localhost:8443/api/requests/

# Test MinIO over HTTPS
curl -k https://localhost:9000

# Run updated test script
./scripts/step1_test.sh
```

## 8. Production Considerations

### Additional Steps for Production

- [x] Replace self-signed certificates with CA-issued certificates
- [x] Update certificate paths in all configurations
- [x] Configure certificate auto-renewal (e.g., with certbot)
- [x] Update DNS and firewall for HTTPS ports
- [x] Enable HSTS headers in Nginx configuration

---

**Priority Order:**

1. Update test scripts (critical for development workflow)
2. Update MinIO cert generation script
3. Verify backup scripts compatibility
4. Update documentation

**Note:** All changes maintain backward compatibility where possible. Development testing now uses the production-like Docker stack with SSL.</content>
<parameter name="filePath">/Users/nawfalrazouk/apm-observability/SSL_POST_IMPLEMENTATION_UPDATES.md
