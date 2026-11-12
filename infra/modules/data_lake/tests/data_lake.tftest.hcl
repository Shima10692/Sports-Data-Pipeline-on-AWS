# Offline: the AWS provider is mocked. Run from this module: terraform init && terraform test

mock_provider "aws" {}

variables {
  project     = "sports"
  environment = "dev"
  account_id  = "123456789012"
}

run "names_follow_env_prefix" {
  command = apply

  assert {
    condition     = output.raw_bucket_name == "sports-dev-raw-123456789012" && output.clean_bucket_name == "sports-dev-clean-123456789012"
    error_message = "Bucket names must be <project>-<env>-<zone>-<account id>."
  }
  assert {
    # The dev apply role may only manage buckets named sports-dev-*.
    condition     = alltrue([for b in aws_s3_bucket.zone : startswith(b.bucket, "sports-dev-")])
    error_message = "Buckets must sit under the env prefix the apply role is allowed to manage."
  }
  assert {
    condition     = output.glue_database_name == "sports_dev_lake"
    error_message = "Glue database name must be sports_<env>_lake."
  }
  assert {
    condition     = aws_glue_catalog_database.lake.location_uri == "s3://sports-dev-clean-123456789012/"
    error_message = "Glue database should default to the clean bucket."
  }
}

run "buckets_are_hardened" {
  command = apply

  assert {
    condition     = alltrue([for b in aws_s3_bucket.zone : b.force_destroy == false])
    error_message = "force_destroy must default to false."
  }
  assert {
    condition     = alltrue([for v in aws_s3_bucket_versioning.zone : one(v.versioning_configuration).status == "Enabled"])
    error_message = "Both zones must be versioned."
  }
  assert {
    condition = alltrue([
      for p in aws_s3_bucket_public_access_block.zone :
      p.block_public_acls && p.block_public_policy && p.ignore_public_acls && p.restrict_public_buckets
    ])
    error_message = "All public access must be blocked on both zones."
  }
  assert {
    condition     = alltrue([for o in aws_s3_bucket_ownership_controls.zone : one(o.rule).object_ownership == "BucketOwnerEnforced"])
    error_message = "ACLs must be disabled."
  }
  assert {
    condition = alltrue([
      for e in aws_s3_bucket_server_side_encryption_configuration.zone :
      one([for r in e.rule : one(r.apply_server_side_encryption_by_default).sse_algorithm]) == "aws:kms"
    ])
    error_message = "Both zones must be KMS-encrypted."
  }
  assert {
    condition = alltrue([
      for p in aws_s3_bucket_policy.zone :
      length([for s in jsondecode(p.policy).Statement : s if s.Sid == "DenyInsecureTransport"]) == 1
    ])
    error_message = "Both zones must deny non-TLS access."
  }
}

run "raw_is_append_only" {
  command = apply

  assert {
    condition = one([
      for s in jsondecode(aws_s3_bucket_policy.zone["raw"].policy).Statement : s.Action if s.Sid == "RawZoneAppendOnly"
    ]) == ["s3:DeleteObject", "s3:DeleteObjectVersion"]
    error_message = "Raw zone must deny deletes."
  }
  assert {
    condition     = length([for s in jsondecode(aws_s3_bucket_policy.zone["clean"].policy).Statement : s if s.Sid == "RawZoneAppendOnly"]) == 0
    error_message = "Clean zone is rewritten by Glue and must allow deletes."
  }
}

run "retention_defaults" {
  command = apply

  assert {
    condition     = one(one(aws_s3_bucket_lifecycle_configuration.zone["raw"].rule).noncurrent_version_expiration).noncurrent_days == 90
    error_message = "Raw noncurrent versions should be kept 90 days by default."
  }
  assert {
    condition     = one(one(aws_s3_bucket_lifecycle_configuration.zone["clean"].rule).noncurrent_version_expiration).noncurrent_days == 7
    error_message = "Clean noncurrent versions should be kept 7 days by default."
  }
}

run "append_only_can_be_disabled" {
  command = apply

  variables {
    raw_append_only = false
  }

  assert {
    condition     = length([for s in jsondecode(aws_s3_bucket_policy.zone["raw"].policy).Statement : s if s.Sid == "RawZoneAppendOnly"]) == 0
    error_message = "raw_append_only = false should drop the delete deny."
  }
}

run "rejects_bad_account_id" {
  command = plan

  variables {
    account_id = "12345"
  }

  expect_failures = [var.account_id]
}
