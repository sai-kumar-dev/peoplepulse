{{ config(
    materialized='incremental',
    unique_key='department_sk',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns'
) }}

with ranked_departments as (
    select
        *,
        row_number() over (
            partition by department_id
            order by coalesce(updated_at, created_at, ingested_at) desc, ingested_at desc
        ) as current_rank
    from {{ ref('stg_hris__departments') }}
    where department_id is not null
),

current_departments as (
    select
        {{ generate_surrogate_key(['department_id']) }} as department_sk,
        department_id,
        department_name,
        parent_department_id,
        cost_center_id,
        source_record_hash as record_hash,
        source_system,
        ingested_at as loaded_at,
        batch_id,
        is_valid_record
    from ranked_departments
    where current_rank = 1
),

unknown_department as (
    select
        {{ unknown_surrogate_key() }} as department_sk,
        cast('__UNKNOWN__' as {{ dbt.type_string() }}) as department_id,
        cast('Unknown department' as {{ dbt.type_string() }}) as department_name,
        cast(null as {{ dbt.type_string() }}) as parent_department_id,
        cast(null as {{ dbt.type_string() }}) as cost_center_id,
        {{ unknown_surrogate_key() }} as record_hash,
        cast('system' as {{ dbt.type_string() }}) as source_system,
        cast(current_timestamp as timestamp) as loaded_at,
        cast('__SYSTEM__' as {{ dbt.type_string() }}) as batch_id,
        true as is_valid_record
)

select * from current_departments
union all
select * from unknown_department

