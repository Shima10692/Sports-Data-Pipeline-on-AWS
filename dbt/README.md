# dbt (phase 6): warehouse models on Athena

dbt-athena project that models the clean zone (`sports_<env>_lake`) into four marts.

```
clean zone (Glue Catalog)        staging (views)                 marts (Parquet tables)
sports_<env>_lake           ->   sports_<env>_staging       ->   sports_<env>_marts
  statsbomb_*                      stg_statsbomb__matches          dim_session
  cricsheet_*                      stg_statsbomb__events           dim_team
  jolpica_*                        stg_statsbomb__lineups          dim_player
                                   stg_cricsheet__matches          fact_events
                                   stg_cricsheet__deliveries
                                   stg_jolpica__races
                                   stg_jolpica__results
                                   stg_jolpica__pitstops
```

The Athena workgroup `sports-<env>` and both Glue databases are created by Terraform
(`infra/modules/athena_warehouse`). dbt only creates views and tables inside them.
Mart data is written to `s3://sports-<env>-clean-<account>/dbt/<schema>/<table>/<uuid>/`.

## The marts

| Model | Grain | Football (StatsBomb) | Cricket (Cricsheet) | F1 (Jolpica) |
|---|---|---|---|---|
| `dim_session` | one sporting session | match | match | race, qualifying, sprint |
| `dim_team` | team per source | team | team (by name) | constructor |
| `dim_player` | player per source | player (from lineups) | player (by name) | driver |
| `fact_events` | one in-session event | event | delivery | pit stop |

Keys are md5 hashes of `<entity>|<source>|<source id>`. They depend only on source ids,
so they stay the same across rebuilds and when processing moves back from Lambda to Glue.
`fact_events` columns that only make sense for one sport (`is_goal`, `xg`, `runs`, `is_wicket`, ...)
are null for the others. `_raw_key` on every fact row points to the raw object it came from.

Choices worth knowing:
- **Snapshot tables** (`statsbomb_matches`, `jolpica_races`) hold one copy per download day. Staging
  keeps the newest copy *per match / race*, not `max(dt)`, so a later partial download never drops rows.
- **Football goals**: `is_goal` = shot scored or `Own Goal For`, including shoot-out kicks (`period = 5`).
  `winner_team_key` is the score after extra time, so a match decided on penalties is a `draw`.
- **Cricket** players and teams are identified by name; the clean zone has no Cricsheet person ids.
- **TheSportsDB** is left out until its raw data is loaded (needs the API key in Secrets Manager).
- **F1 pit stops** are empty today (the backfill does not fetch them yet); the models build regardless.

## Tests

`dbt build` runs models and tests together:
- Generic: `unique` / `not_null` on every key, `relationships` from facts and dimensions to dims,
  `accepted_values`, and `unique_combination` (in `macros/`) on natural keys.
- Singular (`tests/`):
  - `assert_football_goals_match_score`: in-play goals in `fact_events` equal each match score.
  - `assert_known_answer_wc2022_final`: the 2022 World Cup final has 12 goal events (6 + 6 in the shoot-out).
  - `assert_fact_events_row_counts_match_staging`: no events lost or duplicated by joins.
- Unit tests (`models/staging/_staging.yml`): newest-snapshot selection and the goal flag.
- Source freshness (`dbt source freshness`): warns when a snapshot table is more than 8 days old.

pytest (`tests/test_dbt_sources.py`) checks that `models/staging/_sources.yml` still matches the
clean-zone schemas in `processing/glue/src/clean_zone`. After a schema change there, regenerate it:

```bash
python dbt/scripts/gen_sources.py > dbt/models/staging/_sources.yml
```

## Running it

```bash
cd dbt
pip install -r requirements.txt          # botocore[crt] is needed for `aws login` credentials
export DBT_AWS_ACCOUNT_ID=<12-digit account id>
export DBT_PROFILES_DIR=.                # profiles.yml here has no credentials
dbt build                                # dev (default target)
dbt source freshness
```

PowerShell: `$env:DBT_AWS_ACCOUNT_ID = "<id>"; $env:DBT_PROFILES_DIR = "."`.

**Prod** (`--target prod`) stays empty until phase 9 orchestration loads it. Don't run dbt against prod by hand.

Cost: every model and test run once against dev data scanned about 40 MB in total (well under $0.01). The workgroup cancels any single
query over 1 GiB. Query results expire after 3 days (`tmp/` lifecycle rule).

CI runs `dbt parse` on every PR (offline). `dbt build` in automation comes with the phase-9
orchestration and the phase-11 deploy role.
