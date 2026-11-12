# Backfill Lambda: loads historical and reference data into the raw zone.
# Invoked on demand (aws lambda invoke ...) now, by the orchestrator in phase 9.
# Pure-stdlib Python + the runtime's boto3, so the code is zipped as-is.

locals {
  name          = "${var.project}-${var.environment}-backfill"
  boundary_arn  = "arn:${var.partition}:iam::${var.account_id}:policy/${var.project}-boundary-${var.environment}"
  log_group_arn = "arn:${var.partition}:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/${local.name}"
}

data "archive_file" "code" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.root}/.build/${local.name}.zip"
  excludes    = ["**/__pycache__/**", "**/*.pyc"]

  # Same bytes on Windows and Linux: file modes differ per OS otherwise, which
  # changes the hash and shows a phantom code update in every CI plan.
  output_file_mode = "0644"
}

resource "aws_iam_role" "backfill" {
  name                 = local.name
  description          = "Backfill Lambda for ${var.environment}: writes to the raw zone only."
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

resource "aws_iam_role_policy" "backfill" {
  name = "backfill"
  role = aws_iam_role.backfill.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          # GetObject is what HeadObject needs; no delete permission at all.
          Sid      = "AppendToRawZone"
          Effect   = "Allow"
          Action   = ["s3:PutObject", "s3:GetObject"]
          Resource = "${var.raw_bucket_arn}/*"
        },
        {
          # Without ListBucket, HEAD on a missing key returns 403 instead of 404.
          Sid      = "ListRawZone"
          Effect   = "Allow"
          Action   = "s3:ListBucket"
          Resource = var.raw_bucket_arn
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
      ],
      var.api_key_secret_arn == null ? [] : [
        {
          Sid      = "ReadApiKey"
          Effect   = "Allow"
          Action   = "secretsmanager:GetSecretValue"
          Resource = var.api_key_secret_arn
        }
      ]
    )
  })
}

resource "aws_cloudwatch_log_group" "backfill" {
  #checkov:skip=CKV_AWS_158:Logs hold run summaries only, no data or secrets; AWS-managed encryption is enough.
  #checkov:skip=CKV_AWS_338:One-year retention costs more than it is worth for a practice project.
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "backfill" {
  #checkov:skip=CKV_AWS_117:Calls public APIs only; a VPC would need a NAT gateway (~$32/month).
  #checkov:skip=CKV_AWS_116:Invoked synchronously or by Step Functions, which handle failures; a DLQ adds nothing.
  #checkov:skip=CKV_AWS_173:Environment holds only the bucket name and a secret ARN, nothing sensitive.
  #checkov:skip=CKV_AWS_272:Code signing is out of scope for a practice project; CI is the gate.
  #checkov:skip=CKV_AWS_115:Reserved concurrency would eat into a new account's 10-execution limit; runs are triggered one at a time.
  function_name = local.name
  description   = "Backfill historical/reference sports data into the ${var.environment} raw zone."
  role          = aws_iam_role.backfill.arn

  runtime       = "python3.13"
  architectures = ["arm64"] # cheaper per GB-second than x86
  handler       = "backfill.handler.lambda_handler"
  timeout       = 900 # Lambda maximum; the code stops a minute early and can be resumed
  memory_size   = var.memory_mb

  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256

  environment {
    variables = merge(
      { RAW_BUCKET = var.raw_bucket_name },
      var.api_key_secret_arn == null ? {} : { THESPORTSDB_API_KEY_SECRET_ARN = var.api_key_secret_arn }
    )
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [aws_cloudwatch_log_group.backfill, aws_iam_role_policy.backfill]
}
