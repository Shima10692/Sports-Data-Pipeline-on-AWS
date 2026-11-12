"""StatsBomb Open Data → clean tables. Data credit: StatsBomb."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from ..rawkeys import RawKey
from ..table import Column as C
from ..table import Table

SOURCE = "statsbomb"


def _get(obj: Any, *path: str) -> Any:
    for p in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(p)
    return obj


def _xy(point: Any, i: int) -> Any:
    return point[i] if isinstance(point, list) and len(point) > i else None


def _json(value: Any) -> str | None:
    return None if value in (None, [], {}) else json.dumps(value, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------ competitions


def competitions(doc: list[dict], key: RawKey) -> Iterator[dict]:
    for c in doc:
        yield {
            "competition_id": c.get("competition_id"),
            "season_id": c.get("season_id"),
            "competition_name": c.get("competition_name"),
            "country_name": c.get("country_name"),
            "competition_gender": c.get("competition_gender"),
            "competition_youth": c.get("competition_youth"),
            "competition_international": c.get("competition_international"),
            "season_name": c.get("season_name"),
            "match_updated": c.get("match_updated"),
            "match_available": c.get("match_available"),
            "match_updated_360": c.get("match_updated_360"),
            "match_available_360": c.get("match_available_360"),
        }


COMPETITIONS = Table(
    name="statsbomb_competitions",
    source=SOURCE,
    kind="competitions",
    description="StatsBomb competition/season catalogue, one row per competition season. Daily snapshot (dt = download day).",
    columns=(
        C("competition_id", "bigint"),
        C("season_id", "bigint"),
        C("competition_name", "string"),
        C("country_name", "string"),
        C("competition_gender", "string"),
        C("competition_youth", "boolean"),
        C("competition_international", "boolean"),
        C("season_name", "string"),
        C("match_updated", "timestamp"),
        C("match_available", "timestamp"),
        C("match_updated_360", "timestamp"),
        C("match_available_360", "timestamp"),
    ),
    flatten=competitions,
)

# ------------------------------------------------------------------ matches


def matches(doc: list[dict], key: RawKey) -> Iterator[dict]:
    for m in doc:
        yield {
            "match_id": m.get("match_id"),
            "match_date": m.get("match_date"),
            "kick_off": m.get("kick_off"),
            "competition_id": _get(m, "competition", "competition_id"),
            "competition_name": _get(m, "competition", "competition_name"),
            "country_name": _get(m, "competition", "country_name"),
            "season_id": _get(m, "season", "season_id"),
            "season_name": _get(m, "season", "season_name"),
            "competition_stage": _get(m, "competition_stage", "name"),
            "match_week": m.get("match_week"),
            "home_team_id": _get(m, "home_team", "home_team_id"),
            "home_team_name": _get(m, "home_team", "home_team_name"),
            "home_team_gender": _get(m, "home_team", "home_team_gender"),
            "home_team_group": _get(m, "home_team", "home_team_group"),
            "home_team_country": _get(m, "home_team", "country", "name"),
            "away_team_id": _get(m, "away_team", "away_team_id"),
            "away_team_name": _get(m, "away_team", "away_team_name"),
            "away_team_gender": _get(m, "away_team", "away_team_gender"),
            "away_team_group": _get(m, "away_team", "away_team_group"),
            "away_team_country": _get(m, "away_team", "country", "name"),
            "home_score": m.get("home_score"),
            "away_score": m.get("away_score"),
            "match_status": m.get("match_status"),
            "match_status_360": m.get("match_status_360"),
            "last_updated": m.get("last_updated"),
            "last_updated_360": m.get("last_updated_360"),
            "stadium_id": _get(m, "stadium", "id"),
            "stadium_name": _get(m, "stadium", "name"),
            "stadium_country": _get(m, "stadium", "country", "name"),
            "referee_id": _get(m, "referee", "id"),
            "referee_name": _get(m, "referee", "name"),
            "data_version": _get(m, "metadata", "data_version"),
        }


MATCHES = Table(
    name="statsbomb_matches",
    source=SOURCE,
    kind="matches",
    description="StatsBomb matches, one row per match. Daily snapshot of each competition season (dt = download day).",
    columns=(
        C("match_id", "bigint"),
        C("match_date", "date"),
        C("kick_off", "string", "Local kick-off time hh:mm:ss.fff"),
        C("competition_id", "bigint"),
        C("competition_name", "string"),
        C("country_name", "string"),
        C("season_id", "bigint"),
        C("season_name", "string"),
        C("competition_stage", "string"),
        C("match_week", "int"),
        C("home_team_id", "bigint"),
        C("home_team_name", "string"),
        C("home_team_gender", "string"),
        C("home_team_group", "string"),
        C("home_team_country", "string"),
        C("away_team_id", "bigint"),
        C("away_team_name", "string"),
        C("away_team_gender", "string"),
        C("away_team_group", "string"),
        C("away_team_country", "string"),
        C("home_score", "int"),
        C("away_score", "int"),
        C("match_status", "string"),
        C("match_status_360", "string"),
        C("last_updated", "timestamp"),
        C("last_updated_360", "timestamp"),
        C("stadium_id", "bigint"),
        C("stadium_name", "string"),
        C("stadium_country", "string"),
        C("referee_id", "bigint"),
        C("referee_name", "string"),
        C("data_version", "string"),
    ),
    flatten=matches,
)

# ------------------------------------------------------------------ events

# Keys every event can carry. Anything else is the type-specific block
# (pass, shot, carry, ...) and is kept whole in `details`.
_COMMON_EVENT_KEYS = {
    "id", "index", "period", "timestamp", "minute", "second", "type", "possession",
    "possession_team", "play_pattern", "team", "player", "position", "location",
    "duration", "under_pressure", "counterpress", "off_camera", "out", "related_events",
}  # fmt: skip


def events(doc: list[dict], key: RawKey) -> Iterator[dict]:
    match_id = key.attrs.get("match_id")
    for e in doc:
        details = {k: v for k, v in e.items() if k not in _COMMON_EVENT_KEYS}
        blocks = [v for v in details.values() if isinstance(v, dict)]
        outcome = next((_get(b, "outcome", "name") for b in blocks if _get(b, "outcome", "name")), None)
        end = next((b["end_location"] for b in blocks if isinstance(b.get("end_location"), list)), None)
        yield {
            "match_id": match_id,
            "event_id": e.get("id"),
            "event_index": e.get("index"),
            "period": e.get("period"),
            "event_timestamp": e.get("timestamp"),
            "minute": e.get("minute"),
            "second": e.get("second"),
            "type_id": _get(e, "type", "id"),
            "type_name": _get(e, "type", "name"),
            "possession": e.get("possession"),
            "possession_team_id": _get(e, "possession_team", "id"),
            "possession_team_name": _get(e, "possession_team", "name"),
            "play_pattern_name": _get(e, "play_pattern", "name"),
            "team_id": _get(e, "team", "id"),
            "team_name": _get(e, "team", "name"),
            "player_id": _get(e, "player", "id"),
            "player_name": _get(e, "player", "name"),
            "position_name": _get(e, "position", "name"),
            "location_x": _xy(e.get("location"), 0),
            "location_y": _xy(e.get("location"), 1),
            "end_location_x": _xy(end, 0),
            "end_location_y": _xy(end, 1),
            "duration": e.get("duration"),
            "under_pressure": bool(e.get("under_pressure", False)),
            "counterpress": bool(e.get("counterpress", False)),
            "off_camera": bool(e.get("off_camera", False)),
            "out": bool(e.get("out", False)),
            "outcome_name": outcome,
            "shot_xg": _get(e, "shot", "statsbomb_xg"),
            "related_events": e.get("related_events") or [],
            "details": _json(details),
            "source_updated": key.attrs.get("updated"),
        }


EVENTS = Table(
    name="statsbomb_events",
    source=SOURCE,
    kind="events",
    description="StatsBomb event data, one row per on-ball/off-ball event. dt = match date. Latest version per match only.",
    columns=(
        C("match_id", "bigint"),
        C("event_id", "string", "StatsBomb event UUID"),
        C("event_index", "int", "Order of the event within the match"),
        C("period", "int"),
        C("event_timestamp", "string", "Time within the period, hh:mm:ss.fff"),
        C("minute", "int"),
        C("second", "int"),
        C("type_id", "int"),
        C("type_name", "string"),
        C("possession", "int"),
        C("possession_team_id", "bigint"),
        C("possession_team_name", "string"),
        C("play_pattern_name", "string"),
        C("team_id", "bigint"),
        C("team_name", "string"),
        C("player_id", "bigint"),
        C("player_name", "string"),
        C("position_name", "string"),
        C("location_x", "double", "Pitch x, 0-120"),
        C("location_y", "double", "Pitch y, 0-80"),
        C("end_location_x", "double"),
        C("end_location_y", "double"),
        C("duration", "double", "Seconds"),
        C("under_pressure", "boolean"),
        C("counterpress", "boolean"),
        C("off_camera", "boolean"),
        C("out", "boolean"),
        C("outcome_name", "string", "Outcome from the type-specific block, if any"),
        C("shot_xg", "double", "StatsBomb expected goals, shots only"),
        C("related_events", "array<string>"),
        C("details", "string", "Type-specific block(s) as JSON, e.g. {\"pass\": {...}}"),
        C("source_updated", "string", "StatsBomb last_updated stamp of this version"),
    ),
    flatten=events,
)

# ------------------------------------------------------------------ lineups


def lineups(doc: list[dict], key: RawKey) -> Iterator[dict]:
    match_id = key.attrs.get("match_id")
    for team in doc:
        for p in team.get("lineup") or []:
            positions = p.get("positions") or []
            yield {
                "match_id": match_id,
                "team_id": team.get("team_id"),
                "team_name": team.get("team_name"),
                "player_id": p.get("player_id"),
                "player_name": p.get("player_name"),
                "player_nickname": p.get("player_nickname"),
                "jersey_number": p.get("jersey_number"),
                "country_name": _get(p, "country", "name"),
                "started": any(pos.get("start_reason") == "Starting XI" for pos in positions),
                "positions": _json(positions),
                "cards": _json(p.get("cards") or []),
                "source_updated": key.attrs.get("updated"),
            }


LINEUPS = Table(
    name="statsbomb_lineups",
    source=SOURCE,
    kind="lineups",
    description="StatsBomb lineups, one row per player per match (squad, including unused subs). dt = match date.",
    columns=(
        C("match_id", "bigint"),
        C("team_id", "bigint"),
        C("team_name", "string"),
        C("player_id", "bigint"),
        C("player_name", "string"),
        C("player_nickname", "string"),
        C("jersey_number", "int"),
        C("country_name", "string"),
        C("started", "boolean", "In the starting XI"),
        C("positions", "string", "Positions played, JSON list"),
        C("cards", "string", "Cards received, JSON list"),
        C("source_updated", "string"),
    ),
    flatten=lineups,
)

# ------------------------------------------------------------------ 360 freeze frames

_FRAME = "array<struct<teammate:boolean,actor:boolean,keeper:boolean,location_x:double,location_y:double>>"


def three_sixty(doc: list[dict], key: RawKey) -> Iterator[dict]:
    match_id = key.attrs.get("match_id")
    for f in doc:
        yield {
            "match_id": match_id,
            "event_id": f.get("event_uuid"),
            "visible_area": f.get("visible_area") or [],
            "freeze_frame": [
                {
                    "teammate": p.get("teammate"),
                    "actor": p.get("actor"),
                    "keeper": p.get("keeper"),
                    "location_x": _xy(p.get("location"), 0),
                    "location_y": _xy(p.get("location"), 1),
                }
                for p in f.get("freeze_frame") or []
            ],
            "source_updated": key.attrs.get("updated"),
        }


THREE_SIXTY = Table(
    name="statsbomb_three_sixty",
    source=SOURCE,
    kind="three-sixty",
    description="StatsBomb 360 freeze frames, one row per event that has one. Join to statsbomb_events on event_id.",
    columns=(
        C("match_id", "bigint"),
        C("event_id", "string"),
        C("visible_area", "array<double>", "Polygon as x1,y1,x2,y2,..."),
        C("freeze_frame", _FRAME, "Visible players at the moment of the event"),
        C("source_updated", "string"),
    ),
    flatten=three_sixty,
)

TABLES = (COMPETITIONS, MATCHES, EVENTS, LINEUPS, THREE_SIXTY)
