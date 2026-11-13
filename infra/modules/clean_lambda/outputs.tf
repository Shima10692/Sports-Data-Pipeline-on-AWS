output "function_name" {
  description = "Raw-to-clean Lambda name, for `aws lambda invoke`."
  value       = aws_lambda_function.fn.function_name
}

output "function_arn" {
  description = "Raw-to-clean Lambda ARN (for the orchestrator in phase 9)."
  value       = aws_lambda_function.fn.arn
}

output "role_arn" {
  description = "Execution role ARN."
  value       = aws_iam_role.fn.arn
}
