output "job_name" {
  description = "Glue job name; start with aws glue start-job-run --job-name <this>."
  value       = aws_glue_job.raw_to_clean.name
}

output "role_arn" {
  description = "IAM role the job runs as."
  value       = aws_iam_role.glue.arn
}

output "log_group_name" {
  description = "CloudWatch log group for the job's driver and executor logs."
  value       = aws_cloudwatch_log_group.job.name
}
