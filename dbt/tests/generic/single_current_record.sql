{% test single_current_record(
    model,
    business_key,
    is_current_column='is_current'
) %}

select
    {{ business_key }} as business_key,
    sum(case when {{ is_current_column }} then 1 else 0 end) as current_record_count
from {{ model }}
where {{ business_key }} is not null
group by {{ business_key }}
having sum(case when {{ is_current_column }} then 1 else 0 end) <> 1

{% endtest %}

