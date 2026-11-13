# Athena warehouse for one environment (phase 6):
#
#   <project>-<env>                    Athena workgroup (engine v3) used by dbt and ad-hoc queries.
#                                      Query results go to the artifacts bucket under tmp/athena/,
#                                      which expires (data_lake module lifecycle rule).
#   <project>_<env>_staging            Glue database for dbt staging views.
#   <project>_<env>_marts              Glue database for dbt mart tables (fact_events, dim_*).
#
# dbt writes mart table data to s3://<clean bucket>/dbt/... (see dbt/profiles.yml).
#
# The workgroup does NOT enforce its settings on clients. If it did, Athena would
# reject the CTAS external_location that dbt-athena sends and would put table data
# under the query results prefix instead, which expires after a few days.
# The per-query scan cutoff still applies to every query in the workgroup.

locals {
  env_prefix  = "${var.project}-${var.environment}"
  db_prefix   = replace(local.env_prefix, "-", "_")
  results_uri = "s3://${var.artifacts_bucket_name}/tmp/athena/${var.environment}/"

  databases = {
    staging = "dbt staging views over the ${var.environment} clean zone. Rebuilt by dbt; do not edit by hand."
    marts   = "dbt mart tables (facts and dimensions) for the ${var.environment} environment. Rebuilt by dbt."
  }
}

resource "aws_athena_workgroup" "this" {
  name        = local.env_prefix
  description = "Athena workgroup for the ${var.environment} sports pipeline (dbt and ad-hoc queries)."
  state       = "ENABLED"

  # Saved queries and history only; the data lives in S3 and the Glue Catalog.
  force_destroy = true

  configuration {
    #checkov:skip=CKV_AWS_82:Enforcing workgroup settings breaks dbt-athena CTAS (external_location is rejected and data lands in the expiring results prefix). See the comment at the top of this file.
    enforce_workgroup_configuration    = false
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.bytes_scanned_cutoff_per_query

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    result_configuration {
      output_location = local.results_uri

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  tags = { Environment = var.environment }
}

resource "aws_glue_catalog_database" "dbt" {
  for_each = local.databases

  name        = "${local.db_prefix}_${each.key}"
  description = each.value

  # Default location for tables created without an explicit one; dbt always sets one.
  location_uri = "s3://${var.clean_bucket_name}/dbt/${local.db_prefix}_${each.key}/"

  tags = { Environment = var.environment }
}
