-- fact_events must have exactly one row per staged event: no rows lost, none fanned out by joins.
with expected as (

    select 'football' as sport, count(*) as n from {{ ref('stg_statsbomb__events') }}
    union all
    select 'cricket', count(*) from {{ ref('stg_cricsheet__deliveries') }}
    union all
    select 'f1', count(*) from {{ ref('stg_jolpica__pitstops') }}

),

actual as (

    select sport, count(*) as n
    from {{ ref('fact_events') }}
    group by sport

)

select e.sport, e.n as expected_rows, coalesce(a.n, 0) as actual_rows
from expected as e
left join actual as a
    on e.sport = a.sport
where e.n <> coalesce(a.n, 0)
