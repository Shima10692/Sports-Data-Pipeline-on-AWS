"""Parse raw-zone keys and pick the newest version of each object.

Raw keys look like

    source=<name>/date=<yyyy-mm-dd>/<kind>[/<attr>=<value>...].json
    source=statsbomb/date=2022-11-20/events/match_id=3857286/updated=20260503T160533.json
    source=statsbomb/date=2026-11-12/competitions.json

`kind` is the first path segment after the date (without ".json"). Every later
segment of the form name=value becomes an attribute.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_KEY_RE = re.compile(r"^source=(?P<source>[a-z0-9_]+)/date=(?P<date>\d{4}-\d{2}-\d{2})/(?P<rest>.+)\.json$")

# StatsBomb writes a corrected match as a new object with a later `updated=` stamp.
VERSION_ATTR = "updated"


@dataclass(frozen=True)
class RawKey:
    key: str
    source: str
    date: str
    kind: str
    attrs: dict[str, str] = field(default_factory=dict, hash=False, compare=False)

    @property
    def identity(self) -> tuple:
        """Everything that names the object except its version."""
        return (self.source, self.date, self.kind, tuple(sorted((k, v) for k, v in self.attrs.items() if k != VERSION_ATTR)))

    @property
    def version(self) -> str:
        # Stamps are yyyymmddThhmmss, so they sort as text. The backfill writes
        # "unknown" when the source had no timestamp; that ranks below any real stamp.
        value = self.attrs.get(VERSION_ATTR, "")
        return value if value[:1].isdigit() else ""


def parse_key(key: str) -> RawKey | None:
    """Return the parsed key, or None for anything that is not a raw JSON object."""
    m = _KEY_RE.match(key)
    if not m:
        return None
    parts = m.group("rest").split("/")
    attrs: dict[str, str] = {}
    for part in parts[1:]:
        name, sep, value = part.partition("=")
        if not sep or not name or not value:
            return None
        attrs[name] = value
    return RawKey(key=key, source=m.group("source"), date=m.group("date"), kind=parts[0], attrs=attrs)


def latest_versions(keys: Iterable[RawKey]) -> list[RawKey]:
    """Keep only the newest version of each object, sorted by key for stable runs."""
    best: dict[tuple, RawKey] = {}
    for k in keys:
        current = best.get(k.identity)
        if current is None or k.version > current.version:
            best[k.identity] = k
    return sorted(best.values(), key=lambda k: k.key)
