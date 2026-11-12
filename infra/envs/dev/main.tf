# dev environment.
#
# Naming rule: every resource is named "${var.project}-dev-..." and every IAM role
# sets permissions_boundary to the "${var.project}-boundary-dev" policy from the
# bootstrap stack. The dev apply role cannot create anything outside that.

data "aws_caller_identity" "current" {}

# Phase 3: S3 raw + clean zones and the Glue Data Catalog database.
module "data_lake" {
  source = "../../modules/data_lake"

  project     = var.project
  environment = "dev"
  account_id  = data.aws_caller_identity.current.account_id
}

# Phase 4: batch backfill Lambda writing historical/reference data to the raw zone.
module "backfill" {
  source = "../../modules/backfill_lambda"

  project         = var.project
  environment     = "dev"
  account_id      = data.aws_caller_identity.current.account_id
  region          = var.aws_region
  raw_bucket_name = module.data_lake.raw_bucket_name
  raw_bucket_arn  = module.data_lake.raw_bucket_arn
  source_dir      = "${path.root}/../../../ingestion/backfill/src"
}
