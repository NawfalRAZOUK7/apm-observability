#!/usr/bin/env bash

repo_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$script_dir/../.." && pwd
}

cd_repo_root() {
  cd "$(repo_root)"
}

load_env_files() {
  local env_file
  for env_file in "$@"; do
    if [[ -f "$env_file" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "$env_file"
      set +a
    fi
  done
}

configure_step_environment() {
  STACK="${STACK:-main}"
  APP_HOST="${APP_HOST:-127.0.0.1}"

  load_env_files docker/.env.ports docker/.env.ports.localdev

  if [[ "$STACK" == "cluster" ]]; then
    APP_HTTPS_PORT="${APP_HTTPS_PORT:-${CLUSTER_APP_NGINX_HTTPS_HOST_PORT:-18443}}"
    POSTMAN_ENV_DEFAULT="postman/APM_Observability.cluster.postman_environment.json"
    DB_PORT_DEFAULT="${CLUSTER_DATA_DB_HOST_PORT:-5432}"
  else
    APP_HTTPS_PORT="${APP_HTTPS_PORT:-${MAIN_NGINX_HTTPS_HOST_PORT:-8443}}"
    POSTMAN_ENV_DEFAULT="postman/APM_Observability.main.postman_environment.json"
    DB_PORT_DEFAULT="${MAIN_DB_HOST_PORT:-5432}"
  fi

  POSTMAN_ENV="${POSTMAN_ENV:-$POSTMAN_ENV_DEFAULT}"
  BASE_URL="${BASE_URL:-https://${APP_HOST}:${APP_HTTPS_PORT}}"
  DB_HOST="${DB_HOST:-localhost}"
  DB_PORT="${DB_PORT:-$DB_PORT_DEFAULT}"
  DB_NAME="${DB_NAME:-apm}"
  DB_USER="${DB_USER:-apm}"
  DB_PASSWORD="${DB_PASSWORD:-apm}"
  REPORT_DIR="${REPORT_DIR:-reports}"
  SSL_VERIFY="${SSL_VERIFY:-false}"

  if [[ "$SSL_VERIFY" == "false" ]]; then
    CURL_SSL_FLAGS="-k"
    NEWMAN_SSL_FLAGS="--insecure"
  else
    CURL_SSL_FLAGS=""
    NEWMAN_SSL_FLAGS=""
  fi
}

wait_for_django_api() {
  echo "Waiting for Django API to be ready..."
  for i in {1..40}; do
    if curl $CURL_SSL_FLAGS -sf "$BASE_URL/api/requests/" >/dev/null 2>&1; then
      echo "Django API is ready."
      return 0
    fi
    echo "Django API not ready yet. Waiting ($i/40)..."
    sleep 0.25
  done
}
