# Offline: the AWS provider is mocked. Run from this module: terraform init && terraform test

mock_provider "aws" {}

variables {
  bucket_name = "sports-tfstate-123456789012"
}

run "bucket_is_hardened" {
  command = apply

  assert {
    condition     = aws_s3_bucket.state.bucket == "sports-tfstate-123456789012"
    error_message = "Bucket name not passed through."
  }
  assert {
    condition     = aws_s3_bucket.state.force_destroy == false
    error_message = "State bucket must never be force-destroyed."
  }
  assert {
    condition     = one(aws_s3_bucket_versioning.state.versioning_configuration).status == "Enabled"
    error_message = "State bucket must be versioned."
  }
  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.state.block_public_acls,
      aws_s3_bucket_public_access_block.state.block_public_policy,
      aws_s3_bucket_public_access_block.state.ignore_public_acls,
      aws_s3_bucket_public_access_block.state.restrict_public_buckets,
    ])
    error_message = "All public access must be blocked."
  }
  assert {
    condition     = one(aws_s3_bucket_ownership_controls.state.rule).object_ownership == "BucketOwnerEnforced"
    error_message = "ACLs must be disabled."
  }
  assert {
    condition     = one([for r in aws_s3_bucket_server_side_encryption_configuration.state.rule : one(r.apply_server_side_encryption_by_default).sse_algorithm]) == "aws:kms"
    error_message = "State must be KMS-encrypted."
  }
  assert {
    condition     = jsondecode(aws_s3_bucket_policy.state.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "Bucket policy must deny non-TLS access."
  }
  assert {
    condition     = one(one(aws_s3_bucket_lifecycle_configuration.state.rule).noncurrent_version_expiration).noncurrent_days == 90
    error_message = "Old state versions should expire after the default 90 days."
  }
}

run "rejects_zero_retention" {
  command = plan

  variables {
    noncurrent_version_retention_days = 0
  }

  expect_failures = [var.noncurrent_version_retention_days]
}
