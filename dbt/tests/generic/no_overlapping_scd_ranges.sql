{% test no_overlapping_scd_ranges(
    model,
    business_key,
    valid_from_column='valid_from',
    valid_to_column='valid_to'
) %}

with ordered_ranges as (
    select
        {{ business_key }} as business_key,
        {{ valid_from_column }} as valid_from,
        {{ valid_to_column }} as valid_to,
        lag({{ valid_to_column }}) over (
            partition by {{ business_key }}
            order by {{ valid_from_column }}, {{ valid_to_column }}
        ) as previous_valid_to,
        row_number() over (
            partition by {{ business_key }}
            order by {{ valid_from_column }}, {{ valid_to_column }}
        ) as range_number
    from {{ model }}
    where {{ business_key }} is not null
)

select *
from ordered_ranges
where (valid_to is not null and valid_to <= valid_from)
    or (
        range_number > 1
        and (previous_valid_to is null or valid_from < previous_valid_to)
    )

{% endtest %}

