# STOPGAP raw-to-clean engine: the same clean_zone code as the Glue job, run in
# one Lambda with pyarrow. Used while Glue job creation is blocked on the account
# (AWS Support case open). Switch back with processing_engine = "glue" in the env;
# this module is then destroyed and the Glue job created. Output is identical:
# same S3 layout, same Glue Catalog tables and partitions.
#
# Invoke on demand: aws lambda invoke --function-name <name> --payload '{"sources":"jolpica"}'.
# If the response has "complete": false, invoke again with its "resume" payload.

locals {
  name          = "${var.project}-${var.environment}-raw-to-clean"
  role_name     = "${local.name}-fn" # the Glue job's role already uses local.name
  boundary_arn  = "arn:${var.partition}:iam::${var.account_id}:policy/${var.project}-boundary-${var.environment}"
  log_group_arn = "arn:${var.partition}:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/${local.name}"

  catalog_arn  = "arn:${var.partition}:glue:${var.region}:${var.account_id}:catalog"
  database_arn = "arn:${var.partition}:glue:${var.region}:${var.account_id}:database/${var.glue_database_name}"
  tables_arn   = "arn:${var.partition}:glue:${var.region}:${var.account_id}:table/${var.glue_database_name}/*"
}

# AWS SDK for pandas layer (ships pyarrow). AWS publishes its ARN as a public SSM
# parameter, so no account ID is hardcoded and the version is pinned here.
data "aws_ssm_parameter" "pandas_layer" {
  name = "/aws/service/aws-sdk-pandas/${var.sdk_pandas_version}/py3.13/arm64/layer-arn"
}

data "archive_file" "code" {
  type        = "zip"
  source_dir  = "${var.source_dir}/src"
  output_path = "${path.root}/.build/${local.name}.zip"
  excludes    = ["**/__pycache__/**", "**/*.pyc"]

  # Same bytes on Windows and Linux, so CI plans show no phantom code update.
  output_file_mode = "0644"
}

resource "aws_iam_role" "fn" {
  name                 = local.role_name
  description          = "Raw-to-clean Lambda for ${var.environment}: reads raw, rewrites clean, updates the catalog."
  permissions_boundary = local.boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
        # Confused-deputy protection: only Lambda acting for this account.
        Condition = { StringEquals = { "aws:SourceAccount" = var.account_id } }
      }
    ]
  })
}

resource "aws_iam_role_policy" "fn" {
  name = "raw-to-clean"
  role = aws_iam_role.fn.id

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
        # Partitions are replaced: upload the new file, delete the old ones.
        Sid      = "ReadWriteCleanZone"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${var.clean_bucket_arn}/*"
      },
      {
        Sid      = "ListLakeBuckets"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = [var.raw_bucket_arn, var.clean_bucket_arn]
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
        Sid      = "WriteOwnLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${local.log_group_arn}:*"
      },
      {
        Sid      = "Tracing"
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "fn" {
  #checkov:skip=CKV_AWS_158:Logs hold run summaries only, no data or secrets; AWS-managed encryption is enough.
  #checkov:skip=CKV_AWS_338:One-year retention costs more than it is worth for a practice project.
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "fn" {
  #checkov:skip=CKV_AWS_117:Talks to S3 and Glue only; a VPC would need endpoints or a NAT gateway for no gain.
  #checkov:skip=CKV_AWS_116:Invoked synchronously or by Step Functions, which handle failures; a DLQ adds nothing.
  #checkov:skip=CKV_AWS_173:Environment holds only bucket and database names, nothing sensitive.
  #checkov:skip=CKV_AWS_272:Code signing is out of scope for a practice project; CI is the gate.
  #checkov:skip=CKV_AWS_115:Reserved concurrency would eat into a new account's 10-execution limit; runs are triggered one at a time.
  function_name = local.name
  description   = "STOPGAP for the Glue job: raw JSON to clean Parquet + Glue Catalog (${var.environment})."
  role          = aws_iam_role.fn.arn

  runtime       = "python3.13"
  architectures = ["arm64"] # cheaper per GB-second than x86
  handler       = "clean_zone.lambda_handler.lambda_handler"
  timeout       = 900 # Lambda maximum; the code stops two minutes early and returns a resume payload
  memory_size   = var.memory_mb
  layers        = [nonsensitive(data.aws_ssm_parameter.pandas_layer.value)]

  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256

  environment {
    variables = {
      RAW_BUCKET    = var.raw_bucket_name
      CLEAN_BUCKET  = var.clean_bucket_name
      GLUE_DATABASE = var.glue_database_name
    }
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [aws_cloudwatch_log_group.fn, aws_iam_role_policy.fn]
}
