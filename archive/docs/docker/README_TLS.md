# pgBackRest — Option 2 (TLS server) + db-init (healthcheck) — quick commands

## 1) Generate pgBackRest mTLS certs

```bash
bash docker/certs/gen_pgbackrest_mtls.sh
```

## 2) Start the backup stack

```bash
docker compose -f docker/docker-compose.backup.yml up -d --build
```

## 3) Create the stanza (once)

```bash
docker compose -f docker/docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=apm stanza-create
```

## 4) Check

```bash
docker compose -f docker/docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=apm check
```

## 5) Full backup

```bash
docker compose -f docker/docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=apm backup --type=full
```

## 6) Info

```bash
docker compose -f docker/docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=apm info
```

## Fast troubleshooting

* Password prompt: make sure `docker/backup/pgpass` exists, is mounted, and chmod 600.
* TLS fails: server CN/SAN must be `pgbackrest-server`; client CN must match `tls-server-auth` (`pgbr-client`).
