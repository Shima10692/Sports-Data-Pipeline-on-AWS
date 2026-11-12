output "function_name" {
  description = "Backfill Lambda name, for `aws lambda invoke`."
  value       = aws_lambda_function.backfill.function_name
}

output "function_arn" {
  description = "Backfill Lambda ARN (used by the orchestrator in phase 9)."
  value       = aws_lambda_function.backfill.arn
}

output "role_arn" {
  description = "Execution role ARN."
  value       = aws_iam_role.backfill.arn
}
