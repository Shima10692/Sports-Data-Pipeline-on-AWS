"""Lambda engine end to end against fake S3 and Glue: raw JSON in, Parquet + catalog out."""

import io

import pyarrow.parquet as pq
import pytest

from clean_zone import lambda_handler as handler_module
from clean_zone.lambda_handler import lambda_handler
from clean_zone.lambda_job import run

RAW = "sports-dev-raw-123456789012"
CLEAN = "sports-dev-clean-123456789012"
DB = "sports_dev_lake"


def _races(season, rounds):
    return {
        "MRData": {
            "RaceTable": {
                "Races": [{"season": season, "round": str(r), "date": f"2024-03-0{r}", "raceName": f"GP {r}"} for r in rounds]
            }
        }
    }


@pytest.fixture
def raw(fake_s3_factory):
    return fake_s3_factory(
        {
            "source=jolpica/date=2026-11-10/races/season=2024.json": _races("2024", [1]),
            "source=jolpica/date=2026-11-12/races/season=2024.json": _races("2024", [1, 2]),
        }
    )


def _run(s3, glue, **kw):
    kw.setdefault("sources", "jolpica")
    return run(s3, glue, raw_bucket=RAW, clean_bucket=CLEAN, database=DB, run_id="r1", **kw)


def _rows(s3, prefix):
    keys = [k for k in s3.objects if k.startswith(prefix) and k.endswith(".parquet")]
    return [r for k in keys for r in pq.read_table(io.BytesIO(s3.objects[k])).to_pylist()]


def test_run_writes_partitions_and_registers_them(raw, fake_glue):
    out = _run(raw, fake_glue)
    assert out["complete"] and "resume" not in out
    races = next(t for t in out["tables"] if t["table"] == "jolpica_races")
    assert races == {"table": "jolpica_races", "catalog": "created", "raw_objects": 2, "rows": 3,
                     "partitions": 2, "created": 2, "updated": 0}  # fmt: skip
    assert len(_rows(raw, "jolpica_races/dt=2026-11-12/")) == 2
    assert sorted(fake_glue.partitions[(DB, "jolpica_races")]) == [("2026-11-10",), ("2026-11-12",)]
    # Every jolpica table is created in the catalog, even ones without raw data yet.
    assert {name for _, name in fake_glue.tables} == {t["table"] for t in out["tables"]}


def test_rerun_is_idempotent(raw, fake_glue):
    _run(raw, fake_glue)
    before = sorted(k for k in raw.objects if k.startswith("jolpica_races/"))
    again = run(raw, fake_glue, raw_bucket=RAW, clean_bucket=CLEAN, database=DB, sources="jolpica", run_id="r2")
    races = next(t for t in again["tables"] if t["table"] == "jolpica_races")
    assert races["catalog"] == "updated" and races["updated"] == 2 and races["created"] == 0
    after = sorted(k for k in raw.objects if k.startswith("jolpica_races/"))
    assert len(after) == len(before) and all("part-r2" in k for k in after)  # old run's files replaced
    assert len(_rows(raw, "jolpica_races/")) == 3


def test_dates_limit_the_rebuild(raw, fake_glue):
    out = _run(raw, fake_glue, dates="2026-11-12")
    races = next(t for t in out["tables"] if t["table"] == "jolpica_races")
    assert races["partitions"] == 1 and not any("dt=2026-11-10" in k for k in raw.objects)


def test_stops_before_timeout_and_returns_resume(raw, fake_glue):
    clock = iter([900, 30])  # enough time for the first partition, not the second
    out = _run(raw, fake_glue, seconds_left=lambda: next(clock, 0))
    assert out["complete"] is False
    assert out["resume"] == {"sources": "jolpica", "dates": "2026-11-12"}
    assert sorted(fake_glue.partitions[(DB, "jolpica_races")]) == [("2026-11-10",)]

    finished = _run(raw, fake_glue, **out["resume"])
    assert finished["complete"] and len(_rows(raw, "jolpica_races/")) == 3


def test_bad_raw_data_fails_loudly(fake_s3_factory, fake_glue):
    s3 = fake_s3_factory({"source=jolpica/date=2026-11-12/races/season=2024.json": _races("twenty", [1])})
    with pytest.raises(ValueError, match=r"jolpica_races\.season"):
        _run(s3, fake_glue)
    assert not any(k.endswith(".parquet") for k in s3.objects)


class _Context:
    def get_remaining_time_in_millis(self):
        return 900_000


def test_handler_reads_env_and_accepts_lists(raw, fake_glue, monkeypatch):
    monkeypatch.setenv("RAW_BUCKET", RAW)
    monkeypatch.setenv("CLEAN_BUCKET", CLEAN)
    monkeypatch.setenv("GLUE_DATABASE", DB)
    out = lambda_handler({"sources": ["jolpica"], "dates": ["2026-11-12"]}, _Context(), s3=raw, glue=fake_glue)
    assert out["complete"] and {t["table"] for t in out["tables"]} >= {"jolpica_races"}


@pytest.mark.parametrize("event", [["jolpica"], {"sources": 3}, {"sources": "espn"}])
def test_handler_rejects_bad_events(event, raw, fake_glue, monkeypatch):
    for name, value in (("RAW_BUCKET", RAW), ("CLEAN_BUCKET", CLEAN), ("GLUE_DATABASE", DB)):
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        handler_module.lambda_handler(event, None, s3=raw, glue=fake_glue)
