"""Jolpica (Ergast-compatible) Formula 1 data → clean tables.

Every response is {"MRData": {"RaceTable": {"Races": [...]}}}; per-race files
hold one race whose results list is named per endpoint.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from ..rawkeys import RawKey
from ..table import Column as C
from ..table import Table

SOURCE = "jolpica"

_LAP_RE = re.compile(r"^(?:(\d+):)?(\d+)(?:\.(\d{1,3}))?$")


def lap_ms(text: Any) -> int | None:
    """'1:29.179' -> 89179, '22.345' -> 22345. Anything else -> None."""
    if not isinstance(text, str):
        return None
    m = _LAP_RE.match(text.strip())
    if not m:
        return None
    minutes, seconds, frac = m.groups()
    return (int(minutes or 0) * 60 + int(seconds)) * 1000 + int((frac or "0").ljust(3, "0"))


def _races(doc: dict) -> list[dict]:
    return ((doc.get("MRData") or {}).get("RaceTable") or {}).get("Races") or []


def _race_cols(race: dict) -> dict:
    return {
        "season": race.get("season"),
        "round": race.get("round"),
        "race_name": race.get("raceName"),
        "race_date": race.get("date"),
        "circuit_id": (race.get("Circuit") or {}).get("circuitId"),
    }


def _driver_cols(row: dict) -> dict:
    d, c = row.get("Driver") or {}, row.get("Constructor") or {}
    return {
        "driver_id": d.get("driverId"),
        "driver_code": d.get("code"),
        "car_number": row.get("number"),
        "given_name": d.get("givenName"),
        "family_name": d.get("familyName"),
        "driver_nationality": d.get("nationality"),
        "constructor_id": c.get("constructorId"),
        "constructor_name": c.get("name"),
    }


_RACE_COLUMNS = (
    C("season", "int"),
    C("round", "int"),
    C("race_name", "string"),
    C("race_date", "date"),
    C("circuit_id", "string"),
)
_DRIVER_COLUMNS = (
    C("driver_id", "string", "Jolpica/Ergast driver id, e.g. max_verstappen"),
    C("driver_code", "string", "Three-letter code, e.g. VER"),
    C("car_number", "int"),
    C("given_name", "string"),
    C("family_name", "string"),
    C("driver_nationality", "string"),
    C("constructor_id", "string"),
    C("constructor_name", "string"),
)

# ------------------------------------------------------------------ race schedule


def races(doc: dict, key: RawKey) -> Iterator[dict]:
    for r in _races(doc):
        circuit = r.get("Circuit") or {}
        loc = circuit.get("Location") or {}
        yield {
            **_race_cols(r),
            "race_time": r.get("time"),
            "circuit_name": circuit.get("circuitName"),
            "locality": loc.get("locality"),
            "country": loc.get("country"),
            "latitude": loc.get("lat"),
            "longitude": loc.get("long"),
            "qualifying_date": (r.get("Qualifying") or {}).get("date"),
            "sprint_date": (r.get("Sprint") or {}).get("date"),
            "has_sprint": "Sprint" in r,
            "url": r.get("url"),
        }


RACES = Table(
    name="jolpica_races",
    source=SOURCE,
    kind="races",
    description="F1 race calendar, one row per race. Daily snapshot of each season (dt = download day).",
    columns=(
        *_RACE_COLUMNS,
        C("race_time", "string", "UTC start time, hh:mm:ssZ"),
        C("circuit_name", "string"),
        C("locality", "string"),
        C("country", "string"),
        C("latitude", "double"),
        C("longitude", "double"),
        C("qualifying_date", "date"),
        C("sprint_date", "date"),
        C("has_sprint", "boolean"),
        C("url", "string"),
    ),
    flatten=races,
)

# ------------------------------------------------------------------ race + sprint results

_RESULT_COLUMNS = (
    *_RACE_COLUMNS,
    *_DRIVER_COLUMNS,
    C("grid", "int", "Starting position; 0 = pit lane"),
    C("position", "int", "Classified position"),
    C("position_text", "string", "R = retired, D = disqualified, W = withdrew, ..."),
    C("points", "double"),
    C("laps", "int"),
    C("status", "string"),
    C("time_ms", "bigint", "Race time in ms, classified finishers on the lead lap only"),
    C("time_text", "string", "Winner's time, or the gap for others"),
    C("fastest_lap_rank", "int"),
    C("fastest_lap_number", "int"),
    C("fastest_lap_ms", "bigint"),
    C("fastest_lap_avg_kph", "double"),
)


def _results(list_name: str):
    def flatten(doc: dict, key: RawKey) -> Iterator[dict]:
        for race in _races(doc):
            for row in race.get(list_name) or []:
                fl = row.get("FastestLap") or {}
                yield {
                    **_race_cols(race),
                    **_driver_cols(row),
                    "grid": row.get("grid"),
                    "position": row.get("position"),
                    "position_text": row.get("positionText"),
                    "points": row.get("points"),
                    "laps": row.get("laps"),
                    "status": row.get("status"),
                    "time_ms": (row.get("Time") or {}).get("millis"),
                    "time_text": (row.get("Time") or {}).get("time"),
                    "fastest_lap_rank": fl.get("rank"),
                    "fastest_lap_number": fl.get("lap"),
                    "fastest_lap_ms": lap_ms((fl.get("Time") or {}).get("time")),
                    "fastest_lap_avg_kph": (fl.get("AverageSpeed") or {}).get("speed"),
                }

    return flatten


RESULTS = Table(
    name="jolpica_results",
    source=SOURCE,
    kind="results",
    description="F1 race results, one row per driver per race. dt = race date.",
    columns=_RESULT_COLUMNS,
    flatten=_results("Results"),
)

SPRINT = Table(
    name="jolpica_sprint_results",
    source=SOURCE,
    kind="sprint",
    description="F1 sprint results, one row per driver per sprint. dt = race (Sunday) date.",
    columns=_RESULT_COLUMNS,
    flatten=_results("SprintResults"),
)

# ------------------------------------------------------------------ qualifying


def qualifying(doc: dict, key: RawKey) -> Iterator[dict]:
    for race in _races(doc):
        for row in race.get("QualifyingResults") or []:
            yield {
                **_race_cols(race),
                **_driver_cols(row),
                "position": row.get("position"),
                "q1": row.get("Q1"),
                "q2": row.get("Q2"),
                "q3": row.get("Q3"),
                "q1_ms": lap_ms(row.get("Q1")),
                "q2_ms": lap_ms(row.get("Q2")),
                "q3_ms": lap_ms(row.get("Q3")),
            }


QUALIFYING = Table(
    name="jolpica_qualifying",
    source=SOURCE,
    kind="qualifying",
    description="F1 qualifying, one row per driver per race. dt = race date.",
    columns=(
        *_RACE_COLUMNS,
        *_DRIVER_COLUMNS,
        C("position", "int"),
        C("q1", "string"),
        C("q2", "string"),
        C("q3", "string"),
        C("q1_ms", "bigint"),
        C("q2_ms", "bigint"),
        C("q3_ms", "bigint"),
    ),
    flatten=qualifying,
)

# ------------------------------------------------------------------ pit stops


def pitstops(doc: dict, key: RawKey) -> Iterator[dict]:
    for race in _races(doc):
        for row in race.get("PitStops") or []:
            yield {
                **_race_cols(race),
                "driver_id": row.get("driverId"),
                "lap": row.get("lap"),
                "stop": row.get("stop"),
                "time_of_day": row.get("time"),
                "duration_text": row.get("duration"),
                "duration_ms": lap_ms(row.get("duration")),
            }


PITSTOPS = Table(
    name="jolpica_pitstops",
    source=SOURCE,
    kind="pitstops",
    description="F1 pit stops, one row per stop. dt = race date.",
    columns=(
        *_RACE_COLUMNS,
        C("driver_id", "string"),
        C("lap", "int"),
        C("stop", "int"),
        C("time_of_day", "string", "Local time of the stop"),
        C("duration_text", "string"),
        C("duration_ms", "bigint", "Pit-lane time in ms"),
    ),
    flatten=pitstops,
)

TABLES = (RACES, RESULTS, SPRINT, QUALIFYING, PITSTOPS)
