# Offline: AWS is mocked; the archive provider zips the real package locally.
# Run from this module: terraform init && terraform test

mock_provider "aws" {
  # The Lambda resource validates that its role is a real ARN.
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/sports-dev-raw-to-clean-fn"
    }
  }
  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "arn:aws:lambda:us-east-1:123456789012:layer:AWSSDKPandas-Python313-Arm64:17"
    }
  }
}

variables {
  project            = "sports"
  environment        = "dev"
  account_id         = "123456789012"
  region             = "us-east-1"
  raw_bucket_name    = "sports-dev-raw-123456789012"
  raw_bucket_arn     = "arn:aws:s3:::sports-dev-raw-123456789012"
  clean_bucket_name  = "sports-dev-clean-123456789012"
  clean_bucket_arn   = "arn:aws:s3:::sports-dev-clean-123456789012"
  glue_database_name = "sports_dev_lake"
  source_dir         = "../../../processing/glue"
}

run "function_config" {
  command = apply

  assert {
    condition     = aws_lambda_function.fn.function_name == "sports-dev-raw-to-clean" && aws_iam_role.fn.name == "sports-dev-raw-to-clean-fn"
    error_message = "Function is <project>-<env>-raw-to-clean; its role must not clash with the Glue job's role name."
  }
  assert {
    condition     = aws_lambda_function.fn.handler == "clean_zone.lambda_handler.lambda_handler" && aws_lambda_function.fn.runtime == "python3.13"
    error_message = "Handler or runtime is wrong."
  }
  assert {
    condition     = tolist(aws_lambda_function.fn.architectures) == tolist(["arm64"]) && aws_lambda_function.fn.timeout == 900 && aws_lambda_function.fn.memory_size == 3008
    error_message = "Expected arm64, the 900 s maximum timeout and 3008 MB."
  }
  assert {
    condition     = data.aws_ssm_parameter.pandas_layer.name == "/aws/service/aws-sdk-pandas/3.18.0/py3.13/arm64/layer-arn" && length(aws_lambda_function.fn.layers) == 1
    error_message = "pyarrow must come from the pinned AWS SDK for pandas layer matching the runtime."
  }
  assert {
    condition = aws_lambda_function.fn.environment[0].variables == tomap({
      RAW_BUCKET    = "sports-dev-raw-123456789012"
      CLEAN_BUCKET  = "sports-dev-clean-123456789012"
      GLUE_DATABASE = "sports_dev_lake"
    })
    error_message = "The handler reads exactly these three variables."
  }
  assert {
    condition     = aws_cloudwatch_log_group.fn.name == "/aws/lambda/sports-dev-raw-to-clean" && aws_cloudwatch_log_group.fn.retention_in_days == 14
    error_message = "Logs go to a Terraform-managed group with 14-day retention."
  }
  assert {
    condition     = data.archive_file.code.output_size > 0 && fileexists("${var.source_dir}/src/clean_zone/lambda_handler.py")
    error_message = "Code zip must contain the clean_zone package with the handler."
  }
}

run "role_is_bounded_and_scoped" {
  command = apply

  assert {
    condition     = aws_iam_role.fn.permissions_boundary == "arn:aws:iam::123456789012:policy/sports-boundary-dev"
    error_message = "Role must carry the env boundary."
  }
  assert {
    condition = (
      jsondecode(aws_iam_role.fn.assume_role_policy).Statement[0].Principal.Service == "lambda.amazonaws.com" &&
      jsondecode(aws_iam_role.fn.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "123456789012"
    )
    error_message = "Only Lambda for this account may assume the role."
  }
  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.fn.policy).Statement :
      !(contains(flatten([s.Resource]), "${var.raw_bucket_arn}/*") && anytrue([for a in flatten([s.Action]) : a != "s3:GetObject"]))
    ])
    error_message = "The raw zone must be read-only for the function."
  }
  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.fn.policy).Statement : s.Resource if s.Sid == "ReadWriteCleanZone"
    ]) == "${var.clean_bucket_arn}/*"
    error_message = "Writes must be limited to the clean bucket."
  }
  assert {
    condition = alltrue([
      for r in one([for s in jsondecode(aws_iam_role_policy.fn.policy).Statement : s.Resource if s.Sid == "CatalogTablesAndPartitions"]) :
      strcontains(r, ":catalog") || strcontains(r, "sports_dev_lake")
    ])
    error_message = "Catalog access must be limited to the env database."
  }
  assert {
    condition     = !strcontains(aws_iam_role_policy.fn.policy, "glue:Delete") && !strcontains(aws_iam_role_policy.fn.policy, "glue:CreateJob")
    error_message = "The function never deletes catalog objects or touches Glue jobs."
  }
}

run "rejects_too_little_memory" {
  command = plan

  variables {
    memory_mb = 512
  }

  expect_failures = [var.memory_mb]
}
