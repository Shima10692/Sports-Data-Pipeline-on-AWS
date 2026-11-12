# State for this stack lives in the bucket it creates. The very first apply used
# local state; it was then migrated here with:
#
#   terraform init -migrate-state -backend-config="bucket=<state_bucket_name output>"
#
# The bucket name contains the AWS account ID, so it is passed at init time
# rather than committed to this public repo. Re-creating from scratch: comment
# this block out, apply with local state, then migrate again.

terraform {
  backend "s3" {
    key          = "bootstrap/terraform.tfstate"
    region       = "us-east-1" # must match var.aws_region
    encrypt      = true
    use_lockfile = true
  }
}
