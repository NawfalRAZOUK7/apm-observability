# Runbook — Secret rotation

Rotate on a schedule and immediately on suspected exposure. Three classes of
secret, three procedures.

## 1. Application ingestion API keys (Phase 5)

Per-project keys are hashed at rest and support rotation without downtime.

```bash
# via API (operator role): issues a new key, revokes the old one
curl -X POST /api/tenancy/projects/<id>/keys/<key_id>/rotate/ -H "Authorization: Bearer <jwt>"
```

The response returns the new plaintext once. Update the emitting service, then
confirm the old prefix stops appearing in `last_used_at`.

## 2. Infrastructure secrets via External Secrets (Option A)

1. Update the value in the store (AWS Secrets Manager / Vault).
2. External Secrets re-syncs within `refreshInterval` (1h) — or force it:
   `kubectl annotate externalsecret apm-secret force-sync=$(date +%s) -n apm --overwrite`.
3. Restart the deployment to pick up the new env:
   `kubectl rollout restart deploy/apm-apm-observability -n apm`.

## 3. Sealed Secrets / SOPS (Options B/C)

1. Re-create the Secret with new values and re-seal / re-encrypt.
2. Commit the new `SealedSecret` / `*.enc.yaml`.
3. GitOps (ArgoCD) applies it; roll the deployment.

## After any rotation

- Verify the app is healthy (`/api/health/`) and no auth errors in logs.
- If rotating due to exposure: invalidate the leaked value at the source,
  audit access logs, and open an incident (Phase 9).
- Confirm `gitleaks` is green and the leaked secret is not in git history
  (rewrite history if it is).
