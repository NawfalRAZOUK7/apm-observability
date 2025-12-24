# pgBackRest — Option 2 (TLS server / mTLS) + MinIO (S3 over HTTPS)

This project uses **pgBackRest host protocol over TLS (mTLS)** between:

* **pgbackrest (client)** → **pgbackrest-server (server)** on port **8432**
* **pgbackrest-server** → **PostgreSQL** over the internal Docker network (TCP 5432)
* **pgBackRest** → **MinIO** over **HTTPS** (S3 API)

> SSH is **not used** in this setup.

---

## Files involved

### Certificates

1. MinIO TLS (dev self-signed with SANs)

* `docker/certs/public.crt`
* `docker/certs/private.key`

Generate:

```bash
bash docker/certs/setup-ssl.sh
# or
bash docker/minio/gen-minio-cert.sh
```

2. pgBackRest mTLS

* `docker/certs/pgbackrest/ca.crt`
* `docker/certs/pgbackrest/server.crt`, `server.key`
* `docker/certs/pgbackrest/client.crt`, `client.key`

Generate:

```bash
bash docker/certs/gen_pgbackrest_mtls.sh
```

### pgBackRest config

* Server config: `docker/backup/pgbackrest-server.conf`
* Client config: `docker/backup/pgbackrest-client.conf`

### pgpass (avoid password prompt)

* `docker/backup/pgpass` (DO NOT COMMIT)

Ensure permissions on host:

```bash
chmod 600 docker/backup/pgpass
```

---

## Bring up the backup stack

```bash
docker compose -f docker/docker-compose.backup.yml up -d --build
```

The stack includes:

* `db` + `db-init` (idempotent init gate)
* `minio` + `minio-init` (creates bucket `pgbackrest`)
* `pgbackrest-server` (TLS server)
* `pgbackrest` (client container for running commands)

---

## Commands

### Create stanza (once)

```bash
docker compose -f docker/docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=apm stanza-create
```

### Check

```bash
docker compose -f docker/docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=apm check
```

### Full backup

```bash
docker compose -f docker/docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=apm backup --type=full
```

### Info

```bash
docker compose -f docker/docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=apm info
```

---

## Common issues

### 1) Password prompt (should never happen)

* Ensure `docker/backup/pgpass` exists
* Ensure `chmod 600 docker/backup/pgpass` on the **host**
* Ensure the host name in pgpass matches `pg1-host` in `pgbackrest-server.conf` (default: `db`)

### 2) TLS errors between client and pgbackrest-server

* Ensure client CN matches server auth mapping:

  * Client cert CN: `pgbr-client`
  * Server config: `tls-server-auth=pgbr-client=apm`
* Ensure server SAN/CN is `pgbackrest-server`

### 3) MinIO TLS verify errors

* Ensure `repo1-s3-ca-file=/certs/public.crt` points to the CA/cert used by MinIO
* Ensure MinIO cert has SAN `DNS:minio`

---

## Security notes

* Never commit `docker/backup/pgpass`
* Never commit private keys (`docker/certs/*.key`, `docker/certs/pgbackrest/*.key`)
