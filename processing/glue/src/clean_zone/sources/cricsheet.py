"""Cricsheet ball-by-ball JSON → clean tables.

Data: Cricsheet (cricsheet.org), Open Data Commons Attribution License.
Format reference: https://cricsheet.org/format/json/
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..rawkeys import RawKey
from ..table import Column as C
from ..table import Table

SOURCE = "cricsheet"


def _first(values: Any) -> Any:
    return values[0] if isinstance(values, list) and values else None


def _last(values: Any) -> Any:
    return values[-1] if isinstance(values, list) and values else None


def matches(doc: dict, key: RawKey) -> Iterator[dict]:
    info = doc.get("info") or {}
    meta = doc.get("meta") or {}
    outcome = info.get("outcome") or {}
    by = outcome.get("by") or {}
    teams = info.get("teams") or []
    event = info.get("event") or {}
    toss = info.get("toss") or {}
    officials = info.get("officials") or {}
    yield {
        "match_id": key.attrs.get("match_id"),
        "data_version": meta.get("data_version"),
        "revision": meta.get("revision"),
        "match_type": info.get("match_type"),
        "match_type_number": info.get("match_type_number"),
        "gender": info.get("gender"),
        "team_type": info.get("team_type"),
        "season": info.get("season"),
        "start_date": _first(info.get("dates")),
        "end_date": _last(info.get("dates")),
        "city": info.get("city"),
        "venue": info.get("venue"),
        "event_name": event.get("name"),
        "event_match_number": event.get("match_number"),
        "event_stage": event.get("stage"),
        "event_group": event.get("group"),
        "team_1": teams[0] if len(teams) > 0 else None,
        "team_2": teams[1] if len(teams) > 1 else None,
        "toss_winner": toss.get("winner"),
        "toss_decision": toss.get("decision"),
        "winner": outcome.get("winner"),
        "result": outcome.get("result"),
        "win_by_runs": by.get("runs"),
        "win_by_wickets": by.get("wickets"),
        "win_by_innings": bool(by.get("innings")),
        "method": outcome.get("method"),
        "eliminator": outcome.get("eliminator"),
        "player_of_match": info.get("player_of_match") or [],
        "overs": info.get("overs"),
        "balls_per_over": info.get("balls_per_over"),
        "umpires": officials.get("umpires") or [],
    }


MATCHES = Table(
    name="cricsheet_matches",
    source=SOURCE,
    kind="matches",
    description="Cricsheet match summaries, one row per match. dt = first day of the match.",
    columns=(
        C("match_id", "bigint", "Cricsheet match id"),
        C("data_version", "string"),
        C("revision", "int", "Cricsheet revision of this match file"),
        C("match_type", "string", "Test, ODI, T20, IT20, ODM, MDM"),
        C("match_type_number", "int"),
        C("gender", "string"),
        C("team_type", "string", "international or club"),
        C("season", "string"),
        C("start_date", "date"),
        C("end_date", "date"),
        C("city", "string"),
        C("venue", "string"),
        C("event_name", "string"),
        C("event_match_number", "int"),
        C("event_stage", "string"),
        C("event_group", "string"),
        C("team_1", "string"),
        C("team_2", "string"),
        C("toss_winner", "string"),
        C("toss_decision", "string", "bat or field"),
        C("winner", "string"),
        C("result", "string", "draw, no result or tie when there is no winner"),
        C("win_by_runs", "int"),
        C("win_by_wickets", "int"),
        C("win_by_innings", "boolean"),
        C("method", "string", "e.g. D/L"),
        C("eliminator", "string", "Super-over / bowl-out winner"),
        C("player_of_match", "array<string>"),
        C("overs", "int", "Scheduled overs per innings (limited-overs games)"),
        C("balls_per_over", "int"),
        C("umpires", "array<string>"),
    ),
    flatten=matches,
)


def deliveries(doc: dict, key: RawKey) -> Iterator[dict]:
    match_id = key.attrs.get("match_id")
    start_date = _first((doc.get("info") or {}).get("dates"))
    for innings_number, innings in enumerate(doc.get("innings") or [], start=1):
        for over in innings.get("overs") or []:
            for ball, d in enumerate(over.get("deliveries") or [], start=1):
                runs = d.get("runs") or {}
                extras = d.get("extras") or {}
                wickets = d.get("wickets") or []
                yield {
                    "match_id": match_id,
                    "start_date": start_date,
                    "innings_number": innings_number,
                    "batting_team": innings.get("team"),
                    "super_over": bool(innings.get("super_over", False)),
                    "over_number": over.get("over"),
                    "ball_in_over": ball,
                    "batter": d.get("batter"),
                    "bowler": d.get("bowler"),
                    "non_striker": d.get("non_striker"),
                    "runs_batter": runs.get("batter"),
                    "runs_extras": runs.get("extras"),
                    "runs_total": runs.get("total"),
                    "extras_wides": extras.get("wides"),
                    "extras_noballs": extras.get("noballs"),
                    "extras_byes": extras.get("byes"),
                    "extras_legbyes": extras.get("legbyes"),
                    "extras_penalty": extras.get("penalty"),
                    "is_wicket": bool(wickets),
                    "wicket_kinds": [w.get("kind") for w in wickets],
                    "players_out": [w.get("player_out") for w in wickets],
                }


DELIVERIES = Table(
    name="cricsheet_deliveries",
    source=SOURCE,
    kind="matches",
    description="Cricsheet ball-by-ball, one row per delivery (wides and no-balls included). dt = first day of the match.",
    columns=(
        C("match_id", "bigint"),
        C("start_date", "date"),
        C("innings_number", "int", "1-based, in playing order"),
        C("batting_team", "string"),
        C("super_over", "boolean"),
        C("over_number", "int", "0-based, as in Cricsheet"),
        C("ball_in_over", "int", "1-based position in the over, counting extras"),
        C("batter", "string"),
        C("bowler", "string"),
        C("non_striker", "string"),
        C("runs_batter", "int"),
        C("runs_extras", "int"),
        C("runs_total", "int"),
        C("extras_wides", "int"),
        C("extras_noballs", "int"),
        C("extras_byes", "int"),
        C("extras_legbyes", "int"),
        C("extras_penalty", "int"),
        C("is_wicket", "boolean"),
        C("wicket_kinds", "array<string>"),
        C("players_out", "array<string>"),
    ),
    flatten=deliveries,
)

TABLES = (MATCHES, DELIVERIES)
