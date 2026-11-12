"""Append-only writer for the S3 raw zone.

Every object lives at  source=<name>/date=<yyyy-mm-dd>/<path>.json  and is
written at most once: existing keys are skipped before anything is fetched, and
the write itself is conditional (If-None-Match: *), so concurrent runs cannot
overwrite each other.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_SOURCE_RE = re.compile(r"^[a-z0-9_]+$")
_PATH_RE = re.compile(r"^[A-Za-z0-9_=./-]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NOT_FOUND = {"404", "NoSuchKey", "NotFound"}
_ALREADY_EXISTS = {"412", "PreconditionFailed", "ConditionalRequestConflict"}


def raw_key(source: str, date: dt.date | str, path: str) -> str:
    """Build a raw-zone key. `path` must be relative and safe (no '..', no spaces)."""
    if not _SOURCE_RE.match(source):
        raise ValueError(f"invalid source name: {source!r}")
    day = date if isinstance(date, str) else date.isoformat()
    # fromisoformat alone also accepts "20240101" (Python 3.11+); partitions must be yyyy-mm-dd.
    if not _DATE_RE.match(day):
        raise ValueError(f"date must be yyyy-mm-dd: {day!r}")
    dt.date.fromisoformat(day)  # rejects impossible dates such as 2024-13-01
    if not _PATH_RE.match(path) or path.startswith("/") or ".." in path.split("/"):
        raise ValueError(f"invalid object path: {path!r}")
    return f"source={source}/date={day}/{path}"


def _error_code(err: Exception) -> str | None:
    response = getattr(err, "response", None) or {}
    return str(response.get("Error", {}).get("Code")) if response else None


@dataclass
class RunStats:
    written: int = 0
    skipped: int = 0
    keys_written: list[str] = field(default_factory=list)


class RawWriter:
    def __init__(self, s3_client: Any, bucket: str, *, dry_run: bool = False):
        self.s3 = s3_client
        self.bucket = bucket
        self.dry_run = dry_run
        self.stats = RunStats()

    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as err:  # botocore ClientError, without importing botocore
            if _error_code(err) in _NOT_FOUND:
                return False
            raise

    def put(self, key: str, body: bytes, *, source_url: str, content_type: str = "application/json") -> bool:
        """Write `body` at `key` unless it already exists. Returns True if written."""
        if self.dry_run:
            self.stats.written += 1
            self.stats.keys_written.append(key)
            return True
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                IfNoneMatch="*",
                Metadata={"source-url": source_url[:1024]},
            )
        except Exception as err:
            if _error_code(err) in _ALREADY_EXISTS:
                self.stats.skipped += 1
                return False
            raise
        self.stats.written += 1
        self.stats.keys_written.append(key)
        return True

    def put_if_absent(
        self, key: str, fetch: Callable[[], bytes], *, source_url: str, content_type: str = "application/json"
    ) -> bool:
        """Fetch and write only when `key` is missing, so re-runs cost no API calls."""
        if not self.dry_run and self.exists(key):
            self.stats.skipped += 1
            return False
        return self.put(key, fetch(), source_url=source_url, content_type=content_type)
