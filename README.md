# APM Observability (PostgreSQL + TimescaleDB)

APM Observability is a Django-based APM backend built on PostgreSQL + TimescaleDB,
with optional pgvector embeddings, pgBackRest backups (hot/cold), and a full
monitoring stack (Prometheus + Grafana). It supports a local single-node setup
and a multi-node cluster layout (DATA / CONTROL / APP).

## Highlights
- Time-series storage with TimescaleDB hypertables and continuous aggregates.
- Read/write routing with primary + replicas.
- Hot/cold backups with pgBackRest + MinIO (S3-compatible).
- Observability stack: Prometheus + Grafana + exporters.
- Optional Gemini embeddings with pgvector and semantic search.
- Ansible-based deployment automation.
- CI pipeline for lint, tests, and Docker compose smoke.

## Quick Start (single-machine cluster)
This is the recommended local mode that mirrors the multi-node design.

Prerequisites:
- Docker + Docker Compose
- Python 3.12 (optional for local management commands)

1) Create a local cluster config (gitignored):
```
cp configs/cluster/cluster.example.yml configs/cluster/cluster.yml
```

2) Generate the cluster env + Prometheus targets:
```
python scripts/cluster/switch_cluster_mode.py --config configs/cluster/cluster.yml
```

3) Bring up the stacks:
```
make up-data
make up-control
make up-app
```

4) Seed data and validate:
```
make seed
make validate
```

5) Monitoring:
```
make grafana
make prometheus
make targets
```

For the full runbook, see `docs/PRISE_EN_MAIN.md`.

## Main Stack (single-node, minimal)
```
docker compose -f docker/docker-compose.yml up -d --build
```

## Configuration
- `.env.docker` - web app defaults.
- `docker/cluster/.env.cluster` - cluster runtime configuration.
- `docker/.env.ports.localdev` - local port overrides.
- `configs/cluster/cluster.yml` - local config used by the switcher (gitignored).

## Backups (pgBackRest)
- Hot repository: `pgbackrest` bucket (MinIO).
- Cold repository: `pgbackrest-cold` bucket (MinIO).

Common commands:
```
make pgbackrest-info
make pgbackrest-check
make pgbackrest-full
make pgbackrest-full-repo2
```

Backup scheduling is defined in `docker/backup/pgbackrest-cron.sh`.

## Monitoring (TLS)
Grafana and Prometheus are exposed over HTTPS via a TLS proxy on CONTROL:
- `https://<CONTROL_NODE_IP>:3000` (Grafana)
- `https://<CONTROL_NODE_IP>:9090` (Prometheus)

The app Nginx is also HTTPS-only. Self-signed certs are used for local dev.

## AI Embeddings (Gemini + pgvector)
Optional semantic search is supported via Gemini embeddings.

Setup:
- Create `.env.gemini` (ignored) with `GEMINI_API_KEY=...`
- Ensure DB has pgvector: `docker/db/Dockerfile` + `docker/initdb/002_pgvector.sql`

Backfill embeddings:
```
python manage.py embed_apirequests --status-from 500 --limit 1000 --batch-size 16
```

Semantic search endpoint:
```
GET /api/requests/semantic-search/?q=timeout&limit=10
```

## Ansible Deployment
Ansible playbook and roles live in `infra/ansible/`.

Validate (local or remote):
```
ansible-playbook infra/ansible/site.yml --tags validate -e run_validation=true
```

## Testing
- Unit/API tests: `python manage.py test`
- Step scripts: `scripts/step1_test.sh` ... `scripts/step6_test.sh`
- Full suite: `bash scripts/run_all_tests.sh`

Test evidence is stored under `reports/`.

## Documentation
- `docs/PRISE_EN_MAIN.md` - step-by-step runbook.
- `docs/ARCHITECTURE.md` - repo structure and component roles.
- `docs/sections/` - project writeups mapped to assignment sections.

## Troubleshooting
- Re-generate cluster env: `python scripts/cluster/switch_cluster_mode.py --config configs/cluster/cluster.yml`
- Rebuild stacks: `make up-data`, `make up-control`, `make up-app`
- Wipe cluster containers/volumes: `make down-all`

If a container is unhealthy, wait 20-30 seconds and re-run `make up-data`.

---

Maintained for the APM Observability project (IDATA 3A 2025/2026).
