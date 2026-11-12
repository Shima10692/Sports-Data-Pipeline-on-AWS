# Offline: the AWS provider is mocked. Run from this module: terraform init && terraform test

mock_provider "aws" {}

variables {
  project              = "sports"
  environment          = "dev"
  other_environments   = ["prod"]
  oidc_subject_prefix  = "repo:example-org/example-repo"
  oidc_provider_arn    = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
  state_bucket_arn     = "arn:aws:s3:::sports-tfstate-123456789012"
  other_state_prefixes = ["bootstrap", "prod"]
  account_id           = "123456789012"
}

run "trust_policies_are_scoped" {
  command = apply

  assert {
    condition     = aws_iam_role.this["apply"].name == "sports-github-dev-apply" && aws_iam_role.this["plan"].name == "sports-github-dev-plan"
    error_message = "Unexpected role names."
  }
  assert {
    condition     = jsondecode(aws_iam_role.this["apply"].assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:example-org/example-repo:environment:dev"
    error_message = "Apply role must trust only the dev GitHub Environment."
  }
  assert {
    condition     = jsondecode(aws_iam_role.this["plan"].assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:example-org/example-repo:pull_request"
    error_message = "Plan role must trust only pull requests."
  }
  assert {
    condition = alltrue([
      for r in aws_iam_role.this :
      jsondecode(r.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
      && jsondecode(r.assume_role_policy).Statement[0].Principal.Federated == var.oidc_provider_arn
    ])
    error_message = "Every role must trust only the GitHub OIDC provider with aud sts.amazonaws.com."
  }
  assert {
    condition     = alltrue([for r in aws_iam_role.this : !startswith(r.name, "sports-dev-")])
    error_message = "Deploy role names must not match the <project>-<env>-* prefix they manage."
  }
}

run "plan_role_is_read_only" {
  command = apply

  assert {
    condition     = aws_iam_role_policy_attachment.plan_read_only.policy_arn == "arn:aws:iam::aws:policy/ReadOnlyAccess"
    error_message = "Plan role should use ReadOnlyAccess."
  }
  assert {
    # init lists workspaces under "env:/", so listing must not be limited to the env prefix.
    condition = alltrue([
      for p in [aws_iam_role_policy.plan_state.policy, aws_iam_role_policy.apply.policy] :
      one([for s in jsondecode(p).Statement : s if s.Sid == "ListStateBucket"]).Resource == var.state_bucket_arn
      && !can(one([for s in jsondecode(p).Statement : s if s.Sid == "ListStateBucket"]).Condition)
    ])
    error_message = "Both roles need unconditional ListBucket on the state bucket for terraform init."
  }
  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.plan_state.policy).Statement : s.Action if s.Sid == "WriteOwnLockFile"
      ]) == ["s3:PutObject", "s3:DeleteObject"] && one([
      for s in jsondecode(aws_iam_role_policy.plan_state.policy).Statement : s.Resource if s.Sid == "WriteOwnLockFile"
    ]) == "arn:aws:s3:::sports-tfstate-123456789012/dev/*.tflock"
    error_message = "Plan role may write only its own lock file."
  }
  assert {
    condition = toset(one([
      for s in jsondecode(aws_iam_role_policy.plan_state.policy).Statement : s.Resource if s.Sid == "DenyOtherState"
    ])) == toset(["arn:aws:s3:::sports-tfstate-123456789012/bootstrap/*", "arn:aws:s3:::sports-tfstate-123456789012/prod/*"])
    error_message = "Plan role must be denied other stacks' state."
  }
}

run "apply_role_is_scoped" {
  command = apply

  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.apply.policy).Statement : s.Resource if s.Sid == "ReadWriteOwnState"
    ]) == "arn:aws:s3:::sports-tfstate-123456789012/dev/*"
    error_message = "Apply role must be limited to the dev/ state prefix."
  }
  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.apply.policy).Statement : s.Condition.StringEquals["iam:PermissionsBoundary"]
      if s.Sid == "CreateEnvRolesWithBoundary"
    ]) == "arn:aws:iam::123456789012:policy/sports-boundary-dev"
    error_message = "New roles must carry the dev permissions boundary."
  }
  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.apply.policy).Statement : s.Effect if s.Sid == "KeepBoundaries"
    ]) == "Deny"
    error_message = "Removing a permissions boundary must be denied."
  }
  assert {
    condition = one([
      for s in jsondecode(aws_iam_role_policy.apply.policy).Statement : s.Condition.StringEquals["aws:ResourceTag/Environment"]
      if s.Sid == "DenyOtherEnvironmentResources"
    ]) == ["prod"]
    error_message = "Resources tagged with another environment must be denied."
  }
  assert {
    # The boundary policy itself sits outside the prefix the apply role may edit.
    condition     = !startswith(aws_iam_policy.boundary.name, "sports-dev-")
    error_message = "The boundary must not be editable by the apply role."
  }
  assert {
    condition     = !strcontains(aws_iam_role_policy.apply.policy, "\"iam:*\"") && !strcontains(aws_iam_role_policy.apply.policy, "\"*:*\"")
    error_message = "Apply role must not get blanket IAM or admin access."
  }
}

run "boundary_has_no_iam_write" {
  command = apply

  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_policy.boundary.policy).Statement : [
        for a in flatten([s.Action]) :
        !startswith(a, "iam:") || a == "iam:PassRole"
      ] if s.Effect == "Allow"
    ]))
    error_message = "Workload boundary must allow no IAM action except PassRole."
  }
}

run "policies_fit_iam_size_limits" {
  command = apply

  # IAM counts characters excluding whitespace; jsonencode output has none.
  assert {
    condition     = length(aws_iam_role_policy.apply.policy) + length(aws_iam_role_policy.plan_state.policy) < 10240
    error_message = "Inline role policies exceed the 10,240-character IAM limit."
  }
  assert {
    condition     = length(aws_iam_policy.boundary.policy) < 6144
    error_message = "Boundary exceeds the 6,144-character managed policy limit."
  }
}

run "single_environment_has_no_cross_env_deny" {
  command = apply

  variables {
    other_environments   = []
    other_state_prefixes = []
  }

  assert {
    condition     = length([for s in jsondecode(aws_iam_role_policy.apply.policy).Statement : s if s.Effect == "Deny"]) == 1
    error_message = "With one environment only the boundary-protection deny should remain."
  }
}
