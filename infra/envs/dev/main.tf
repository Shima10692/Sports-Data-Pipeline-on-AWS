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
