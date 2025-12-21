# Create the bucket using MinIO client (`mc`) from your host

This guide creates the MinIO bucket **from your host machine** (not from inside Docker).

## Prerequisites

* Your MinIO service must expose:

  * API: `9000:9000`
  * Console: `9001:9001`
* MinIO credentials (from `docker-compose.backup.yml`):

  * `MINIO_ROOT_USER=minioadmin`
  * `MINIO_ROOT_PASSWORD=minioadmin123`

## 1) Start MinIO

From the project root:

```bash
docker compose -f docker/docker-compose.backup.yml up -d minio
```

(Optional) Confirm MinIO is running:

```bash
docker ps | grep minio
```

## 2) Install `mc` (macOS)

### Apple Silicon (M1/M2/M3)

```bash
curl -L https://dl.min.io/client/mc/release/darwin-arm64/mc -o mc
chmod +x mc
sudo mv mc /usr/local/bin/mc
mc --version
```

### Intel Mac

```bash
curl -L https://dl.min.io/client/mc/release/darwin-amd64/mc -o mc
chmod +x mc
sudo mv mc /usr/local/bin/mc
mc --version
```

## 3) Configure the alias (IMPORTANT: use API port 9000)

MinIO’s **web console** is on `9001`, but the **S3 API** that `mc` talks to is on `9000`.

```bash
mc alias set local http://localhost:9000 minioadmin minioadmin123
```

Verify alias:

```bash
mc alias list
```

## 4) Create the bucket

```bash
mc mb --ignore-existing local/apm-backups
```

## 5) Verify the bucket exists

```bash
mc ls local
mc ls local/apm-backups
```

## Troubleshooting

* If alias fails, confirm MinIO is reachable:

  * API: `http://localhost:9000`
  * Console: `http://localhost:9001`
* If you changed credentials in compose, update the `mc alias set` command accordingly.
