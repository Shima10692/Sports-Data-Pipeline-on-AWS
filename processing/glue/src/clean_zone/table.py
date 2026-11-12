"""A clean-zone table: its schema and how to build its rows from one raw object."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from .coltypes import Type, coerce, parse_type
from .rawkeys import RawKey

PARTITION_COLUMN = "dt"  # raw `date=` value; `date` itself is a reserved word in Athena
LINEAGE_COLUMN = "_raw_key"  # the raw object a row came from

Flatten = Callable[[Any, RawKey], Iterable[dict[str, Any]]]


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    comment: str = ""

    @property
    def parsed(self) -> Type:
        return parse_type(self.type)


@dataclass(frozen=True)
class Table:
    name: str
    source: str  # raw source=<name>
    kind: str  # raw kind: first segment after date=
    description: str
    columns: tuple[Column, ...]  # data columns; lineage + partition columns are added
    flatten: Flatten

    def __post_init__(self):
        names = [c.name for c in self.columns]
        if len(names) != len(set(names)):
            raise ValueError(f"{self.name}: duplicate column names")
        if {LINEAGE_COLUMN, PARTITION_COLUMN} & set(names):
            raise ValueError(f"{self.name}: {LINEAGE_COLUMN} and {PARTITION_COLUMN} are added automatically")
        for c in self.columns:
            c.parsed  # fail at import time on a typo in a type string

    @property
    def all_columns(self) -> tuple[Column, ...]:
        """Data columns + lineage. The partition column is separate (Glue keeps it apart)."""
        return (*self.columns, Column(LINEAGE_COLUMN, "string", "Raw-zone key this row was built from."))

    def spark_ddl(self) -> str:
        """Schema for spark.createDataFrame, partition column last."""
        cols = [*self.all_columns, Column(PARTITION_COLUMN, "string")]
        # Spark's DDL parser takes Hive type strings as-is (keeps struct field case).
        return ", ".join(f"`{c.name}` {c.parsed.ddl()}" for c in cols)

    def matches(self, key: RawKey) -> bool:
        return key.source == self.source and key.kind == self.kind

    def rows(self, doc: Any, key: RawKey) -> Iterator[tuple]:
        """Flatten one raw document into schema-ordered, type-checked tuples."""
        types = [(c.name, c.parsed) for c in self.columns]
        allowed = {c.name for c in self.columns}
        for i, record in enumerate(self.flatten(doc, key)):
            unknown = set(record) - allowed
            if unknown:
                raise ValueError(f"{self.name}: flattener produced unknown columns {sorted(unknown)}")
            values = [coerce(record.get(n), t, f"{self.name}.{n} (row {i} of {key.key})") for n, t in types]
            yield (*values, key.key, key.date)
