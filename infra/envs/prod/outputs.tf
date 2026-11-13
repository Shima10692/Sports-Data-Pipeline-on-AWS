output "raw_bucket_name" {
  description = "Raw zone bucket: JSON, source=<name>/date=<yyyy-mm-dd>/, append-only."
  value       = module.data_lake.raw_bucket_name
}

output "clean_bucket_name" {
  description = "Clean zone bucket: Parquet."
  value       = module.data_lake.clean_bucket_name
}

output "glue_database_name" {
  description = "Glue Data Catalog database for clean-zone tables."
  value       = module.data_lake.glue_database_name
}

output "backfill_function_name" {
  description = "Backfill Lambda; invoke with aws lambda invoke --function-name <this> --payload '{\"source\": \"jolpica\"}'."
  value       = module.backfill.function_name
}

output "glue_job_name" {
  description = "Raw-to-clean Glue job (null while processing_engine = \"lambda\"); run with aws glue start-job-run --job-name <this>."
  value       = module.processing.job_name
}

output "raw_to_clean_function_name" {
  description = "Stopgap raw-to-clean Lambda (null while processing_engine = \"glue\"); invoke with --payload '{\"sources\": \"jolpica\"}'."
  value       = one(module.processing_lambda[*].function_name)
}

output "athena_workgroup_name" {
  description = "Athena workgroup for dbt (DBT_ATHENA_WORKGROUP) and ad-hoc queries."
  value       = module.warehouse.workgroup_name
}

output "dbt_marts_database_name" {
  description = "Glue database holding the dbt marts (fact_events, dim_*)."
  value       = module.warehouse.marts_database_name
}

output "dbt_data_location" {
  description = "S3 prefix dbt writes table data under (DBT_S3_DATA_DIR)."
  value       = module.warehouse.dbt_data_location
}
