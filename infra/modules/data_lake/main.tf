# S3 data lake for one environment:
#
#   <project>-<env>-raw-<account id>    raw zone: JSON exactly as received, append-only,
#                                       laid out as source=<name>/date=<yyyy-mm-dd>/...
#   <project>-<env>-clean-<account id>  clean zone: Parquet written by Glue (phase 5)
#
# plus a Glue Data Catalog database that clean-zone tables are registered in.
# Bucket names carry the account ID because S3 names are global; it is looked up
# at plan time, never committed.

locals {
  env_prefix = "${var.project}-${var.environment}"

  zones = {
    raw = {
      bucket                  = "${local.env_prefix}-raw-${var.account_id}"
      noncurrent_version_days = var.raw_noncurrent_version_days
    }
    clean = {
      bucket                  = "${local.env_prefix}-clean-${var.account_id}"
      noncurrent_version_days = var.clean_noncurrent_version_days
    }
  }

  # Glue database names allow lowercase letters, digits and underscores only.
  glue_database_name = replace("${local.env_prefix}_lake", "-", "_")
}

resource "aws_s3_bucket" "zone" {
  #checkov:skip=CKV_AWS_144:Cross-region replication doubles storage cost; raw data can be re-fetched from the sources.
  #checkov:skip=CKV_AWS_18:Server access logging needs a log bucket per env; CloudTrail covers management events for this practice project.
  #checkov:skip=CKV2_AWS_62:Event notifications are added when a consumer needs them (phase 5).
  for_each = local.zones

  bucket = each.value.bucket

  # Only an empty bucket can be destroyed. Prod data is never wiped by `terraform destroy`.
  force_destroy = var.force_destroy

  tags = { Zone = each.key }
}

resource "aws_s3_bucket_ownership_controls" "zone" {
  for_each = local.zones

  bucket = aws_s3_bucket.zone[each.key].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "zone" {
  for_each = local.zones

  bucket                  = aws_s3_bucket.zone[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "zone" {
  for_each = local.zones

  bucket = aws_s3_bucket.zone[each.key].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "zone" {
  for_each = local.zones

  bucket = aws_s3_bucket.zone[each.key].id
  rule {
    apply_server_side_encryption_by_default {
      # AWS-managed key (aws/s3): no key to manage or pay for; bucket key cuts KMS requests.
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "zone" {
  for_each = local.zones

  bucket = aws_s3_bucket.zone[each.key].id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = each.value.noncurrent_version_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.zone]
}

resource "aws_s3_bucket_policy" "zone" {
  for_each = local.zones

  bucket = aws_s3_bucket.zone[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid       = "DenyInsecureTransport"
          Effect    = "Deny"
          Principal = "*"
          Action    = "s3:*"
          Resource  = [aws_s3_bucket.zone[each.key].arn, "${aws_s3_bucket.zone[each.key].arn}/*"]
          Condition = { Bool = { "aws:SecureTransport" = "false" } }
        },
      ],
      # Raw zone is append-only: nobody may delete objects or versions. Overwrites
      # keep the previous version (versioning), so history is never lost.
      each.key == "raw" && var.raw_append_only ? [
        {
          Sid       = "RawZoneAppendOnly"
          Effect    = "Deny"
          Principal = "*"
          Action    = ["s3:DeleteObject", "s3:DeleteObjectVersion"]
          Resource  = "${aws_s3_bucket.zone[each.key].arn}/*"
        },
      ] : []
    )
  })

  depends_on = [aws_s3_bucket_public_access_block.zone]
}

resource "aws_glue_catalog_database" "lake" {
  name        = local.glue_database_name
  description = "Clean-zone tables for the ${var.environment} sports data lake."

  # Default location for tables created without an explicit one.
  location_uri = "s3://${aws_s3_bucket.zone["clean"].bucket}/"

  tags = { Environment = var.environment }
}
