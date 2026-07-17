output "cluster_name" {
  description = "Local kind cluster name."
  value       = kind_cluster.this.name
}

output "kubeconfig_path" {
  description = "Path to the generated kubeconfig."
  value       = kind_cluster.this.kubeconfig_path
}

output "app_namespace" {
  description = "Namespace the app was deployed into."
  value       = module.apm.namespace
}
