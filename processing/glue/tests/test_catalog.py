import pytest

from clean_zone.catalog import ensure_table, partition_location, register_partitions, table_input
from clean_zone.sources import TABLES

DB = "sports_dev_lake"
CLEAN = "sports-dev-clean-123456789012"
EVENTS = TABLES["statsbomb_events"]


def test_table_input_is_partitioned_parquet():
    ti = table_input(EVENTS, CLEAN)
    sd = ti["StorageDescriptor"]
    assert ti["TableType"] == "EXTERNAL_TABLE" and ti["Parameters"]["classification"] == "parquet"
    assert ti["PartitionKeys"] == [{"Name": "dt", "Type": "string", "Comment": "Raw-zone date= partition"}]
    assert sd["Location"] == f"s3://{CLEAN}/statsbomb_events/"
    assert sd["SerdeInfo"]["SerializationLibrary"].endswith("ParquetHiveSerDe")
    names = [c["Name"] for c in sd["Columns"]]
    assert names[-1] == "_raw_key" and "dt" not in names
    assert {"Name": "related_events", "Type": "array<string>"} in sd["Columns"]


def test_partition_location():
    assert partition_location(CLEAN, EVENTS, "2022-11-20") == f"s3://{CLEAN}/statsbomb_events/dt=2022-11-20/"


def test_ensure_table_creates_then_updates(fake_glue):
    assert ensure_table(fake_glue, DB, EVENTS, CLEAN) == "created"
    assert ensure_table(fake_glue, DB, EVENTS, CLEAN) == "updated"
    assert fake_glue.calls == ["get_table", "create_table", "get_table", "update_table"]


def test_ensure_table_reraises_other_errors(fake_glue, client_error):
    def denied(**_):
        raise client_error("AccessDeniedException")

    fake_glue.get_table = denied
    with pytest.raises(Exception, match="AccessDenied"):
        ensure_table(fake_glue, DB, EVENTS, CLEAN)


def test_register_partitions_is_idempotent(fake_glue):
    ensure_table(fake_glue, DB, EVENTS, CLEAN)
    assert register_partitions(fake_glue, DB, EVENTS, CLEAN, ["2022-11-20", "2022-11-21"]) == {"created": 2, "updated": 0}
    # Re-run with one old and one new date: the old one is refreshed, not duplicated.
    assert register_partitions(fake_glue, DB, EVENTS, CLEAN, ["2022-11-21", "2022-11-22", "2022-11-22"]) == {
        "created": 1,
        "updated": 1,
    }
    parts = fake_glue.partitions[(DB, "statsbomb_events")]
    assert sorted(parts) == [("2022-11-20",), ("2022-11-21",), ("2022-11-22",)]
    assert parts[("2022-11-22",)]["StorageDescriptor"]["Location"].endswith("/dt=2022-11-22/")


def test_register_partitions_batches_of_100(fake_glue):
    ensure_table(fake_glue, DB, EVENTS, CLEAN)
    dates = [f"2024-{m:02d}-{d:02d}" for m in range(1, 9) for d in range(1, 29)]  # 224 dates
    assert register_partitions(fake_glue, DB, EVENTS, CLEAN, dates)["created"] == 224
    assert fake_glue.calls.count("batch_create_partition") == 3


def test_register_partitions_raises_on_real_errors(fake_glue):
    fake_glue.batch_create_partition = lambda **_: {
        "Errors": [{"PartitionValues": ["2024-01-01"], "ErrorDetail": {"ErrorCode": "InternalServiceException"}}]
    }
    with pytest.raises(RuntimeError, match="could not create"):
        register_partitions(fake_glue, DB, EVENTS, CLEAN, ["2024-01-01"])
