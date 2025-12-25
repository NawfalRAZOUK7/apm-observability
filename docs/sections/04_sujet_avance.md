# 4. Sujet avance

## 4.1 IA / Embeddings (Google Gemini)
Objectif: enrichir les erreurs et requetes avec embeddings pour recherche semantique.

Lien projet:
- Client Gemini: `observability/ai/gemini.py`
- Commande backfill: `observability/management/commands/embed_apirequests.py`
- Modele embeddings: `observability/models.py` (ApiRequestEmbedding)
- Migration: `observability/migrations/0008_embeddings.py`
- pgvector: `docker/db/Dockerfile`, `docker/initdb/002_pgvector.sql`
- Endpoint search: `observability/views.py` (`/api/requests/semantic-search/`)

Configuration:
- Cle locale: `.env.gemini` (ignoree par git)
- CI: `GEMINI_API_KEY` en secrets GitHub

## 4.2 Deploiement Ansible (Terraform optionnel)
Objectif: deploiement repeatable sur 1 ou plusieurs machines.

Lien projet:
- Playbook: `infra/ansible/site.yml`
- Inventory: `infra/ansible/inventory/hosts.ini`
- Vars: `infra/ansible/group_vars/*.yml`
- Roles: `infra/ansible/roles/` (stack_data, stack_control, stack_app)
- Validation: `infra/ansible/roles/validate/`, `scripts/ansible/validate.sh`

Terraform:
- Non present actuellement (possible ajout futur si besoin cloud).

## 4.3 Observabilite (Grafana + Prometheus)
Objectif: visualiser la sante infra + KPIs APM.

Lien projet:
- Prometheus config: `docker/monitoring/prometheus.yml`
- Grafana datasources/dashboards:
  `docker/monitoring/grafana/provisioning/`
- Control stack: `docker/cluster/docker-compose.control.yml`
- TLS proxy monitoring: `docker/monitoring/nginx/conf.d/monitoring.conf`
- Make targets: `make grafana`, `make prometheus`, `make targets`
