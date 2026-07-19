variable "github_owner" {
  type        = string
  description = "GitHub org/user that owns the repository."
  default     = "NawfalRAZOUK7"
}

variable "github_repo" {
  type        = string
  description = "Repository name (without owner)."
  default     = "apm-observability"
}

variable "allowed_subjects" {
  type        = list(string)
  description = <<-EOT
    List of GitHub OIDC `sub` claims allowed to assume the role. Scope this as
    tightly as the workflows need. Examples:
      repo:OWNER/REPO:ref:refs/heads/main
      repo:OWNER/REPO:environment:production
      repo:OWNER/REPO:pull_request
    Leave empty to auto-derive `ref:refs/heads/main` + `environment:production`.
  EOT
  default     = []
}

variable "create_oidc_provider" {
  type        = bool
  description = "Create the account-level GitHub OIDC provider. Set false if one already exists (only one per account)."
  default     = true
}

variable "existing_oidc_provider_arn" {
  type        = string
  description = "ARN of a pre-existing GitHub OIDC provider (used when create_oidc_provider = false)."
  default     = ""
}

variable "role_name" {
  type        = string
  description = "Name of the IAM role GitHub Actions assumes."
  default     = "github-actions-apm-observability"
}

variable "managed_policy_arns" {
  type        = list(string)
  description = "Managed policies attached to the role. Defaults to read-only (plan/estimate only — no apply)."
  default     = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to created resources."
  default     = {}
}
