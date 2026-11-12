"""Jolpica F1 API (Ergast-compatible), api.jolpi.ca.

Unauthenticated limits: 4 requests/s burst, 500/hour sustained (HTTP 429 when
exceeded). One request every 8 s stays under 500/hour.

Keys:
  date=<today>/races/season=<yyyy>.json                       daily schedule snapshot
  date=<race date>/<endpoint>/season=<yyyy>/round=<rr>.json   per completed race
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from ..storage import raw_key

BASE_URL = "https://api.jolpi.ca/ergast/f1"
SOURCE = "jolpica"
MIN_INTERVAL = 8.0
ENDPOINTS = {"results", "qualifying", "sprint", "pitstops"}
DEFAULTS: dict[str, Any] = {"seasons": [2024], "endpoints": ["results", "qualifying"]}


def run(params: dict[str, Any], ctx) -> bool:
    w, http, today = ctx.writer, ctx.http, ctx.today
    endpoints = list(params["endpoints"])
    unknown = set(endpoints) - ENDPOINTS
    if unknown:
        raise ValueError(f"unsupported jolpica endpoints: {sorted(unknown)}")

    for season in params["seasons"]:
        if ctx.should_stop():
            return False
        season = int(season)
        url = f"{BASE_URL}/{season}/races.json?limit=100"
        body = http.get_bytes(url)
        w.put(raw_key(SOURCE, today, f"races/season={season}.json"), body, source_url=url)

        for race in json.loads(body)["MRData"]["RaceTable"]["Races"]:
            race_day = dt.date.fromisoformat(race["date"])
            if race_day > today:
                continue  # not raced yet
            rnd = int(race["round"])
            for endpoint in endpoints:
                if endpoint == "sprint" and "Sprint" not in race:
                    continue
                if ctx.should_stop():
                    return False
                ep_url = f"{BASE_URL}/{season}/{rnd}/{endpoint}.json?limit=100"
                w.put_if_absent(
                    raw_key(SOURCE, race_day, f"{endpoint}/season={season}/round={rnd:02d}.json"),
                    lambda u=ep_url: http.get_bytes(u),
                    source_url=ep_url,
                )
    return True
