"""Hive/Spark column types and value coercion.

Every clean-zone table has an explicit schema written as Hive DDL type strings
("bigint", "array<double>", "struct<a:boolean,b:string>"). The same strings are
used for the Glue Catalog columns and for Spark's schema, so the two can never
drift apart.

`coerce` turns raw JSON values (sources often send numbers as strings) into the
Python value Spark expects for a type, and fails loudly on anything it cannot
convert. Bad data stops the job instead of landing as silent nulls.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any

PRIMITIVES = {"string", "bigint", "int", "double", "boolean", "date", "timestamp"}


@dataclass(frozen=True)
class Type:
    kind: str  # a primitive name, "array" or "struct"
    element: Type | None = None  # array element type
    fields: tuple[tuple[str, Type], ...] = ()  # struct fields, in order

    def ddl(self) -> str:
        if self.kind == "array":
            return f"array<{self.element.ddl()}>"
        if self.kind == "struct":
            return "struct<" + ",".join(f"{n}:{t.ddl()}" for n, t in self.fields) + ">"
        return self.kind


def parse_type(text: str) -> Type:
    """Parse a Hive type string. Raises ValueError on anything unsupported."""
    t, rest = _parse(text.replace(" ", "").lower())
    if rest:
        raise ValueError(f"trailing text in type {text!r}: {rest!r}")
    return t


def _parse(s: str) -> tuple[Type, str]:
    if s.startswith("array<"):
        element, rest = _parse(s[len("array<") :])
        if not rest.startswith(">"):
            raise ValueError(f"expected '>' in array type near {rest!r}")
        return Type("array", element=element), rest[1:]
    if s.startswith("struct<"):
        rest = s[len("struct<") :]
        fields: list[tuple[str, Type]] = []
        while True:
            name, sep, rest = rest.partition(":")
            if not sep or not name.replace("_", "").isalnum():
                raise ValueError(f"bad struct field near {name!r}")
            ftype, rest = _parse(rest)
            fields.append((name, ftype))
            if rest.startswith(","):
                rest = rest[1:]
                continue
            if rest.startswith(">"):
                return Type("struct", fields=tuple(fields)), rest[1:]
            raise ValueError(f"expected ',' or '>' in struct type near {rest!r}")
    for prim in sorted(PRIMITIVES, key=len, reverse=True):
        if s.startswith(prim):
            return Type(prim), s[len(prim) :]
    raise ValueError(f"unsupported type near {s!r}")


_TRUE = {"true", "1", "yes"}
_FALSE = {"false", "0", "no"}
INT_RANGE = {"int": 2**31, "bigint": 2**63}


def coerce(value: Any, t: Type, where: str = "value") -> Any:
    """Convert `value` to the Python object Spark expects for `t`. None stays None.

    Every failure is a ValueError that names `where` (table.column and raw key).
    """
    try:
        return _coerce(value, t, where)
    except ValueError as err:
        if str(err).startswith(where):
            raise
        raise ValueError(f"{where}: cannot convert {value!r} to {t.ddl()} ({err})") from err


def _coerce(value: Any, t: Type, where: str) -> Any:
    if value is None or (isinstance(value, str) and value.strip() == "" and t.kind != "string"):
        return None

    if t.kind == "string":
        if isinstance(value, (dict, list)):
            raise ValueError(f"{where}: expected a scalar for string, got {type(value).__name__}")
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    if t.kind in ("int", "bigint"):
        if isinstance(value, bool):
            raise ValueError(f"{where}: boolean is not an integer")
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError(f"{where}: {value!r} is not a whole number")
            value = int(value)
        elif isinstance(value, str):
            value = int(value.strip())
        elif not isinstance(value, int):
            raise ValueError(f"{where}: cannot convert {type(value).__name__} to {t.kind}")
        if not -INT_RANGE[t.kind] <= value < INT_RANGE[t.kind]:
            raise ValueError(f"{where}: {value} out of range for {t.kind}")
        return value

    if t.kind == "double":
        if isinstance(value, bool):
            raise ValueError(f"{where}: boolean is not a number")
        if isinstance(value, (int, float)):
            out = float(value)
        elif isinstance(value, str):
            out = float(value.strip())
        else:
            raise ValueError(f"{where}: cannot convert {type(value).__name__} to double")
        if math.isnan(out) or math.isinf(out):
            raise ValueError(f"{where}: {value!r} is not a finite number")
        return out

    if t.kind == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in _TRUE | _FALSE:
            return value.strip().lower() in _TRUE
        raise ValueError(f"{where}: cannot convert {value!r} to boolean")

    if t.kind == "date":
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        text = str(value).strip()
        if text.startswith("0000-00-00"):
            return None  # TheSportsDB's "unknown date"
        return dt.date.fromisoformat(text[:10])

    if t.kind == "timestamp":
        if isinstance(value, dt.datetime):
            return value
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(text)
        # Parquet timestamps carry no zone; store everything as naive UTC.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return parsed

    if t.kind == "array":
        if not isinstance(value, list):
            raise ValueError(f"{where}: expected a list, got {type(value).__name__}")
        return [coerce(v, t.element, f"{where}[{i}]") for i, v in enumerate(value)]

    if t.kind == "struct":
        if not isinstance(value, dict):
            raise ValueError(f"{where}: expected an object, got {type(value).__name__}")
        unknown = set(value) - {n for n, _ in t.fields}
        if unknown:
            raise ValueError(f"{where}: unexpected struct fields {sorted(unknown)}")
        # Spark accepts structs as tuples in field order.
        return tuple(coerce(value.get(n), ft, f"{where}.{n}") for n, ft in t.fields)

    raise ValueError(f"{where}: unsupported type {t.kind}")
