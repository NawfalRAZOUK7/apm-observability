# SSL/TLS & HTTPS Enablement Checklist for All Docker Services

## 1. Certificate Generation

- [x] Create a directory for certificates: `docker/certs/`
- [x] Generate a self-signed certificate and private key (for dev):
  ```sh
  mkdir -p docker/certs
  openssl req -x509 -newkey rsa:4096 -keyout docker/certs/private.key -out docker/certs/public.crt -days 365 -nodes -subj "/CN=localhost"
  ```
- [ ] (Optional) Use a trusted CA for production certificates

## 2. MinIO SSL Configuration

- [x] Mount `docker/certs/` into MinIO container at `/root/.minio/certs/`
- [x] Ensure MinIO command includes `--certs-dir /root/.minio/certs`
- [x] Restart MinIO and verify access at `https://localhost:9000`

## 3. Django SSL Configuration

- [x] (Recommended) Use a reverse proxy (Nginx/Caddy) for HTTPS
- [ ] (Optional for dev) Use `runserver_plus` with certs:
  ```sh
  pip install django-extensions
  python manage.py runserver_plus --cert-file docker/certs/public.crt --key-file docker/certs/private.key
  ```
- [x] For production, configure Django to trust `X-Forwarded-Proto` and set `SECURE_SSL_REDIRECT = True`

## 4. Reverse Proxy (Nginx/Caddy) Setup

- [x] Add Nginx or Caddy service to `docker-compose.yml`
- [x] Mount `docker/certs/` into the proxy container
- [x] Configure proxy to serve HTTPS on 443 and forward to Django/MinIO
- [ ] Example Nginx config:
  ```nginx
  server {
      listen 443 ssl;
      server_name localhost;
      ssl_certificate     /etc/nginx/certs/public.crt;
      ssl_certificate_key /etc/nginx/certs/private.key;
      location /api/ {
          proxy_pass http://minio:9000;
      }
      location / {
          proxy_pass http://django:8000;
      }
  }
  ```
- [x] Update Docker Compose to mount config and certs

## 5. Other Services (if any)

- [x] For any other web services, mount `docker/certs/` and configure them to use the certs for HTTPS

## 6. Test & Validate

- [x] Rebuild and restart all containers: `docker compose up -d --build`
- [x] Access all endpoints via `https://` and accept self-signed cert warning (for dev)
- [x] Verify all services are accessible and secure

---

**Tip:** For production, always use certificates from a trusted CA and automate renewal (e.g., with Let's Encrypt).
