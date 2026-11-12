output "raw_bucket_name" {
  description = "Raw zone bucket (JSON, source=<name>/date=<yyyy-mm-dd>/)."
  value       = aws_s3_bucket.zone["raw"].bucket
}

output "raw_bucket_arn" {
  description = "Raw zone bucket ARN."
  value       = aws_s3_bucket.zone["raw"].arn
}

output "clean_bucket_name" {
  description = "Clean zone bucket (Parquet)."
  value       = aws_s3_bucket.zone["clean"].bucket
}

output "clean_bucket_arn" {
  description = "Clean zone bucket ARN."
  value       = aws_s3_bucket.zone["clean"].arn
}

output "artifacts_bucket_name" {
  description = "Artifacts bucket: Glue scripts and packages, tmp/ for scratch."
  value       = aws_s3_bucket.zone["artifacts"].bucket
}

output "artifacts_bucket_arn" {
  description = "Artifacts bucket ARN."
  value       = aws_s3_bucket.zone["artifacts"].arn
}

output "glue_database_name" {
  description = "Glue Data Catalog database for clean-zone tables."
  value       = aws_glue_catalog_database.lake.name
}
