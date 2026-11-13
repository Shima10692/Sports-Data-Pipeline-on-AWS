-- One row per sporting session: a football match, a cricket match, or an F1 session
-- (race, qualifying, sprint) of a race weekend.
with football as (

    select
        {{ sk('session', "'statsbomb'", 'match_id') }} as session_key,
        'football' as sport,
        'statsbomb' as source,
        cast(match_id as varchar) as source_session_id,
        'match' as session_type,
        home_team_name || ' vs ' || away_team_name as session_name,
        competition_name,
        season_name as season,
        competition_stage as stage,
        match_date as session_date,
        kick_off as start_time,
        stadium_name as venue,
        cast(null as varchar) as city,
        stadium_country as country,
        {{ sk('team', "'statsbomb'", 'home_team_id') }} as home_team_key,
        {{ sk('team', "'statsbomb'", 'away_team_id') }} as away_team_key,
        home_score,
        away_score,
        -- Score after extra time; shoot-out winners are not in the match record.
        case
            when home_score > away_score then {{ sk('team', "'statsbomb'", 'home_team_id') }}
            when away_score > home_score then {{ sk('team', "'statsbomb'", 'away_team_id') }}
        end as winner_team_key,
        case
            when home_score is null or away_score is null then 'unknown'
            when home_score = away_score then 'draw'
            else 'win'
        end as result_type
    from {{ ref('stg_statsbomb__matches') }}

),

cricket as (

    select
        {{ sk('session', "'cricsheet'", 'match_id') }} as session_key,
        'cricket' as sport,
        'cricsheet' as source,
        cast(match_id as varchar) as source_session_id,
        match_type as session_type,
        team_1 || ' vs ' || team_2 as session_name,
        event_name as competition_name,
        season,
        event_stage as stage,
        start_date as session_date,
        cast(null as varchar) as start_time,
        venue,
        city,
        cast(null as varchar) as country,
        -- Cricsheet has no home/away; team_1/team_2 in the order Cricsheet lists them.
        {{ sk('team', "'cricsheet'", 'team_1') }} as home_team_key,
        {{ sk('team', "'cricsheet'", 'team_2') }} as away_team_key,
        cast(null as integer) as home_score,
        cast(null as integer) as away_score,
        -- A tie settled by a super over has the super-over winner as eliminator.
        {{ sk_or_null('team', "'cricsheet'", 'coalesce(winner, eliminator)') }} as winner_team_key,
        case
            when winner is not null then 'win'
            when result is not null then result
            else 'unknown'
        end as result_type
    from {{ ref('stg_cricsheet__matches') }}

),

f1_sessions as (

    select season, round, race_name, circuit_name, locality, country,
           'race' as session_type, race_date as session_date, race_time as start_time
    from {{ ref('stg_jolpica__races') }}
    union all
    select season, round, race_name, circuit_name, locality, country,
           'qualifying', qualifying_date, cast(null as varchar)
    from {{ ref('stg_jolpica__races') }}
    where qualifying_date is not null
    union all
    select season, round, race_name, circuit_name, locality, country,
           'sprint', sprint_date, cast(null as varchar)
    from {{ ref('stg_jolpica__races') }}
    where has_sprint

),

f1_winners as (

    select season, round, session_type, constructor_id
    from {{ ref('stg_jolpica__results') }}
    where position = 1 and session_type in ('race', 'sprint')

),

f1 as (

    select
        {{ sk('session', "'jolpica'", "concat_ws('-', cast(s.season as varchar), cast(s.round as varchar), s.session_type)") }} as session_key,
        'f1' as sport,
        'jolpica' as source,
        concat_ws('-', cast(s.season as varchar), cast(s.round as varchar), s.session_type) as source_session_id,
        s.session_type,
        s.race_name || ' - ' || upper(substr(s.session_type, 1, 1)) || substr(s.session_type, 2) as session_name,
        'Formula One World Championship' as competition_name,
        cast(s.season as varchar) as season,
        'Round ' || cast(s.round as varchar) as stage,
        s.session_date,
        s.start_time,
        s.circuit_name as venue,
        s.locality as city,
        s.country,
        cast(null as varchar) as home_team_key,
        cast(null as varchar) as away_team_key,
        cast(null as integer) as home_score,
        cast(null as integer) as away_score,
        {{ sk_or_null('team', "'jolpica'", 'w.constructor_id') }} as winner_team_key,
        case when w.constructor_id is not null then 'win' else 'unknown' end as result_type
    from f1_sessions as s
    left join f1_winners as w
        on s.season = w.season and s.round = w.round and s.session_type = w.session_type

)

select * from football
union all
select * from cricket
union all
select * from f1
