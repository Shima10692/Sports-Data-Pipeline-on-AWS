# Offline: the AWS provider is mocked. Run from this module: terraform init && terraform test

mock_provider "aws" {}

variables {
  project               = "sports"
  environment           = "dev"
  clean_bucket_name     = "sports-dev-clean-123456789012"
  artifacts_bucket_name = "sports-dev-artifacts-123456789012"
}

run "names_follow_env_prefix" {
  command = apply

  assert {
    condition     = output.workgroup_name == "sports-dev"
    error_message = "Workgroup must be named <project>-<env>."
  }
  assert {
    condition     = output.staging_database_name == "sports_dev_staging" && output.marts_database_name == "sports_dev_marts"
    error_message = "dbt databases must be <project>_<env>_staging and <project>_<env>_marts."
  }
  assert {
    condition     = output.dbt_data_location == "s3://sports-dev-clean-123456789012/dbt/"
    error_message = "dbt table data must live under the clean bucket's dbt/ prefix."
  }
}

run "results_expire_and_scans_are_capped" {
  command = apply

  assert {
    # tmp/ in the artifacts bucket has an expiry rule; results must land there.
    condition     = startswith(output.query_results_location, "s3://sports-dev-artifacts-123456789012/tmp/")
    error_message = "Query results must go under the expiring tmp/ prefix."
  }
  assert {
    condition     = one(aws_athena_workgroup.this.configuration).bytes_scanned_cutoff_per_query == 1073741824
    error_message = "Default per-query scan cutoff must be 1 GiB."
  }
  assert {
    condition     = one(one(one(aws_athena_workgroup.this.configuration).result_configuration).encryption_configuration).encryption_option == "SSE_S3"
    error_message = "Query results must be encrypted."
  }
}

run "dbt_ctas_is_not_blocked" {
  command = apply

  assert {
    # Enforcing would make Athena reject dbt-athena's CTAS external_location.
    condition     = one(aws_athena_workgroup.this.configuration).enforce_workgroup_configuration == false
    error_message = "The workgroup must not enforce client settings, or dbt table builds fail."
  }
}

run "rejects_tiny_cutoff" {
  command = plan

  variables {
    bytes_scanned_cutoff_per_query = 1000
  }

  expect_failures = [var.bytes_scanned_cutoff_per_query]
}
