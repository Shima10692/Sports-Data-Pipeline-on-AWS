-- One row per F1 race weekend: the newest download (dt = download day) of each (season, round).
with ranked as (

    select
        *,
        row_number() over (partition by season, round order by dt desc, _raw_key desc) as snapshot_rank
    from {{ source('clean', 'jolpica_races') }}

)

select
    season,
    round,
    race_name,
    race_date,
    race_time,
    circuit_id,
    circuit_name,
    locality,
    country,
    qualifying_date,
    sprint_date,
    has_sprint,
    dt as snapshot_dt,
    _raw_key
from ranked
where snapshot_rank = 1
