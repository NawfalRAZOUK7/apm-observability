# Infrastructure as Code (Terraform / OpenTofu)

Declarative provisioning for the platform (Phase 14). Works with both Terraform
and OpenTofu (`tofu` is a drop-in — substitute the command).

```
infra/terraform/
├── modules/
│   ├── apm_platform/   # deploy the Helm chart (secrets injected from TF, not values.yaml)
│   └── monitoring/     # in-cluster kube-prometheus-stack + Loki + Tempo
└── environments/
    ├── local/          # kind cluster + app — fully local, $0
    └── aws/            # reference: VPC + EKS + RDS + S3 (billable)
```

## Local (free, no cloud account)

Provisions a `kind` cluster and deploys the app onto it.

```bash
cd infra/terraform/environments/local
cp terraform.tfvars.example terraform.tfvars   # edit the secret
terraform init
terraform plan
terraform apply
# ... then:  kubectl --context kind-apm-local get pods -n apm
terraform destroy
```

Requires: Terraform ≥ 1.5 (or OpenTofu), Docker (for kind), and the chart at
`deploy/helm/apm-observability`.

## AWS (reference — costs money)

`environments/aws` provisions a production-shaped stack — VPC, EKS, a Multi-AZ
RDS Postgres, and an encrypted/versioned S3 backups bucket — using the
well-maintained `terraform-aws-modules`, then deploys the app onto EKS pointed at
RDS. State is stored remotely in S3 + DynamoDB (see `backend.tf`).

```bash
cd infra/terraform/environments/aws
export TF_VAR_django_secret_key=...   # prefer env/secret manager over tfvars
export TF_VAR_postgres_password=...
terraform init
terraform plan
terraform apply
```

> **Cost warning:** EKS + NAT + Multi-AZ RDS incur ongoing charges. Run
> `terraform destroy` when done.

## Secrets

Application secrets (`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`) are injected into
the Helm release from Terraform variables via `set_sensitive` — never committed
into `values.yaml`. Source them from `TF_VAR_*` env vars, CI secrets, or a secret
manager. Phase 15 replaces this with External Secrets / SOPS.

## CI

`.github/workflows/terraform.yml` runs `fmt -check`, `validate`, `tflint`, and a
`trivy config` (tfsec-style) scan on every change under `infra/terraform/`.
