"""TheSportsDB reference data (teams, players), v1 API.

Free tier: public key "123", 30 requests/minute, at most 10 results per list call.
A paid key, if ever used, lives in Secrets Manager (see handler.py).

Keys (daily snapshots):
  date=<today>/teams/league=<slug>.json
  date=<today>/players/team_id=<id>.json
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from ..storage import raw_key

SOURCE = "thesportsdb"
FREE_API_KEY = "123"
MIN_INTERVAL = 2.2  # 30 requests/minute with headroom
DEFAULTS: dict[str, Any] = {"leagues": ["English Premier League"], "include_players": True}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def base_url(api_key: str) -> str:
    return f"https://www.thesportsdb.com/api/v1/json/{urllib.parse.quote(api_key, safe='')}"


def run(params: dict[str, Any], ctx) -> bool:
    w, http, today = ctx.writer, ctx.http, ctx.today
    base = base_url(ctx.api_keys.get(SOURCE, FREE_API_KEY))

    for league in params["leagues"]:
        if ctx.should_stop():
            return False
        url = f"{base}/search_all_teams.php?l={urllib.parse.quote(league)}"
        body = http.get_bytes(url)  # needed every run to enumerate teams
        w.put(raw_key(SOURCE, today, f"teams/league={slug(league)}.json"), body, source_url=_redact(url))

        if not params.get("include_players", True):
            continue
        for team in json.loads(body).get("teams") or []:
            if ctx.should_stop():
                return False
            team_id = int(team["idTeam"])
            p_url = f"{base}/lookup_all_players.php?id={team_id}"
            w.put_if_absent(
                raw_key(SOURCE, today, f"players/team_id={team_id}.json"),
                lambda u=p_url: http.get_bytes(u),
                source_url=_redact(p_url),
            )
    return True


def _redact(url: str) -> str:
    """Never store an API key in object metadata."""
    return re.sub(r"/json/[^/]+/", "/json/<key>/", url)
