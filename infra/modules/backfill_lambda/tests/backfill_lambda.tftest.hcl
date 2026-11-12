# Offline: AWS is mocked; the archive provider zips the real package locally.
# Run from this module: terraform init && terraform test

mock_provider "aws" {
  # The Lambda resource validates that its role is a real ARN.
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/sports-dev-backfill"
    }
  }
}

variables {
  project         = "sports"
  environment     = "dev"
  account_id      = "123456789012"
  region          = "us-east-1"
  raw_bucket_name = "sports-dev-raw-123456789012"
  raw_bucket_arn  = "arn:aws:s3:::sports-dev-raw-123456789012"
  source_dir      = "../../../ingestion/backfill/src"
}

run "function_config" {
  command = apply

  assert {
    condition     = aws_lambda_function.backfill.function_name == "sports-dev-backfill"
    error_message = "Function must be named <project>-<env>-backfill."
  }
  assert {
    condition     = aws_lambda_function.backfill.handler == "backfill.handler.lambda_handler" && aws_lambda_function.backfill.runtime == "python3.13"
    error_message = "Handler or runtime is wrong."
  }
  assert {
    condition     = tolist(aws_lambda_function.backfill.architectures) == tolist(["arm64"]) && aws_lambda_function.backfill.timeout == 900
    error_message = "Expected arm64 and the 900 s maximum timeout."
  }
  assert {
    condition     = aws_lambda_function.backfill.environment[0].variables == tomap({ RAW_BUCKET = "sports-dev-raw-123456789012" })
    error_message = "Only RAW_BUCKET should be set when no API key secret is given."
  }
  assert {
    condition     = aws_cloudwatch_log_group.backfill.name == "/aws/lambda/sports-dev-backfill" && aws_cloudwatch_log_group.backfill.retention_in_days == 14
    error_message = "Log group must match the function and expire after 14 days."
  }
}

run "role_is_bounded_and_scoped" {
  command = apply

  assert {
    condition     = aws_iam_role.backfill.permissions_boundary == "arn:aws:iam::123456789012:policy/sports-boundary-dev"
    error_message = "Role must carry the env boundary, or the apply role could not create it."
  }
  assert {
    condition     = startswith(aws_iam_role.backfill.name, "sports-dev-")
    error_message = "Role must sit under the env prefix."
  }
  assert {
    condition     = jsondecode(aws_iam_role.backfill.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "123456789012"
    error_message = "Trust policy needs aws:SourceAccount (confused deputy)."
  }
  assert {
    condition     = !strcontains(aws_iam_role_policy.backfill.policy, "Delete")
    error_message = "Backfill must never delete; the raw zone is append-only."
  }
  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.backfill.policy).Statement : s.Resource if s.Sid == "AppendToRawZone"
    ]) == "arn:aws:s3:::sports-dev-raw-123456789012/*"
    error_message = "Writes must be limited to the raw bucket."
  }
  assert {
    condition     = length([for s in jsondecode(aws_iam_role_policy.backfill.policy).Statement : s if s.Sid == "ListRawZone"]) == 1
    error_message = "ListBucket is required so HEAD on a missing key returns 404."
  }
  assert {
    condition     = length([for s in jsondecode(aws_iam_role_policy.backfill.policy).Statement : s if s.Sid == "ReadApiKey"]) == 0
    error_message = "No secret access unless a secret ARN is given."
  }
}

run "package_contains_handler" {
  command = apply

  assert {
    condition     = data.archive_file.code.output_size > 0 && fileexists("${var.source_dir}/backfill/handler.py")
    error_message = "Zip must contain the backfill package."
  }
}

run "optional_api_key_secret" {
  command = apply

  variables {
    api_key_secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:sports-dev-thesportsdb-AbCdEf"
  }

  assert {
    condition     = aws_lambda_function.backfill.environment[0].variables["THESPORTSDB_API_KEY_SECRET_ARN"] == var.api_key_secret_arn
    error_message = "Secret ARN should be passed to the function."
  }
  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.backfill.policy).Statement : s.Resource if s.Sid == "ReadApiKey"
    ]) == var.api_key_secret_arn
    error_message = "Role may read only the given secret."
  }
}

run "rejects_bad_memory" {
  command = plan

  variables {
    memory_mb = 64
  }

  expect_failures = [var.memory_mb]
}
