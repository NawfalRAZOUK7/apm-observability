locals {
  # Repo root is four levels up from environments/local.
  repo_root  = abspath("${path.module}/../../../..")
  chart_path = "${local.repo_root}/deploy/helm/apm-observability"
}

module "apm" {
  source = "../../modules/apm_platform"

  namespace         = "apm"
  create_namespace  = true
  release_name      = "apm"
  chart_path        = local.chart_path
  image_tag         = var.image_tag
  replica_count     = 1
  values_files      = ["${local.chart_path}/values.yaml", "${local.chart_path}/values-staging.yaml"]
  django_secret_key = var.django_secret_key
  postgres_password = var.postgres_password

  # In-cluster Postgres is convenient for local; OTEL points at the demo stack.
  extra_set = {
    "postgres.enabled"    = "true"
    "config.OTEL_ENABLED" = "0"
  }
}

module "monitoring" {
  source = "../../modules/monitoring"
  count  = var.enable_monitoring ? 1 : 0

  namespace = "monitoring"
}
