"""Rate-limited HTTP client with retries, built on urllib."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from . import __version__

USER_AGENT = f"sports-data-pipeline-backfill/{__version__} (practice data engineering project)"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    def __init__(self, url: str, status: int | None, message: str):
        super().__init__(f"{status or 'network error'} fetching {url}: {message}")
        self.url = url
        self.status = status


class RateLimitedClient:
    """Spaces requests at least `min_interval` seconds apart and retries transient failures.

    `clock` and `sleep` are injectable so tests run instantly.
    """

    def __init__(
        self,
        min_interval: float,
        *,
        max_retries: int = 5,
        backoff_base: float = 2.0,
        timeout: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self._clock = clock
        self._sleep = sleep
        self._opener = opener
        self._last_request: float | None = None
        self.requests_made = 0

    def _wait_for_slot(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def get_bytes(self, url: str) -> bytes:
        attempt = 0
        while True:
            self._wait_for_slot()
            self.requests_made += 1
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as err:
                status, retry_after = err.code, _retry_after(err)
                if status not in RETRY_STATUSES or attempt >= self.max_retries:
                    raise HttpError(url, status, str(err.reason)) from err
            except (urllib.error.URLError, TimeoutError) as err:
                status, retry_after = None, None
                if attempt >= self.max_retries:
                    raise HttpError(url, None, str(err)) from err
            delay = retry_after if retry_after is not None else self.backoff_base * (2**attempt)
            self._sleep(delay)
            attempt += 1

    def get_json(self, url: str) -> Any:
        return json.loads(self.get_bytes(url))


def _retry_after(err: urllib.error.HTTPError) -> float | None:
    value = err.headers.get("Retry-After") if err.headers else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
