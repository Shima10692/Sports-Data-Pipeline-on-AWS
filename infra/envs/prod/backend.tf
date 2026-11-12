# Partial S3 backend config: the bucket name (which contains the AWS account ID)
# and region are supplied at init time, e.g.
#
#   terraform init -backend-config="bucket=$TF_STATE_BUCKET" -backend-config="region=$AWS_REGION"
#
# Locking uses an S3 lock file next to the state (no DynamoDB table).
terraform {
  backend "s3" {
    key          = "prod/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}
