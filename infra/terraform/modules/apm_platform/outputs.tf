output "namespace" {
  description = "Namespace the release was deployed into."
  value       = var.namespace
}

output "release_name" {
  description = "Helm release name."
  value       = helm_release.apm.name
}

output "release_status" {
  description = "Helm release status."
  value       = helm_release.apm.status
}
