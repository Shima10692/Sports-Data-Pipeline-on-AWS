# Sports Data Pipeline on AWS

Practice data engineering project with live and historical sports data.

- Design: `docs/architecture.md` (diagram: `docs/architecture.png`)
- Instructions for Claude Code / agents: `CLAUDE.md`

## Status
| Phase | State |
|---|---|
| 1. Bootstrap (state bucket, OIDC, deploy roles) | Applied — see `infra/bootstrap/README.md` |
| 2. CI skeleton | Next |

## Layout
```
infra/bootstrap      One-off stack: state bucket, GitHub OIDC, plan/apply roles (run locally)
infra/envs/dev|prod  Environment stacks (state keys dev/, prod/)
infra/modules        Reusable Terraform modules, each with offline tests
ingestion/ dbt/ orchestration/ docs/
```

## Test
```bash
for d in infra/modules/state_backend infra/modules/github_env_roles infra/bootstrap; do
  (cd "$d" && terraform init -backend=false && terraform test)
done
```
