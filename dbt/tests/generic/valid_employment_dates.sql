{% test valid_employment_dates(
    model,
    hire_date_column='hire_date',
    termination_date_column='termination_date'
) %}

select *
from {{ model }}
where {{ hire_date_column }} is not null
    and {{ termination_date_column }} is not null
    and {{ termination_date_column }} < {{ hire_date_column }}

{% endtest %}

