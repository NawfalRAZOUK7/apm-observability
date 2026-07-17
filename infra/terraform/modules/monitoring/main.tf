resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  namespace        = var.namespace
  create_namespace = true
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = var.kube_prometheus_stack_version

  set_sensitive {
    name  = "grafana.adminPassword"
    value = var.grafana_admin_password
  }
}

resource "helm_release" "loki" {
  count            = var.enable_loki ? 1 : 0
  name             = "loki"
  namespace        = var.namespace
  create_namespace = true
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "loki"
  version          = var.loki_version

  # Single-binary, filesystem storage — fine for demo/staging.
  set {
    name  = "deploymentMode"
    value = "SingleBinary"
  }
}

resource "helm_release" "tempo" {
  count            = var.enable_tempo ? 1 : 0
  name             = "tempo"
  namespace        = var.namespace
  create_namespace = true
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "tempo"
  version          = var.tempo_version
}
