#!/usr/bin/env bash
# Install Argo CD into the current kube-context and deploy the app via GitOps.
#
# This script removes the two usual friction points for a local demo:
#   1. Git source: Argo CD syncs the chart FROM Git. The script targets the
#      CURRENT branch (not a hardcoded main) and can push it for you (PUSH=1).
#   2. App image base: the image is built from a NON-Docker-Hub mirror by default
#      (AWS ECR Public), so a blocked Docker Hub does not break the build.
#
# Prerequisites: kubectl + a reachable cluster (docker-desktop k8s, kind, minikube),
# docker, and git.
#
# Env vars:
#   ARGOCD_VERSION   Argo CD manifests ref (default: stable)
#   APP_MANIFEST     base Application manifest (default: deploy/argocd/application-local.yaml)
#   TARGET_REVISION  git branch Argo CD tracks (default: current branch)
#   PUSH             1 = push the current branch to origin before syncing (default: 0)
#   BUILD_IMAGE      1 = build the app image locally (default: 1)
#   IMAGE_TAG        local image tag (default: apm-web:local)
#   BASE_IMAGE       Python base image (default: AWS ECR Public mirror, not Docker Hub)
set -euo pipefail

ARGOCD_VERSION="${ARGOCD_VERSION:-stable}"
APP_MANIFEST="${APP_MANIFEST:-deploy/argocd/application-local.yaml}"
TARGET_REVISION="${TARGET_REVISION:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"
PUSH="${PUSH:-0}"
BUILD_IMAGE="${BUILD_IMAGE:-1}"
IMAGE_TAG="${IMAGE_TAG:-apm-web:local}"
BASE_IMAGE="${BASE_IMAGE:-public.ecr.aws/docker/library/python:3.12-slim}"

command -v kubectl >/dev/null 2>&1 || { echo "ERROR: kubectl not found." >&2; exit 1; }
kubectl cluster-info >/dev/null 2>&1 || {
  echo "ERROR: no reachable cluster. Start docker-desktop k8s / kind / minikube first." >&2
  exit 1
}
ctx="$(kubectl config current-context)"
echo ">> kube-context : ${ctx}"
echo ">> git revision : ${TARGET_REVISION}"

# 0) Ensure the chart is on the remote at the tracked branch (GitOps reads Git).
if [[ "${PUSH}" == "1" ]]; then
  echo ">> Pushing ${TARGET_REVISION} to origin so Argo CD can read the chart..."
  git push origin "HEAD:${TARGET_REVISION}"
else
  echo ">> NOTE: Argo CD syncs deploy/helm from Git@${TARGET_REVISION}."
  echo "   If you have local, unpushed changes, run: PUSH=1 make argocd-up"
  echo "   (or: git push origin HEAD:${TARGET_REVISION})"
fi

# 1) Install Argo CD (control-plane images come from quay.io/ghcr, not Docker Hub).
kubectl get ns argocd >/dev/null 2>&1 || kubectl create namespace argocd
echo ">> Installing Argo CD (${ARGOCD_VERSION})..."
kubectl apply -n argocd \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
echo ">> Waiting for argocd-server to be ready..."
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s

# 2) Build the app image from a non-Docker-Hub base and make it available.
if [[ "${BUILD_IMAGE}" == "1" ]]; then
  echo ">> Building ${IMAGE_TAG} from base ${BASE_IMAGE} (bypasses Docker Hub)..."
  docker build --build-arg "PYTHON_IMAGE=${BASE_IMAGE}" -t "${IMAGE_TAG}" .
  if [[ "${ctx}" == kind-* ]]; then
    echo ">> Loading image into kind cluster..."
    kind load docker-image "${IMAGE_TAG}" --name "${ctx#kind-}"
  fi
fi

# 3) Deploy the app via GitOps, tracking the current branch.
tmp_manifest="$(mktemp)"
trap 'rm -f "${tmp_manifest}"' EXIT
sed -E "s|^([[:space:]]*targetRevision:).*|\1 ${TARGET_REVISION}|" "${APP_MANIFEST}" > "${tmp_manifest}"
echo ">> Applying Argo CD Application (targetRevision=${TARGET_REVISION})..."
kubectl apply -f "${tmp_manifest}"

# 4) Access information.
cat <<'EOF'

=================== Argo CD ready ===================
  UI:        kubectl -n argocd port-forward svc/argocd-server 8080:443
             then open https://localhost:8080  (accept the self-signed cert)
  User:      admin
  Password:  kubectl -n argocd get secret argocd-initial-admin-secret \
               -o jsonpath='{.data.password}' | base64 -d ; echo
  App:       apm-observability  (destination namespace: apm)
=====================================================
Tip: `make argocd-ui` and `make argocd-password` wrap the two commands above.
EOF
