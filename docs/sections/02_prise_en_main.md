# 2. Prise en main

## 2.1 Demarrage d'une seule instance
Option simple (main stack):
```
docker compose -f docker/docker-compose.yml up -d --build
```

Option cluster (single-machine, 3 stacks):
```
python scripts/cluster/switch_cluster_mode.py --config configs/cluster/cluster.yml
make up-data
make up-control
make up-app
```

Lien projet:
- Runbook complet: `docs/PRISE_EN_MAIN.md`
- Compose principal: `docker/docker-compose.yml`
- Compose cluster: `docker/cluster/docker-compose.*.yml`

## 2.2 Procedure de connexion a la base
Depuis le conteneur:
```
docker compose -f docker/docker-compose.yml exec db psql -U apm -d apm
```

Depuis Django (app):
- Variables `POSTGRES_*` dans `.env.docker` ou `docker/cluster/.env.cluster`.
- Connexion gered par Django settings: `apm_platform/settings.py`.

## 2.3 Interaction avec la base
Creation de tables et migrations:
```
python manage.py migrate
```

Insertion/seed (ORM):
```
python manage.py seed_apirequests --count 1000 --days 1
```

Tables et objets utiles:
- `observability.ApiRequest` (table principale)
- `observability.ApiRequestEmbedding` (embeddings)
- CAGG (hourly/daily) pour KPIs (materialized views)

Lien projet:
- Models: `observability/models.py`
- Migrations: `observability/migrations/`
- Seed: `observability/management/commands/seed_apirequests.py`

## 2.4 Particularites fonctionnelles
Fonctionnalites principales exploitees:
- Hypertable (time-series) pour ApiRequest.
- CAGG hourly/daily pour KPIs.
- Embeddings vectoriels (pgvector).
- Read routing (primary/replica) cote application.

Lien projet:
- Hypertable: `observability/migrations/0002_timescale.py`
- CAGG: `observability/migrations/0003_hourly_cagg.py`, `0004_daily_cagg.py`
- Read routing: `apm_platform/db_router.py`, `apm_platform/db_middleware.py`

## 2.5 Lancement d'un cluster 3 machines (HA)
Architecture logique:
- DATA node: DB primary + replicas + pgbackrest server
- CONTROL node: MinIO + pgbackrest client + monitoring
- APP node: Django + nginx

En pratique (multi-node):
- Mettre les IPs reelles dans `configs/cluster/cluster.yml`
- Relancer le switcher pour generer `.env.cluster`

Lien projet:
- Switcher: `scripts/cluster/switch_cluster_mode.py`
- Env cluster: `docker/cluster/.env.cluster`

## 2.6 Assurer la connexion entre machines
Verification des routes primary/replicas:
```
python manage.py check_cluster_dbs
```

Checks automatiques:
```
make check-dbs
bash scripts/step2_test.sh
```

Variables reseau:
- `CLUSTER_DB_PRIMARY_HOST`, `CLUSTER_DB_REPLICA_HOSTS`, `CLUSTER_DB_HOSTS`
- IPs des nodes dans `docker/cluster/.env.cluster`
