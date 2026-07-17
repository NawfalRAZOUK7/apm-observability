output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API endpoint."
  value       = module.eks.cluster_endpoint
}

output "db_address" {
  description = "RDS Postgres endpoint address."
  value       = module.rds.db_instance_address
}

output "backups_bucket" {
  description = "S3 bucket for backups."
  value       = module.backups_bucket.s3_bucket_id
}

output "app_namespace" {
  description = "Namespace the app was deployed into."
  value       = module.apm.namespace
}
