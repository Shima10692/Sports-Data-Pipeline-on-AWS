-- One row per player per source: StatsBomb footballers, Cricsheet cricketers, Jolpica F1 drivers.
-- Attributes and latest_team_key come from the player's most recent appearance.
with appearances as (

    select
        'football' as sport,
        'statsbomb' as source,
        cast(player_id as varchar) as source_player_id,
        player_name,
        player_nickname as nickname,
        cast(null as varchar) as short_code,
        nationality,
        {{ sk('team', "'statsbomb'", 'team_id') }} as team_key,
        match_date as session_date
    from {{ ref('stg_statsbomb__lineups') }}

    union all
    -- Cricsheet gives names only (no player ids in the clean zone), so the name is the id.
    select 'cricket', 'cricsheet', batter, batter, cast(null as varchar), cast(null as varchar), cast(null as varchar),
           {{ sk('team', "'cricsheet'", 'batting_team') }}, match_date
    from {{ ref('stg_cricsheet__deliveries') }}
    union all
    select 'cricket', 'cricsheet', non_striker, non_striker, cast(null as varchar), cast(null as varchar), cast(null as varchar),
           {{ sk('team', "'cricsheet'", 'batting_team') }}, match_date
    from {{ ref('stg_cricsheet__deliveries') }}
    union all
    select 'cricket', 'cricsheet', bowler, bowler, cast(null as varchar), cast(null as varchar), cast(null as varchar),
           {{ sk('team', "'cricsheet'", 'bowling_team') }}, match_date
    from {{ ref('stg_cricsheet__deliveries') }}

    union all
    select 'f1', 'jolpica', driver_id, given_name || ' ' || family_name, cast(null as varchar), driver_code,
           driver_nationality, {{ sk('team', "'jolpica'", 'constructor_id') }}, race_date
    from {{ ref('stg_jolpica__results') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by source, source_player_id order by session_date desc, team_key
        ) as recency_rank,
        min(session_date) over (partition by source, source_player_id) as first_session_date,
        max(session_date) over (partition by source, source_player_id) as last_session_date
    from appearances
    where source_player_id is not null

)

select
    {{ sk('player', 'source', 'source_player_id') }} as player_key,
    sport,
    source,
    source_player_id,
    player_name,
    nickname,
    short_code,
    nationality,
    team_key as latest_team_key,
    first_session_date,
    last_session_date
from ranked
where recency_rank = 1
