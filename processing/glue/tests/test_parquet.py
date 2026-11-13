"""Lambda engine: Arrow schema must match the catalog; partition writes replace old files."""

import datetime as dt
import io

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from clean_zone.catalog import table_input
from clean_zone.coltypes import parse_type
from clean_zone.parquet import arrow_schema, arrow_type, to_arrow, write_partition
from clean_zone.rawkeys import parse_key
from clean_zone.sources import TABLES
from clean_zone.table import Column, Table

CLEAN = "sports-dev-clean-123456789012"


@pytest.mark.parametrize(
    "hive,arrow",
    [
        ("bigint", pa.int64()),
        ("int", pa.int32()),
        ("date", pa.date32()),
        ("array<double>", pa.list_(pa.float64())),
        ("struct<a:boolean,b:string>", pa.struct([("a", pa.bool_()), ("b", pa.string())])),
    ],
)
def test_arrow_type(hive, arrow):
    assert arrow_type(parse_type(hive)) == arrow


@pytest.mark.parametrize("table", TABLES.values(), ids=lambda t: t.name)
def test_arrow_schema_matches_catalog_columns(table):
    """Same names in the same order as the Glue table, so Athena reads Lambda files."""
    catalog = [c["Name"] for c in table_input(table, CLEAN)["StorageDescriptor"]["Columns"]]
    assert arrow_schema(table).names == catalog


def _table():
    cols = (
        Column("n", "bigint"),
        Column("when", "timestamp"),
        Column("frame", "array<struct<keeper:boolean,x:double>>"),
    )
    return Table("x_t", "x", "k", "d", cols, lambda doc, key: doc)


def _rows(table, records, key="source=x/date=2024-01-01/k.json"):
    return list(table.rows(records, parse_key(key)))


def _read(s3, key):
    return pq.read_table(io.BytesIO(s3.objects[key]))


def test_rows_round_trip_through_parquet(fake_s3_factory):
    t = _table()
    rows = _rows(t, [{"n": "7", "when": "2024-01-01T10:00:00.123456Z", "frame": [{"keeper": True, "x": 1.5}]}, {}])
    s3 = fake_s3_factory()
    key = write_partition(s3, CLEAN, t, "2024-01-01", to_arrow(t, rows), "run1")

    assert key == "x_t/dt=2024-01-01/part-run1.snappy.parquet"
    out = _read(s3, key).to_pylist()
    assert out[0]["n"] == 7 and out[0]["frame"] == [{"keeper": True, "x": 1.5}]
    assert out[0]["when"] == dt.datetime(2024, 1, 1, 10, 0, 0, 123000)  # ms precision
    assert out[0]["_raw_key"] == "source=x/date=2024-01-01/k.json"
    assert out[1] == {"n": None, "when": None, "frame": None, "_raw_key": "source=x/date=2024-01-01/k.json"}
    assert "dt" not in _read(s3, key).column_names


def test_write_partition_replaces_only_that_partition(fake_s3_factory):
    t = _table()
    s3 = fake_s3_factory(
        {
            "x_t/dt=2024-01-01/part-old-a.snappy.parquet": b"old",
            "x_t/dt=2024-01-01/part-old-b.snappy.parquet": b"old",
            "x_t/dt=2024-01-02/part-old.snappy.parquet": b"keep",
        }
    )
    write_partition(s3, CLEAN, t, "2024-01-01", to_arrow(t, _rows(t, [{"n": 1}])), "new")
    assert sorted(s3.objects) == ["x_t/dt=2024-01-01/part-new.snappy.parquet", "x_t/dt=2024-01-02/part-old.snappy.parquet"]
    assert s3.puts == ["x_t/dt=2024-01-01/part-new.snappy.parquet"]  # upload before delete


def test_same_run_id_rewrite_keeps_the_file(fake_s3_factory):
    t = _table()
    s3 = fake_s3_factory()
    for _ in range(2):
        write_partition(s3, CLEAN, t, "2024-01-01", to_arrow(t, _rows(t, [{"n": 1}])), "same")
    assert list(s3.objects) == ["x_t/dt=2024-01-01/part-same.snappy.parquet"] and s3.deleted == []


def test_empty_partition_still_has_the_schema(fake_s3_factory):
    t = _table()
    s3 = fake_s3_factory()
    key = write_partition(s3, CLEAN, t, "2024-01-01", to_arrow(t, []), "r")
    assert _read(s3, key).num_rows == 0 and _read(s3, key).schema.names == ["n", "when", "frame", "_raw_key"]
