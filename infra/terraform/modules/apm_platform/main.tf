resource "kubernetes_namespace" "this" {
  count = var.create_namespace ? 1 : 0

  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of"    = "apm-observability"
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
}

resource "helm_release" "apm" {
  name             = var.release_name
  namespace        = var.namespace
  chart            = var.chart_path
  create_namespace = false
  atomic           = true
  wait             = true
  timeout          = 300

  # Base + environment values files, in order.
  values = [for f in var.values_files : file(f)]

  # Only override when a tag is given; otherwise the chart falls back to its
  # appVersion. Always setting this would pin image.tag to the variable's default
  # and defeat that fallback.
  dynamic "set" {
    for_each = var.image_tag == "" ? [] : [var.image_tag]
    content {
      name  = "image.tag"
      value = set.value
    }
  }

  set {
    name  = "replicaCount"
    value = var.replica_count
  }

  # Secrets are injected from Terraform variables (sourced from tfvars, a secret
  # manager, or CI secrets) rather than committed into values.yaml.
  set_sensitive {
    name  = "secrets.DJANGO_SECRET_KEY"
    value = var.django_secret_key
  }

  set_sensitive {
    name  = "secrets.POSTGRES_PASSWORD"
    value = var.postgres_password
  }

  dynamic "set" {
    for_each = var.extra_set
    content {
      name  = set.key
      value = set.value
    }
  }

  depends_on = [kubernetes_namespace.this]
}
