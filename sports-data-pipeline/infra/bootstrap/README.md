# Bootstrap (phase 1)

One-off stack you run **locally** with admin credentials. It creates what GitHub Actions needs before it can deploy anything:

| Resource | Name | Purpose |
|---|---|---|
| S3 bucket | `sports-tfstate-<account id>` | Terraform state for `bootstrap/`, `dev/`, `prod/` (separate keys). Versioned, KMS-encrypted, public access blocked, TLS only. |
| Lock | `<key>.tflock` objects in the same bucket | S3-native state locking (`use_lockfile = true`, Terraform ≥ 1.10). No DynamoDB table needed. |
| OIDC provider | `token.actions.githubusercontent.com` | Lets GitHub Actions get short-lived AWS credentials. No stored keys. |
| IAM role | `sports-github-<env>-plan` | Assumable from **pull requests** only. `ReadOnlyAccess` + read its own state + write its own lock file. Denied other stacks' state. |
| IAM role | `sports-github-<env>-apply` | Assumable only by jobs running in the **GitHub Environment `<env>`**. Manages resources named `sports-<env>-*`. |
| IAM policy | `sports-boundary-<env>` | Permissions boundary every role created by the apply role must carry, so it cannot escalate privileges. |

Cost: effectively nothing (a few KB of state in S3, IAM is free).

## Guardrails on the apply roles
- IAM: can create roles only named `sports-<env>-*` **and** only with the `sports-boundary-<env>` boundary attached; cannot remove boundaries; cannot touch the deploy roles or the boundary itself (they sit outside the prefix).
- S3 and Secrets Manager: only `sports-<env>-*`.
- Anything tagged `Environment=<other env>` is denied (best-effort isolation while dev and prod share an account).
- Other services (Glue, Athena, Kinesis, Lambda, ECS, …) are allowed at service level for now; tighten them as each phase lands. Separate AWS accounts for dev and prod would give real isolation.
- No KMS key management yet: use AWS-managed keys until a phase needs a customer key.

## Run it

```bash
cd infra/bootstrap
cp terraform.tfvars.example terraform.tfvars   # set aws_region; repo is pre-filled
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

Then move this stack's own state into the bucket it just created:

1. Uncomment the block in `backend.tf` (set `region` to your `aws_region`).
2. `terraform init -migrate-state -backend-config="bucket=$(terraform output -raw state_bucket_name)"`
3. Answer `yes`, then delete the local `terraform.tfstate*` files.

## Wire up GitHub (used from phase 2)

Repository **variables** (Settings → Secrets and variables → Actions → Variables). These are identifiers, not secrets:

| Variable | Value |
|---|---|
| `AWS_REGION` | `terraform output -raw aws_region` |
| `TF_STATE_BUCKET` | `terraform output -raw state_bucket_name` |
| `AWS_PLAN_ROLE_DEV` / `AWS_PLAN_ROLE_PROD` | `terraform output plan_role_arns` |
| `AWS_APPLY_ROLE_DEV` / `AWS_APPLY_ROLE_PROD` | `terraform output apply_role_arns` |

GitHub **Environments**: create `dev` and `prod` (add required reviewers to `prod`). A job that uses an apply role must declare `environment: dev` or `environment: prod`, because that is what the role trusts.

Workflow jobs need `permissions: id-token: write` and `aws-actions/configure-aws-credentials` with `role-to-assume`.

Note: a PR job that declares an `environment:` gets the `environment:<name>` subject instead of `pull_request`, so it can't use the plan role. PRs from forks get no OIDC token at all.

## Environment stacks

`infra/envs/dev` and `infra/envs/prod` use the same bucket with keys `dev/terraform.tfstate` and `prod/terraform.tfstate`:

```bash
cd infra/envs/dev
terraform init -backend-config="bucket=$TF_STATE_BUCKET" -backend-config="region=$AWS_REGION"
```

## Tests

Offline, with a mocked AWS provider (no credentials needed):

```bash
for d in infra/modules/state_backend infra/modules/github_env_roles infra/bootstrap; do
  (cd "$d" && terraform init -backend=false && terraform test)
done
```
