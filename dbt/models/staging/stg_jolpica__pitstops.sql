-- One row per F1 pit stop. Empty until the backfill fetches pit stops; the models still build.
select
    season,
    round,
    race_date,
    driver_id,
    lap,
    stop,
    time_of_day,
    duration_ms,
    _raw_key
from {{ source('clean', 'jolpica_pitstops') }}
