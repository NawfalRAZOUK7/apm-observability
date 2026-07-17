#!/usr/bin/env bash
# Track A — deploy the Helm chart to a namespace with atomic rollout + smoke test.
#
# Usage:
#   scripts/deploy/deploy-k8s.sh <staging|production> <image_tag>
#
# `helm upgrade --atomic` auto-rolls back on a failed rollout, giving us
# automatic rollback on health-check failure for free. A post-deploy smoke test
# provides a second gate. Optionally annotates Grafana with the deployment.
set -euo pipefail

ENVIRONMENT="${1:?usage: deploy-k8s.sh <staging|production> <image_tag>}"
IMAGE_TAG="${2:?image tag required}"
RELEASE="apm-${ENVIRONMENT}"
CHART_DIR="$(cd "$(dirname "$0")/../../deploy/helm/apm-observability" && pwd)"
VALUES="${CHART_DIR}/values-${ENVIRONMENT}.yaml"
TIMEOUT="${DEPLOY_TIMEOUT:-180s}"

if [[ ! -f "${VALUES}" ]]; then
  echo "No values file for environment '${ENVIRONMENT}' (${VALUES})" >&2
  exit 1
fi

# Record a deployment for DORA metrics (Phase 18). No-op unless DORA_ENDPOINT is
# set. status: success | rolled_back | failed.
record_dora() {
  local status="$1"
  [[ -n "${DORA_ENDPOINT:-}" ]] || return 0
  curl -fsS -X POST "${DORA_ENDPOINT%/}/api/dora/deployments/" \
    -H "Content-Type: application/json" \
    -d "{\"environment\":\"${ENVIRONMENT}\",\"version\":\"${IMAGE_TAG}\",\"commit_sha\":\"${GIT_SHA:-}\",\"status\":\"${status}\",\"triggered_by\":\"deploy-k8s.sh\"}" \
    >/dev/null 2>&1 || echo "    (dora record failed, non-fatal)"
}

if [[ "${ROLLOUT:-0}" == "1" ]]; then
  # Progressive delivery (Phase 17): Argo Rollouts manages canary progression +
  # metric analysis itself, so we don't use helm --atomic/--wait here.
  echo "==> Deploying ${RELEASE} (tag=${IMAGE_TAG}) as an Argo Rollout"
  helm upgrade --install "${RELEASE}" "${CHART_DIR}" \
    --namespace "${ENVIRONMENT}" --create-namespace \
    --values "${CHART_DIR}/values.yaml" --values "${VALUES}" \
    --set image.tag="${IMAGE_TAG}" --set rollout.enabled=true

  echo "==> Watching canary rollout (auto-aborts on SLO breach)"
  if ! kubectl argo rollouts status "${RELEASE}-apm-observability" \
        -n "${ENVIRONMENT}" --timeout "${TIMEOUT}"; then
    echo "    canary failed analysis — undoing" >&2
    kubectl argo rollouts undo "${RELEASE}-apm-observability" -n "${ENVIRONMENT}" || true
    record_dora "rolled_back"
    exit 1
  fi
else
  echo "==> Deploying ${RELEASE} (tag=${IMAGE_TAG}) to namespace ${ENVIRONMENT}"
  helm upgrade --install "${RELEASE}" "${CHART_DIR}" \
    --namespace "${ENVIRONMENT}" --create-namespace \
    --values "${CHART_DIR}/values.yaml" \
    --values "${VALUES}" \
    --set image.tag="${IMAGE_TAG}" \
    --atomic --timeout "${TIMEOUT}" \
    --wait

  echo "==> Waiting for rollout"
  kubectl -n "${ENVIRONMENT}" rollout status "deployment/${RELEASE}-apm-observability" --timeout="${TIMEOUT}"
fi

echo "==> Smoke test"
"$(dirname "$0")/smoke.sh" "${ENVIRONMENT}" "${RELEASE}"

if [[ -n "${GRAFANA_URL:-}" && -n "${GRAFANA_TOKEN:-}" ]]; then
  echo "==> Annotating Grafana"
  curl -fsS -X POST "${GRAFANA_URL%/}/api/annotations" \
    -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"tags\":[\"deploy\",\"${ENVIRONMENT}\"],\"text\":\"Deployed ${RELEASE} tag ${IMAGE_TAG}\"}" \
    >/dev/null || echo "    (grafana annotation failed, non-fatal)"
fi

record_dora "success"
echo "==> ${RELEASE} deployed successfully."
