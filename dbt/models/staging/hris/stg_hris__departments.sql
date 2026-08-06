with source_records as (
    select
        {{ normalize_text('department_id') }} as department_id,
        {{ normalize_text('department_name') }} as department_name,
        {{ normalize_text('parent_department_id') }} as parent_department_id,
        {{ normalize_text('cost_center_id') }} as cost_center_id,
        {{ safe_timestamp('created_at') }} as created_at,
        {{ safe_timestamp('updated_at') }} as updated_at,
        coalesce({{ normalize_code('source_system') }}, 'hris') as source_system,
        {{ safe_timestamp('_ingested_at') }} as ingested_at,
        {{ normalize_text('_batch_id') }} as batch_id
    from {{ source('hris', 'departments') }}
),

ranked_deliveries as (
    select
        *,
        row_number() over (
            partition by department_id, coalesce(updated_at, created_at)
            order by ingested_at desc, batch_id desc
        ) as delivery_rank
    from source_records
),

deduplicated as (
    select *
    from ranked_deliveries
    where delivery_rank = 1
)

select
    department_id,
    department_name,
    parent_department_id,
    cost_center_id,
    created_at,
    updated_at,
    source_system,
    ingested_at,
    batch_id,
    {{ generate_surrogate_key([
        'department_id',
        'department_name',
        'parent_department_id',
        'cost_center_id'
    ]) }} as source_record_hash,
    department_id is not null and department_name is not null as is_valid_record
from deduplicated

