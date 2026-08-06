with source_records as (
    select
        {{ normalize_text('termination_event_id') }} as termination_event_id,
        {{ normalize_text('employee_id') }} as employee_id,
        {{ safe_date('termination_date') }} as termination_date,
        case
            when {{ normalize_code('termination_type') }} in ('voluntary', 'involuntary', 'retirement', 'other')
                then {{ normalize_code('termination_type') }}
            else 'unknown'
        end as termination_type,
        {{ normalize_text('termination_reason') }} as termination_reason,
        {{ normalized_boolean('voluntary_flag') }} as is_voluntary,
        {{ normalize_text('department_id') }} as department_id,
        {{ safe_timestamp('created_at') }} as created_at,
        {{ safe_timestamp('updated_at') }} as updated_at,
        coalesce({{ normalize_code('source_system') }}, 'hris') as source_system,
        {{ safe_timestamp('_ingested_at') }} as ingested_at,
        {{ normalize_text('_batch_id') }} as batch_id
    from {{ source('hris', 'terminations') }}
),

ranked_deliveries as (
    select
        *,
        row_number() over (
            partition by termination_event_id, employee_id, termination_date
            order by ingested_at desc, coalesce(updated_at, created_at) desc, batch_id desc
        ) as delivery_rank
    from source_records
)

select
    termination_event_id,
    employee_id,
    termination_date,
    termination_type,
    termination_reason,
    coalesce(is_voluntary, termination_type = 'voluntary') as is_voluntary,
    department_id,
    created_at,
    updated_at,
    source_system,
    ingested_at,
    batch_id,
    {{ generate_surrogate_key([
        'termination_event_id',
        'employee_id',
        'termination_date',
        'termination_type',
        'termination_reason',
        'is_voluntary',
        'department_id'
    ]) }} as source_record_hash,
    termination_event_id is not null
        and employee_id is not null
        and termination_date is not null
        as is_valid_record
from ranked_deliveries
where delivery_rank = 1

