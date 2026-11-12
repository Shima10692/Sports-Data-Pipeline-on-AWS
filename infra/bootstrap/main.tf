data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  account_id        = data.aws_caller_identity.current.account_id
  partition         = data.aws_partition.current.partition
  state_bucket_name = coalesce(var.state_bucket_name, "${var.project}-tfstate-${local.account_id}")
  github_oidc_url   = "https://token.actions.githubusercontent.com"

  oidc_provider_arn = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

module "state_backend" {
  source = "../modules/state_backend"

  bucket_name                       = local.state_bucket_name
  noncurrent_version_retention_days = var.state_version_retention_days
}

# AWS validates GitHub's certificate chain itself, so no thumbprint is pinned.
resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 1 : 0

  url            = local.github_oidc_url
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 0 : 1
  url   = local.github_oidc_url
}

module "github_env_roles" {
  source   = "../modules/github_env_roles"
  for_each = toset(var.environments)

  project            = var.project
  environment        = each.key
  other_environments = [for e in var.environments : e if e != each.key]
  github_repository  = var.github_repository
  oidc_provider_arn  = local.oidc_provider_arn
  state_bucket_arn   = module.state_backend.bucket_arn
  account_id         = local.account_id
  partition          = local.partition

  other_state_prefixes = concat(["bootstrap"], [for e in var.environments : e if e != each.key])
}
