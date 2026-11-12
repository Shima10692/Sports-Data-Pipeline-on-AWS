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
  description = "Clean zone bucket the job writes Parquet to."
  type        = string
}

variable "clean_bucket_arn" {
  description = "Clean zone bucket ARN."
  type        = string
}

variable "artifacts_bucket_name" {
  description = "Bucket for the job script, package and temp dir."
  type        = string
}

variable "artifacts_bucket_arn" {
  description = "Artifacts bucket ARN."
  type        = string
}

variable "glue_database_name" {
  description = "Glue Data Catalog database the clean tables are registered in."
  type        = string
}

variable "source_dir" {
  description = "processing/glue directory: glue_entry.py and src/clean_zone."
  type        = string
}

variable "worker_type" {
  description = "Glue worker type. G.1X = 1 DPU (4 vCPU, 16 GB)."
  type        = string
  default     = "G.1X"

  validation {
    condition     = contains(["G.1X", "G.2X"], var.worker_type)
    error_message = "Use G.1X or G.2X (the types Flex supports)."
  }
}

variable "number_of_workers" {
  description = "Workers per run, including the driver. 2 is Glue's minimum."
  type        = number
  default     = 2

  validation {
    condition     = var.number_of_workers >= 2 && var.number_of_workers <= 10
    error_message = "Between 2 and 10 workers; more is never needed at this data size."
  }
}

variable "execution_class" {
  description = "FLEX (spare capacity, ~35% cheaper, may start slower) or STANDARD."
  type        = string
  default     = "FLEX"

  validation {
    condition     = contains(["FLEX", "STANDARD"], var.execution_class)
    error_message = "execution_class must be FLEX or STANDARD."
  }
}

variable "timeout_minutes" {
  description = "Hard stop for a run; caps the cost of a stuck job."
  type        = number
  default     = 30
}

variable "max_concurrent_runs" {
  description = "Runs allowed at once (e.g. one per source from the orchestrator)."
  type        = number
  default     = 2
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the job's continuous logs."
  type        = number
  default     = 14
}
