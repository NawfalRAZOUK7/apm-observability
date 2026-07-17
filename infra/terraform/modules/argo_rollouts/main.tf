# Argo Rollouts controller (Phase 17): progressive delivery (canary/blue-green)
# with metric-based analysis. Install once; the app chart then renders a Rollout
# instead of a Deployment when `rollout.enabled=true`.
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
  default = "argo-rollouts"
}

variable "chart_version" {
  type    = string
  default = "2.37.7"
}

variable "install_dashboard" {
  type    = bool
  default = true
}

resource "helm_release" "argo_rollouts" {
  name             = "argo-rollouts"
  namespace        = var.namespace
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-rollouts"
  version          = var.chart_version

  set {
    name  = "dashboard.enabled"
    value = tostring(var.install_dashboard)
  }
}

output "namespace" {
  value = var.namespace
}
