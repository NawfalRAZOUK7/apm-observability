output "namespace" {
  description = "Namespace the monitoring stack is deployed into."
  value       = var.namespace
}

output "grafana_release" {
  description = "Grafana/kube-prometheus-stack release name."
  value       = helm_release.kube_prometheus_stack.name
}
