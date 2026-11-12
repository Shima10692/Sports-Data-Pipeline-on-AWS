output "plan_role_arn" {
  description = "Role for pull-request plans."
  value       = aws_iam_role.this["plan"].arn
}

output "apply_role_arn" {
  description = "Role for applies from the matching GitHub Environment."
  value       = aws_iam_role.this["apply"].arn
}

output "permissions_boundary_arn" {
  description = "Boundary that every role created in this environment must use."
  value       = aws_iam_policy.boundary.arn
}
