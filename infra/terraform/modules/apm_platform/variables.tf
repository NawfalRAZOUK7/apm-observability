variable "namespace" {
  description = "Kubernetes namespace to deploy into."
  type        = string
}

variable "create_namespace" {
  description = "Whether this module should create the namespace."
  type        = bool
  default     = true
}

variable "release_name" {
  description = "Helm release name."
  type        = string
  default     = "apm"
}

variable "chart_path" {
  description = "Path to the apm-observability Helm chart."
  type        = string
}

variable "image_tag" {
  description = <<-EOT
    Container image tag to deploy. Empty (the default) leaves it to the chart,
    which uses its appVersion -- an immutable tag published by release.yml. A
    floating "latest" is rejected by the disallow-latest-tag Kyverno policy.
  EOT
  type        = string
  default     = ""
}

variable "replica_count" {
  description = "Number of web replicas."
  type        = number
  default     = 1
}

variable "values_files" {
  description = "Ordered list of Helm values file paths (later overrides earlier)."
  type        = list(string)
  default     = []
}

variable "django_secret_key" {
  description = "Django secret key. Injected as a Helm secret value; never stored in values.yaml."
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "Postgres password. Injected as a Helm secret value."
  type        = string
  sensitive   = true
}

variable "extra_set" {
  description = "Additional non-sensitive Helm --set overrides (name => value)."
  type        = map(string)
  default     = {}
}
