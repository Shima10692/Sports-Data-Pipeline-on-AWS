# Offline: AWS is mocked; the archive provider zips the real package locally.
# Run from this module: terraform init && terraform test

mock_provider "aws" {
  # The Glue job validates that its role is a real ARN.
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/sports-dev-raw-to-clean"
    }
  }
}

variables {
  project               = "sports"
  environment           = "dev"
  account_id            = "123456789012"
  region                = "us-east-1"
  raw_bucket_name       = "sports-dev-raw-123456789012"
  raw_bucket_arn        = "arn:aws:s3:::sports-dev-raw-123456789012"
  clean_bucket_name     = "sports-dev-clean-123456789012"
  clean_bucket_arn      = "arn:aws:s3:::sports-dev-clean-123456789012"
  artifacts_bucket_name = "sports-dev-artifacts-123456789012"
  artifacts_bucket_arn  = "arn:aws:s3:::sports-dev-artifacts-123456789012"
  glue_database_name    = "sports_dev_lake"
  source_dir            = "../../../processing/glue"
}

run "job_config" {
  command = apply

  assert {
    condition     = aws_glue_job.raw_to_clean.name == "sports-dev-raw-to-clean" && aws_glue_job.raw_to_clean.glue_version == "5.0"
    error_message = "Job must be <project>-<env>-raw-to-clean on Glue 5.0."
  }
  assert {
    condition     = aws_glue_job.raw_to_clean.execution_class == "FLEX" && aws_glue_job.raw_to_clean.worker_type == "G.1X" && aws_glue_job.raw_to_clean.number_of_workers == 2
    error_message = "Defaults must be the cheapest config: Flex, G.1X, 2 workers."
  }
  assert {
    condition     = aws_glue_job.raw_to_clean.timeout == 30 && aws_glue_job.raw_to_clean.max_retries == 0
    error_message = "A 30-minute timeout caps cost; retries belong to the orchestrator."
  }
  assert {
    condition     = one(aws_glue_job.raw_to_clean.command).script_location == "s3://sports-dev-artifacts-123456789012/glue/sports-dev-raw-to-clean/glue_entry.py"
    error_message = "Script must be the uploaded glue_entry.py."
  }
  assert {
    condition     = aws_glue_job.raw_to_clean.default_arguments["--extra-py-files"] == "s3://sports-dev-artifacts-123456789012/glue/sports-dev-raw-to-clean/clean_zone.zip"
    error_message = "The clean_zone package must be passed with --extra-py-files."
  }
  assert {
    condition = (
      aws_glue_job.raw_to_clean.default_arguments["--raw_bucket"] == var.raw_bucket_name &&
      aws_glue_job.raw_to_clean.default_arguments["--clean_bucket"] == var.clean_bucket_name &&
      aws_glue_job.raw_to_clean.default_arguments["--database"] == "sports_dev_lake" &&
      aws_glue_job.raw_to_clean.default_arguments["--sources"] == "all" &&
      aws_glue_job.raw_to_clean.default_arguments["--dates"] == "all"
    )
    error_message = "Every argument glue_entry.py reads needs a default."
  }
  assert {
    condition     = startswith(aws_glue_job.raw_to_clean.default_arguments["--TempDir"], "s3://sports-dev-artifacts-123456789012/tmp/")
    error_message = "TempDir must sit under tmp/ so the lifecycle rule cleans it up."
  }
  assert {
    condition     = aws_glue_job.raw_to_clean.default_arguments["--continuous-log-logGroup"] == aws_cloudwatch_log_group.job.name && aws_cloudwatch_log_group.job.retention_in_days == 14
    error_message = "Logs go to a Terraform-managed group with 14-day retention."
  }
}

run "role_is_bounded_and_scoped" {
  command = apply

  assert {
    condition     = aws_iam_role.glue.permissions_boundary == "arn:aws:iam::123456789012:policy/sports-boundary-dev" && startswith(aws_iam_role.glue.name, "sports-dev-")
    error_message = "Role must carry the env boundary and sit under the env prefix."
  }
  assert {
    condition = (
      jsondecode(aws_iam_role.glue.assume_role_policy).Statement[0].Principal.Service == "glue.amazonaws.com" &&
      jsondecode(aws_iam_role.glue.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "123456789012"
    )
    error_message = "Only Glue for this account may assume the role."
  }
  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.glue.policy).Statement :
      !(contains(flatten([s.Resource]), "${var.raw_bucket_arn}/*") && anytrue([for a in flatten([s.Action]) : a != "s3:GetObject"]))
    ])
    error_message = "The raw zone must be read-only for the job."
  }
  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.glue.policy).Statement : s.Resource if s.Sid == "ReadWriteCleanZone"
    ]) == "${var.clean_bucket_arn}/*"
    error_message = "Writes must be limited to the clean bucket."
  }
  assert {
    condition = alltrue([
      for r in one([for s in jsondecode(aws_iam_role_policy.glue.policy).Statement : s.Resource if s.Sid == "CatalogTablesAndPartitions"]) :
      strcontains(r, ":catalog") || strcontains(r, "sports_dev_lake")
    ])
    error_message = "Catalog access must be limited to the env database."
  }
  assert {
    condition     = !strcontains(aws_iam_role_policy.glue.policy, "glue:Delete")
    error_message = "The job never deletes catalog objects."
  }
}

run "code_is_uploaded" {
  command = apply

  assert {
    condition     = aws_s3_object.package.bucket == var.artifacts_bucket_name && aws_s3_object.script.key == "glue/sports-dev-raw-to-clean/glue_entry.py"
    error_message = "Script and package go to the artifacts bucket under glue/<job>/."
  }
  assert {
    condition     = data.archive_file.package.output_size > 0 && fileexists("${var.source_dir}/src/clean_zone/job.py")
    error_message = "Package zip must contain clean_zone."
  }
}

run "rejects_bad_sizing" {
  command = plan

  variables {
    number_of_workers = 1
    execution_class   = "SPOT"
  }

  expect_failures = [var.number_of_workers, var.execution_class]
}
