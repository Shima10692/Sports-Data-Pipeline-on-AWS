-- Goals counted in fact_events (periods 1-4, i.e. without the shoot-out) must equal
-- the match score in dim_session. Catches a broken goal flag or dropped/duplicated events.
with goals as (

    select session_key, count_if(is_goal and period between 1 and 4) as goals
    from {{ ref('fact_events') }}
    where sport = 'football'
    group by session_key

)

select s.session_key, s.session_name, s.home_score + s.away_score as score_goals, coalesce(g.goals, 0) as event_goals
from {{ ref('dim_session') }} as s
left join goals as g
    on s.session_key = g.session_key
where s.sport = 'football'
  and s.home_score is not null
  and s.away_score is not null
  and s.home_score + s.away_score <> coalesce(g.goals, 0)
