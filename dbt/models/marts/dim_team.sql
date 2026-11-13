-- One row per team per source: StatsBomb football teams, Cricsheet cricket teams,
-- Jolpica F1 constructors. Attributes come from the team's most recent appearance.
with appearances as (

    select 'football' as sport, 'statsbomb' as source, cast(home_team_id as varchar) as source_team_id,
           home_team_name as team_name, home_team_country as country, home_team_gender as gender,
           cast(null as varchar) as team_type, match_date as session_date
    from {{ ref('stg_statsbomb__matches') }}
    union all
    select 'football', 'statsbomb', cast(away_team_id as varchar),
           away_team_name, away_team_country, away_team_gender,
           cast(null as varchar), match_date
    from {{ ref('stg_statsbomb__matches') }}

    union all
    -- Cricsheet identifies teams by name only.
    select 'cricket', 'cricsheet', team_1, team_1, cast(null as varchar), gender, team_type, start_date
    from {{ ref('stg_cricsheet__matches') }}
    union all
    select 'cricket', 'cricsheet', team_2, team_2, cast(null as varchar), gender, team_type, start_date
    from {{ ref('stg_cricsheet__matches') }}

    union all
    select 'f1', 'jolpica', constructor_id, constructor_name, cast(null as varchar), cast(null as varchar),
           'constructor', race_date
    from {{ ref('stg_jolpica__results') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by source, source_team_id order by session_date desc, team_name
        ) as recency_rank,
        min(session_date) over (partition by source, source_team_id) as first_session_date,
        max(session_date) over (partition by source, source_team_id) as last_session_date
    from appearances
    where source_team_id is not null

)

select
    {{ sk('team', 'source', 'source_team_id') }} as team_key,
    sport,
    source,
    source_team_id,
    team_name,
    country,
    gender,
    team_type,
    first_session_date,
    last_session_date
from ranked
where recency_rank = 1
