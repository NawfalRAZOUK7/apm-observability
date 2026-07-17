variable "namespace" {
  description = "Namespace for the monitoring stack."
  type        = string
  default     = "monitoring"
}

variable "enable_loki" {
  description = "Deploy Loki (logs)."
  type        = bool
  default     = true
}

variable "enable_tempo" {
  description = "Deploy Tempo (traces)."
  type        = bool
  default     = true
}

variable "kube_prometheus_stack_version" {
  type    = string
  default = "62.7.0"
}

variable "loki_version" {
  type    = string
  default = "6.10.0"
}

variable "tempo_version" {
  type    = string
  default = "1.10.3"
}

variable "grafana_admin_password" {
  description = "Grafana admin password."
  type        = string
  sensitive   = true
  default     = "change-me"
}
