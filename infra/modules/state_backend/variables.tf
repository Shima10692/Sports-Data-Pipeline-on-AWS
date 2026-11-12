variable "bucket_name" {
  description = "Globally unique name of the Terraform state bucket."
  type        = string
}

variable "noncurrent_version_retention_days" {
  description = "Days to keep superseded state versions before they expire."
  type        = number
  default     = 90

  validation {
    condition     = var.noncurrent_version_retention_days >= 1
    error_message = "Retention must be at least 1 day."
  }
}
