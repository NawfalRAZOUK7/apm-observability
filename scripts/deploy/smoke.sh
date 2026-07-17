#!/usr/bin/env bash
# Track A — post-deploy smoke test: port-forward the service and hit /api/health/.
# Usage: scripts/deploy/smoke.sh <namespace> <release>
set -euo pipefail

NAMESPACE="${1:?namespace required}"
RELEASE="${2:?release required}"
SERVICE="${RELEASE}-apm-observability"
LOCAL_PORT="${SMOKE_PORT:-18080}"
RETRIES="${SMOKE_RETRIES:-10}"

echo "    port-forwarding svc/${SERVICE} in ${NAMESPACE}"
kubectl -n "${NAMESPACE}" port-forward "svc/${SERVICE}" "${LOCAL_PORT}:80" >/dev/null 2>&1 &
PF_PID=$!
trap 'kill "${PF_PID}" 2>/dev/null || true' EXIT
sleep 3

ok=0
for i in $(seq 1 "${RETRIES}"); do
  if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/api/health/" >/dev/null; then
    ok=1
    break
  fi
  echo "    health not ready (attempt ${i}/${RETRIES})"; sleep 3
done

if [[ "${ok}" != "1" ]]; then
  echo "    SMOKE TEST FAILED: /api/health/ never returned 200" >&2
  exit 1
fi
echo "    smoke test passed (/api/health/ = 200)"
