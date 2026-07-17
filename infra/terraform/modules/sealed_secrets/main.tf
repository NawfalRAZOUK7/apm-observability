# Sealed Secrets controller (Phase 15): decrypts SealedSecret CRs (safe to commit
# to git) into native k8s Secrets. GitOps-friendly, no external store needed.
terraform {
  required_version = ">= 1.5"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

variable "namespace" {
  type    = string
  default = "kube-system"
}

variable "chart_version" {
  type    = string
  default = "2.16.1"
}

resource "helm_release" "sealed_secrets" {
  name       = "sealed-secrets"
  namespace  = var.namespace
  repository = "https://bitnami-labs.github.io/sealed-secrets"
  chart      = "sealed-secrets"
  version    = var.chart_version
}

output "namespace" {
  value = var.namespace
}
