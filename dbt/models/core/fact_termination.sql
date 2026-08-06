{{ config(
    materialized='incremental',
    unique_key='termination_sk',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns'
) }}

with attrition_events as (
    select *
    from {{ ref('int_attrition_events') }}
),

resolved_keys as (
    select
        attrition_events.*,
        employee.employee_sk,
        department.department_sk,
        row_number() over (
            partition by attrition_events.termination_event_id
            order by employee.valid_from desc nulls last
        ) as employee_version_rank
    from attrition_events
    left join {{ ref('dim_employee') }} as employee
        on attrition_events.employee_id = employee.employee_id
        and cast(attrition_events.termination_date as timestamp) >= employee.valid_from
        and (
            employee.valid_to is null
            or cast(attrition_events.termination_date as timestamp) < employee.valid_to
        )
    left join {{ ref('dim_department') }} as department
        on attrition_events.department_id = department.department_id
)

select
    {{ generate_surrogate_key(['termination_event_id']) }} as termination_sk,
    termination_event_id,
    coalesce(employee_sk, {{ unknown_surrogate_key() }}) as employee_sk,
    employee_id,
    coalesce(department_sk, {{ unknown_surrogate_key() }}) as department_sk,
    department_id,
    termination_date,
    cast(date_trunc('month', termination_date) as date) as termination_month,
    termination_type,
    termination_reason,
    is_voluntary,
    job_id,
    job_level,
    location_id,
    employment_type,
    tenure_days_at_termination,
    1 as termination_count,
    source_record_hash as record_hash,
    source_system,
    ingested_at as loaded_at,
    batch_id,
    is_valid_record
from resolved_keys
where employee_version_rank = 1

