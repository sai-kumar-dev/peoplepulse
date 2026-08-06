{% snapshot employee_master_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key='employee_id',
        strategy='timestamp',
        updated_at='snapshot_updated_at',
        invalidate_hard_deletes=true
    )
}}

with ranked_source as (
    select
        *,
        row_number() over (
            partition by employee_id
            order by coalesce(updated_at, created_at, _ingested_at) desc, _ingested_at desc, _batch_id desc
        ) as source_rank
    from {{ source('hris', 'employees') }}
    where employee_id is not null
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
    created_at,
    updated_at,
    source_system,
    _ingested_at,
    _batch_id,
    coalesce(updated_at, created_at, _ingested_at) as snapshot_updated_at
from ranked_source
where source_rank = 1

{% endsnapshot %}

