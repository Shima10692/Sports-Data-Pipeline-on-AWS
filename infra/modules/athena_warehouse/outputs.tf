output "workgroup_name" {
  description = "Athena workgroup for dbt and ad-hoc queries."
  value       = aws_athena_workgroup.this.name
}

output "query_results_location" {
  description = "Default Athena query results location (expires via the artifacts bucket tmp/ rule)."
  value       = local.results_uri
}

output "staging_database_name" {
  description = "Glue database for dbt staging views."
  value       = aws_glue_catalog_database.dbt["staging"].name
}

output "marts_database_name" {
  description = "Glue database for dbt mart tables."
  value       = aws_glue_catalog_database.dbt["marts"].name
}

output "dbt_data_location" {
  description = "S3 prefix dbt writes table data under (s3_data_dir in dbt/profiles.yml)."
  value       = "s3://${var.clean_bucket_name}/dbt/"
}
