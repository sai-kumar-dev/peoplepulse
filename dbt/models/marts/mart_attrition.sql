with daily_headcount as (
    select
        cast(date_trunc('month', snapshot_date) as date) as metric_month,
        department_sk,
        snapshot_date,
        sum(headcount_count) as headcount
    from {{ ref('fact_employee_snapshot') }}
    group by
        cast(date_trunc('month', snapshot_date) as date),
        department_sk,
        snapshot_date
),

monthly_headcount as (
    select
        metric_month,
        department_sk,
        avg(headcount) as average_headcount,
        max(headcount) as ending_observed_headcount,
        count(*) as observed_snapshot_days
    from daily_headcount
    group by metric_month, department_sk
),

monthly_terminations as (
    select
        termination_month as metric_month,
        department_sk,
        sum(termination_count) as terminations,
        sum(case when is_voluntary then termination_count else 0 end) as voluntary_terminations,
        sum(case when not is_voluntary then termination_count else 0 end) as involuntary_terminations,
        avg(tenure_days_at_termination) / 365.25 as average_tenure_years_at_exit
    from {{ ref('fact_termination') }}
    group by termination_month, department_sk
),

combined as (
    select
        coalesce(terminations.metric_month, headcount.metric_month) as metric_month,
        coalesce(terminations.department_sk, headcount.department_sk) as department_sk,
        coalesce(terminations.terminations, 0) as terminations,
        coalesce(terminations.voluntary_terminations, 0) as voluntary_terminations,
        coalesce(terminations.involuntary_terminations, 0) as involuntary_terminations,
        terminations.average_tenure_years_at_exit,
        headcount.average_headcount,
        headcount.ending_observed_headcount,
        coalesce(headcount.observed_snapshot_days, 0) as observed_snapshot_days
    from monthly_terminations as terminations
    full outer join monthly_headcount as headcount
        on terminations.metric_month = headcount.metric_month
        and terminations.department_sk = headcount.department_sk
)

select
    combined.metric_month,
    combined.department_sk,
    department.department_name,
    combined.terminations,
    combined.voluntary_terminations,
    combined.involuntary_terminations,
    combined.average_headcount,
    combined.ending_observed_headcount,
    combined.observed_snapshot_days,
    {{ safe_divide('combined.terminations', 'combined.average_headcount') }} as monthly_attrition_rate,
    {{ safe_divide('combined.terminations * 12', 'combined.average_headcount') }}
        as annualized_attrition_rate,
    {{ safe_divide('combined.voluntary_terminations', 'combined.terminations') }}
        as voluntary_attrition_share,
    combined.average_tenure_years_at_exit,
    cast(current_timestamp as timestamp) as refreshed_at
from combined
left join {{ ref('dim_department') }} as department
    on combined.department_sk = department.department_sk

