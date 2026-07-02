# Kubernetes deployment (Helm + GitOps)

This directory holds the Kubernetes delivery path, complementing the Docker
Compose (single-node) and Ansible (cluster) paths.

```
deploy/
  helm/apm-observability/   # Helm chart for the API (+ optional in-cluster TimescaleDB)
  argocd/application.yaml    # ArgoCD Application (declarative GitOps)
```

## Prerequisites

- A cluster: [kind](https://kind.sigs.k8s.io/) or
  [minikube](https://minikube.sigs.k8s.io/) for local use.
- `kubectl` and `helm` 3.x.

## Deploy with Helm (imperative)

```bash
# From the repo root. Uses the in-cluster TimescaleDB by default (postgres.enabled=true).
helm lint deploy/helm/apm-observability
helm install apm deploy/helm/apm-observability --namespace apm --create-namespace

# Watch rollout, then port-forward the API
kubectl -n apm rollout status deploy/apm-apm-observability
kubectl -n apm port-forward svc/apm-apm-observability 8000:80
# open http://localhost:8000/api/docs/
```

Render the manifests without installing (useful for review / `kubeconform`):

```bash
helm template apm deploy/helm/apm-observability | less
```

### Common overrides

```bash
# Use a managed Postgres instead of the in-cluster one
helm install apm deploy/helm/apm-observability \
  --set postgres.enabled=false \
  --set config.POSTGRES_HOST=my-db.internal \
  --set secrets.POSTGRES_PASSWORD=*** \
  --set secrets.DJANGO_SECRET_KEY=***

# Expose via Ingress + enable autoscaling + tracing
helm upgrade apm deploy/helm/apm-observability \
  --set ingress.enabled=true --set ingress.hosts[0].host=apm.example.com \
  --set autoscaling.enabled=true \
  --set config.OTEL_ENABLED=1
```

> Secrets here are chart defaults for local demos only. In real environments,
> inject them from a secret manager (e.g. External Secrets, Sealed Secrets) and
> never commit real values.

## Deploy with ArgoCD (declarative GitOps)

With ArgoCD already installed in the cluster:

```bash
kubectl apply -f deploy/argocd/application.yaml
```

ArgoCD then continuously syncs the cluster to the Helm chart in Git. Any drift is
reverted (`selfHeal`), removed resources are pruned (`prune`), and the target
namespace is created automatically. Push a change to the chart on `main` and the
cluster converges — no manual `helm upgrade` needed.

### One-command local ArgoCD (for a demo / screenshot)

`make argocd-up` (script: `deploy/argocd/bootstrap.sh`) installs ArgoCD into the
current kube-context, optionally builds the app image locally, and applies the
**local** Application (`deploy/argocd/application-local.yaml`), which uses the
locally-built image on SQLite to minimise external image pulls.

```bash
PUSH=1 make argocd-up   # push current branch + install ArgoCD + deploy via GitOps
make argocd-password     # print the initial admin password
make argocd-ui           # port-forward https://localhost:8080  (user: admin)
make argocd-down         # remove the app and uninstall ArgoCD
```

The script removes the two usual friction points:

- **Git source (no manual push to `main`).** ArgoCD syncs the chart from Git, so
  the script targets your **current branch** automatically. Run with `PUSH=1` and
  it pushes that branch for you before syncing; without it, it just prints the
  one-line push command. (Override the branch with `TARGET_REVISION=...`.)
- **App image without Docker Hub.** The image is built from a non-Docker-Hub
  mirror by default (`public.ecr.aws/docker/library/python:3.12-slim` via the
  `PYTHON_IMAGE` build-arg), so a blocked Docker Hub does not break the build.
  Override with `BASE_IMAGE=...`, or skip building with `BUILD_IMAGE=0`.

The local Application runs on SQLite (`postgres.enabled=false`, `FORCE_SQLITE=1`)
so only the app image is needed — easiest path to a `Synced/Healthy` screenshot.

Requirements: a running cluster in the current context (docker-desktop k8s, kind,
or minikube), plus `docker`, `kubectl`, and `git`. ArgoCD's own images come from
quay.io/ghcr (unaffected by a Docker Hub block).

For a production-like run against the released GHCR image + in-cluster TimescaleDB,
use `deploy/argocd/application.yaml` instead (`make k8s-argocd`).
