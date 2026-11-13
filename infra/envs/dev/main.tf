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

# Phase 5: Glue job turning raw JSON into clean-zone Parquet + Glue Catalog tables.
module "processing" {
  source = "../../modules/glue_etl"

  project               = var.project
  environment           = "dev"
  account_id            = data.aws_caller_identity.current.account_id
  region                = var.aws_region
  raw_bucket_name       = module.data_lake.raw_bucket_name
  raw_bucket_arn        = module.data_lake.raw_bucket_arn
  clean_bucket_name     = module.data_lake.clean_bucket_name
  clean_bucket_arn      = module.data_lake.clean_bucket_arn
  artifacts_bucket_name = module.data_lake.artifacts_bucket_name
  artifacts_bucket_arn  = module.data_lake.artifacts_bucket_arn
  glue_database_name    = module.data_lake.glue_database_name
  source_dir            = "${path.root}/../../../processing/glue"

  create_job = var.processing_engine == "glue"
}

# STOPGAP while Glue job creation is blocked on the account: the same clean_zone
# code in a Lambda. Destroyed automatically when processing_engine = "glue".
module "processing_lambda" {
  source = "../../modules/clean_lambda"
  count  = var.processing_engine == "lambda" ? 1 : 0

  project            = var.project
  environment        = "dev"
  account_id         = data.aws_caller_identity.current.account_id
  region             = var.aws_region
  raw_bucket_name    = module.data_lake.raw_bucket_name
  raw_bucket_arn     = module.data_lake.raw_bucket_arn
  clean_bucket_name  = module.data_lake.clean_bucket_name
  clean_bucket_arn   = module.data_lake.clean_bucket_arn
  glue_database_name = module.data_lake.glue_database_name
  source_dir         = "${path.root}/../../../processing/glue"
}
