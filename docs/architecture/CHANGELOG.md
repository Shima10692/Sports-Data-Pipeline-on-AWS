# Architecture changelog

Newest first. Snapshots live in `versions/<version>/`. Never edit a released entry; add a new one.

## v1.1.0 — 2026-11-12 — Processing engine switch (temporary Lambda stand-in)

**Type:** MINOR · **Status:** Temporary · **Phase:** 5 (Processing) · **ADR:** [ADR-0001](decisions/ADR-0001-processing-engine-switch.md)

- Raw → clean processing now has two interchangeable engines, chosen by one Terraform setting: `processing_engine = "lambda" | "glue"`.
- **Active:** AWS Lambda `sports-<env>-raw-to-clean` (Python 3.13, arm64, AWS SDK for pandas layer). Raw JSON → Parquet at `<table>/dt=<date>/`, registers tables and partitions in the Glue Data Catalog. Started on demand until phase 9.
- **Planned:** Glue 5.0 Spark job (FLEX, 2× G.1X), same inputs and outputs. Blocked by AWS ("Account is denied access"); support case open. IAM role, log group and code upload already deployed.
- Diagram: new "Planned, not deployed yet" line style; Glue Data Quality check arrow re-routed; build order phase 5 text updated.

Files: `versions/v1.1.0/` — both diagram PDFs, `architecture.md`, `VERSION.md`.

## v1.0.0 — 2026-11-12 — Initial architecture

**Type:** MAJOR · **Status:** Superseded by v1.1.0

- Full AWS pipeline: sources → Lambda / Fargate / backfill → Kinesis → S3 raw → Glue jobs → S3 clean + Catalog → Athena → dbt → QuickSight / notebooks.
- Orchestration (EventBridge, MWAA or Step Functions), data quality + monitoring, deployment lane (GitHub → Actions → OIDC → Terraform → dev → approval → prod).
- 12-phase build order.

Files: `versions/v1.0.0/` — both diagram PDFs, `VERSION.md`.
