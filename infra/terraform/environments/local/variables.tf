variable "cluster_name" {
  description = "Name of the local kind cluster."
  type        = string
  default     = "apm-local"
}

variable "image_tag" {
  description = "Container image tag to deploy. Empty => the chart's appVersion."
  type        = string
  default     = ""
}

variable "django_secret_key" {
  description = "Django secret key (set via TF_VAR_django_secret_key or *.tfvars)."
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "Postgres password."
  type        = string
  sensitive   = true
  default     = "apm"
}

variable "enable_monitoring" {
  description = "Also deploy the in-cluster LGTM monitoring stack."
  type        = bool
  default     = false
}
