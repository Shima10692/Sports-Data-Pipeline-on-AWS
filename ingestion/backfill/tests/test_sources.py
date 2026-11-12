import io
import json
import zipfile

import pytest

from backfill.sources import cricsheet, jolpica, statsbomb, thesportsdb

SB = statsbomb.BASE_URL
JP = jolpica.BASE_URL


# ---------------------------------------------------------------- StatsBomb


def statsbomb_fixture(http, include_360_match=True):
    http.add(f"{SB}/competitions.json", [{"competition_id": 43, "season_id": 106}])
    matches = [
        {"match_id": 1, "match_date": "2022-11-20", "last_updated": "2024-09-28T20:46:38.893391"},
        {
            "match_id": 2,
            "match_date": "2022-12-18",
            "last_updated": "2023-01-01T10:00:00",
            "match_status_360": "available" if include_360_match else "unscheduled",
            "last_updated_360": "2023-02-02T11:00:00",
        },
    ]
    http.add(f"{SB}/matches/43/106.json", matches)
    for mid in (1, 2):
        http.add(f"{SB}/events/{mid}.json", [{"type": "Pass"}])
        http.add(f"{SB}/lineups/{mid}.json", [])
    http.add(f"{SB}/three-sixty/2.json", [])


def test_statsbomb_layout(http, s3, make_ctx):
    statsbomb_fixture(http)
    assert statsbomb.run(statsbomb.DEFAULTS, make_ctx()) is True
    assert s3.keys() == [
        "source=statsbomb/date=2022-11-20/events/match_id=1/updated=20240928T204638.json",
        "source=statsbomb/date=2022-11-20/lineups/match_id=1/updated=20240928T204638.json",
        "source=statsbomb/date=2022-12-18/events/match_id=2/updated=20230101T100000.json",
        "source=statsbomb/date=2022-12-18/lineups/match_id=2/updated=20230101T100000.json",
        "source=statsbomb/date=2022-12-18/three-sixty/match_id=2/updated=20230202T110000.json",
        "source=statsbomb/date=2026-11-12/competitions.json",
        "source=statsbomb/date=2026-11-12/matches/competition_id=43/season_id=106.json",
    ]


def test_statsbomb_rerun_only_refetches_match_list(http, s3, make_ctx):
    statsbomb_fixture(http)
    statsbomb.run(statsbomb.DEFAULTS, make_ctx())
    http.calls.clear()
    statsbomb.run(statsbomb.DEFAULTS, make_ctx())
    assert http.calls == [f"{SB}/matches/43/106.json"]


def test_statsbomb_corrected_match_lands_as_new_object(http, s3, make_ctx):
    statsbomb_fixture(http)
    statsbomb.run(statsbomb.DEFAULTS, make_ctx())
    matches = json.loads(http.get_bytes(f"{SB}/matches/43/106.json"))
    matches[0]["last_updated"] = "2025-05-05T05:05:05"
    http.add(f"{SB}/matches/43/106.json", matches)
    statsbomb.run(statsbomb.DEFAULTS, make_ctx())
    events_1 = [k for k in s3.keys() if "events/match_id=1/" in k]
    assert len(events_1) == 2  # old version kept, corrected version added


def test_statsbomb_skips_360_when_not_available_or_disabled(http, s3, make_ctx):
    statsbomb_fixture(http, include_360_match=False)
    statsbomb.run(statsbomb.DEFAULTS, make_ctx())
    assert not any("three-sixty" in k for k in s3.keys())

    s3.objects.clear()
    statsbomb_fixture(http, include_360_match=True)
    statsbomb.run({**statsbomb.DEFAULTS, "include_360": False}, make_ctx())
    assert not any("three-sixty" in k for k in s3.keys())


def test_statsbomb_stops_early_and_resumes(http, s3, make_ctx):
    statsbomb_fixture(http)
    budget = iter([False, False, True])
    assert statsbomb.run(statsbomb.DEFAULTS, make_ctx(should_stop=lambda: next(budget, True))) is False
    partial = len(s3.keys())
    assert statsbomb.run(statsbomb.DEFAULTS, make_ctx()) is True
    assert len(s3.keys()) == 7 > partial


# ---------------------------------------------------------------- Jolpica


def jolpica_fixture(http):
    races = [
        {"season": "2026", "round": "1", "date": "2026-03-08"},
        {"season": "2026", "round": "2", "date": "2026-03-22", "Sprint": {"date": "2026-03-21"}},
        {"season": "2026", "round": "3", "date": "2026-12-06"},  # after TODAY
    ]
    http.add(f"{JP}/2026/races.json?limit=100", {"MRData": {"RaceTable": {"Races": races}}})
    for rnd in (1, 2, 3):
        for ep in ("results", "qualifying", "sprint"):
            http.add(f"{JP}/2026/{rnd}/{ep}.json?limit=100", {"MRData": {}})


def test_jolpica_writes_completed_races_only(http, s3, make_ctx):
    jolpica_fixture(http)
    assert jolpica.run({"seasons": [2026], "endpoints": ["results", "qualifying"]}, make_ctx()) is True
    assert s3.keys() == [
        "source=jolpica/date=2026-03-08/qualifying/season=2026/round=01.json",
        "source=jolpica/date=2026-03-08/results/season=2026/round=01.json",
        "source=jolpica/date=2026-03-22/qualifying/season=2026/round=02.json",
        "source=jolpica/date=2026-03-22/results/season=2026/round=02.json",
        "source=jolpica/date=2026-11-12/races/season=2026.json",
    ]
    assert not any("/3/" in c for c in http.calls)


def test_jolpica_sprint_only_for_sprint_weekends(http, s3, make_ctx):
    jolpica_fixture(http)
    jolpica.run({"seasons": [2026], "endpoints": ["sprint"]}, make_ctx())
    assert [k for k in s3.keys() if "/sprint/" in k] == ["source=jolpica/date=2026-03-22/sprint/season=2026/round=02.json"]


def test_jolpica_rerun_costs_one_request_per_season(http, s3, make_ctx):
    jolpica_fixture(http)
    params = {"seasons": [2026], "endpoints": ["results", "qualifying"]}
    jolpica.run(params, make_ctx())
    http.calls.clear()
    jolpica.run(params, make_ctx())
    assert http.calls == [f"{JP}/2026/races.json?limit=100"]  # well inside 500 requests/hour


def test_jolpica_rejects_unknown_endpoint(make_ctx):
    with pytest.raises(ValueError, match="laps"):
        jolpica.run({"seasons": [2026], "endpoints": ["laps"]}, make_ctx())


# ---------------------------------------------------------------- Cricsheet


def cricsheet_zip(matches: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("README.txt", "cricsheet")
        for match_id, first_day in matches.items():
            zf.writestr(f"{match_id}.json", json.dumps({"info": {"dates": [first_day, "2099-01-01"]}, "innings": []}))
    return buf.getvalue()


def test_cricsheet_unpacks_matches_by_first_day(http, s3, make_ctx):
    http.add(f"{cricsheet.BASE_URL}/recently_added_7_json.zip", cricsheet_zip({"1001": "2026-11-01", "1002": "2026-11-03"}))
    assert cricsheet.run(cricsheet.DEFAULTS, make_ctx()) is True
    assert s3.keys() == [
        "source=cricsheet/date=2026-11-01/matches/match_id=1001.json",
        "source=cricsheet/date=2026-11-03/matches/match_id=1002.json",
    ]
    body = json.loads(s3.objects["source=cricsheet/date=2026-11-01/matches/match_id=1001.json"]["Body"])
    assert body["info"]["dates"][0] == "2026-11-01"  # stored exactly as received


def test_cricsheet_rerun_skips_existing_matches(http, s3, make_ctx):
    http.add(f"{cricsheet.BASE_URL}/recently_added_7_json.zip", cricsheet_zip({"1001": "2026-11-01"}))
    cricsheet.run(cricsheet.DEFAULTS, make_ctx())
    ctx = make_ctx()
    cricsheet.run(cricsheet.DEFAULTS, ctx)
    assert (ctx.writer.stats.written, ctx.writer.stats.skipped) == (0, 1)


@pytest.mark.parametrize("bad", ["../all", "All", "ipl.zip", "x y"])
def test_cricsheet_rejects_bad_dataset_names(bad, make_ctx):
    with pytest.raises(ValueError):
        cricsheet.run({"datasets": [bad]}, make_ctx())


# ---------------------------------------------------------------- TheSportsDB


def sportsdb_fixture(http, key="123"):
    base = thesportsdb.base_url(key)
    http.add(
        f"{base}/search_all_teams.php?l=English%20Premier%20League",
        {"teams": [{"idTeam": "133604", "strTeam": "Arsenal"}, {"idTeam": "133612", "strTeam": "Chelsea"}]},
    )
    http.add(f"{base}/lookup_all_players.php?id=133604", {"player": []})
    http.add(f"{base}/lookup_all_players.php?id=133612", {"player": []})


def test_thesportsdb_snapshots_teams_and_players(http, s3, make_ctx):
    sportsdb_fixture(http)
    assert thesportsdb.run(thesportsdb.DEFAULTS, make_ctx()) is True
    assert s3.keys() == [
        "source=thesportsdb/date=2026-11-12/players/team_id=133604.json",
        "source=thesportsdb/date=2026-11-12/players/team_id=133612.json",
        "source=thesportsdb/date=2026-11-12/teams/league=english-premier-league.json",
    ]


def test_thesportsdb_uses_secret_key_but_never_stores_it(http, s3, make_ctx):
    sportsdb_fixture(http, key="paid-secret-key")
    thesportsdb.run(thesportsdb.DEFAULTS, make_ctx(api_keys={"thesportsdb": "paid-secret-key"}))
    assert all("/json/paid-secret-key/" in c for c in http.calls)
    stored_urls = [o["Metadata"]["source-url"] for o in s3.objects.values()]
    assert stored_urls and not any("paid-secret-key" in u for u in stored_urls)


def test_thesportsdb_handles_league_with_no_teams(http, s3, make_ctx):
    http.add(f"{thesportsdb.base_url('123')}/search_all_teams.php?l=Nowhere", {"teams": None})
    assert thesportsdb.run({"leagues": ["Nowhere"]}, make_ctx()) is True
    assert s3.keys() == ["source=thesportsdb/date=2026-11-12/teams/league=nowhere.json"]


def test_slug():
    assert thesportsdb.slug("English Premier League") == "english-premier-league"
    assert thesportsdb.slug("  Ligue 1 (France) ") == "ligue-1-france"
