output "role_arn" {
  description = "ARN of the IAM role GitHub Actions assumes (set as the AWS_ROLE_ARN secret)."
  value       = aws_iam_role.github_actions.arn
}

output "role_name" {
  description = "Name of the IAM role."
  value       = aws_iam_role.github_actions.name
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider used by the role's trust policy."
  value       = local.provider_arn
}
