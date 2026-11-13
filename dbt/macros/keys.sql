{#
  Surrogate keys for the marts.

  sk('team', "'statsbomb'", 'home_team_id')  ->  md5 hex of 'team|statsbomb|<id>'

  The entity and source are part of the hash, so ids from different sources
  (StatsBomb team 1 vs a Jolpica constructor) never collide. The key depends only
  on source ids, so it is stable across rebuilds and across processing engines.
#}
{% macro sk(entity, source_sql, id_sql) -%}
    lower(to_hex(md5(to_utf8(concat_ws('|', '{{ entity }}', {{ source_sql }}, cast({{ id_sql }} as varchar))))))
{%- endmacro %}

{#- Same, but null when the id is null (an event with no player has no player_key). -#}
{% macro sk_or_null(entity, source_sql, id_sql) -%}
    case when {{ id_sql }} is not null then {{ sk(entity, source_sql, id_sql) }} end
{%- endmacro %}
