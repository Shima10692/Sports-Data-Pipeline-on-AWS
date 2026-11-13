-- Known answer: the 2022 World Cup final (StatsBomb match 3869685), Argentina 3-3 France,
-- Argentina won 4-2 on penalties, so 12 goal events (6 in play + 6 shoot-out kicks scored).
-- Passes when the match is not loaded (e.g. an empty prod), so it only checks real data.
select session_key, count_if(is_goal) as goal_events, count_if(is_goal and period = 5) as shootout_goals
from {{ ref('fact_events') }}
where session_key = {{ sk('session', "'statsbomb'", var('known_answer_match_id')) }}
group by session_key
having count_if(is_goal) <> 12 or count_if(is_goal and period = 5) <> 6
