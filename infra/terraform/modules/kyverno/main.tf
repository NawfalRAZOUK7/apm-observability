# Kyverno policy engine (Phase 16): admission-time policy enforcement +
# Cosign image-signature verification. Policies themselves live in
# infra/policy/kyverno and are applied via GitOps (ArgoCD) or kubectl.
terraform {
  required_version = ">= 1.5"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.2"
    }
  }
}

variable "namespace" {
  type    = string
  default = "kyverno"
}

variable "chart_version" {
  type    = string
  default = "3.2.6"
}

resource "helm_release" "kyverno" {
  name             = "kyverno"
  namespace        = var.namespace
  create_namespace = true
  repository       = "https://kyverno.github.io/kyverno/"
  chart            = "kyverno"
  version          = var.chart_version
}

output "namespace" {
  value = var.namespace
}
