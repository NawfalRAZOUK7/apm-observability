# infra/

Infrastructure, delivery, and security tooling for the platform.

| Directory | What it is |
|---|---|
| [`terraform/`](./terraform/) | **Infrastructure as Code** (Terraform/OpenTofu). A `local` kind environment ($0) and a reference `aws` environment (VPC + EKS + RDS + S3), plus reusable modules. See [`terraform/README.md`](./terraform/README.md). |
| [`policy/`](./policy/) | **Policy-as-code**: Kyverno admission policies (Cosign signature verification, non-root, registry allowlist, no `:latest`, requests/limits, probes) + CLI test fixtures. See [`policy/README.md`](./policy/README.md). |
| [`secrets/`](./secrets/) | **Secrets management**: External Secrets Operator, Sealed Secrets, and SOPS+age workflows — no plaintext in git. See [`secrets/README.md`](./secrets/README.md). |
| `ansible/` | Config-management deployment (single-node + multi-node cluster topologies) — the pre-Kubernetes delivery path. |

Related, elsewhere in the repo:

- **Helm chart:** [`deploy/helm/apm-observability`](../deploy/helm/apm-observability) — the app chart (supports canary Rollouts, NetworkPolicy, externally-managed secrets).
- **GitOps:** [`deploy/argocd`](../deploy/argocd) — ArgoCD Applications for the app + per-namespace staging/production.
- **CD scripts:** [`scripts/deploy`](../scripts/deploy) — kind bootstrap, deploy-with-canary, smoke tests.
- **Progressive delivery:** [`docs/PROGRESSIVE_DELIVERY.md`](../docs/PROGRESSIVE_DELIVERY.md).
