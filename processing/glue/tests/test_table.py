import ast
import re
from pathlib import Path

import pytest

from clean_zone.rawkeys import parse_key
from clean_zone.sources import SOURCES, TABLES, tables_for
from clean_zone.table import Column, Table

SRC = Path(__file__).resolve().parents[1] / "src" / "clean_zone"
IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


def test_every_source_has_tables():
    assert set(SOURCES) == {"statsbomb", "jolpica", "cricsheet", "thesportsdb"}
    assert all(tables_for([s]) for s in SOURCES)


@pytest.mark.parametrize("table", TABLES.values(), ids=lambda t: t.name)
def test_table_naming(table):
    # Athena/Glue table and column names: lowercase, digits, underscores.
    assert table.name.startswith(f"{table.source}_") and IDENT.match(table.name)
    assert all(IDENT.match(c.name) for c in table.columns)
    assert table.description


@pytest.mark.parametrize("table", TABLES.values(), ids=lambda t: t.name)
def test_spark_ddl_puts_partition_last(table):
    ddl = table.spark_ddl()
    assert ddl.endswith("`dt` string") and "`_raw_key` string" in ddl
    assert ddl.count("`") == 2 * (len(table.columns) + 2)


def test_tables_for_rejects_unknown_source():
    with pytest.raises(ValueError, match="unknown sources"):
        tables_for(["espn"])


def test_table_rejects_reserved_or_duplicate_columns():
    with pytest.raises(ValueError, match="added automatically"):
        Table("x_t", "x", "k", "d", (Column("dt", "string"),), lambda d, k: [])
    with pytest.raises(ValueError, match="duplicate"):
        Table("x_t", "x", "k", "d", (Column("a", "int"), Column("a", "int")), lambda d, k: [])
    with pytest.raises(ValueError):
        Table("x_t", "x", "k", "d", (Column("a", "integer"),), lambda d, k: [])


def test_rows_reject_unknown_columns_from_flattener():
    t = Table("x_t", "x", "k", "d", (Column("a", "int"),), lambda d, k: [{"a": 1, "typo": 2}])
    with pytest.raises(ValueError, match="unknown columns"):
        list(t.rows({}, parse_key("source=x/date=2024-01-01/k.json")))


def test_rows_error_points_at_the_raw_object():
    t = Table("x_t", "x", "k", "d", (Column("a", "int"),), lambda d, k: [{"a": "not a number"}])
    with pytest.raises(ValueError, match=r"x_t\.a \(row 0 of source=x/date=2024-01-01/k\.json\)"):
        list(t.rows({}, parse_key("source=x/date=2024-01-01/k.json")))


def test_package_runs_on_glue_python():
    """Glue 5.0 runs Python 3.11: no newer syntax in the shipped package."""
    for path in SRC.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))
