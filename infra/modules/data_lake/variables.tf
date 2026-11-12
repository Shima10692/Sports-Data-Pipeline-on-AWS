variable "project" {
  description = "Project prefix; must match the bootstrap stack so the apply role may manage these resources."
  type        = string
}

variable "environment" {
  description = "Environment name, e.g. dev or prod."
  type        = string
}

variable "account_id" {
  description = "AWS account ID, used to make bucket names globally unique."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "account_id must be 12 digits."
  }
}

variable "raw_append_only" {
  description = "Deny object and version deletes in the raw zone."
  type        = bool
  default     = true
}

variable "raw_noncurrent_version_days" {
  description = "Days to keep overwritten raw objects. Raw is append-only, so this mainly covers accidental overwrites."
  type        = number
  default     = 90

  validation {
    condition     = var.raw_noncurrent_version_days >= 1
    error_message = "Must be at least 1 day."
  }
}

variable "clean_noncurrent_version_days" {
  description = "Days to keep overwritten clean-zone Parquet. Glue rewrites partitions, so keep this short."
  type        = number
  default     = 7

  validation {
    condition     = var.clean_noncurrent_version_days >= 1
    error_message = "Must be at least 1 day."
  }
}

variable "artifacts_tmp_days" {
  description = "Days before objects under tmp/ in the artifacts bucket expire."
  type        = number
  default     = 3

  validation {
    condition     = var.artifacts_tmp_days >= 1
    error_message = "Must be at least 1 day."
  }
}

variable "force_destroy" {
  description = "Allow Terraform to delete non-empty buckets. Keep false; never true for prod."
  type        = bool
  default     = false
}
