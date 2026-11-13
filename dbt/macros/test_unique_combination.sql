{#
  Generic test: no two rows share the same values in `columns`.
    data_tests:
      - unique_combination:
          arguments:
            columns: [season, round, driver_id]
#}
{% test unique_combination(model, columns) %}

select {{ columns | join(', ') }}, count(*) as n_rows
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
