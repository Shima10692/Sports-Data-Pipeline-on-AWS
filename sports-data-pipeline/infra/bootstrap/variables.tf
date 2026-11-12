variable "aws_region" {
  description = "AWS region for the state bucket and every environment."
  type        = string
}

variable "project" {
  description = "Short project name; prefixes every resource name."
  type        = string
  default     = "sports"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project))
    error_message = "project must be 2-21 characters of lowercase letters, digits and hyphens, starting with a letter."
  }
}

variable "github_repository" {
  description = "GitHub repository that may assume the deploy roles, as owner/name. Matching is case-sensitive."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "github_repository must look like owner/name."
  }
}

variable "environments" {
  description = "Environments that get their own plan and apply roles and their own state key."
  type        = list(string)
  default     = ["dev", "prod"]

  validation {
    condition     = length(var.environments) > 0 && alltrue([for e in var.environments : can(regex("^[a-z][a-z0-9]{1,9}$", e))])
    error_message = "Each environment must be 2-10 lowercase letters or digits, starting with a letter."
  }

  validation {
    condition     = !contains(var.environments, "bootstrap")
    error_message = "\"bootstrap\" is reserved for this stack's own state key."
  }
}

variable "state_bucket_name" {
  description = "Override for the state bucket name. Defaults to <project>-tfstate-<account id>."
  type        = string
  default     = null
}

variable "create_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if the account already has one (only one is allowed per URL)."
  type        = bool
  default     = true
}

variable "state_version_retention_days" {
  description = "Days to keep old state versions."
  type        = number
  default     = 90
}
