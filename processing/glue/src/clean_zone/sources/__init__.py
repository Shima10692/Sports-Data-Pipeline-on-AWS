"""Registry of every clean-zone table, grouped by raw source."""

from __future__ import annotations

from ..table import Table
from . import cricsheet, jolpica, statsbomb, thesportsdb

_MODULES = (statsbomb, jolpica, cricsheet, thesportsdb)

TABLES: dict[str, Table] = {t.name: t for m in _MODULES for t in m.TABLES}
SOURCES: tuple[str, ...] = tuple(m.SOURCE for m in _MODULES)


def tables_for(sources: list[str] | None = None) -> list[Table]:
    """Tables built from the given raw sources (all sources when None)."""
    wanted = set(SOURCES if sources is None else sources)
    unknown = wanted - set(SOURCES)
    if unknown:
        raise ValueError(f"unknown sources {sorted(unknown)}; expected some of {list(SOURCES)}")
    return [t for t in TABLES.values() if t.source in wanted]
