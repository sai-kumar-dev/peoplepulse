with snapshot_summary as (
    select
        snapshot_date,
        sum(headcount_count) as total_headcount,
        sum(active_employee_count) as active_employees,
        sum(leave_employee_count) as employees_on_leave,
        sum(inactive_employee_count) as inactive_employees,
        count(distinct department_sk) as represented_departments,
        {{ safe_divide(
            'sum(case when headcount_count = 1 then tenure_days else 0 end)',
            'sum(headcount_count)'
        ) }} / 365.25 as average_tenure_years,
        max(loaded_at) as snapshot_loaded_at
    from {{ ref('fact_employee_snapshot') }}
    group by snapshot_date
),

hire_metrics as (
    select
        snapshot.snapshot_date,
        sum(case
            when hire.hire_date = snapshot.snapshot_date then hire.hire_count else 0
        end) as hires_today,
        sum(case
            when hire.hire_date >= cast(date_trunc('month', snapshot.snapshot_date) as date)
                and hire.hire_date <= snapshot.snapshot_date then hire.hire_count else 0
        end) as hires_month_to_date,
        sum(case
            when hire.hire_date >= cast(date_trunc('year', snapshot.snapshot_date) as date)
                and hire.hire_date <= snapshot.snapshot_date then hire.hire_count else 0
        end) as hires_year_to_date
    from snapshot_summary as snapshot
    left join {{ ref('fact_hire') }} as hire
        on hire.hire_date <= snapshot.snapshot_date
        and hire.hire_date >= cast(date_trunc('year', snapshot.snapshot_date) as date)
    group by snapshot.snapshot_date
),

termination_metrics as (
    select
        snapshot.snapshot_date,
        sum(case
            when termination.termination_date = snapshot.snapshot_date
                then termination.termination_count else 0
        end) as terminations_today,
        sum(case
            when termination.termination_date
                >= cast(date_trunc('month', snapshot.snapshot_date) as date)
                and termination.termination_date <= snapshot.snapshot_date
                then termination.termination_count else 0
        end) as terminations_month_to_date,
        sum(case
            when termination.termination_date
                >= cast(date_trunc('year', snapshot.snapshot_date) as date)
                and termination.termination_date <= snapshot.snapshot_date
                then termination.termination_count else 0
        end) as terminations_year_to_date,
        sum(case
            when termination.termination_date
                >= cast(date_trunc('year', snapshot.snapshot_date) as date)
                and termination.termination_date <= snapshot.snapshot_date
                and termination.is_voluntary
                then termination.termination_count else 0
        end) as voluntary_terminations_year_to_date
    from snapshot_summary as snapshot
    left join {{ ref('fact_termination') }} as termination
        on termination.termination_date <= snapshot.snapshot_date
        and termination.termination_date >= cast(date_trunc('year', snapshot.snapshot_date) as date)
    group by snapshot.snapshot_date
),

quality_score as (
    select
        100.0 * coalesce(
            {{ safe_divide('sum(passed_count)', 'sum(records_tested)') }},
            1.0
        ) as data_quality_score
    from {{ ref('mart_data_quality_summary') }}
)

select
    snapshot.snapshot_date,
    snapshot.total_headcount,
    snapshot.active_employees,
    snapshot.employees_on_leave,
    snapshot.inactive_employees,
    snapshot.represented_departments,
    snapshot.average_tenure_years,
    coalesce(hire.hires_today, 0) as hires_today,
    coalesce(hire.hires_month_to_date, 0) as hires_month_to_date,
    coalesce(hire.hires_year_to_date, 0) as hires_year_to_date,
    coalesce(termination.terminations_today, 0) as terminations_today,
    coalesce(termination.terminations_month_to_date, 0) as terminations_month_to_date,
    coalesce(termination.terminations_year_to_date, 0) as terminations_year_to_date,
    coalesce(termination.voluntary_terminations_year_to_date, 0)
        as voluntary_terminations_year_to_date,
    {{ safe_divide(
        'coalesce(termination.terminations_year_to_date, 0)',
        'snapshot.total_headcount'
    ) }} as year_to_date_attrition_rate,
    quality.data_quality_score,
    snapshot.snapshot_loaded_at,
    cast(current_timestamp as timestamp) as refreshed_at
from snapshot_summary as snapshot
left join hire_metrics as hire
    on snapshot.snapshot_date = hire.snapshot_date
left join termination_metrics as termination
    on snapshot.snapshot_date = termination.snapshot_date
cross join quality_score as quality

