"""Lambda engine for raw JSON → clean Parquet → Glue Data Catalog.

STOPGAP: Glue job creation is blocked on the AWS account (support case open).
This engine does exactly what the Glue job does, using the same planning,
flatteners and catalog code, but in one Lambda process with pyarrow instead of
Spark. When Glue is restored, set `processing_engine = "glue"` and this goes
unused (see processing/glue/README.md).

Same semantics as the Glue job: every dt partition is rebuilt from all of its
raw objects (newest versions), so runs are idempotent. Lambda stops after 15
minutes, so the run checks the clock before each partition. If time is short it
stops cleanly and returns `resume`, the event that finishes the work.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .catalog import ensure_table, register_partitions
from .job import list_raw_keys, parse_selection, plan
from .parquet import to_arrow, write_partition
from .rawkeys import RawKey
from .sources import SOURCES, tables_for

log = logging.getLogger("clean_zone")
SAFETY_SECONDS = 120  # the largest partition (a StatsBomb match day) takes well under this
READ_THREADS = 8


def _read_docs(s3: Any, bucket: str, keys: list[RawKey]) -> list[tuple[RawKey, Any]]:
    def get(k: RawKey) -> tuple[RawKey, Any]:
        return k, json.loads(s3.get_object(Bucket=bucket, Key=k.key)["Body"].read())

    with ThreadPoolExecutor(max_workers=READ_THREADS) as pool:
        return list(pool.map(get, keys))


def run(s3: Any, glue: Any, *, raw_bucket: str, clean_bucket: str, database: str, sources: str = "all",
        dates: str = "all", seconds_left: Callable[[], float] | None = None,
        run_id: str | None = None) -> dict:  # fmt: skip
    selected_sources, selected_dates = parse_selection(sources, dates)
    tables = tables_for(selected_sources)
    run_id = run_id or uuid.uuid4().hex[:12]

    by_source = {s: list_raw_keys(s3, raw_bucket, s, selected_dates) for s in selected_sources or SOURCES}
    summary: list[dict] = []
    remaining: dict[str, set[str]] = defaultdict(set)  # source -> dates not done

    for table in tables:
        work = plan([table], by_source[table.source])[table.name]
        result = {"table": table.name, "catalog": ensure_table(glue, database, table, clean_bucket),
                  "raw_objects": len(work), "rows": 0, "partitions": 0}  # fmt: skip
        by_dt: dict[str, list[RawKey]] = defaultdict(list)
        for k in work:
            by_dt[k.date].append(k)

        written = []
        for dt in sorted(by_dt):
            if seconds_left is not None and seconds_left() < SAFETY_SECONDS:
                remaining[table.source].add(dt)
                continue
            rows = [row for key, doc in _read_docs(s3, raw_bucket, by_dt[dt]) for row in table.rows(doc, key)]
            write_partition(s3, clean_bucket, table, dt, to_arrow(table, rows), run_id)
            result["rows"] += len(rows)
            written.append(dt)

        result["partitions"] = len(written)
        if written:
            result.update(register_partitions(glue, database, table, clean_bucket, written))
        log.info(json.dumps(result))
        summary.append(result)

    out: dict[str, Any] = {"complete": not remaining, "run_id": run_id, "tables": summary}
    if remaining:
        out["resume"] = {
            "sources": ",".join(sorted(remaining)),
            "dates": ",".join(sorted(set().union(*remaining.values()))),
        }
    return out
