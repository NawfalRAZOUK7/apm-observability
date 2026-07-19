# github_oidc

Keyless authentication from GitHub Actions to AWS. Creates the account-level
GitHub OIDC provider and an IAM role whose trust policy is scoped to specific
GitHub `sub` claims (repo + branch/environment). Workflows then assume the role
with a short-lived OIDC token — **no long-lived AWS access keys in repo secrets.**

## Usage

```hcl
module "github_oidc" {
  source = "../../modules/github_oidc"

  github_owner = "NawfalRAZOUK7"
  github_repo  = "apm-observability"

  # Read-only by default (plan/estimate only). Widen for a role that applies.
  managed_policy_arns = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]

  allowed_subjects = [
    "repo:NawfalRAZOUK7/apm-observability:ref:refs/heads/main",
    "repo:NawfalRAZOUK7/apm-observability:pull_request",
  ]
}

output "ci_role_arn" {
  value = module.github_oidc.role_arn
}
```

Apply once (with admin creds), then set the output `role_arn` as the repo secret
`AWS_ROLE_ARN`. The [`terraform-plan-aws`](../../../../.github/workflows/terraform-plan-aws.yml)
workflow consumes it.

| Input | Default | Notes |
|---|---|---|
| `github_owner` / `github_repo` | this repo | Used to build default subjects. |
| `allowed_subjects` | `main` ref + `production` env | Tighten to exactly the workflows that need it. |
| `create_oidc_provider` | `true` | Set `false` if the account already has a GitHub OIDC provider (only one allowed). |
| `managed_policy_arns` | `ReadOnlyAccess` | Least privilege; grant only what the workflow needs. |

> Because the default role is read-only, it's safe for `terraform plan` and
> Infracost estimates. A separate, more tightly scoped role should back any
> workflow that actually applies.
