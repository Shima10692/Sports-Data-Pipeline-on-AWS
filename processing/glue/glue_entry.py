"""AWS Glue script for the raw → clean job. Uploaded to S3 by Terraform.

The `clean_zone` package arrives through --extra-py-files. Job arguments
(defaults are set on the job; override per run):

  --raw_bucket --clean_bucket --database --region   set by Terraform
  --sources   all | comma list, e.g. statsbomb,jolpica
  --dates     all | comma list of yyyy-mm-dd raw date partitions to rebuild
"""

import sys

from awsglue.utils import getResolvedOptions

from clean_zone.job import main

ARGS = ["raw_bucket", "clean_bucket", "database", "region", "sources", "dates"]

main(getResolvedOptions(sys.argv, ARGS))
