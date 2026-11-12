# Two roles per environment, both assumed by GitHub Actions through OIDC:
#
#   <project>-github-<env>-plan   pull requests only; read-only AWS + its own state key.
#   <project>-github-<env>-apply  jobs running in the GitHub Environment "<env>" only;
#                                 manages resources named "<project>-<env>-*".
#
# The role names deliberately do not match "<project>-<env>-*", so an apply role
# cannot edit itself, the other environment's roles, or its permissions boundary.

locals {
  env_prefix = "${var.project}-${var.environment}"
  iam_arn    = "arn:${var.partition}:iam::${var.account_id}"
  oidc_host  = "token.actions.githubusercontent.com"

  state_object_arn = "${var.state_bucket_arn}/${var.environment}/*"
  other_state_arns = [for p in var.other_state_prefixes : "${var.state_bucket_arn}/${p}/*"]

  subjects = {
    plan  = "repo:${var.github_repository}:pull_request"
    apply = "repo:${var.github_repository}:environment:${var.environment}"
  }

  boundary_name = "${var.project}-boundary-${var.environment}"
  boundary_arn  = "${local.iam_arn}:policy/${local.boundary_name}"

  # Best-effort guardrail while dev and prod share one AWS account: deny touching or
  # creating anything tagged with another environment. Actions that do not support
  # these condition keys are simply not matched.
  cross_env_deny = length(var.other_environments) == 0 ? [] : [
    {
      Sid       = "DenyOtherEnvironmentResources"
      Effect    = "Deny"
      Action    = "*"
      Resource  = "*"
      Condition = { StringEquals = { "aws:ResourceTag/Environment" = var.other_environments } }
    },
    {
      Sid       = "DenyTaggingAsOtherEnvironment"
      Effect    = "Deny"
      Action    = "*"
      Resource  = "*"
      Condition = { StringEquals = { "aws:RequestTag/Environment" = var.other_environments } }
    },
  ]
}

# ---------------------------------------------------------------- trust policies

resource "aws_iam_role" "this" {
  for_each = local.subjects

  name                 = "${var.project}-github-${var.environment}-${each.key}"
  description          = "GitHub Actions ${each.key} role for the ${var.environment} environment."
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "GitHubOidc"
        Effect    = "Allow"
        Principal = { Federated = var.oidc_provider_arn }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${local.oidc_host}:aud" = "sts.amazonaws.com"
            "${local.oidc_host}:sub" = each.value
          }
        }
      }
    ]
  })

  tags = { Environment = var.environment }
}

# ---------------------------------------------------------------- plan role

resource "aws_iam_role_policy_attachment" "plan_read_only" {
  role       = aws_iam_role.this["plan"].name
  policy_arn = "arn:${var.partition}:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "plan_state" {
  name = "terraform-state"
  role = aws_iam_role.this["plan"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid       = "ListOwnStatePrefix"
          Effect    = "Allow"
          Action    = "s3:ListBucket"
          Resource  = var.state_bucket_arn
          Condition = { StringLike = { "s3:prefix" = ["${var.environment}/*"] } }
        },
        {
          Sid      = "ReadOwnState"
          Effect   = "Allow"
          Action   = "s3:GetObject"
          Resource = local.state_object_arn
        },
        {
          # `terraform plan` takes the lock, so the plan role may write the lock file only.
          Sid      = "WriteOwnLockFile"
          Effect   = "Allow"
          Action   = ["s3:PutObject", "s3:DeleteObject"]
          Resource = "${var.state_bucket_arn}/${var.environment}/*.tflock"
        },
      ],
      # ReadOnlyAccess can read every bucket, so block other stacks' state explicitly.
      length(local.other_state_arns) == 0 ? [] : [
        {
          Sid      = "DenyOtherState"
          Effect   = "Deny"
          Action   = "s3:GetObject*"
          Resource = local.other_state_arns
        }
      ]
    )
  })
}

# ---------------------------------------------------------------- permissions boundary

# Every role the apply role creates must carry this boundary. It caps what pipeline
# workloads (Lambda, Glue, Fargate, Step Functions, Firehose) can ever do.
resource "aws_iam_policy" "boundary" {
  #checkov:skip=CKV_AWS_290:A boundary is a ceiling, not a grant; workload roles narrow it further.
  #checkov:skip=CKV_AWS_355:Services such as Glue and Kinesis need resource "*" at the ceiling level.
  #checkov:skip=CKV_AWS_289:Same as above.
  name        = local.boundary_name
  description = "Permissions boundary for ${var.environment} pipeline workload roles."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid    = "EnvBuckets"
          Effect = "Allow"
          Action = "s3:*"
          Resource = [
            "arn:${var.partition}:s3:::${local.env_prefix}-*",
            "arn:${var.partition}:s3:::${local.env_prefix}-*/*",
          ]
        },
        {
          Sid    = "PipelineServices"
          Effect = "Allow"
          Action = [
            "s3:ListAllMyBuckets", "s3:GetBucketLocation",
            "glue:*", "athena:*",
            "kinesis:*", "firehose:*",
            "states:*", "lambda:InvokeFunction", "events:PutEvents",
            "ecs:RunTask", "ecs:StopTask", "ecs:DescribeTasks",
            "ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability",
            "logs:*", "cloudwatch:PutMetricData", "xray:PutTraceSegments", "xray:PutTelemetryRecords",
            "sns:Publish", "sqs:SendMessage",
            "kms:Decrypt", "kms:GenerateDataKey*", "kms:DescribeKey",
            "ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface", "ec2:Describe*",
            "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses",
          ]
          Resource = "*"
        },
        {
          Sid      = "EnvSecrets"
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
          Resource = "arn:${var.partition}:secretsmanager:*:${var.account_id}:secret:${local.env_prefix}-*"
        },
        {
          # e.g. Step Functions passing a role to a Glue job or ECS task.
          Sid      = "PassEnvRoles"
          Effect   = "Allow"
          Action   = "iam:PassRole"
          Resource = "${local.iam_arn}:role/${local.env_prefix}-*"
        },
      ],
      local.cross_env_deny
    )
  })

  tags = { Environment = var.environment }
}

# ---------------------------------------------------------------- apply role

resource "aws_iam_role_policy" "apply" {
  #checkov:skip=CKV_AWS_290:Terraform needs write access to create the pipeline; IAM, S3 and secrets are scoped by name below.
  #checkov:skip=CKV_AWS_355:Many services (Glue, Athena, Kinesis, CloudWatch) need resource "*" for create/describe calls.
  #checkov:skip=CKV_AWS_289:Same as above; privilege escalation is blocked by the mandatory permissions boundary.
  #checkov:skip=CKV_AWS_288:Data access is limited to buckets and secrets named for this environment.
  name = "terraform-apply"
  role = aws_iam_role.this["apply"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        # --- Terraform state (own prefix only)
        {
          Sid       = "ListOwnStatePrefix"
          Effect    = "Allow"
          Action    = "s3:ListBucket"
          Resource  = var.state_bucket_arn
          Condition = { StringLike = { "s3:prefix" = ["${var.environment}/*"] } }
        },
        {
          Sid      = "ReadWriteOwnState"
          Effect   = "Allow"
          Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
          Resource = local.state_object_arn
        },

        # --- S3: only buckets named <project>-<env>-*
        {
          Sid    = "EnvBuckets"
          Effect = "Allow"
          Action = "s3:*"
          Resource = [
            "arn:${var.partition}:s3:::${local.env_prefix}-*",
            "arn:${var.partition}:s3:::${local.env_prefix}-*/*",
          ]
        },

        # --- Pipeline services (tighten per service as later phases land)
        {
          Sid    = "PipelineServices"
          Effect = "Allow"
          Action = [
            "s3:ListAllMyBuckets", "s3:GetBucketLocation",
            "glue:*", "athena:*",
            "kinesis:*", "firehose:*",
            "lambda:*", "ecs:*", "ecr:*",
            "events:*", "scheduler:*", "states:*",
            "logs:*", "cloudwatch:*", "sns:*", "sqs:*",
            "kms:Describe*", "kms:List*", "kms:Get*",
            "ec2:Describe*", "ec2:*Vpc*", "ec2:*Subnet*", "ec2:*SecurityGroup*",
            "ec2:*RouteTable*", "ec2:*Route", "ec2:*InternetGateway*",
            "ec2:*NetworkAcl*", "ec2:CreateTags", "ec2:DeleteTags",
          ]
          Resource = "*"
        },

        # --- Secrets: containers only for <project>-<env>-*; values are set out of band
        {
          Sid      = "EnvSecrets"
          Effect   = "Allow"
          Action   = "secretsmanager:*"
          Resource = "arn:${var.partition}:secretsmanager:*:${var.account_id}:secret:${local.env_prefix}-*"
        },
        {
          Sid      = "SecretsGlobal"
          Effect   = "Allow"
          Action   = ["secretsmanager:ListSecrets", "secretsmanager:GetRandomPassword"]
          Resource = "*"
        },

        # --- IAM
        {
          Sid      = "IamRead"
          Effect   = "Allow"
          Action   = ["iam:Get*", "iam:List*"]
          Resource = "*"
        },
        {
          Sid      = "CreateEnvRolesWithBoundary"
          Effect   = "Allow"
          Action   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
          Resource = "${local.iam_arn}:role/${local.env_prefix}-*"
          Condition = {
            StringEquals = { "iam:PermissionsBoundary" = local.boundary_arn }
          }
        },
        {
          Sid    = "ManageEnvRoles"
          Effect = "Allow"
          Action = [
            "iam:DeleteRole", "iam:UpdateRole", "iam:UpdateRoleDescription", "iam:UpdateAssumeRolePolicy",
            "iam:TagRole", "iam:UntagRole",
            "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:PutRolePolicy", "iam:DeleteRolePolicy",
            "iam:PassRole",
          ]
          Resource = "${local.iam_arn}:role/${local.env_prefix}-*"
        },
        {
          Sid    = "ManageEnvPolicies"
          Effect = "Allow"
          Action = [
            "iam:CreatePolicy", "iam:DeletePolicy", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion",
            "iam:SetDefaultPolicyVersion", "iam:TagPolicy", "iam:UntagPolicy",
          ]
          Resource = "${local.iam_arn}:policy/${local.env_prefix}-*"
        },
        {
          Sid      = "ServiceLinkedRoles"
          Effect   = "Allow"
          Action   = "iam:CreateServiceLinkedRole"
          Resource = "${local.iam_arn}:role/aws-service-role/*"
        },
        {
          Sid      = "KeepBoundaries"
          Effect   = "Deny"
          Action   = "iam:DeleteRolePermissionsBoundary"
          Resource = "*"
        },
      ],
      local.cross_env_deny
    )
  })
}
