"""Batch backfill of historical and reference sports data into the S3 raw zone.

Standard library only (plus boto3, which the Lambda runtime provides), so the
Lambda needs no build step.
"""

__version__ = "0.1.0"
