with ranked_current_versions as (
    select
        *,
        row_number() over (
            partition by employee_id
            order by valid_from desc, loaded_at desc, record_hash desc
        ) as current_rank
    from {{ ref('int_employee_history') }}
    where is_current
)

select
    employee_id,
    legal_entity_id,
    first_name,
    last_name,
    preferred_name,
    date_of_birth,
    gender,
    email,
    phone,
    hire_date,
    termination_date,
    employment_status,
    employment_type,
    manager_employee_id,
    department_id,
    job_id,
    job_level,
    location_id,
    cost_center_id,
    worker_category,
    work_arrangement,
    valid_from,
    record_hash,
    source_system,
    loaded_at,
    batch_id,
    is_valid_employment_dates,
    is_valid_employment_status,
    is_valid_employment_type
from ranked_current_versions
where current_rank = 1

