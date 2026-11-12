import pytest

from clean_zone.rawkeys import latest_versions, parse_key


def test_parse_key_with_attrs():
    k = parse_key("source=statsbomb/date=2022-11-20/events/match_id=3857286/updated=20260503T160533.json")
    assert (k.source, k.date, k.kind) == ("statsbomb", "2022-11-20", "events")
    assert k.attrs == {"match_id": "3857286", "updated": "20260503T160533"}
    assert k.version == "20260503T160533"


def test_parse_top_level_file():
    k = parse_key("source=statsbomb/date=2026-11-12/competitions.json")
    assert k.kind == "competitions" and k.attrs == {}


@pytest.mark.parametrize(
    "key",
    [
        "source=statsbomb/date=2026-11-12/",  # folder marker
        "source=statsbomb/date=2026-11-12/events.txt",
        "source=Stats/date=2026-11-12/x.json",
        "source=statsbomb/date=20261112/x.json",
        "source=statsbomb/date=2026-11-12/events/oops.json",  # segment without name=value
        "other/thing.json",
    ],
)
def test_parse_rejects_non_raw_keys(key):
    assert parse_key(key) is None


def test_latest_version_wins_per_object():
    keys = [
        parse_key("source=statsbomb/date=2022-11-20/events/match_id=1/updated=20240101T000000.json"),
        parse_key("source=statsbomb/date=2022-11-20/events/match_id=1/updated=20250101T000000.json"),
        parse_key("source=statsbomb/date=2022-11-20/events/match_id=2/updated=20240101T000000.json"),
        # Same match, different kind: versioned separately.
        parse_key("source=statsbomb/date=2022-11-20/lineups/match_id=1/updated=20240101T000000.json"),
    ]
    kept = [k.key for k in latest_versions(keys)]
    assert kept == sorted(
        [
            "source=statsbomb/date=2022-11-20/events/match_id=1/updated=20250101T000000.json",
            "source=statsbomb/date=2022-11-20/events/match_id=2/updated=20240101T000000.json",
            "source=statsbomb/date=2022-11-20/lineups/match_id=1/updated=20240101T000000.json",
        ]
    )


def test_unknown_stamp_ranks_below_real_one():
    keys = [
        parse_key("source=statsbomb/date=2022-11-20/events/match_id=1/updated=unknown.json"),
        parse_key("source=statsbomb/date=2022-11-20/events/match_id=1/updated=20240101T000000.json"),
    ]
    assert [k.version for k in latest_versions(keys)] == ["20240101T000000"]


def test_unversioned_objects_are_all_kept():
    keys = [
        parse_key("source=jolpica/date=2024-03-02/results/season=2024/round=01.json"),
        parse_key("source=jolpica/date=2024-03-09/results/season=2024/round=02.json"),
    ]
    assert len(latest_versions(keys)) == 2
