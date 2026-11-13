-- One row per StatsBomb match: the newest download (dt = download day) of each match.
-- Picked per match, not by max(dt), so a later partial download never drops other matches.
with ranked as (

    select
        *,
        row_number() over (partition by match_id order by dt desc, _raw_key desc) as snapshot_rank
    from {{ source('clean', 'statsbomb_matches') }}

)

select
    match_id,
    match_date,
    kick_off,
    competition_id,
    competition_name,
    country_name as competition_country,
    season_id,
    season_name,
    competition_stage,
    match_week,
    home_team_id,
    home_team_name,
    home_team_gender,
    home_team_country,
    away_team_id,
    away_team_name,
    away_team_gender,
    away_team_country,
    home_score,
    away_score,
    match_status,
    stadium_name,
    stadium_country,
    referee_name,
    last_updated,
    dt as snapshot_dt,
    _raw_key
from ranked
where snapshot_rank = 1
