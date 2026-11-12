"""TheSportsDB v1 reference data (teams, players) → clean tables.

The API returns every value as a string (or null), with field names prefixed by
type: idTeam, strTeam, intFormedYear. Some names changed over time, so a few
columns try more than one field.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..rawkeys import RawKey
from ..table import Column as C
from ..table import Table

SOURCE = "thesportsdb"


def _any(row: dict, *names: str) -> Any:
    for n in names:
        if row.get(n) not in (None, ""):
            return row[n]
    return None


def teams(doc: dict, key: RawKey) -> Iterator[dict]:
    for t in doc.get("teams") or []:
        yield {
            "team_id": t.get("idTeam"),
            "team_name": t.get("strTeam"),
            "team_short": t.get("strTeamShort"),
            "team_alternate": t.get("strTeamAlternate"),
            "formed_year": t.get("intFormedYear"),
            "sport": t.get("strSport"),
            "league_id": t.get("idLeague"),
            "league_name": t.get("strLeague"),
            "league_slug": key.attrs.get("league"),
            "stadium": _any(t, "strStadium", "strVenue"),
            "stadium_capacity": _any(t, "intStadiumCapacity"),
            "location": _any(t, "strLocation", "strStadiumLocation"),
            "country": t.get("strCountry"),
            "website": t.get("strWebsite"),
            "badge_url": _any(t, "strBadge", "strTeamBadge"),
        }


TEAMS = Table(
    name="thesportsdb_teams",
    source=SOURCE,
    kind="teams",
    description="TheSportsDB teams, one row per team per league. Daily snapshot (dt = download day).",
    columns=(
        C("team_id", "bigint", "TheSportsDB idTeam"),
        C("team_name", "string"),
        C("team_short", "string"),
        C("team_alternate", "string"),
        C("formed_year", "int"),
        C("sport", "string"),
        C("league_id", "bigint"),
        C("league_name", "string"),
        C("league_slug", "string", "League slug from the raw key"),
        C("stadium", "string"),
        C("stadium_capacity", "int"),
        C("location", "string"),
        C("country", "string"),
        C("website", "string"),
        C("badge_url", "string"),
    ),
    flatten=teams,
)


def players(doc: dict, key: RawKey) -> Iterator[dict]:
    for p in doc.get("player") or doc.get("players") or []:
        yield {
            "player_id": p.get("idPlayer"),
            "team_id": _any(p, "idTeam") or key.attrs.get("team_id"),
            "player_name": p.get("strPlayer"),
            "team_name": p.get("strTeam"),
            "nationality": p.get("strNationality"),
            "position": p.get("strPosition"),
            "birth_date": p.get("dateBorn"),
            "shirt_number": p.get("strNumber"),
            "height": p.get("strHeight"),
            "weight": p.get("strWeight"),
            "gender": p.get("strGender"),
            "sport": p.get("strSport"),
            "status": p.get("strStatus"),
        }


PLAYERS = Table(
    name="thesportsdb_players",
    source=SOURCE,
    kind="players",
    description="TheSportsDB players, one row per player per team. Daily snapshot (dt = download day).",
    columns=(
        C("player_id", "bigint", "TheSportsDB idPlayer"),
        C("team_id", "bigint"),
        C("player_name", "string"),
        C("team_name", "string"),
        C("nationality", "string"),
        C("position", "string"),
        C("birth_date", "date"),
        C("shirt_number", "string", "Free text in the source"),
        C("height", "string", "Free text, e.g. 1.85 m (6 ft 1 in)"),
        C("weight", "string"),
        C("gender", "string"),
        C("sport", "string"),
        C("status", "string"),
    ),
    flatten=players,
)

TABLES = (TEAMS, PLAYERS)
