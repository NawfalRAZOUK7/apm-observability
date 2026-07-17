# Policy-as-code (Phase 16)

Admission-time enforcement with **Kyverno**, closing the loop on the supply-chain
work: CI *signs* images (Cosign keyless), and these policies *verify* them at
deploy. Install the engine via `infra/terraform/modules/kyverno`, then apply the
policies (GitOps/ArgoCD or `kubectl apply -f infra/policy/kyverno`).

## Policies (`kyverno/`)

| Policy | Enforces |
|---|---|
| `verify-image-signatures` | Only Cosign-signed images from this repo's release workflow (keyless, Fulcio/Rekor) |
| `restrict-registries` | Images only from ghcr.io / registry.k8s.io / docker.io |
| `disallow-latest-tag` | Explicit image tags (no `:latest`) |
| `require-nonroot` | Non-root, no privilege escalation, drop ALL capabilities |
| `require-requests-limits` | CPU/memory requests + limits on every container |
| `require-probes` | Readiness + liveness probes |

All ship with `validationFailureAction: Enforce` and exclude `kube-system` /
`kyverno`. The app chart is already compliant (Phase 16 securityContext +
resources + probes), so it admits cleanly.

## Testing

`kyverno test infra/policy/kyverno/tests` runs the policies against good/bad
fixtures; the `Policy (Kyverno)` CI workflow does this on every change.

## Pod Security Standards

Complementary to Kyverno, label the app namespace to enforce the built-in
`restricted` PSS admission:

```bash
kubectl label ns apm \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/warn=restricted
```
