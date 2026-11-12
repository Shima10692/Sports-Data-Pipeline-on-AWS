"""Cricsheet ball-by-ball match data (cricsheet.org).

Open Data Commons Attribution License: credit Cricsheet in any public use.

Datasets are zip files at https://cricsheet.org/downloads/<name>_json.zip, e.g.
"recently_added_7", "ipl", "t20s", "all" (about 150 MB, needs a big Lambda).

Keys:
  date=<first match day>/matches/match_id=<id>.json
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Any

from ..storage import raw_key

BASE_URL = "https://cricsheet.org/downloads"
SOURCE = "cricsheet"
MIN_INTERVAL = 2.0
DEFAULTS: dict[str, Any] = {"datasets": ["recently_added_7"]}
_DATASET_RE = re.compile(r"^[a-z0-9_]+$")


def run(params: dict[str, Any], ctx) -> bool:
    w, http = ctx.writer, ctx.http

    for dataset in params["datasets"]:
        if not _DATASET_RE.match(dataset):
            raise ValueError(f"invalid cricsheet dataset name: {dataset!r}")
        if ctx.should_stop():
            return False
        url = f"{BASE_URL}/{dataset}_json.zip"
        archive = zipfile.ZipFile(io.BytesIO(http.get_bytes(url)))

        for member in sorted(archive.namelist()):
            if not member.endswith(".json") or "/" in member:
                continue  # README.txt and anything nested
            if ctx.should_stop():
                return False
            data = archive.read(member)
            match_id = member[: -len(".json")]
            first_day = json.loads(data)["info"]["dates"][0]
            w.put_if_absent(
                raw_key(SOURCE, first_day, f"matches/match_id={match_id}.json"),
                lambda d=data: d,
                source_url=f"{url}#{member}",
            )
    return True
