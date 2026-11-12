# The bootstrap stack creates the state bucket, so its first apply uses local state.
# After that first apply, uncomment this block and run:
#
#   terraform init -migrate-state -backend-config="bucket=<state_bucket_name output>"
#
# The bucket name contains the AWS account ID, so it is passed at init time
# rather than committed to this public repo.

# terraform {
#   backend "s3" {
#     key          = "bootstrap/terraform.tfstate"
#     region       = "us-east-1" # must match var.aws_region
#     encrypt      = true
#     use_lockfile = true
#   }
# }
