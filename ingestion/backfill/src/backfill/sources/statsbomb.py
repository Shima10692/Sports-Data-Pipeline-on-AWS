"""StatsBomb Open Data (github.com/hudl/open-data).

Free for research; publications must credit StatsBomb as the data source.

Keys:
  date=<today>/competitions.json                                       daily catalogue snapshot
  date=<today>/matches/competition_id=<c>/season_id=<s>.json           daily match-list snapshot
  date=<match date>/events/match_id=<m>/updated=<stamp>.json
  date=<match date>/lineups/match_id=<m>/updated=<stamp>.json
  date=<match date>/three-sixty/match_id=<m>/updated=<stamp>.json      only when 360 data exists

<stamp> is the source's last_updated time, so a corrected match lands as a new
object instead of overwriting the old one.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..storage import raw_key

BASE_URL = "https://raw.githubusercontent.com/hudl/open-data/master/data"
SOURCE = "statsbomb"
MIN_INTERVAL = 0.25
# FIFA World Cup 2022: 64 matches, a quick first load.
DEFAULTS: dict[str, Any] = {"competitions": [{"competition_id": 43, "season_id": 106}], "include_360": True}


def _stamp(value: str | None) -> str:
    """'2024-09-28T20:46:38.893391' -> '20240928T204638'."""
    if not value:
        return "unknown"
    digits = re.sub(r"[^0-9T]", "", value.split(".")[0])
    return digits or "unknown"


def run(params: dict[str, Any], ctx) -> bool:
    w, http, today = ctx.writer, ctx.http, ctx.today

    url = f"{BASE_URL}/competitions.json"
    w.put_if_absent(raw_key(SOURCE, today, "competitions.json"), lambda: http.get_bytes(url), source_url=url)

    for comp in params["competitions"]:
        if ctx.should_stop():
            return False
        cid, sid = int(comp["competition_id"]), int(comp["season_id"])
        url = f"{BASE_URL}/matches/{cid}/{sid}.json"
        body = http.get_bytes(url)  # needed every run to enumerate matches
        w.put(raw_key(SOURCE, today, f"matches/competition_id={cid}/season_id={sid}.json"), body, source_url=url)

        for match in json.loads(body):
            if ctx.should_stop():
                return False
            mid, day = int(match["match_id"]), match["match_date"]
            files = [("events", match.get("last_updated")), ("lineups", match.get("last_updated"))]
            if params.get("include_360", True) and match.get("match_status_360") == "available":
                files.append(("three-sixty", match.get("last_updated_360") or match.get("last_updated")))
            for kind, updated in files:
                file_url = f"{BASE_URL}/{kind}/{mid}.json"
                w.put_if_absent(
                    raw_key(SOURCE, day, f"{kind}/match_id={mid}/updated={_stamp(updated)}.json"),
                    lambda u=file_url: http.get_bytes(u),
                    source_url=file_url,
                )
    return True
