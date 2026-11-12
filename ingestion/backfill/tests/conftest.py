"""Offline fakes: no network, no AWS."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest

from backfill.sources import Context
from backfill.storage import RawWriter


class FakeClientError(Exception):
    """Mimics botocore's ClientError shape (err.response['Error']['Code'])."""

    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self):
        self.objects: dict[str, dict[str, Any]] = {}
        self.puts = 0
        self.heads = 0

    def head_object(self, Bucket: str, Key: str):
        self.heads += 1
        if Key not in self.objects:
            raise FakeClientError("404")
        return {"ContentLength": len(self.objects[Key]["Body"])}

    def put_object(self, Bucket: str, Key: str, Body: bytes, IfNoneMatch: str | None = None, **kwargs):
        self.puts += 1
        if IfNoneMatch == "*" and Key in self.objects:
            raise FakeClientError("PreconditionFailed")
        self.objects[Key] = {"Body": Body, **kwargs}
        return {}

    def keys(self) -> list[str]:
        return sorted(self.objects)


class FakeHttp:
    """Serves canned responses by URL and records every request."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = responses or {}
        self.calls: list[str] = []
        self.requests_made = 0

    def add(self, url: str, payload: Any) -> None:
        self.responses[url] = payload

    def get_bytes(self, url: str) -> bytes:
        self.calls.append(url)
        self.requests_made += 1
        if url not in self.responses:
            raise AssertionError(f"unexpected request: {url}")
        payload = self.responses[url]
        return payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def get_json(self, url: str) -> Any:
        return json.loads(self.get_bytes(url))


TODAY = dt.date(2026, 11, 12)


@pytest.fixture
def s3() -> FakeS3:
    return FakeS3()


@pytest.fixture
def http() -> FakeHttp:
    return FakeHttp()


@pytest.fixture
def make_ctx(s3, http):
    def _make(should_stop=lambda: False, api_keys=None, dry_run=False):
        return Context(
            http=http,
            writer=RawWriter(s3, "raw-bucket", dry_run=dry_run),
            today=TODAY,
            should_stop=should_stop,
            api_keys=api_keys or {},
        )

    return _make
