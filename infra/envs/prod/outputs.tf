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
