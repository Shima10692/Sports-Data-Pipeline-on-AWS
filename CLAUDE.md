# CLAUDE.md — Sports Data Pipeline on AWS

Read this first. The full design is in `docs/architecture.md`; the diagram is `docs/architecture.png` (export it from the Design canvas and add it).

## Goal
A data engineering practice project: ingest live and historical sports data on AWS, land it in an S3 lake, model it with dbt, and serve dashboards. Everything is built with Terraform and deployed by GitHub Actions to a dev and a prod environment.

## Repo layout
```
/infra               Terraform: modules/ + envs/dev, envs/prod
/ingestion           Lambda pollers, ECS Fargate (websockets + OpenF1 replay), batch backfill
/processing          Glue jobs: raw JSON → clean Parquet + Glue Catalog
/dbt                 dbt project (dbt-athena first; dbt-redshift optional)
/orchestration       Airflow DAGs for MWAA (or Step Functions definitions)
/.github/workflows   CI/CD
/docs                architecture.md, architecture.png
```

## Hard rules
- No stored AWS keys anywhere. GitHub Actions uses OIDC to assume an IAM role.
- API keys live only in AWS Secrets Manager. Never commit secrets or `.env` files.
- Terraform state: S3 backend with state locking, separate state for dev and prod.
- All AWS resources are created by Terraform. No click-ops.
- Stay low cost: prefer Athena over Redshift, Step Functions over MWAA unless asked, serverless where possible.
- Respect API limits (API-Football free tier is ~100 calls/day). Pollers must be rate-limited and idempotent.
- Raw zone is append-only JSON partitioned by `source=/date=`. Clean zone is Parquet.
- Every new piece ships with tests: pytest for Python, dbt tests for models.

## Build order (do one phase at a time, open a PR per phase)
1. **Bootstrap** — Terraform state bucket + lock, GitHub OIDC provider and IAM roles (dev, prod).
2. **CI skeleton** — PR workflow: `terraform fmt/validate`, Checkov/tfsec, `terraform plan` posted to PR, pytest.
3. **Storage** — S3 raw and clean buckets, Glue Data Catalog database.
4. **Batch first** — backfill job (StatsBomb Open Data, Jolpica/FastF1, Cricsheet, TheSportsDB) into S3 raw. Easiest to test, no live data needed.
5. **Processing** — Glue jobs raw JSON → Parquet in clean zone; register tables in the Catalog.
6. **Warehouse + dbt** — Athena workgroup; dbt models `fact_events`, `dim_team`, `dim_player`, `dim_session` + tests.
7. **Streaming** — Kinesis Data Streams → Firehose → S3 raw; Lambda pollers on EventBridge Scheduler; Secrets Manager.
8. **Fargate** — websocket listener (SportScore) and OpenF1 replay simulator, image in ECR.
9. **Orchestration** — DAGs / state machine: backfill → Glue → dbt build + test.
10. **Quality + monitoring** — Glue Data Quality rules, late/corrected event handling, CloudWatch alarms.
11. **Deploy pipeline** — merge-to-main workflow and prod promotion with GitHub Environments approval.
12. **Outputs** — QuickSight dashboards, analysis notebooks.

## Architecture changes (version-controlled, never overwritten)
- Any change to the architecture (new, removed or swapped component, engine, data flow, storage layout, orchestration or deployment) gets a new version. Follow `docs/architecture/README.md`.
- Before changing a diagram or `docs/architecture.md`, make sure the current version is archived in `docs/architecture/versions/`.
- Write an ADR in `docs/architecture/decisions/`, add a `docs/architecture/CHANGELOG.md` entry, and save the new diagrams in a new `versions/vX.Y.Z/` folder.
- Never edit, rename or delete anything under `docs/architecture/versions/`.
- Current version: **v1.1.0** (temporary Lambda stand-in for Glue in phase 5, see ADR-0001).

## Working style
- Ask before creating anything that costs money beyond the free tier (MWAA, Redshift, QuickSight, Fargate running 24/7).
- Keep changes small. Explain what you built in the PR description.
- Run `terraform plan` and tests locally before pushing.
