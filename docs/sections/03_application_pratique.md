# 3. Application pratique

## 3.1 Securiser backend <-> base (roles)
Objectif: separer lecture/criture.
- `apm_writer` pour l'agent (write)
- `apm_reader` pour Grafana/analytics (read)

Lien projet:
- Roles SQL: `docker/initdb/001_roles.sql`
- Routing: `apm_platform/db_router.py`, `apm_platform/db_middleware.py`
- Settings: `apm_platform/settings.py` (DATABASES / READ_AFTER_WRITE_TTL)
- Env: `POSTGRES_APP_USER`, `POSTGRES_READONLY_USER` dans `.env.docker` et `docker/cluster/.env.cluster`

## 3.2 Programmation de backup (S3 hot/cold)
Hot storage: MinIO bucket `pgbackrest`
Cold storage: MinIO bucket `pgbackrest-cold` (future AWS Glacier)

Lien projet:
- pgBackRest config: `docker/backup/pgbackrest-client.conf`, `docker/backup/pgbackrest-server.conf`
- Cron schedule: `docker/backup/pgbackrest-cron.sh`
- MinIO init: `docker/minio/init.sh`
- Control stack: `docker/cluster/docker-compose.control.yml`

Commandes:
```
make pgbackrest-info
make pgbackrest-full
make pgbackrest-full-repo2
```

## 3.3 Seeding avec Faker
Objectif: remplir la base avec donnees realistes.

Lien projet:
- Commande: `observability/management/commands/seed_apirequests.py`
- Helper: `scripts/seed_faker.sh`
- Make target: `make seed`

## 3.4 Simulation de panne + recovery
Objectif: valider resilience du cluster (primary, replicas, backup).

Lien projet:
- Drills: `scripts/drills/00_baseline.sh`, `01_primary_restore.sh`,
  `02_failover_replica.sh`, `03_minio_outage.sh`
- Tests: `scripts/step6_test.sh`

## 3.5 Optimisation par indexes
Indexes utilises:
- Composite indexes (service/endpoint/time)
- Index partiel pour erreurs (status_code >= 500)
- Indexes pour KPIs (hourly/daily)

Lien projet:
- Index definitions: `observability/models.py`
- Migrations: `observability/migrations/0005_step5_indexes.py`,
  `observability/migrations/0007_task7_indexes.py`
