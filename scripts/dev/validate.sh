#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_PORTS="docker/.env.ports"
ENV_PORTS_LOCAL="docker/.env.ports.localdev"
ENV_CLUSTER="docker/cluster/.env.cluster"

APP_COMPOSE="docker/cluster/docker-compose.app.yml"
CONTROL_COMPOSE="docker/cluster/docker-compose.control.yml"

APP_CMD=(docker compose -p apm-app --env-file "$ENV_PORTS" --env-file "$ENV_PORTS_LOCAL" --env-file "$ENV_CLUSTER" -f "$APP_COMPOSE")
CONTROL_CMD=(docker compose -p apm-control --env-file "$ENV_PORTS" --env-file "$ENV_PORTS_LOCAL" --env-file "$ENV_CLUSTER" -f "$CONTROL_COMPOSE")

"${APP_CMD[@]}" exec web python manage.py check_cluster_dbs
"${CONTROL_CMD[@]}" exec pgbackrest pgbackrest --stanza=apm info
curl -kI https://localhost:18443/api/health/ | head -n 5
