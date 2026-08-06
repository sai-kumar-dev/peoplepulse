{{ config(materialized='view') }}

with normalized_versions as (
    select
        *,
        coalesce(updated_at, created_at, ingested_at) as source_version_at
    from {{ ref('stg_hris__employees') }}
    where employee_id is not null
),

version_starts as (
    select
        *,
        case
            when row_number() over (
                partition by employee_id
                order by source_version_at, ingested_at, source_record_hash
            ) = 1
                and hire_date is not null
                and hire_date < cast(source_version_at as date)
                then cast(hire_date as timestamp)
            else source_version_at
        end as valid_from
    from normalized_versions
),

effective_ranges as (
    select
        *,
        lead(valid_from) over (
            partition by employee_id
            order by valid_from, ingested_at, source_record_hash
        ) as valid_to
    from version_starts
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
    source_version_at,
    valid_from,
    valid_to,
    valid_to is null as is_current,
    source_record_hash as record_hash,
    source_system,
    ingested_at as loaded_at,
    batch_id,
    is_valid_employment_dates,
    is_valid_employment_status,
    is_valid_employment_type
from effective_ranges
