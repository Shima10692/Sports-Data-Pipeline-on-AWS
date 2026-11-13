# Glue (Spark) job: raw JSON → clean-zone Parquet, registered in the Glue Data Catalog.
#
#   s3://<artifacts>/glue/<job>/glue_entry.py     job script
#   s3://<artifacts>/glue/<job>/clean_zone.zip    the clean_zone package (--extra-py-files)
#   s3://<artifacts>/tmp/glue/<job>/              --TempDir (expires via the bucket lifecycle)
#
# Nothing runs on a schedule yet: start it with `aws glue start-job-run`, and from the
# orchestrator in phase 9. Cost is per run only (Flex: ~$0.29 per DPU-hour, 1-minute minimum).

locals {
  name         = "${var.project}-${var.environment}-raw-to-clean"
  boundary_arn = "arn:${var.partition}:iam::${var.account_id}:policy/${var.project}-boundary-${var.environment}"
  log_group    = "/aws-glue/jobs/${local.name}"

  code_prefix = "glue/${local.name}"
  temp_prefix = "tmp/glue/${local.name}"

  catalog_arn  = "arn:${var.partition}:glue:${var.region}:${var.account_id}:catalog"
  database_arn = "arn:${var.partition}:glue:${var.region}:${var.account_id}:database/${var.glue_database_name}"
  tables_arn   = "arn:${var.partition}:glue:${var.region}:${var.account_id}:table/${var.glue_database_name}/*"
}

# ---------------------------------------------------------------- code

data "archive_file" "package" {
  type        = "zip"
  source_dir  = "${var.source_dir}/src"
  output_path = "${path.root}/.build/${local.name}-clean_zone.zip"
  excludes    = ["**/__pycache__/**", "**/*.pyc"]

  # Same bytes on Windows and Linux, so CI plans show no phantom change.
  output_file_mode = "0644"
}

resource "aws_s3_object" "package" {
  bucket = var.artifacts_bucket_name
  key    = "${local.code_prefix}/clean_zone.zip"
  source = data.archive_file.package.output_path
  # source_hash, not etag: on a KMS-encrypted bucket the ETag is not the MD5.
  source_hash = data.archive_file.package.output_md5
}

resource "aws_s3_object" "script" {
  bucket      = var.artifacts_bucket_name
  key         = "${local.code_prefix}/glue_entry.py"
  source      = "${var.source_dir}/glue_entry.py"
  source_hash = filemd5("${var.source_dir}/glue_entry.py")
}

# ---------------------------------------------------------------- IAM

resource "aws_iam_role" "glue" {
  name                 = local.name
  description          = "Glue raw-to-clean job for ${var.environment}: reads raw, rewrites clean, updates the catalog."
  permissions_boundary = local.boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "glue.amazonaws.com" }
        Action    = "sts:AssumeRole"
        # Confused-deputy protection: only Glue acting for this account.
        Condition = { StringEquals = { "aws:SourceAccount" = var.account_id } }
      }
    ]
  })
}

resource "aws_iam_role_policy" "glue" {
  name = "raw-to-clean"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Read-only on raw: the raw zone stays append-only.
        Sid      = "ReadRawZone"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${var.raw_bucket_arn}/*"
      },
      {
        # Spark rewrites dt partitions, so the clean zone needs delete as well.
        Sid      = "ReadWriteCleanZone"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${var.clean_bucket_arn}/*"
      },
      {
        Sid      = "ListLakeBuckets"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [var.raw_bucket_arn, var.clean_bucket_arn, var.artifacts_bucket_arn]
      },
      {
        Sid      = "ReadJobCode"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${var.artifacts_bucket_arn}/${local.code_prefix}/*"
      },
      {
        Sid      = "TempDir"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${var.artifacts_bucket_arn}/${local.temp_prefix}/*"
      },
      {
        Sid    = "CatalogTablesAndPartitions"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable", "glue:CreateTable", "glue:UpdateTable",
          "glue:GetPartition", "glue:GetPartitions",
          "glue:BatchCreatePartition", "glue:BatchUpdatePartition", "glue:BatchGetPartition",
        ]
        Resource = [local.catalog_arn, local.database_arn, local.tables_arn]
      },
      {
        # Glue writes driver/executor logs here (continuous logging), plus its
        # standard /aws-glue/jobs/output and /error groups.
        Sid      = "WriteJobLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:AssociateKmsKey"]
        Resource = "arn:${var.partition}:logs:${var.region}:${var.account_id}:log-group:/aws-glue/*"
      },
      {
        Sid       = "JobMetrics"
        Effect    = "Allow"
        Action    = "cloudwatch:PutMetricData"
        Resource  = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = "Glue" } }
      },
    ]
  })
}

# ---------------------------------------------------------------- logs

resource "aws_cloudwatch_log_group" "job" {
  #checkov:skip=CKV_AWS_158:Logs hold run summaries and Spark output only, no secrets; AWS-managed encryption is enough.
  #checkov:skip=CKV_AWS_338:One-year retention costs more than it is worth for a practice project.
  name              = local.log_group
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------- job

resource "aws_glue_job" "raw_to_clean" {
  # Off while Glue job creation is blocked on the account; everything else in this
  # module (role, code, logs) stays deployed so switching back is one variable.
  count = var.create_job ? 1 : 0

  #checkov:skip=CKV_AWS_195:A security configuration encrypts logs/bookmarks with a customer KMS key ($1/month each); S3 data is already KMS-encrypted by bucket default.
  name        = local.name
  description = "Raw JSON to clean-zone Parquet for ${var.environment}; registers tables and partitions in ${var.glue_database_name}."
  role_arn    = aws_iam_role.glue.arn

  glue_version      = "5.0" # Spark 3.5, Python 3.11
  worker_type       = var.worker_type
  number_of_workers = var.number_of_workers
  execution_class   = var.execution_class
  timeout           = var.timeout_minutes
  max_retries       = 0 # the orchestrator decides about retries

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.artifacts_bucket_name}/${aws_s3_object.script.key}"
  }

  execution_property {
    max_concurrent_runs = var.max_concurrent_runs
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--extra-py-files"                   = "s3://${var.artifacts_bucket_name}/${aws_s3_object.package.key}"
    "--TempDir"                          = "s3://${var.artifacts_bucket_name}/${local.temp_prefix}/"
    "--job-bookmark-option"              = "job-bookmark-disable" # the job tracks work by dt partition itself
    "--enable-metrics"                   = "true"
    "--enable-observability-metrics"     = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--continuous-log-logGroup"          = aws_cloudwatch_log_group.job.name
    "--enable-spark-ui"                  = "false"

    # Read by glue_entry.py; override --sources / --dates per run.
    "--raw_bucket"   = var.raw_bucket_name
    "--clean_bucket" = var.clean_bucket_name
    "--database"     = var.glue_database_name
    "--region"       = var.region
    "--sources"      = "all"
    "--dates"        = "all"
  }

  depends_on = [aws_iam_role_policy.glue]
}
