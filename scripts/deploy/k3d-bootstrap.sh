#!/usr/bin/env bash
# Track A — create a local k3d cluster with staging + production namespaces.
# This is the free ($0) stand-in for managed EKS/GKE/AKS: one local cluster,
# two namespaces. ArgoCD (optional) then syncs both from Git.
#
# Requires: k3d, kubectl, helm. Usage: scripts/deploy/k3d-bootstrap.sh
set -euo pipefail

CLUSTER="${K3D_CLUSTER:-apm}"
NAMESPACES=("staging" "production")

echo "==> Creating k3d cluster '${CLUSTER}' (if absent)"
if ! k3d cluster list 2>/dev/null | grep -q "^${CLUSTER}\b"; then
  k3d cluster create "${CLUSTER}" \
    --agents 1 \
    --port "8081:80@loadbalancer" \
    --wait
else
  echo "    cluster '${CLUSTER}' already exists"
fi

kubectl config use-context "k3d-${CLUSTER}"

for ns in "${NAMESPACES[@]}"; do
  echo "==> Ensuring namespace '${ns}'"
  kubectl get namespace "${ns}" >/dev/null 2>&1 || kubectl create namespace "${ns}"
done

if [[ "${INSTALL_ARGOCD:-0}" == "1" ]]; then
  echo "==> Installing Argo CD"
  kubectl get namespace argocd >/dev/null 2>&1 || kubectl create namespace argocd
  kubectl apply -n argocd \
    -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  echo "    apply deploy/argocd/application-staging.yaml and application-production.yaml when ready"
fi

echo "==> Done. Namespaces:"
kubectl get namespaces staging production
