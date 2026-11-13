"""Lambda entry point for the raw → clean stopgap engine.

Event (all optional):
    {"sources": "all" | "statsbomb,jolpica" | ["statsbomb"],
     "dates":   "all" | "2022-11-20,2022-11-21" | ["2022-11-20"]}

Environment (set by Terraform): RAW_BUCKET, CLEAN_BUCKET, GLUE_DATABASE.
If the result has "complete": false, invoke again with its "resume" event.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .lambda_job import run

logging.getLogger().setLevel(logging.INFO)


def _as_text(value: Any) -> str:
    if value is None:
        return "all"
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    if isinstance(value, str):
        return value
    raise ValueError(f"expected a string or list, got {type(value).__name__}")


def lambda_handler(event: Any, context: Any, *, s3: Any = None, glue: Any = None) -> dict:
    event = event or {}
    if not isinstance(event, dict):
        raise ValueError("event must be a JSON object")
    if s3 is None or glue is None:
        import boto3

        s3 = s3 or boto3.client("s3")
        glue = glue or boto3.client("glue")
    seconds_left = (lambda: context.get_remaining_time_in_millis() / 1000) if context is not None else None
    return run(
        s3,
        glue,
        raw_bucket=os.environ["RAW_BUCKET"],
        clean_bucket=os.environ["CLEAN_BUCKET"],
        database=os.environ["GLUE_DATABASE"],
        sources=_as_text(event.get("sources")),
        dates=_as_text(event.get("dates")),
        seconds_left=seconds_left,
    )
