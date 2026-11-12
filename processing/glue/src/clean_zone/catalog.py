"""Glue Data Catalog registration: one external Parquet table per clean table,
partitioned by `dt`, plus its partitions.

The job writes the Parquet files itself and then registers exactly the
partitions it wrote, so no crawler (and no crawler cost or schema guessing) is
needed. Every call is idempotent.
"""

from __future__ import annotations

import copy
from typing import Any

from .table import PARTITION_COLUMN, Table

PARQUET_SD = {
    "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
    "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
    "SerdeInfo": {
        "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
        "Parameters": {"serialization.format": "1"},
    },
}
BATCH_SIZE = 100  # Glue's limit for BatchCreatePartition / BatchUpdatePartition


def table_location(clean_bucket: str, table: Table) -> str:
    return f"s3://{clean_bucket}/{table.name}/"


def partition_location(clean_bucket: str, table: Table, dt: str) -> str:
    return f"{table_location(clean_bucket, table)}{PARTITION_COLUMN}={dt}/"


def _storage(columns: list[dict], location: str) -> dict:
    return {**copy.deepcopy(PARQUET_SD), "Columns": columns, "Location": location}


def _columns(table: Table) -> list[dict]:
    out = []
    for c in table.all_columns:
        col = {"Name": c.name, "Type": c.parsed.ddl()}
        if c.comment:
            col["Comment"] = c.comment[:255]
        out.append(col)
    return out


def table_input(table: Table, clean_bucket: str) -> dict:
    return {
        "Name": table.name,
        "Description": table.description[:2048],
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "classification": "parquet",
            "EXTERNAL": "TRUE",
            "parquet.compression": "SNAPPY",
            "source": table.source,
        },
        "PartitionKeys": [{"Name": PARTITION_COLUMN, "Type": "string", "Comment": "Raw-zone date= partition"}],
        "StorageDescriptor": _storage(_columns(table), table_location(clean_bucket, table)),
    }


def partition_input(table: Table, clean_bucket: str, dt: str) -> dict:
    return {
        "Values": [dt],
        "StorageDescriptor": _storage(_columns(table), partition_location(clean_bucket, table, dt)),
    }


def _code(err: Exception) -> str:
    return str((getattr(err, "response", None) or {}).get("Error", {}).get("Code", ""))


def ensure_table(glue: Any, database: str, table: Table, clean_bucket: str) -> str:
    """Create the table, or update it so the catalog always matches the code. Returns the action taken."""
    ti = table_input(table, clean_bucket)
    try:
        glue.get_table(DatabaseName=database, Name=table.name)
    except Exception as err:  # botocore ClientError, without importing botocore
        if _code(err) != "EntityNotFoundException":
            raise
        glue.create_table(DatabaseName=database, TableInput=ti)
        return "created"
    glue.update_table(DatabaseName=database, TableInput=ti)
    return "updated"


def register_partitions(glue: Any, database: str, table: Table, clean_bucket: str, dts: list[str]) -> dict:
    """Add the partitions; ones that already exist are updated to the current schema."""
    created = updated = 0
    dts = sorted(set(dts))
    for i in range(0, len(dts), BATCH_SIZE):
        chunk = dts[i : i + BATCH_SIZE]
        inputs = {d: partition_input(table, clean_bucket, d) for d in chunk}
        resp = glue.batch_create_partition(
            DatabaseName=database, TableName=table.name, PartitionInputList=list(inputs.values())
        )
        existing, failed = [], []
        for e in resp.get("Errors") or []:
            values = e.get("PartitionValues") or []
            code = (e.get("ErrorDetail") or {}).get("ErrorCode", "")
            (existing if code == "AlreadyExistsException" else failed).append((values, code))
        if failed:
            raise RuntimeError(f"{table.name}: could not create partitions {failed}")
        created += len(chunk) - len(existing)

        if existing:
            entries = [
                {"PartitionValueList": values, "PartitionInput": inputs[values[0]]} for values, _ in existing
            ]
            resp = glue.batch_update_partition(DatabaseName=database, TableName=table.name, Entries=entries)
            if resp.get("Errors"):
                raise RuntimeError(f"{table.name}: could not update partitions {resp['Errors']}")
            updated += len(existing)
    return {"created": created, "updated": updated}
