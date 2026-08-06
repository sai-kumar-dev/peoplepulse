{{ config(
    materialized='incremental',
    unique_key='hire_sk',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns'
) }}

with hire_events as (
    select *
    from {{ ref('stg_hris__hires') }}
),

resolved_keys as (
    select
        hire_events.*,
        employee.employee_sk,
        department.department_sk,
        row_number() over (
            partition by hire_events.hire_event_id
            order by employee.valid_from desc nulls last
        ) as employee_version_rank
    from hire_events
    left join {{ ref('dim_employee') }} as employee
        on hire_events.employee_id = employee.employee_id
        and cast(hire_events.hire_date as timestamp) >= employee.valid_from
        and (
            employee.valid_to is null
            or cast(hire_events.hire_date as timestamp) < employee.valid_to
        )
    left join {{ ref('dim_department') }} as department
        on hire_events.department_id = department.department_id
)

select
    {{ generate_surrogate_key(['hire_event_id']) }} as hire_sk,
    hire_event_id,
    coalesce(employee_sk, {{ unknown_surrogate_key() }}) as employee_sk,
    employee_id,
    coalesce(department_sk, {{ unknown_surrogate_key() }}) as department_sk,
    department_id,
    hire_date,
    cast(date_trunc('month', hire_date) as date) as hire_month,
    hire_type,
    job_id,
    location_id,
    requisition_id,
    1 as hire_count,
    source_record_hash as record_hash,
    source_system,
    ingested_at as loaded_at,
    batch_id,
    is_valid_record
from resolved_keys
where employee_version_rank = 1

