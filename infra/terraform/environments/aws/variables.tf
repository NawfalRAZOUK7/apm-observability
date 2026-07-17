variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-west-1"
}

variable "name" {
  description = "Name prefix for all resources."
  type        = string
  default     = "apm-observability"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "kubernetes_version" {
  type    = string
  default = "1.30"
}

variable "node_instance_type" {
  type    = string
  default = "t3.large"
}

variable "cluster_endpoint_public_access" {
  description = <<-EOT
    Expose the EKS API server endpoint to the internet. Off by default: reaching
    the cluster then requires being inside the VPC (bastion/VPN/SSM). Turning it
    on without also narrowing cluster_endpoint_public_access_cidrs leaves the API
    server open to 0.0.0.0/0 (trivy AWS-0040 / AWS-0041, both CRITICAL).
  EOT
  type        = bool
  default     = false
}

variable "cluster_endpoint_public_access_cidrs" {
  description = <<-EOT
    CIDRs allowed to reach the public API server endpoint. Only meaningful when
    cluster_endpoint_public_access is true, in which case it must be set to your
    own ranges -- an empty list here would let the upstream module fall back to
    its 0.0.0.0/0 default.
  EOT
  type        = list(string)
  default     = []

  validation {
    condition     = !contains(var.cluster_endpoint_public_access_cidrs, "0.0.0.0/0")
    error_message = "Refusing 0.0.0.0/0: restrict the EKS public endpoint to known CIDRs."
  }
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.medium"
}

variable "image_tag" {
  description = "Container image tag to deploy. Empty => the chart's appVersion."
  type        = string
  default     = ""
}

variable "django_secret_key" {
  type      = string
  sensitive = true
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "tags" {
  type = map(string)
  default = {
    Project   = "apm-observability"
    ManagedBy = "terraform"
  }
}
