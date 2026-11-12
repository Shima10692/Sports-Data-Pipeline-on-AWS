"""Job planning and executor-side reading. Spark itself is exercised by the dev run."""

import pytest

from clean_zone.job import flatten_keys, list_raw_keys, parse_selection, plan
from clean_zone.rawkeys import parse_key
from clean_zone.sources import TABLES, tables_for

RAW = "sports-dev-raw-123456789012"


@pytest.mark.parametrize(
    "sources,dates,expected",
    [
        ("all", "all", (None, None)),
        ("", "", (None, None)),
        ("statsbomb, jolpica", "all", (["statsbomb", "jolpica"], None)),
        ("all", "2024-03-09,2024-03-02,2024-03-02", (None, ["2024-03-02", "2024-03-09"])),
    ],
)
def test_parse_selection(sources, dates, expected):
    assert parse_selection(sources, dates) == expected


@pytest.mark.parametrize("sources,dates", [("espn", "all"), ("all", "2024/03/02"), ("all", "yesterday")])
def test_parse_selection_rejects_bad_input(sources, dates):
    with pytest.raises(ValueError):
        parse_selection(sources, dates)


def test_list_raw_keys_pages_and_filters(fake_s3_factory):
    s3 = fake_s3_factory(
        {
            "source=jolpica/date=2024-03-02/results/season=2024/round=01.json": {},
            "source=jolpica/date=2024-03-02/qualifying/season=2024/round=01.json": {},
            "source=jolpica/date=2024-03-09/results/season=2024/round=02.json": {},
            "source=jolpica/date=2024-03-09/notes.txt": b"ignored",
            "source=statsbomb/date=2024-03-02/competitions.json": {},
        }
    )
    keys = list_raw_keys(s3, RAW, "jolpica", None)
    assert len(keys) == 3 and {k.source for k in keys} == {"jolpica"}
    assert s3.prefixes == ["source=jolpica/"]

    only = list_raw_keys(s3, RAW, "jolpica", ["2024-03-09", "2024-04-01"])
    assert [k.date for k in only] == ["2024-03-09"]
    assert s3.prefixes[-2:] == ["source=jolpica/date=2024-03-09/", "source=jolpica/date=2024-04-01/"]


def test_plan_routes_kinds_and_keeps_newest():
    keys = [
        parse_key("source=statsbomb/date=2022-11-20/events/match_id=1/updated=20240101T000000.json"),
        parse_key("source=statsbomb/date=2022-11-20/events/match_id=1/updated=20250101T000000.json"),
        parse_key("source=statsbomb/date=2022-11-20/lineups/match_id=1/updated=20240101T000000.json"),
        parse_key("source=statsbomb/date=2026-11-12/competitions.json"),
    ]
    work = plan(tables_for(["statsbomb"]), keys)
    assert [k.version for k in work["statsbomb_events"]] == ["20250101T000000"]
    assert len(work["statsbomb_lineups"]) == 1 and len(work["statsbomb_competitions"]) == 1
    assert work["statsbomb_three_sixty"] == [] and work["statsbomb_matches"] == []


def test_one_cricsheet_file_feeds_two_tables():
    key = parse_key("source=cricsheet/date=2014-03-16/matches/match_id=1.json")
    work = plan(tables_for(["cricsheet"]), [key])
    assert work == {"cricsheet_matches": [key], "cricsheet_deliveries": [key]}


def test_flatten_keys_reads_each_object(fake_s3_factory):
    key = "source=jolpica/date=2026-11-12/races/season=2024.json"
    doc = {"MRData": {"RaceTable": {"Races": [{"season": "2024", "round": "1", "date": "2024-03-02"}]}}}
    s3 = fake_s3_factory({key: doc})
    out = list(flatten_keys("jolpica_races", RAW, [key], s3))
    assert s3.gets == [key]
    assert len(out) == 1 and out[0][-2:] == (key, "2026-11-12")
    assert len(out[0]) == len(TABLES["jolpica_races"].all_columns) + 1
