variable "aws_region" {
  description = "AWS region for this environment."
  type        = string
}

variable "project" {
  description = "Project prefix; must match the bootstrap stack. Resources are named <project>-prod-*."
  type        = string
  default     = "sports"
}

variable "processing_engine" {
  description = "Raw-to-clean engine. \"glue\" is the design; \"lambda\" is the stopgap while AWS has Glue job creation blocked on the account. Flip back to \"glue\" when Support restores it."
  type        = string
  default     = "lambda"

  validation {
    condition     = contains(["glue", "lambda"], var.processing_engine)
    error_message = "processing_engine must be \"glue\" or \"lambda\"."
  }
}
