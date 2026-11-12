"""Run a backfill locally.

  python -m backfill --source jolpica --params '{"seasons": [2024]}' --bucket <raw bucket>
  python -m backfill --source statsbomb --dry-run          # fetches, writes nothing

Run from ingestion/backfill/src (or with it on PYTHONPATH). Uses your AWS CLI login.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .handler import run_source
from .sources import registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backfill", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--source", required=True, choices=sorted(registry()))
    parser.add_argument("--params", default="{}", help="JSON object merged over the source defaults")
    parser.add_argument("--bucket", help="raw zone bucket (required unless --dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="fetch but do not write to S3")
    args = parser.parse_args(argv)

    if not args.dry_run and not args.bucket:
        parser.error("--bucket is required unless --dry-run")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s3 = None
    if not args.dry_run:
        import boto3

        s3 = boto3.client("s3")
    summary = run_source(
        args.source, json.loads(args.params), s3_client=s3, bucket=args.bucket or "", dry_run=args.dry_run
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
