# Backfill (phase 4)

Loads historical and reference sports data into the S3 **raw zone**. It runs as the Lambda `sports-<env>-backfill`, or locally from the command line.

## Sources

| Source | What | Published limit | Request spacing | Default scope |
|---|---|---|---|---|
| `statsbomb` | Football events, lineups, 360 (`hudl/open-data` on GitHub) | none stated | 0.25 s | FIFA World Cup 2022 (`competition_id` 43, `season_id` 106) |
| `jolpica` | F1 race results and qualifying (`api.jolpi.ca`) | 4/s burst, **500/hour** | 8 s | 2024 season |
| `cricsheet` | Cricket ball-by-ball (zip downloads) | none stated | 2 s | `recently_added_7` |
| `thesportsdb` | Teams and players (v1, free key `123`) | **30/minute**, 10 results per call | 2.2 s | English Premier League |

**Attribution** (required if you publish anything built on this data):
- Football data: StatsBomb.
- Cricket data: Cricsheet, under the Open Data Commons Attribution License.

## Raw layout

```
source=<name>/date=<yyyy-mm-dd>/<kind>/<id>=<value>....json
```

`date` is the match or race date when the data has one, and otherwise the download date (for daily snapshots of catalogues, schedules, teams and players).

| Source | Keys |
|---|---|
| statsbomb | `date=<match date>/events/match_id=<m>/updated=<last_updated>.json` (also `lineups`, `three-sixty`); `date=<today>/competitions.json`, `date=<today>/matches/competition_id=<c>/season_id=<s>.json` |
| jolpica | `date=<race date>/<results\|qualifying\|sprint\|pitstops>/season=<y>/round=<rr>.json`; `date=<today>/races/season=<y>.json` |
| cricsheet | `date=<first match day>/matches/match_id=<id>.json` |
| thesportsdb | `date=<today>/teams/league=<slug>.json`, `date=<today>/players/team_id=<id>.json` |

## Guarantees
- **Append-only:** writes are conditional (`If-None-Match: *`). Nothing is ever overwritten, and the bucket policy denies deletes.
- **Idempotent:** a key that already exists is skipped *before* fetching, so re-runs cost almost no API calls. A StatsBomb match that gets corrected upstream lands as a new `updated=` object.
- **Rate-limited:** each source is spaced to its published limit. 429 and 5xx responses retry with backoff and respect `Retry-After`.
- **Resumable:** a run stops a minute before the 15-minute Lambda limit and returns `"complete": false`. Invoke again with the same event to continue.

## Run it

Lambda (dev):
```bash
aws lambda invoke --function-name sports-dev-backfill \
  --cli-binary-format raw-in-base64-out \
  --payload '{"source": "jolpica", "params": {"seasons": [2023, 2024]}}' out.json && cat out.json
```

Locally (uses your AWS CLI login):
```bash
cd ingestion/backfill/src
python -m backfill --source thesportsdb --dry-run                         # fetch only, write nothing
python -m backfill --source cricsheet --params '{"datasets": ["ipl"]}' --bucket sports-dev-raw-<account id>
```

`params` is merged over the source defaults:
- `statsbomb`: `{"competitions": [{"competition_id": 43, "season_id": 106}], "include_360": true}`. IDs are listed in `competitions.json`.
- `jolpica`: `{"seasons": [2024], "endpoints": ["results", "qualifying"]}`. Endpoints can be `results`, `qualifying`, `sprint` or `pitstops`.
- `cricsheet`: `{"datasets": ["recently_added_7"]}`. Any `<name>` from cricsheet.org/downloads works (`<name>_json.zip`). The 150 MB `all` dataset needs about 2 GB of Lambda memory.
- `thesportsdb`: `{"leagues": ["English Premier League"], "include_players": true}`

## Tests
```bash
pytest ingestion/backfill   # offline: fake S3 and fake HTTP
```
