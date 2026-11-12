# Sports Data Pipeline on AWS

Practice data engineering project with live and historical sports data.

- Design: `docs/architecture.md` (diagram: `docs/architecture.png`)
- Instructions for Claude Code / agents: `CLAUDE.md`

## Status
| Phase | State |
|---|---|
| 1. Bootstrap (state bucket, OIDC, deploy roles) | Applied — see `infra/bootstrap/README.md` |
| 2. CI skeleton (fmt, validate, tests, Checkov, pytest, plan on PR) | In review |
| 3. Storage | Next |

## Layout
```
infra/bootstrap      One-off stack: state bucket, GitHub OIDC, plan/apply roles (run locally)
infra/envs/dev|prod  Environment stacks (state keys dev/, prod/)
infra/modules        Reusable Terraform modules, each with offline tests
ingestion/ dbt/ orchestration/ docs/
```

## Checks (same as CI, `.github/workflows/pr.yml`)
```bash
terraform fmt -check -recursive infra
for d in infra/modules/state_backend infra/modules/github_env_roles infra/bootstrap; do
  (cd "$d" && terraform init -backend=false && terraform test)
done
pip install -r requirements-dev.txt
pytest
checkov --config-file .checkov.yaml   # on Windows: set PYTHONUTF8=1 first
```
Every PR also gets a `terraform plan` for dev and prod posted as a comment, using the read-only plan roles via OIDC.
