"""Each flattener against a small hand-made document shaped like the real API output."""

import datetime as dt
import json

import pytest

from clean_zone.rawkeys import parse_key
from clean_zone.sources import TABLES
from clean_zone.sources.jolpica import lap_ms


def rows(table_name: str, doc, key: str) -> list[dict]:
    """Rows as dicts (column -> value) for readable asserts."""
    table = TABLES[table_name]
    names = [c.name for c in table.all_columns] + ["dt"]
    raw = parse_key(key)
    assert raw is not None and table.matches(raw), f"{key} should feed {table_name}"
    return [dict(zip(names, r, strict=True)) for r in table.rows(doc, raw)]


# ------------------------------------------------------------------ statsbomb

SB_EVENTS_KEY = "source=statsbomb/date=2022-11-20/events/match_id=3857286/updated=20260503T160533.json"


def test_statsbomb_events():
    doc = [
        {
            "id": "e1", "index": 1, "period": 1, "timestamp": "00:00:00.000", "minute": 0, "second": 0,
            "type": {"id": 35, "name": "Starting XI"}, "possession": 1,
            "possession_team": {"id": 3566, "name": "Qatar"}, "play_pattern": {"id": 1, "name": "Regular Play"},
            "team": {"id": 3566, "name": "Qatar"}, "duration": 0.0,
            "tactics": {"formation": 352, "lineup": []},
        },
        {
            "id": "e2", "index": 431, "period": 1, "timestamp": "00:15:49.482", "minute": 15, "second": 49,
            "type": {"id": 16, "name": "Shot"}, "possession": 25,
            "possession_team": {"id": 3565, "name": "Ecuador"}, "play_pattern": {"id": 5, "name": "Other"},
            "team": {"id": 3565, "name": "Ecuador"}, "player": {"id": 28559, "name": "Enner Valencia"},
            "position": {"id": 22, "name": "Right Center Forward"}, "location": [108.1, 40.1],
            "duration": 0.594371, "under_pressure": True, "related_events": ["e9"],
            "shot": {"statsbomb_xg": 0.7835, "end_location": [120.0, 43.4, 0.2], "outcome": {"id": 97, "name": "Goal"}},
        },
    ]  # fmt: skip
    first, shot = rows("statsbomb_events", doc, SB_EVENTS_KEY)

    assert first["match_id"] == 3857286 and first["player_id"] is None and first["location_x"] is None
    assert json.loads(first["details"]) == {"tactics": {"formation": 352, "lineup": []}}
    assert first["related_events"] == [] and first["under_pressure"] is False

    assert shot["type_name"] == "Shot" and shot["player_name"] == "Enner Valencia"
    assert (shot["location_x"], shot["location_y"]) == (108.1, 40.1)
    assert (shot["end_location_x"], shot["end_location_y"]) == (120.0, 43.4)
    assert shot["outcome_name"] == "Goal" and shot["shot_xg"] == 0.7835
    assert shot["under_pressure"] is True and shot["related_events"] == ["e9"]
    assert shot["source_updated"] == "20260503T160533"
    assert shot["dt"] == "2022-11-20" and shot["_raw_key"] == SB_EVENTS_KEY


def test_statsbomb_lineups():
    doc = [
        {
            "team_id": 3565,
            "team_name": "Ecuador",
            "lineup": [
                {
                    "player_id": 1, "player_name": "A", "player_nickname": None, "jersey_number": 8,
                    "country": {"id": 65, "name": "Ecuador"}, "cards": [],
                    "positions": [{"position": "Goalkeeper", "start_reason": "Starting XI"}],
                },
                {"player_id": 2, "player_name": "B", "jersey_number": 22, "cards": [], "positions": []},
            ],
        },
        {"team_id": 3566, "team_name": "Qatar", "lineup": []},
    ]  # fmt: skip
    out = rows("statsbomb_lineups", doc, SB_EVENTS_KEY.replace("/events/", "/lineups/"))
    assert [(r["player_id"], r["started"]) for r in out] == [(1, True), (2, False)]
    assert out[0]["country_name"] == "Ecuador" and out[1]["country_name"] is None
    assert json.loads(out[0]["positions"])[0]["position"] == "Goalkeeper"
    assert out[1]["positions"] is None and out[1]["cards"] is None


def test_statsbomb_three_sixty():
    doc = [
        {
            "event_uuid": "e2",
            "visible_area": [1, 2.5, 3, 4],
            "freeze_frame": [{"teammate": True, "actor": False, "keeper": False, "location": [38.1, 37.6]}],
        }
    ]
    (r,) = rows("statsbomb_three_sixty", doc, SB_EVENTS_KEY.replace("/events/", "/three-sixty/"))
    assert r["event_id"] == "e2" and r["visible_area"] == [1.0, 2.5, 3.0, 4.0]
    assert r["freeze_frame"] == [(True, False, False, 38.1, 37.6)]


def test_statsbomb_matches_and_competitions():
    match = {
        "match_id": 3857276, "match_date": "2022-12-01", "kick_off": "15:00:00.000",
        "competition": {"competition_id": 43, "competition_name": "FIFA World Cup", "country_name": "International"},
        "season": {"season_id": 106, "season_name": "2022"},
        "home_team": {"home_team_id": 1833, "home_team_name": "Canada", "home_team_group": "F", "country": {"name": "Canada"}},
        "away_team": {"away_team_id": 788, "away_team_name": "Morocco", "away_team_group": None},
        "home_score": 1, "away_score": 2, "last_updated": "2026-05-04T01:46:04.664252", "match_week": 3,
        "competition_stage": {"id": 10, "name": "Group Stage"}, "stadium": {"id": 1000838, "name": "Al Thumama"},
    }  # fmt: skip
    (m,) = rows("statsbomb_matches", [match], "source=statsbomb/date=2026-11-12/matches/competition_id=43/season_id=106.json")
    assert m["match_date"] == dt.date(2022, 12, 1) and m["home_team_name"] == "Canada"
    assert m["away_team_group"] is None and m["referee_name"] is None
    assert m["last_updated"] == dt.datetime(2026, 5, 4, 1, 46, 4, 664252)
    assert m["dt"] == "2026-11-12"

    comp = {"competition_id": 43, "season_id": 106, "competition_name": "FIFA World Cup", "competition_youth": False,
            "match_updated": "2024-02-13T02:35:28.134882", "match_available_360": None}  # fmt: skip
    (c,) = rows("statsbomb_competitions", [comp], "source=statsbomb/date=2026-11-12/competitions.json")
    assert c["competition_id"] == 43 and c["competition_youth"] is False and c["match_available_360"] is None


# ------------------------------------------------------------------ jolpica

DRIVER = {
    "driverId": "max_verstappen", "code": "VER", "givenName": "Max", "familyName": "Verstappen",
    "nationality": "Dutch", "permanentNumber": "3",
}  # fmt: skip
CONSTRUCTOR = {"constructorId": "red_bull", "name": "Red Bull"}
RACE = {
    "season": "2024", "round": "1", "raceName": "Bahrain Grand Prix", "date": "2024-03-02", "time": "15:00:00Z",
    "Circuit": {"circuitId": "bahrain", "circuitName": "Bahrain International Circuit",
                "Location": {"lat": "26.0325", "long": "50.5106", "locality": "Sakhir", "country": "Bahrain"}},
}  # fmt: skip


def mrdata(races: list[dict]) -> dict:
    return {"MRData": {"RaceTable": {"season": "2024", "Races": races}}}


def test_jolpica_results():
    winner = {
        "number": "1", "position": "1", "positionText": "1", "points": "26", "Driver": DRIVER,
        "Constructor": CONSTRUCTOR, "grid": "1", "laps": "57", "status": "Finished",
        "Time": {"millis": "5504742", "time": "1:31:44.742"},
        "FastestLap": {"rank": "1", "lap": "39", "Time": {"time": "1:32.608"}, "AverageSpeed": {"units": "kph", "speed": "210.383"}},
    }  # fmt: skip
    retired = {"number": "2", "position": "20", "positionText": "R", "points": "0", "Driver": {"driverId": "x"},
               "Constructor": CONSTRUCTOR, "grid": "0", "laps": "3", "status": "Engine"}  # fmt: skip
    a, b = rows("jolpica_results", mrdata([{**RACE, "Results": [winner, retired]}]),
                "source=jolpica/date=2024-03-02/results/season=2024/round=01.json")  # fmt: skip
    assert (a["season"], a["round"], a["race_date"]) == (2024, 1, dt.date(2024, 3, 2))
    assert a["driver_code"] == "VER" and a["car_number"] == 1 and a["points"] == 26.0
    assert a["time_ms"] == 5504742 and a["fastest_lap_ms"] == 92608 and a["fastest_lap_avg_kph"] == 210.383
    assert b["position_text"] == "R" and b["time_ms"] is None and b["fastest_lap_rank"] is None


def test_jolpica_sprint_uses_sprint_list():
    row = {"number": "1", "position": "1", "positionText": "1", "points": "8", "Driver": DRIVER, "Constructor": CONSTRUCTOR}
    out = rows("jolpica_sprint_results", mrdata([{**RACE, "SprintResults": [row]}]),
               "source=jolpica/date=2024-05-05/sprint/season=2024/round=06.json")  # fmt: skip
    assert len(out) == 1 and out[0]["points"] == 8.0


def test_jolpica_qualifying():
    q = {"number": "10", "position": "20", "Driver": DRIVER, "Constructor": CONSTRUCTOR, "Q1": "1:30.948"}
    (r,) = rows("jolpica_qualifying", mrdata([{**RACE, "QualifyingResults": [q]}]),
                "source=jolpica/date=2024-03-02/qualifying/season=2024/round=01.json")  # fmt: skip
    assert r["q1_ms"] == 90948 and r["q2"] is None and r["q2_ms"] is None and r["position"] == 20


def test_jolpica_pitstops():
    stops = [{"driverId": "norris", "lap": "15", "stop": "1", "time": "15:30:01", "duration": "22.345"},
             {"driverId": "norris", "lap": "40", "stop": "2", "time": "16:10:00", "duration": "1:02.5"}]  # fmt: skip
    a, b = rows("jolpica_pitstops", mrdata([{**RACE, "PitStops": stops}]),
                "source=jolpica/date=2024-03-02/pitstops/season=2024/round=01.json")  # fmt: skip
    assert (a["lap"], a["stop"], a["duration_ms"]) == (15, 1, 22345)
    assert b["duration_ms"] == 62500


def test_jolpica_races():
    sprint_race = {**RACE, "round": "6", "Qualifying": {"date": "2024-05-04"}, "Sprint": {"date": "2024-05-04"}}
    a, b = rows("jolpica_races", mrdata([RACE, sprint_race]), "source=jolpica/date=2026-11-12/races/season=2024.json")
    assert a["has_sprint"] is False and a["sprint_date"] is None and a["latitude"] == 26.0325
    assert b["has_sprint"] is True and b["sprint_date"] == dt.date(2024, 5, 4)


def test_jolpica_empty_race_table():
    assert rows("jolpica_results", mrdata([]), "source=jolpica/date=2024-03-02/results/season=2024/round=01.json") == []


@pytest.mark.parametrize(
    "text,ms",
    [("1:29.179", 89179), ("22.345", 22345), ("1:02.5", 62500), ("59", 59000), ("", None), (None, None), ("DNF", None)],
)
def test_lap_ms(text, ms):
    assert lap_ms(text) == ms


# ------------------------------------------------------------------ cricsheet

CRICKET_KEY = "source=cricsheet/date=2014-03-16/matches/match_id=682899.json"
CRICKET = {
    "meta": {"data_version": "1.1.0", "revision": 2},
    "info": {
        "dates": ["2014-03-16", "2014-03-17"], "match_type": "T20", "gender": "male", "teams": ["Hong Kong", "Nepal"],
        "toss": {"winner": "Hong Kong", "decision": "field"}, "outcome": {"winner": "Nepal", "by": {"runs": 80}},
        "event": {"name": "World T20", "match_number": 2}, "officials": {"umpires": ["Aleem Dar", "RJ Tucker"]},
        "player_of_match": ["SP Gauchan"], "overs": 20, "venue": "Chittagong",
    },
    "innings": [
        {"team": "Nepal", "overs": [{"over": 0, "deliveries": [
            {"batter": "A", "bowler": "X", "non_striker": "B", "runs": {"batter": 4, "extras": 0, "total": 4}},
            {"batter": "A", "bowler": "X", "non_striker": "B", "runs": {"batter": 0, "extras": 1, "total": 1}, "extras": {"wides": 1}},
            {"batter": "A", "bowler": "X", "non_striker": "B", "runs": {"batter": 0, "extras": 0, "total": 0},
             "wickets": [{"player_out": "A", "kind": "bowled"}]},
        ]}]},
        {"team": "Hong Kong", "super_over": True, "overs": [{"over": 0, "deliveries": [
            {"batter": "C", "bowler": "Y", "non_striker": "D", "runs": {"batter": 1, "extras": 0, "total": 1}},
        ]}]},
    ],
}  # fmt: skip


def test_cricsheet_match_summary():
    (m,) = rows("cricsheet_matches", CRICKET, CRICKET_KEY)
    assert m["match_id"] == 682899 and m["revision"] == 2
    assert (m["start_date"], m["end_date"]) == (dt.date(2014, 3, 16), dt.date(2014, 3, 17))
    assert (m["team_1"], m["team_2"], m["winner"], m["win_by_runs"]) == ("Hong Kong", "Nepal", "Nepal", 80)
    assert m["win_by_wickets"] is None and m["win_by_innings"] is False and m["result"] is None
    assert m["umpires"] == ["Aleem Dar", "RJ Tucker"] and m["player_of_match"] == ["SP Gauchan"]


def test_cricsheet_no_result():
    doc = {**CRICKET, "info": {**CRICKET["info"], "outcome": {"result": "no result"}}}
    (m,) = rows("cricsheet_matches", doc, CRICKET_KEY)
    assert m["winner"] is None and m["result"] == "no result"


def test_cricsheet_deliveries():
    out = rows("cricsheet_deliveries", CRICKET, CRICKET_KEY)
    assert len(out) == 4
    four, wide, wicket, super_over = out
    assert (four["innings_number"], four["over_number"], four["ball_in_over"], four["runs_total"]) == (1, 0, 1, 4)
    assert wide["extras_wides"] == 1 and wide["extras_noballs"] is None and wide["ball_in_over"] == 2
    assert wicket["is_wicket"] is True and wicket["wicket_kinds"] == ["bowled"] and wicket["players_out"] == ["A"]
    assert four["is_wicket"] is False and four["wicket_kinds"] == []
    assert super_over["innings_number"] == 2 and super_over["super_over"] is True
    assert {r["start_date"] for r in out} == {dt.date(2014, 3, 16)}


# ------------------------------------------------------------------ thesportsdb


def test_thesportsdb_teams():
    doc = {"teams": [{"idTeam": "133604", "strTeam": "Arsenal", "intFormedYear": "1892", "idLeague": "4328",
                      "strStadium": "Emirates Stadium", "intStadiumCapacity": "60338", "strBadge": "https://x/b.png",
                      "strWebsite": ""}]}  # fmt: skip
    (t,) = rows("thesportsdb_teams", doc, "source=thesportsdb/date=2026-11-12/teams/league=english-premier-league.json")
    assert (t["team_id"], t["formed_year"], t["stadium_capacity"]) == (133604, 1892, 60338)
    assert t["league_slug"] == "english-premier-league" and t["badge_url"] == "https://x/b.png"
    assert t["website"] == ""


def test_thesportsdb_players():
    doc = {"player": [{"idPlayer": "34145937", "strPlayer": "Bukayo Saka", "dateBorn": "2001-09-05", "strNumber": "7"},
                      {"idPlayer": "1", "strPlayer": "Unknown", "dateBorn": "0000-00-00", "idTeam": "999"}]}  # fmt: skip
    a, b = rows("thesportsdb_players", doc, "source=thesportsdb/date=2026-11-12/players/team_id=133604.json")
    assert a["team_id"] == 133604 and a["birth_date"] == dt.date(2001, 9, 5) and a["shirt_number"] == "7"
    assert b["team_id"] == 999 and b["birth_date"] is None


def test_thesportsdb_team_without_players():
    assert rows("thesportsdb_players", {"player": None}, "source=thesportsdb/date=2026-11-12/players/team_id=1.json") == []
