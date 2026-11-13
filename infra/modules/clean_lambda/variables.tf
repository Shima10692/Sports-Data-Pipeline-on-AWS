variable "project" {
  description = "Project prefix; must match bootstrap so the boundary and apply role line up."
  type        = string
}

variable "environment" {
  description = "Environment name, e.g. dev or prod."
  type        = string
}

variable "account_id" {
  description = "AWS account ID."
  type        = string
}

variable "region" {
  description = "AWS region."
  type        = string
}

variable "partition" {
  description = "AWS partition."
  type        = string
  default     = "aws"
}

variable "raw_bucket_name" {
  description = "Raw zone bucket (read only)."
  type        = string
}

variable "raw_bucket_arn" {
  description = "Raw zone bucket ARN."
  type        = string
}

variable "clean_bucket_name" {
  description = "Clean zone bucket the function writes Parquet to."
  type        = string
}

variable "clean_bucket_arn" {
  description = "Clean zone bucket ARN."
  type        = string
}

variable "glue_database_name" {
  description = "Glue Data Catalog database the clean tables are registered in."
  type        = string
}

variable "source_dir" {
  description = "processing/glue directory; src/clean_zone is zipped as the function code."
  type        = string
}

variable "sdk_pandas_version" {
  description = "AWS SDK for pandas layer version (provides pyarrow)."
  type        = string
  default     = "3.18.0"
}

variable "memory_mb" {
  description = "Lambda memory. A full StatsBomb run needs well under 1 GB; more memory also means more CPU."
  type        = number
  default     = 3008

  validation {
    condition     = var.memory_mb >= 1024 && var.memory_mb <= 10240
    error_message = "memory_mb must be between 1024 and 10240."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 14
}
