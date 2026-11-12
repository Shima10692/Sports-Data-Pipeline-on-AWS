# ADR-0001: Processing engine switch — Lambda stand-in while Glue is blocked

- **Date:** 2026-11-12
- **Status:** Accepted — Temporary
- **Architecture version:** v1.1.0
- **Phase:** 5 (Processing)

## Context
The design runs raw → clean processing as a Glue 5.0 Spark job. AWS has blocked Glue job creation on this account ("Account is denied access"), and a support case is open. The job's IAM role, log group and code upload in the artifacts bucket are already deployed. Only the job itself is missing. Phases 6+ need clean Parquet data to continue.

## Decision
Add one Terraform setting, `processing_engine = "lambda" | "glue"`, that chooses the engine.

- **Lambda (active now):** `sports-<env>-raw-to-clean`, Python 3.13, arm64, AWS SDK for pandas layer (pyarrow). Reads raw JSON from the raw bucket, writes Parquet to the clean bucket at `<table>/dt=<date>/`, registers tables and partitions in the Glue Data Catalog. Started on demand; the orchestrator starts it from phase 9.
- **Glue job (planned):** Glue 5.0, Spark, FLEX, 2× G.1X. Same inputs and outputs as the Lambda.

## Consequences
- Work on phases 6+ can continue now.
- Lambda limits (15 min, memory) cap the size of a single run. Large backfills may need to be split by date.
- Both engines must produce identical output, so downstream (Catalog, Athena, dbt) does not change.

## Exit plan
When AWS Support lifts the block: set `processing_engine = "glue"`, apply to dev, compare output with the Lambda run, then promote to prod. Record that as a new version (v1.2.0) and set this ADR to "Superseded".
