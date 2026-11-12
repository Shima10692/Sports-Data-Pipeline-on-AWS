variable "aws_region" {
  description = "AWS region for this environment."
  type        = string
}

variable "project" {
  description = "Project prefix; must match the bootstrap stack. Resources are named <project>-prod-*."
  type        = string
  default     = "sports"
}
