# Sports Data Pipeline on AWS

Practice data engineering project with live and historical sports data.

- Design: `docs/architecture.md` (diagram: `docs/architecture.png`)
- Instructions for Claude Code / agents: `CLAUDE.md`

## Status
| Phase | State |
|---|---|
| 1. Bootstrap (state bucket, OIDC, deploy roles) | Applied — see `infra/bootstrap/README.md` |
| 2. CI skeleton (fmt, validate, tests, Checkov, pytest, plan on PR) | Done |
| 3. Storage (S3 raw + clean zones, Glue database) | Applied (dev, prod) |
| 4. Batch backfill Lambda (StatsBomb, Jolpica, Cricsheet, TheSportsDB) | Applied (dev, prod) — see `ingestion/backfill/README.md` |
| 5. Processing (Glue raw → Parquet + Catalog) | Merged; running on a stopgap Lambda engine until AWS re-enables Glue jobs — see `processing/glue/README.md` |
| 6. Warehouse + dbt (Athena) | Next |

## Layout
```
infra/bootstrap      One-off stack: state bucket, GitHub OIDC, plan/apply roles (run locally)
infra/envs/dev|prod  Environment stacks (state keys dev/, prod/)
infra/modules        Reusable Terraform modules, each with offline tests
ingestion/           Backfill Lambda (phase 4); live pollers and Fargate later
processing/glue      Glue job: raw JSON → clean Parquet + Glue Catalog (phase 5)
dbt/ orchestration/ docs/
```

## Data lake (per environment)
| Zone | Bucket | Format | Rules |
|---|---|---|---|
| raw | `sports-<env>-raw-<account id>` | JSON as received, `source=<name>/date=<yyyy-mm-dd>/` | Append-only: deletes denied by bucket policy; overwrites keep the old version (90 days) |
| clean | `sports-<env>-clean-<account id>` | Parquet, `<table>/dt=<yyyy-mm-dd>/` | Written by Glue; old versions kept 7 days |
| artifacts | `sports-<env>-artifacts-<account id>` | Job code (`glue/`), scratch (`tmp/`) | Uploaded by Terraform; `tmp/` expires after 3 days |

All buckets are versioned, KMS-encrypted, private and TLS-only. Clean tables are registered in the Glue database `sports_<env>_lake`.

## Checks (same as CI, `.github/workflows/pr.yml`)
```bash
terraform fmt -check -recursive infra
for d in infra/modules/state_backend infra/modules/github_env_roles infra/modules/data_lake infra/modules/backfill_lambda infra/modules/glue_etl infra/bootstrap; do
  (cd "$d" && terraform init -backend=false && terraform test)
done
pip install -r requirements-dev.txt
pytest
checkov --config-file .checkov.yaml   # on Windows: set PYTHONUTF8=1 first
```
Every PR also gets a `terraform plan` for dev and prod posted as a comment, using the read-only plan roles via OIDC.
