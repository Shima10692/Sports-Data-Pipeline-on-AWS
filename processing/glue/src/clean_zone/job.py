"""The Glue job: raw JSON → clean Parquet → Glue Data Catalog.

For each clean table of the selected sources:
  1. list the raw keys of its kind (all dates, or only the dates asked for),
     keeping the newest version of each object;
  2. read and flatten them on the executors (pure-Python flatteners);
  3. write Parquet to s3://<clean>/<table>/dt=<date>/, replacing only the dt
     partitions being processed (dynamic partition overwrite);
  4. create/update the table and register those partitions in the catalog.

A dt partition is always rebuilt from *every* raw object of that date, so a
re-run gives the same result (idempotent) and reprocessing a date picks up
late or corrected raw objects.

Spark is imported only inside `run`, so the planning code is testable offline.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any

from .catalog import ensure_table, register_partitions, table_location
from .rawkeys import RawKey, latest_versions, parse_key
from .sources import SOURCES, TABLES, tables_for
from .table import PARTITION_COLUMN, Table

log = logging.getLogger("clean_zone")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_selection(sources: str, dates: str) -> tuple[list[str] | None, list[str] | None]:
    """'all' or comma lists → (sources, dates); None means everything."""

    def split(text: str) -> list[str] | None:
        items = [s.strip() for s in (text or "").split(",") if s.strip()]
        return None if not items or items == ["all"] else items

    src, days = split(sources), split(dates)
    if src is not None:
        tables_for(src)  # raises on an unknown source
    for d in days or []:
        if not _DATE_RE.match(d):
            raise ValueError(f"dates must be yyyy-mm-dd, got {d!r}")
    return src, (sorted(set(days)) if days else None)


def list_raw_keys(s3: Any, bucket: str, source: str, dates: list[str] | None) -> list[RawKey]:
    prefixes = [f"source={source}/"] if dates is None else [f"source={source}/date={d}/" for d in dates]
    keys: list[RawKey] = []
    paginator = s3.get_paginator("list_objects_v2")
    for prefix in prefixes:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents") or []:
                parsed = parse_key(obj["Key"])
                if parsed is not None:
                    keys.append(parsed)
    return keys


def plan(tables: Iterable[Table], keys: Iterable[RawKey]) -> dict[str, list[RawKey]]:
    """Raw objects to read for each table: newest version only, sorted."""
    newest = latest_versions(keys)
    return {t.name: [k for k in newest if t.matches(k)] for t in tables}


def flatten_keys(table_name: str, bucket: str, keys: Iterable[str], s3: Any) -> Iterator[tuple]:
    """Executor side: download raw objects and yield the table's rows."""
    table = TABLES[table_name]
    for key in keys:
        raw = parse_key(key)
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        yield from table.rows(json.loads(body), raw)


def run(spark: Any, s3: Any, glue: Any, *, raw_bucket: str, clean_bucket: str, database: str,
        region: str, sources: str = "all", dates: str = "all") -> list[dict]:  # fmt: skip
    selected_sources, selected_dates = parse_selection(sources, dates)
    tables = tables_for(selected_sources)

    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    spark.sparkContext._jsc.hadoopConfiguration().set("mapreduce.fileoutputcommitter.marksuccessfuljobs", "false")
    sc = spark.sparkContext

    by_source: dict[str, list[RawKey]] = defaultdict(list)
    for source in selected_sources or SOURCES:
        by_source[source] = list_raw_keys(s3, raw_bucket, source, selected_dates)

    summary = []
    for table in tables:
        work = plan([table], by_source[table.source])[table.name]
        action = ensure_table(glue, database, table, clean_bucket)
        result = {"table": table.name, "catalog": action, "raw_objects": len(work), "rows": 0, "partitions": 0}
        if work:
            name, bucket, key_list = table.name, raw_bucket, [k.key for k in work]

            def read_partition(it, name=name, bucket=bucket):
                import boto3

                return flatten_keys(name, bucket, it, boto3.client("s3", region_name=region))

            rdd = sc.parallelize(key_list, max(1, min(len(key_list), sc.defaultParallelism * 2)))
            df = spark.createDataFrame(rdd.mapPartitions(read_partition), schema=table.spark_ddl())
            df = df.repartition(PARTITION_COLUMN).cache()
            result["rows"] = df.count()
            df.write.mode("overwrite").partitionBy(PARTITION_COLUMN).parquet(table_location(clean_bucket, table))
            df.unpersist()

            dts = sorted({k.date for k in work})
            result["partitions"] = len(dts)
            result.update(register_partitions(glue, database, table, clean_bucket, dts))
        log.info(json.dumps(result))
        print(json.dumps(result))  # also lands in the Glue job's output log
        summary.append(result)
    return summary


def main(args: dict[str, str]) -> list[dict]:
    """Entry point used by the Glue script (glue_entry.py)."""
    import boto3
    from pyspark.sql import SparkSession

    logging.basicConfig(level=logging.INFO)
    spark = SparkSession.builder.getOrCreate()
    region = args["region"]
    return run(
        spark,
        boto3.client("s3", region_name=region),
        boto3.client("glue", region_name=region),
        raw_bucket=args["raw_bucket"],
        clean_bucket=args["clean_bucket"],
        database=args["database"],
        region=region,
        sources=args.get("sources", "all"),
        dates=args.get("dates", "all"),
    )
