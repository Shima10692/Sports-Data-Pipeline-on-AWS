variable "project" {
  description = "Short project name used as the prefix for every resource."
  type        = string
}

variable "environment" {
  description = "Environment these roles deploy to, e.g. dev or prod."
  type        = string
}

variable "other_environments" {
  description = "The other environments in this account; resources tagged with them are denied."
  type        = list(string)
  default     = []
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the roles, as owner/name (case-sensitive)."
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider."
  type        = string
}

variable "state_bucket_arn" {
  description = "ARN of the Terraform state bucket."
  type        = string
}

variable "other_state_prefixes" {
  description = "State key prefixes the plan role must not read (other environments, bootstrap)."
  type        = list(string)
  default     = []
}

variable "account_id" {
  description = "AWS account ID."
  type        = string
}

variable "partition" {
  description = "AWS partition, usually aws."
  type        = string
  default     = "aws"
}
