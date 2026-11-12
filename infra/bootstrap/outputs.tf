output "state_bucket_name" {
  description = "State bucket; pass it to `terraform init -backend-config=bucket=...` and store it as the TF_STATE_BUCKET GitHub variable."
  value       = module.state_backend.bucket_name
}

output "aws_region" {
  description = "Region of the state bucket."
  value       = var.aws_region
}

output "oidc_subject_prefix" {
  description = "Prefix the roles expect in the GitHub OIDC sub claim."
  value       = local.oidc_subject_prefix
}

output "oidc_provider_arn" {
  description = "GitHub Actions OIDC provider."
  value       = local.oidc_provider_arn
}

output "plan_role_arns" {
  description = "Pull-request plan role per environment."
  value       = { for env, m in module.github_env_roles : env => m.plan_role_arn }
}

output "apply_role_arns" {
  description = "Apply role per environment (GitHub Environment of the same name)."
  value       = { for env, m in module.github_env_roles : env => m.apply_role_arn }
}

output "permissions_boundary_arns" {
  description = "Boundary each environment's workload roles must use."
  value       = { for env, m in module.github_env_roles : env => m.permissions_boundary_arn }
}
