"""Entry points: AWS Lambda (`lambda_handler`) and a shared `run_source`.

Lambda event:
  {"source": "jolpica", "params": {"seasons": [2023, 2024]}, "dry_run": false}

The run stops a minute before the Lambda timeout and returns complete=false;
invoke again with the same event to resume (finished keys are skipped).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from collections.abc import Callable
from typing import Any

from .http import RateLimitedClient
from .sources import Context, registry
from .storage import RawWriter

log = logging.getLogger("backfill")
log.setLevel(logging.INFO)

STOP_MARGIN_MS = 60_000


def run_source(
    source: str,
    params: dict[str, Any] | None,
    *,
    s3_client: Any,
    bucket: str,
    today: dt.date | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    http: RateLimitedClient | None = None,
    api_keys: dict[str, str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    sources = registry()
    if source not in sources:
        raise ValueError(f"unknown source {source!r}; expected one of {sorted(sources)}")
    spec = sources[source]
    merged = {**spec.defaults, **(params or {})}

    writer = RawWriter(s3_client, bucket, dry_run=dry_run)
    client = http or RateLimitedClient(spec.min_interval)
    ctx = Context(
        http=client,
        writer=writer,
        today=today or dt.datetime.now(dt.timezone.utc).date(),
        should_stop=should_stop,
        api_keys=api_keys or {},
    )
    complete = spec.run(merged, ctx)
    summary = {
        "source": source,
        "complete": complete,
        "written": writer.stats.written,
        "skipped": writer.stats.skipped,
        "requests": client.requests_made,
        "dry_run": dry_run,
    }
    log.info(json.dumps(summary))
    return summary


def _api_keys() -> dict[str, str]:
    """Paid API keys come only from Secrets Manager, never from code or the event."""
    keys: dict[str, str] = {}
    arn = os.environ.get("THESPORTSDB_API_KEY_SECRET_ARN")
    if arn:
        import boto3

        keys["thesportsdb"] = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
    return keys


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    import boto3

    def should_stop() -> bool:
        return context is not None and context.get_remaining_time_in_millis() < STOP_MARGIN_MS

    return run_source(
        event["source"],
        event.get("params"),
        s3_client=boto3.client("s3"),
        bucket=os.environ["RAW_BUCKET"],
        should_stop=should_stop,
        api_keys=_api_keys(),
        dry_run=bool(event.get("dry_run", False)),
    )
