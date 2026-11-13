-- One row per Cricsheet delivery (wides and no-balls included), with the bowling team added.
select
    d.match_id,
    d.innings_number,
    d.over_number,
    d.ball_in_over,
    d.super_over,
    d.batting_team,
    case when d.batting_team = m.team_1 then m.team_2 else m.team_1 end as bowling_team,
    d.batter,
    d.bowler,
    d.non_striker,
    d.runs_batter,
    d.runs_extras,
    d.runs_total,
    d.extras_wides,
    d.extras_noballs,
    d.extras_byes,
    d.extras_legbyes,
    d.extras_penalty,
    d.is_wicket,
    d.wicket_kinds,
    d.players_out,
    d.start_date as match_date,
    d._raw_key
from {{ source('clean', 'cricsheet_deliveries') }} as d
inner join {{ ref('stg_cricsheet__matches') }} as m
    on d.match_id = m.match_id
