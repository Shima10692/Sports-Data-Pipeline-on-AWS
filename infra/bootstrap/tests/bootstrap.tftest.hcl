# Offline wiring tests for the bootstrap stack; the AWS provider is mocked.
# Resource-level checks live with each module under infra/modules/*/tests.
# Run from infra/bootstrap:  terraform init -backend=false && terraform test

mock_provider "aws" {
  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "123456789012" }
  }
  override_data {
    target = data.aws_partition.current
    values = { partition = "aws" }
  }
}

variables {
  aws_region        = "us-east-1"
  github_repository = "example-org/example-repo"
}

run "default_wiring" {
  command = apply

  assert {
    condition     = output.state_bucket_name == "sports-tfstate-123456789012"
    error_message = "Default bucket name should be <project>-tfstate-<account id>."
  }
  assert {
    condition     = length(aws_iam_openid_connect_provider.github) == 1
    error_message = "OIDC provider should be created by default."
  }
  assert {
    condition     = aws_iam_openid_connect_provider.github[0].url == "https://token.actions.githubusercontent.com"
    error_message = "OIDC provider must point at GitHub Actions."
  }
  assert {
    condition     = aws_iam_openid_connect_provider.github[0].client_id_list == toset(["sts.amazonaws.com"])
    error_message = "OIDC audience must be sts.amazonaws.com."
  }
  assert {
    condition     = keys(output.plan_role_arns) == ["dev", "prod"] && keys(output.apply_role_arns) == ["dev", "prod"]
    error_message = "Expected plan and apply roles for dev and prod."
  }
  assert {
    condition     = module.github_env_roles["dev"].plan_role_arn != module.github_env_roles["prod"].plan_role_arn
    error_message = "Each environment needs its own roles."
  }
}

run "custom_bucket_name" {
  command = plan

  variables {
    state_bucket_name = "my-own-state-bucket"
  }

  assert {
    condition     = output.state_bucket_name == "my-own-state-bucket"
    error_message = "state_bucket_name override not honoured."
  }
}

run "reuse_existing_oidc_provider" {
  command = plan

  variables {
    create_oidc_provider = false
  }

  override_data {
    target = data.aws_iam_openid_connect_provider.github[0]
    values = { arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" }
  }

  assert {
    condition     = length(aws_iam_openid_connect_provider.github) == 0
    error_message = "No provider should be created when reusing one."
  }
  assert {
    condition     = output.oidc_provider_arn == "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    error_message = "Existing provider ARN should be used."
  }
}

run "rejects_bad_repository" {
  command = plan

  variables {
    github_repository = "not a repo"
  }

  expect_failures = [var.github_repository]
}

run "rejects_reserved_environment" {
  command = plan

  variables {
    environments = ["dev", "bootstrap"]
  }

  expect_failures = [var.environments]
}

run "rejects_bad_project" {
  command = plan

  variables {
    project = "Sports_Pipeline"
  }

  expect_failures = [var.project]
}

run "no_budget_by_default" {
  command = plan

  # terraform test also reads a local terraform.tfvars, so pin the default explicitly.
  variables {
    budget_alert_email = null
  }

  assert {
    condition     = length(aws_budgets_budget.monthly) == 0
    error_message = "Budget should only be created when an email is set."
  }
}

run "budget_with_email" {
  command = apply

  variables {
    budget_alert_email = "alerts@example.com"
  }

  assert {
    condition     = aws_budgets_budget.monthly[0].limit_amount == "5" && aws_budgets_budget.monthly[0].time_unit == "MONTHLY"
    error_message = "Default budget should be 5 USD per month."
  }
  assert {
    condition     = toset([for n in aws_budgets_budget.monthly[0].notification : n.notification_type]) == toset(["ACTUAL", "FORECASTED"])
    error_message = "Budget needs an actual and a forecast alert."
  }
  assert {
    condition     = alltrue([for n in aws_budgets_budget.monthly[0].notification : n.subscriber_email_addresses == toset(["alerts@example.com"])])
    error_message = "Alerts must go to budget_alert_email."
  }
}

run "rejects_bad_budget_email" {
  command = plan

  variables {
    budget_alert_email = "not-an-email"
  }

  expect_failures = [var.budget_alert_email]
}
