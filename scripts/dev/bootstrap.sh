#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

CONFIG_PATH="${CONFIG:-configs/cluster/cluster.yml}"
ENV_PORTS="docker/.env.ports"
ENV_PORTS_LOCAL="docker/.env.ports.localdev"
ENV_CLUSTER="docker/cluster/.env.cluster"

APP_COMPOSE="docker/cluster/docker-compose.app.yml"
DATA_COMPOSE="docker/cluster/docker-compose.data.yml"
CONTROL_COMPOSE="docker/cluster/docker-compose.control.yml"

APP_CMD=(docker compose -p apm-app --env-file "$ENV_PORTS" --env-file "$ENV_PORTS_LOCAL" --env-file "$ENV_CLUSTER" -f "$APP_COMPOSE")
DATA_CMD=(docker compose -p apm-data --env-file "$ENV_PORTS" --env-file "$ENV_PORTS_LOCAL" --env-file "$ENV_CLUSTER" -f "$DATA_COMPOSE")
CONTROL_CMD=(docker compose -p apm-control --env-file "$ENV_PORTS" --env-file "$ENV_PORTS_LOCAL" --env-file "$ENV_CLUSTER" -f "$CONTROL_COMPOSE")

if [[ -f "$CONFIG_PATH" ]]; then
  python scripts/cluster/switch_cluster_mode.py --config "$CONFIG_PATH"
fi

"${DATA_CMD[@]}" up -d --build
"${CONTROL_CMD[@]}" up -d --build
"${APP_CMD[@]}" up -d --build

"${APP_CMD[@]}" exec web python manage.py migrate --noinput
"${APP_CMD[@]}" exec web python manage.py seed_apirequests --count 1000 --days 1

curl -kI https://localhost:18443/api/health/ | head -n 5
