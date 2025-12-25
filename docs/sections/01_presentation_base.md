# 1. Presentation de la base

## 1.1 Base choisie (projet)
Nous utilisons PostgreSQL avec TimescaleDB (time-series) et pgvector (embeddings),
emballe en Docker pour les environnements local/cluster.

Lien projet:
- Extension TimescaleDB + hypertable: `observability/migrations/0002_timescale.py`
- CAGG hourly/daily: `observability/migrations/0003_hourly_cagg.py`, `observability/migrations/0004_daily_cagg.py`
- pgvector: `docker/initdb/002_pgvector.sql`, `observability/migrations/0008_embeddings.py`
- Image DB custom: `docker/db/Dockerfile`

## 1.2 Presentation de la base
PostgreSQL est une base relationnelle open-source. TimescaleDB ajoute des
capacites time-series (hypertables, continuous aggregates) ideales pour les
metriques APM et les requetes temporelles a grande echelle.

Dans notre projet:
- Les requetes APM sont stockees dans `observability.models.ApiRequest`.
- Le temps est la cle de partition (hypertable) pour les volumes importants.

## 1.3 Use cases de la base
Use cases typiques de PostgreSQL/TimescaleDB:
- Observabilite (logs, traces, metriques).
- Donnees temps reel et time-series (IoT, monitoring, finance).
- APIs analytiques (KPI, top endpoints, taux d'erreur).

Lien projet:
- Endpoints KPI: `observability/views.py`
- SQL analytiques: `observability/analytics/sql.py`
- Dashboards: `docker/monitoring/grafana/provisioning/dashboards/`

Exemples d'utilisateurs (liste publique via case studies Timescale/Tiger Data):
- CERN (science research)
- Toyota (automotive)
- Speedcast (telecom)
- Replicated (SaaS)
- Evergen (energy)
Source: https://www.tigerdata.com/case-studies

## 1.4 Architecture interne (fichiers, processus)
PostgreSQL utilise un modele multi-processus avec:
- postmaster + backend par connexion.
- WAL (Write-Ahead Log) pour la durabilite et la replication.
- fichiers data + index (B-Tree), et extensions (Timescale, pgvector).

TimescaleDB ajoute:
- hypertables (partitionnement temporel).
- chunks par intervalle (ex: 1 jour).
- CAGG (continuous aggregates) pour pre-calculs.

Lien projet:
- WAL/backup: `docker/backup/pgbackrest-server.conf`, `docker/backup/pgbackrest-client.conf`
- Replication: `docker/cluster/docker-compose.data.yml`, `docker/cluster/replica/`

Sources officielles:
- PostgreSQL Architecture: https://www.postgresql.org/docs/current/architecture.html
- PostgreSQL WAL: https://www.postgresql.org/docs/current/wal-intro.html
- Timescale Hypertables: https://docs.timescale.com/use-timescale/latest/hypertables/
- Timescale Continuous Aggregates: https://docs.timescale.com/use-timescale/latest/continuous-aggregates/

## 1.5 Particularites de la base
Particularites PostgreSQL/TimescaleDB:
- Scalabilite time-series via hypertables + chunks.
- SQL complet + extensions (pgvector, Timescale).
- Indexation avancee (composite, partielle) pour performance.

Lien projet:
- Indexes: `observability/models.py`, `observability/migrations/0007_task7_indexes.py`
- Embeddings: `observability/ai/gemini.py`

## 1.6 Comparaison avec Oracle Database
Oracle:
- Proprietaire, licensing couteux, enterprise-grade.
- Support commercial fort, fonctionnalites avancees (RAC, etc.).

PostgreSQL/Timescale:
- Open-source, plus leger et facile a dockeriser.
- Large ecosysteme d'extensions, cout d'usage reduit.

Choix projet:
- Objectif pedagogique + infra locale/cluster => PostgreSQL/Timescale est ideal.

## 1.7 On-premise vs cloud (cout/perf)
On-premise (LAN local):
- Controle total, cout materiel interne.
- Performance stable si stockage local (SSD) et latence faible.
- Maintenance lourde (backup, patching, monitoring).

Cloud (AWS RDS/Aurora/Timescale Cloud):
- Scalabilite/HA geres, operations automatisees.
- Cout variable (compute, storage, I/O, egress).
- Latence reseau plus elevee si app/DB separes.

Comparaison rapide:
- Cout: on-prem capex vs cloud opex (facturation a l'usage).
- Performance: on-prem faible latence; cloud depend du type d'instance/stockage.
- Maintenance: on-prem manuel; cloud geres (backups, upgrades).

Sources tarifs:
- AWS RDS PostgreSQL pricing: https://aws.amazon.com/rds/postgresql/pricing/
- Timescale Cloud pricing: https://www.timescale.com/pricing

Lien projet:
- Local/cluster: `docker/cluster/docker-compose.*.yml`
- Cold storage S3 compatible: MinIO `docker/minio/` (migration future AWS)
