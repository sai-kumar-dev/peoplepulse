with source_records as (
    select
        {{ normalize_text('employee_id') }} as employee_id,
        {{ normalize_text('legal_entity_id') }} as legal_entity_id,
        {{ normalize_text('first_name') }} as first_name,
        {{ normalize_text('last_name') }} as last_name,
        {{ normalize_text('preferred_name') }} as preferred_name,
        {{ safe_date('date_of_birth') }} as date_of_birth,
        case
            when {{ normalize_code('gender') }} in ('f', 'female', 'woman') then 'female'
            when {{ normalize_code('gender') }} in ('m', 'male', 'man') then 'male'
            when {{ normalize_code('gender') }} in ('nonbinary', 'non_binary', 'genderqueer') then 'non_binary'
            when {{ normalize_code('gender') }} in ('not_disclosed', 'prefer_not_to_say') then 'not_disclosed'
            else 'unknown'
        end as gender,
        lower({{ normalize_text('email') }}) as email,
        {{ normalize_text('phone') }} as phone,
        {{ safe_date('hire_date') }} as hire_date,
        {{ safe_date('termination_date') }} as termination_date,
        case
            when {{ normalize_code('employment_status') }} in ('active', 'leave', 'terminated', 'inactive')
                then {{ normalize_code('employment_status') }}
            else 'unknown'
        end as employment_status,
        case
            when {{ normalize_code('employment_type') }} = 'contractor' then 'contract'
            when {{ normalize_code('employment_type') }} in ('full_time', 'part_time', 'contract', 'intern')
                then {{ normalize_code('employment_type') }}
            else 'unknown'
        end as employment_type,
        {{ normalize_text('manager_employee_id') }} as manager_employee_id,
        {{ normalize_text('department_id') }} as department_id,
        {{ normalize_text('job_id') }} as job_id,
        {{ normalize_code('job_level') }} as job_level,
        {{ normalize_text('location_id') }} as location_id,
        {{ normalize_text('cost_center_id') }} as cost_center_id,
        case
            when {{ normalize_code('worker_category') }} in ('employee', 'contractor', 'contingent', 'intern')
                then {{ normalize_code('worker_category') }}
            else 'unknown'
        end as worker_category,
        case
            when {{ normalize_code('work_arrangement') }} = 'onsite' then 'on_site'
            when {{ normalize_code('work_arrangement') }} in ('remote', 'hybrid', 'on_site')
                then {{ normalize_code('work_arrangement') }}
            else 'unknown'
        end as work_arrangement,
        {{ safe_timestamp('created_at') }} as created_at,
        {{ safe_timestamp('updated_at') }} as updated_at,
        coalesce({{ normalize_code('source_system') }}, 'hris') as source_system,
        {{ safe_timestamp('_ingested_at') }} as ingested_at,
        {{ normalize_text('_batch_id') }} as batch_id
    from {{ source('hris', 'employees') }}
),

ranked_deliveries as (
    select
        *,
        row_number() over (
            partition by employee_id, coalesce(updated_at, created_at)
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
    ingested_at,
    batch_id,
    {{ generate_surrogate_key([
        'employee_id',
        'legal_entity_id',
        'first_name',
        'last_name',
        'preferred_name',
        'date_of_birth',
        'gender',
        'email',
        'phone',
        'hire_date',
        'termination_date',
        'employment_status',
        'employment_type',
        'manager_employee_id',
        'department_id',
        'job_id',
        'job_level',
        'location_id',
        'cost_center_id',
        'worker_category',
        'work_arrangement'
    ]) }} as source_record_hash,
    employee_id is not null
        and hire_date is not null
        and (termination_date is null or termination_date >= hire_date)
        as is_valid_employment_dates,
    employment_status <> 'unknown' as is_valid_employment_status,
    employment_type <> 'unknown' as is_valid_employment_type
from deduplicated
