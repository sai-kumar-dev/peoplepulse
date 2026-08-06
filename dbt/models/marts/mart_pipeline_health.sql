with source_loads as (
    select
        'hris' as source_name,
        'departments' as entity_name,
        max(ingested_at) as latest_ingested_at,
        count(*) as staged_record_count,
        count(distinct batch_id) as observed_batch_count
    from {{ ref('stg_hris__departments') }}

    union all

    select
        'hris',
        'employees',
        max(ingested_at),
        count(*),
        count(distinct batch_id)
    from {{ ref('stg_hris__employees') }}

    union all

    select
        'hris',
        'hires',
        max(ingested_at),
        count(*),
        count(distinct batch_id)
    from {{ ref('stg_hris__hires') }}

    union all

    select
        'hris',
        'terminations',
        max(ingested_at),
        count(*),
        count(distinct batch_id)
    from {{ ref('stg_hris__terminations') }}
),

health_metrics as (
    select
        *,
        {{ datediff_hours('latest_ingested_at', 'current_timestamp') }} as freshness_lag_hours
    from source_loads
)

select
    source_name,
    entity_name,
    latest_ingested_at,
    freshness_lag_hours,
    staged_record_count,
    observed_batch_count,
    case
        when latest_ingested_at is null then 'unavailable'
        when freshness_lag_hours > {{ var('pipeline_freshness_error_hours', 48) }} then 'failed'
        when freshness_lag_hours > {{ var('pipeline_freshness_warn_hours', 24) }} then 'warning'
        else 'healthy'
    end as health_status,
    cast(current_timestamp as timestamp) as evaluated_at
from health_metrics

