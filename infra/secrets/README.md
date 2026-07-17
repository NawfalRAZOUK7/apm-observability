# Secrets management (Phase 15)

**No plaintext secrets in git.** The chart ships with empty secret defaults; a
`gitleaks` CI job (`.github/workflows/gitleaks.yml`) fails the build if a secret
is ever committed. Provide secrets at deploy time via one of three approaches —
all point the chart at an externally-managed Secret with
`--set existingSecret=apm-secret`.

## Option A — External Secrets Operator (recommended for cloud)

Syncs from AWS Secrets Manager / Vault / etc. into a native Secret; rotation in
the store propagates automatically.

```bash
# 1. Install the operator (Terraform):
terraform -chdir=infra/terraform/environments/<env> apply   # includes the module
# 2. Apply a store + ExternalSecret:
kubectl apply -f infra/secrets/external-secrets/secretstore-aws.yaml
kubectl apply -f infra/secrets/external-secrets/externalsecret-apm.yaml
# 3. Deploy the app pointing at the synced Secret:
helm upgrade --install apm deploy/helm/apm-observability -n apm \
  --set existingSecret=apm-secret
```

## Option B — Sealed Secrets (GitOps, no external store, $0)

Encrypt a Secret to a `SealedSecret` CR that is safe to commit; the in-cluster
controller decrypts it.

```bash
# controller installed via infra/terraform/modules/sealed_secrets
kubectl create secret generic apm-secret -n apm \
  --from-literal=DJANGO_SECRET_KEY=... --from-literal=POSTGRES_PASSWORD=... \
  --dry-run=client -o yaml | kubeseal --format yaml > apm-sealedsecret.yaml
kubectl apply -f apm-sealedsecret.yaml    # safe to commit
```

## Option C — SOPS + age (git-native encrypted files, $0)

Commit an encrypted YAML; decrypt at apply time. See `sops/`.

```bash
age-keygen -o key.txt                       # put the public key in sops/.sops.yaml
cp sops/apm-secret.example.yaml sops/apm-secret.enc.yaml   # edit values
sops --encrypt --in-place sops/apm-secret.enc.yaml          # commit THIS
sops --decrypt sops/apm-secret.enc.yaml | kubectl apply -f -
```

## Rotation

See [`docs/runbooks/SecretRotation.md`](../../docs/runbooks/SecretRotation.md).
Application ingestion API keys rotate via the API/`ApiKey.rotate()` (Phase 5);
infrastructure secrets rotate in the store (Option A) or by re-sealing/re-encrypting.
