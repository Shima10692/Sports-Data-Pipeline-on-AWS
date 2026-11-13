-- One row per in-session event: a football event (StatsBomb), a cricket delivery
-- (Cricsheet) or an F1 pit stop (Jolpica). Shared columns first, then sport-specific
-- measures that are null for the other sports.
--
-- period:       football half (5 = penalty shoot-out), cricket innings, F1 lap.
-- event_clock:  football mm:ss, cricket over.ball (0-based over), F1 "lap N".
with football as (

    select
        {{ sk('event', "'statsbomb'", 'event_id') }} as event_key,
        'football' as sport,
        'statsbomb' as source,
        event_id as source_event_id,
        {{ sk('session', "'statsbomb'", 'match_id') }} as session_key,
        match_date as event_date,
        {{ sk_or_null('team', "'statsbomb'", 'team_id') }} as team_key,
        {{ sk_or_null('player', "'statsbomb'", 'player_id') }} as player_key,
        {{ sk_or_null('player', "'statsbomb'", 'pass_recipient_id') }} as secondary_player_key,
        event_index as event_seq,
        period,
        lpad(cast(minute as varchar), 2, '0') || ':' || lpad(cast(second as varchar), 2, '0') as event_clock,
        type_name as event_type,
        outcome_name as event_outcome,
        is_goal,
        cast(null as boolean) as is_wicket,
        cast(null as integer) as runs,
        shot_xg as xg,
        location_x,
        location_y,
        end_location_x,
        end_location_y,
        duration_seconds,
        details,
        _raw_key
    from {{ ref('stg_statsbomb__events') }}

),

cricket as (

    select
        {{ sk('event', "'cricsheet'", "concat_ws('-', cast(match_id as varchar), cast(innings_number as varchar), cast(over_number as varchar), cast(ball_in_over as varchar))") }} as event_key,
        'cricket' as sport,
        'cricsheet' as source,
        concat_ws('-', cast(match_id as varchar), cast(innings_number as varchar), cast(over_number as varchar), cast(ball_in_over as varchar)) as source_event_id,
        {{ sk('session', "'cricsheet'", 'match_id') }} as session_key,
        match_date as event_date,
        {{ sk('team', "'cricsheet'", 'batting_team') }} as team_key,
        {{ sk_or_null('player', "'cricsheet'", 'batter') }} as player_key,
        {{ sk_or_null('player', "'cricsheet'", 'bowler') }} as secondary_player_key,
        cast(row_number() over (
            partition by match_id order by innings_number, over_number, ball_in_over
        ) as integer) as event_seq,
        innings_number as period,
        cast(over_number as varchar) || '.' || cast(ball_in_over as varchar) as event_clock,
        'delivery' as event_type,
        case
            when is_wicket then array_join(wicket_kinds, ', ')
            when extras_wides > 0 then 'wide'
            when extras_noballs > 0 then 'no ball'
            when extras_byes > 0 then 'bye'
            when extras_legbyes > 0 then 'leg bye'
        end as event_outcome,
        cast(null as boolean) as is_goal,
        is_wicket,
        runs_total as runs,
        cast(null as double) as xg,
        cast(null as double) as location_x,
        cast(null as double) as location_y,
        cast(null as double) as end_location_x,
        cast(null as double) as end_location_y,
        cast(null as double) as duration_seconds,
        json_format(cast(map(
            array['runs_batter', 'runs_extras', 'wides', 'noballs', 'byes', 'legbyes', 'penalty', 'super_over'],
            array[runs_batter, runs_extras, extras_wides, extras_noballs, extras_byes, extras_legbyes, extras_penalty,
                  case when super_over then 1 else 0 end]
        ) as json)) as details,
        _raw_key
    from {{ ref('stg_cricsheet__deliveries') }}

),

f1_constructors as (

    select season, round, driver_id, constructor_id
    from {{ ref('stg_jolpica__results') }}
    where session_type = 'race'

),

f1 as (

    select
        {{ sk('event', "'jolpica'", "concat_ws('-', cast(p.season as varchar), cast(p.round as varchar), p.driver_id, cast(p.stop as varchar))") }} as event_key,
        'f1' as sport,
        'jolpica' as source,
        concat_ws('-', cast(p.season as varchar), cast(p.round as varchar), p.driver_id, cast(p.stop as varchar)) as source_event_id,
        {{ sk('session', "'jolpica'", "concat_ws('-', cast(p.season as varchar), cast(p.round as varchar), 'race')") }} as session_key,
        p.race_date as event_date,
        {{ sk_or_null('team', "'jolpica'", 'c.constructor_id') }} as team_key,
        {{ sk_or_null('player', "'jolpica'", 'p.driver_id') }} as player_key,
        cast(null as varchar) as secondary_player_key,
        cast(row_number() over (
            partition by p.season, p.round order by p.lap, p.time_of_day, p.driver_id
        ) as integer) as event_seq,
        p.lap as period,
        'lap ' || cast(p.lap as varchar) as event_clock,
        'pit_stop' as event_type,
        cast(null as varchar) as event_outcome,
        cast(null as boolean) as is_goal,
        cast(null as boolean) as is_wicket,
        cast(null as integer) as runs,
        cast(null as double) as xg,
        cast(null as double) as location_x,
        cast(null as double) as location_y,
        cast(null as double) as end_location_x,
        cast(null as double) as end_location_y,
        cast(p.duration_ms as double) / 1000 as duration_seconds,
        cast(null as varchar) as details,
        p._raw_key
    from {{ ref('stg_jolpica__pitstops') }} as p
    left join f1_constructors as c
        on p.season = c.season and p.round = c.round and p.driver_id = c.driver_id

)

select * from football
union all
select * from cricket
union all
select * from f1
