-- One row per player per StatsBomb match (whole squad, unused subs included).
select
    match_id,
    team_id,
    team_name,
    player_id,
    player_name,
    player_nickname,
    jersey_number,
    country_name as nationality,
    started,
    cast(dt as date) as match_date,
    _raw_key
from {{ source('clean', 'statsbomb_lineups') }}
