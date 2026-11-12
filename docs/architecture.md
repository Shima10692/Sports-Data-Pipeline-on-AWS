# Architecture — Sports Data Pipeline on AWS

Flow is left to right: sources → ingestion → streaming → raw lake → processing → clean lake → warehouse → models → outputs. Orchestration sits above, data quality and monitoring below, deployment in its own lane.

Line styles in the diagram: **live** = dashed orange, **batch** = solid blue, **orchestration / checks** = dotted grey, **CI/CD** = solid dark.

## 1. Data sources

| Type | Sources | Notes |
|---|---|---|
| Live REST | API-Football, NHL API, MLB StatsAPI, balldontlie, OpenF1 | API-Football free tier ~100 calls/day |
| Live websocket | SportScore (free, websockets), OpenF1 live timing | |
| Reference | TheSportsDB (teams, players) | No live data on free plan |
| Historical | StatsBomb Open Data, Jolpica / FastF1, Cricsheet, nflverse, Kaggle | Files / bulk APIs |

**OpenF1:** live data only during sessions; none between sessions or in the off-season (Dec–Mar). Historical (2023+) is free; real-time may need a paid plan. A **replay simulator** feeds past sessions in time order to mimic a live stream — use it for testing the streaming path any time.

## 2. Ingestion
- **Live polling:** EventBridge Scheduler → Lambda pollers → Kinesis Data Streams. *(live)*
- **Websockets + OpenF1 replay:** ECS Fargate task → Kinesis Data Streams. *(live)*
- **Batch backfill:** Lambda or Glue job loads historical + reference data → S3 raw. *(batch)*
- **Secrets:** API keys in Secrets Manager, read by Lambda, Fargate and backfill.

## 3. Streaming
Kinesis Data Streams → Kinesis Data Firehose → S3 raw (JSON).

## 4. Storage
- **S3 raw zone:** JSON, partitioned by `source=<name>/date=<yyyy-mm-dd>/`. Append-only.
- **S3 clean zone:** Parquet, partitioned.
- **Glue Data Catalog:** table definitions for the clean zone.

## 5. Processing
Glue jobs convert raw JSON → Parquet in the clean zone and update the Catalog.

## 6. Warehouse
Amazon Athena (low cost, default) or Redshift Serverless.

## 7. Modelling (dbt)
dbt-athena (or dbt-redshift). Models: `fact_events`, `dim_team`, `dim_player`, `dim_session`.

## 8. Orchestration
Amazon MWAA (managed Airflow) or Step Functions for lower cost. Runs: backfill → Glue jobs → dbt build + tests. EventBridge Scheduler handles live polling.

## 9. Data quality
- dbt tests: `not_null`, `unique`, `relationships`, source freshness.
- Glue Data Quality rules on the clean zone.
- **Late or corrected events** *(suggested approach, confirm)*: keep the latest version per event id; reprocess the affected date partitions.

## 10. Monitoring
CloudWatch logs, metrics and alarms for Lambda, Fargate, Kinesis, Firehose, Glue and MWAA.

## 11. Outputs
QuickSight dashboards; notebooks for analysis.

## 12. Deployment (Terraform + GitHub CI/CD)

Flow: GitHub repo → GitHub Actions → OIDC → IAM role → Terraform → AWS dev → manual approval → AWS prod.

- **Terraform state:** S3 backend with state locking; separate state for dev and prod.
- **AWS access:** GitHub Actions uses OIDC to assume an IAM role (no stored AWS keys).
- **On pull request:** `terraform fmt` / `validate`, security scan (Checkov / tfsec), `terraform plan` posted to the PR, pytest for Lambda code, `dbt build` on dev.
- **On merge to main:** build Docker image → push to ECR, package Lambdas, `terraform apply` to dev, sync DAGs to S3, run dbt.
- **Promote to prod:** manual approval with GitHub Environments, then `terraform apply` to prod.
