"""Arrow schemas and Parquet partition writes for the Lambda engine.

The Glue engine lets Spark do this. The Lambda engine (a stopgap while Glue job
creation is blocked on the account) writes the same layout itself:

    s3://<clean>/<table>/dt=<date>/part-<run id>.snappy.parquet

with the same column names, order and types as the Glue Catalog table, so
Athena cannot tell which engine wrote a partition.

pyarrow comes from the AWS SDK for pandas Lambda layer; only the Lambda engine
imports this module.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .coltypes import Type
from .table import PARTITION_COLUMN, Table

_PRIMITIVES = {
    "string": pa.string(),
    "bigint": pa.int64(),
    "int": pa.int32(),
    "double": pa.float64(),
    "boolean": pa.bool_(),
    "date": pa.date32(),
    "timestamp": pa.timestamp("us"),
}
DELETE_BATCH = 1000  # S3 DeleteObjects limit


def arrow_type(t: Type) -> pa.DataType:
    if t.kind == "array":
        return pa.list_(arrow_type(t.element))
    if t.kind == "struct":
        return pa.struct([pa.field(n, arrow_type(ft)) for n, ft in t.fields])
    return _PRIMITIVES[t.kind]


def arrow_schema(table: Table) -> pa.Schema:
    """Data columns + _raw_key, in catalog order. dt lives in the path, not the file."""
    return pa.schema([pa.field(c.name, arrow_type(c.parsed)) for c in table.all_columns])


def to_arrow(table: Table, rows: Iterable[tuple]) -> pa.Table:
    """Rows from Table.rows (values..., raw key, dt) → an Arrow table without dt."""
    schema = arrow_schema(table)
    width = len(schema)
    columns: list[list[Any]] = [[] for _ in range(width)]
    for row in rows:
        for i in range(width):
            columns[i].append(row[i])
    return pa.Table.from_arrays([pa.array(col, type=f.type) for col, f in zip(columns, schema)], schema=schema)


def partition_prefix(table: Table, dt: str) -> str:
    return f"{table.name}/{PARTITION_COLUMN}={dt}/"


def write_partition(s3: Any, clean_bucket: str, table: Table, dt: str, data: pa.Table, run_id: str) -> str:
    """Replace one dt partition: upload the new file first, then delete the old ones.

    A query never sees an empty partition (at worst, for the second between the
    two calls, both files). A rerun with the same data writes the same rows.
    """
    prefix = partition_prefix(table, dt)
    key = f"{prefix}part-{run_id}.snappy.parquet"

    buf = io.BytesIO()
    # Millisecond timestamps: the precision Athena reads everywhere.
    pq.write_table(data, buf, compression="snappy", coerce_timestamps="ms", allow_truncated_timestamps=True)
    s3.put_object(Bucket=clean_bucket, Key=key, Body=buf.getvalue())

    stale = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=clean_bucket, Prefix=prefix):
        stale += [o["Key"] for o in page.get("Contents") or [] if o["Key"] != key]
    for i in range(0, len(stale), DELETE_BATCH):
        resp = s3.delete_objects(
            Bucket=clean_bucket, Delete={"Objects": [{"Key": k} for k in stale[i : i + DELETE_BATCH]], "Quiet": True}
        )
        if resp.get("Errors"):
            raise RuntimeError(f"{table.name} dt={dt}: could not delete old files {resp['Errors'][:3]}")
    return key
