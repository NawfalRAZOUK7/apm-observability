# External Secrets Operator (Phase 15): syncs secrets from an external store
# (Kubernetes, AWS Secrets Manager, Vault, …) into native k8s Secrets.
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
  default = "external-secrets"
}

variable "chart_version" {
  type    = string
  default = "0.10.4"
}

resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  namespace        = var.namespace
  create_namespace = true
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  version          = var.chart_version

  set {
    name  = "installCRDs"
    value = "true"
  }
}

output "namespace" {
  value = var.namespace
}
