{{ config(
    materialized='incremental',
    unique_key='employee_sk',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns'
) }}

with employee_history as (
    select *
    from {{ ref('int_employee_history') }}
),

resolved_departments as (
    select
        employee_history.*,
        coalesce(department.department_sk, {{ unknown_surrogate_key() }}) as department_sk
    from employee_history
    left join {{ ref('dim_department') }} as department
        on employee_history.department_id = department.department_id
),

employee_versions as (
    select
        {{ generate_surrogate_key(['employee_id', 'source_version_at']) }} as employee_sk,
        employee_id,
        legal_entity_id,
        first_name,
        last_name,
        preferred_name,
        extract(year from date_of_birth) as birth_year,
        gender,
        {{ generate_surrogate_key(['email']) }} as email_hash,
        {{ generate_surrogate_key(['phone']) }} as phone_hash,
        hire_date,
        termination_date,
        employment_status,
        employment_type,
        manager_employee_id,
        department_sk,
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
        is_current,
        record_hash,
        loaded_at,
        source_system,
        batch_id,
        is_valid_employment_dates,
        is_valid_employment_status,
        is_valid_employment_type
    from resolved_departments
),

unknown_employee as (
    select
        {{ unknown_surrogate_key() }} as employee_sk,
        cast('__UNKNOWN__' as {{ dbt.type_string() }}) as employee_id,
        cast(null as {{ dbt.type_string() }}) as legal_entity_id,
        cast('Unknown' as {{ dbt.type_string() }}) as first_name,
        cast('employee' as {{ dbt.type_string() }}) as last_name,
        cast('Unknown' as {{ dbt.type_string() }}) as preferred_name,
        cast(null as integer) as birth_year,
        cast('unknown' as {{ dbt.type_string() }}) as gender,
        {{ unknown_surrogate_key() }} as email_hash,
        {{ unknown_surrogate_key() }} as phone_hash,
        cast(null as date) as hire_date,
        cast(null as date) as termination_date,
        cast('unknown' as {{ dbt.type_string() }}) as employment_status,
        cast('unknown' as {{ dbt.type_string() }}) as employment_type,
        cast(null as {{ dbt.type_string() }}) as manager_employee_id,
        {{ unknown_surrogate_key() }} as department_sk,
        cast('__UNKNOWN__' as {{ dbt.type_string() }}) as department_id,
        cast(null as {{ dbt.type_string() }}) as job_id,
        cast('unknown' as {{ dbt.type_string() }}) as job_level,
        cast(null as {{ dbt.type_string() }}) as location_id,
        cast(null as {{ dbt.type_string() }}) as cost_center_id,
        cast('unknown' as {{ dbt.type_string() }}) as worker_category,
        cast('unknown' as {{ dbt.type_string() }}) as work_arrangement,
        cast('1900-01-01' as timestamp) as source_version_at,
        cast('1900-01-01' as timestamp) as valid_from,
        cast(null as timestamp) as valid_to,
        true as is_current,
        {{ unknown_surrogate_key() }} as record_hash,
        cast(current_timestamp as timestamp) as loaded_at,
        cast('system' as {{ dbt.type_string() }}) as source_system,
        cast('__SYSTEM__' as {{ dbt.type_string() }}) as batch_id,
        true as is_valid_employment_dates,
        true as is_valid_employment_status,
        true as is_valid_employment_type
)

select * from employee_versions
union all
select * from unknown_employee
