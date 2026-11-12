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

variable "oidc_subject_prefix" {
  description = <<-EOT
    Start of the GitHub OIDC `sub` claim for the repository, without the trailing
    context. Either "repo:<owner>/<name>" (legacy) or, for repos using immutable
    subjects, "repo:<owner>@<owner id>/<name>@<repo id>". Matching is case-sensitive.
  EOT
  type        = string

  validation {
    condition     = startswith(var.oidc_subject_prefix, "repo:") && !endswith(var.oidc_subject_prefix, ":")
    error_message = "oidc_subject_prefix must start with \"repo:\" and must not end with \":\"."
  }
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
