variable "project" {
  description = "Project prefix; must match the bootstrap stack so the apply role may manage these resources."
  type        = string
}

variable "environment" {
  description = "Environment name, e.g. dev or prod."
  type        = string
}

variable "clean_bucket_name" {
  description = "Clean zone bucket. dbt writes mart tables under its dbt/ prefix."
  type        = string
}

variable "artifacts_bucket_name" {
  description = "Artifacts bucket. Athena query results go under tmp/athena/<env>/, which expires."
  type        = string
}

variable "bytes_scanned_cutoff_per_query" {
  description = "Athena cancels any query in the workgroup that scans more than this many bytes. Cost guard: Athena bills $5 per TB scanned."
  type        = number
  default     = 1073741824 # 1 GiB; the whole dev clean zone is well under this.

  validation {
    # Athena's minimum is 10 MB.
    condition     = var.bytes_scanned_cutoff_per_query >= 10485760
    error_message = "bytes_scanned_cutoff_per_query must be at least 10485760 (10 MB)."
  }
}
