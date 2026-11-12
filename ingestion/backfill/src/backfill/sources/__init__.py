"""Source loaders. Each exposes run(params, ctx) -> bool (True when complete)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..http import RateLimitedClient
from ..storage import RawWriter


@dataclass
class Context:
    http: RateLimitedClient
    writer: RawWriter
    today: dt.date
    should_stop: Callable[[], bool] = lambda: False
    api_keys: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Source:
    name: str
    run: Callable[[dict[str, Any], Context], bool]
    min_interval: float  # seconds between requests, from the source's published limits
    defaults: dict[str, Any]


def registry() -> dict[str, Source]:
    from . import cricsheet, jolpica, statsbomb, thesportsdb

    return {
        s.name: s
        for s in (
            Source("statsbomb", statsbomb.run, statsbomb.MIN_INTERVAL, statsbomb.DEFAULTS),
            Source("jolpica", jolpica.run, jolpica.MIN_INTERVAL, jolpica.DEFAULTS),
            Source("cricsheet", cricsheet.run, cricsheet.MIN_INTERVAL, cricsheet.DEFAULTS),
            Source("thesportsdb", thesportsdb.run, thesportsdb.MIN_INTERVAL, thesportsdb.DEFAULTS),
        )
    }
