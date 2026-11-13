-- One row per driver per F1 classified session: race, sprint and qualifying stacked,
-- with session_type telling them apart. Shared columns only; times stay in ms.
with race as (

    select
        'race' as session_type,
        season, round, race_date, driver_id, driver_code, car_number, given_name, family_name,
        driver_nationality, constructor_id, constructor_name,
        grid, position, position_text, points, laps, status, time_ms,
        cast(null as bigint) as best_lap_ms,
        _raw_key
    from {{ source('clean', 'jolpica_results') }}

),

sprint as (

    select
        'sprint' as session_type,
        season, round, race_date, driver_id, driver_code, car_number, given_name, family_name,
        driver_nationality, constructor_id, constructor_name,
        grid, position, position_text, points, laps, status, time_ms,
        cast(null as bigint) as best_lap_ms,
        _raw_key
    from {{ source('clean', 'jolpica_sprint_results') }}

),

qualifying as (

    select
        'qualifying' as session_type,
        season, round, race_date, driver_id, driver_code, car_number, given_name, family_name,
        driver_nationality, constructor_id, constructor_name,
        cast(null as integer) as grid,
        position,
        cast(position as varchar) as position_text,
        cast(null as double) as points,
        cast(null as integer) as laps,
        cast(null as varchar) as status,
        cast(null as bigint) as time_ms,
        -- Best time of the knockout stage the driver reached.
        coalesce(q3_ms, q2_ms, q1_ms) as best_lap_ms,
        _raw_key
    from {{ source('clean', 'jolpica_qualifying') }}

)

select * from race
union all
select * from sprint
union all
select * from qualifying
