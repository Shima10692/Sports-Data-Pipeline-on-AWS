# Processing: raw → clean (phase 5)

One Glue 5.0 (Spark 3.5, Python 3.11) job, `sports-<env>-raw-to-clean`, turns the raw-zone JSON into Parquet tables in the clean zone and registers them in the Glue database `sports_<env>_lake`.

```
processing/glue/
  glue_entry.py          Glue script (uploaded by Terraform)
  src/clean_zone/        the package (zipped by Terraform, passed with --extra-py-files)
    sources/*.py         one module per raw source: table schemas + flatteners
    coltypes.py          Hive type strings + strict value coercion
    rawkeys.py           raw key parsing, newest-version selection
    catalog.py           Glue table / partition registration
    job.py               Spark orchestration (the only Spark code)
  tests/                 pytest, offline (no Spark, no AWS)
```

## How it works
1. List raw keys for the selected sources (all dates, or `--dates`), keeping only the **newest version** of each object (StatsBomb `updated=` stamps).
2. Executors download each object and run the source's **pure-Python flattener**. Each table has an explicit schema, and values are coerced strictly: a value that cannot be converted fails the job and names the table, column and raw key, instead of becoming a silent null.
3. Write Parquet to `s3://sports-<env>-clean-<account>/<table>/dt=<yyyy-mm-dd>/` with **dynamic partition overwrite**: only the `dt` partitions being processed are replaced.
4. Create or update the catalog table from the same schema, and register the partitions it wrote. No crawler is used.

`dt` is the raw `date=` value: the match or race date, or the download day for snapshots. It is not called `date` because that is a reserved word in Athena. Every row also carries `_raw_key`, the raw object it came from.

**Idempotent:** a `dt` partition is always rebuilt from *every* raw object of that date, so a re-run gives the same result. Reprocessing a date (`--dates`) picks up late or corrected raw objects.

## Tables

| Table | Grain | dt |
|---|---|---|
| `statsbomb_competitions` | competition season | download day |
| `statsbomb_matches` | match | download day |
| `statsbomb_events` | event (type-specific block kept as JSON in `details`) | match date |
| `statsbomb_lineups` | player per match | match date |
| `statsbomb_three_sixty` | event with a 360 freeze frame (nested `array<struct>`) | match date |
| `jolpica_races` | race | download day |
| `jolpica_results`, `jolpica_sprint_results` | driver per race / sprint | race date |
| `jolpica_qualifying` | driver per race | race date |
| `jolpica_pitstops` | pit stop | race date |
| `cricsheet_matches` | match | first match day |
| `cricsheet_deliveries` | delivery (wides and no-balls included) | first match day |
| `thesportsdb_teams` | team per league | download day |
| `thesportsdb_players` | player per team | download day |

Snapshot tables hold one copy per download day; dbt (phase 6) picks the latest.

## Run it
```bash
# everything
aws glue start-job-run --job-name sports-dev-raw-to-clean
# one source, a few raw dates
aws glue start-job-run --job-name sports-dev-raw-to-clean \
  --arguments '{"--sources":"jolpica","--dates":"2024-03-02,2024-03-09"}'
aws glue get-job-runs --job-name sports-dev-raw-to-clean --max-items 1
```
The job prints one JSON summary line per table (`raw_objects`, `rows`, `partitions`, catalog action) to the log group `/aws-glue/jobs/sports-dev-raw-to-clean`.

**Cost:** Flex execution, 2 × G.1X workers: about $0.29 per DPU-hour with a 1-minute minimum, so a full run over the current dev data costs a few cents. Nothing runs on a schedule; phase 9 adds orchestration.

## Adding a table
Add a `Table(...)` with its columns and a flattener to the source module and append it to that module's `TABLES`. Then add a test in `tests/test_sources.py`. The next run creates the catalog table. Changing a column type updates the table and the partitions the run rewrites; reprocess all dates (`--dates all`) so older partitions match.

## Known limits
- A `dt` partition that ends up with zero rows is not removed (dynamic overwrite only replaces partitions it writes). Raw is append-only, so this only happens if a source withdraws data.
- Each run reads every raw object of the selected dates. That is fine at this size (about 500k rows); phase 9 passes `--dates` for incremental runs.

## Tests
```bash
pytest processing   # offline: fake S3 and fake Glue, no Spark
```
