#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
INVENTORY=${ANSIBLE_INVENTORY:-"${ROOT_DIR}/infra/ansible/inventory/hosts.ini"}
PLAYBOOK=${ANSIBLE_PLAYBOOK:-"${ROOT_DIR}/infra/ansible/site.yml"}
PRIVATE_KEY_FILE=${ANSIBLE_PRIVATE_KEY_FILE:-""}

if [[ -n "${ANSIBLE_PRIVATE_KEY:-}" && -z "${PRIVATE_KEY_FILE}" ]]; then
  echo "ANSIBLE_PRIVATE_KEY is set, but it expects key contents."
  echo "Use ANSIBLE_PRIVATE_KEY_FILE for key paths."
fi

LOG_DIR="${ROOT_DIR}/reports/ansible"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/validation_${TIMESTAMP}.txt"

mkdir -p "${LOG_DIR}"

cmd=("ansible-playbook" "-i" "${INVENTORY}" "${PLAYBOOK}" "--tags" "validate" "-e" "run_validation=true" "-e" "install_docker=false")
if [[ -n "${PRIVATE_KEY_FILE}" ]]; then
  cmd+=("--private-key" "${PRIVATE_KEY_FILE}")
fi

"${cmd[@]}" | tee "${LOG_FILE}"

echo "Saved validation log to ${LOG_FILE}"
