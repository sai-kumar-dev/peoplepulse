with source_records as (
    select
        {{ normalize_text('hire_event_id') }} as hire_event_id,
        {{ normalize_text('employee_id') }} as employee_id,
        {{ safe_date('hire_date') }} as hire_date,
        case
            when {{ normalize_code('hire_type') }} in (
                'external', 'new_hire', 'rehire', 'conversion', 'acquisition'
            )
                then {{ normalize_code('hire_type') }}
            else 'unknown'
        end as hire_type,
        {{ normalize_text('department_id') }} as department_id,
        {{ normalize_text('job_id') }} as job_id,
        {{ normalize_text('location_id') }} as location_id,
        {{ normalize_text('requisition_id') }} as requisition_id,
        {{ safe_timestamp('created_at') }} as created_at,
        {{ safe_timestamp('updated_at') }} as updated_at,
        coalesce({{ normalize_code('source_system') }}, 'hris') as source_system,
        {{ safe_timestamp('_ingested_at') }} as ingested_at,
        {{ normalize_text('_batch_id') }} as batch_id
    from {{ source('hris', 'hires') }}
),

ranked_deliveries as (
    select
        *,
        row_number() over (
            partition by hire_event_id, employee_id, hire_date
            order by ingested_at desc, coalesce(updated_at, created_at) desc, batch_id desc
        ) as delivery_rank
    from source_records
)

select
    hire_event_id,
    employee_id,
    hire_date,
    hire_type,
    department_id,
    job_id,
    location_id,
    requisition_id,
    created_at,
    updated_at,
    source_system,
    ingested_at,
    batch_id,
    {{ generate_surrogate_key([
        'hire_event_id',
        'employee_id',
        'hire_date',
        'hire_type',
        'department_id',
        'job_id',
        'location_id',
        'requisition_id'
    ]) }} as source_record_hash,
    hire_event_id is not null
        and employee_id is not null
        and hire_date is not null
        and hire_date <= cast(current_timestamp as date)
        as is_valid_record
from ranked_deliveries
where delivery_rank = 1
