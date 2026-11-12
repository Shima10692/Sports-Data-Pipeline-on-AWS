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
  description = "AWS region (for the log group ARN)."
  type        = string
}

variable "partition" {
  description = "AWS partition."
  type        = string
  default     = "aws"
}

variable "raw_bucket_name" {
  description = "Raw zone bucket the Lambda writes to."
  type        = string
}

variable "raw_bucket_arn" {
  description = "ARN of the raw zone bucket."
  type        = string
}

variable "source_dir" {
  description = "Directory containing the `backfill` Python package (ingestion/backfill/src)."
  type        = string
}

variable "memory_mb" {
  description = "Lambda memory. 1024 MB fits mid-size Cricsheet zips; the 150 MB 'all' zip needs ~2048."
  type        = number
  default     = 1024

  validation {
    condition     = var.memory_mb >= 128 && var.memory_mb <= 10240
    error_message = "memory_mb must be between 128 and 10240."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 14
}

variable "api_key_secret_arn" {
  description = "Optional Secrets Manager ARN for a paid TheSportsDB key. Null uses the free public key."
  type        = string
  default     = null
}
