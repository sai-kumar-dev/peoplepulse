{{ config(
    materialized='incremental',
    unique_key='employee_snapshot_sk',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns'
) }}

with parameters as (
    select {{ snapshot_date() }} as snapshot_date
),

eligible_versions as (
    select
        employee.*,
        parameters.snapshot_date,
        row_number() over (
            partition by employee.employee_id
            order by employee.valid_from desc, employee.loaded_at desc
        ) as employee_version_rank
    from {{ ref('dim_employee') }} as employee
    cross join parameters
    where employee.employee_id <> '__UNKNOWN__'
        and cast(employee.valid_from as date) <= parameters.snapshot_date
        and (
            employee.valid_to is null
            or cast(employee.valid_to as date) >= parameters.snapshot_date
        )
)

select
    {{ generate_surrogate_key(['snapshot_date', 'employee_id']) }} as employee_snapshot_sk,
    snapshot_date,
    employee_sk,
    employee_id,
    department_sk,
    department_id,
    legal_entity_id,
    job_id,
    job_level,
    location_id,
    cost_center_id,
    manager_employee_id,
    employment_status,
    employment_type,
    worker_category,
    work_arrangement,
    gender,
    hire_date,
    termination_date,
    case
        when hire_date <= snapshot_date
            and (termination_date is null or termination_date > snapshot_date)
            and employment_status in ('active', 'leave')
            then 1
        else 0
    end as headcount_count,
    case when employment_status = 'active' then 1 else 0 end as active_employee_count,
    case when employment_status = 'leave' then 1 else 0 end as leave_employee_count,
    case when employment_status in ('terminated', 'inactive') then 1 else 0 end
        as inactive_employee_count,
    greatest(
        0,
        {{ datediff_days(
            'hire_date',
            "case when termination_date is not null and termination_date < snapshot_date
                then termination_date else snapshot_date end"
        ) }}
    ) as tenure_days,
    record_hash as employee_record_hash,
    cast(current_timestamp as timestamp) as loaded_at
from eligible_versions
where employee_version_rank = 1
