with employee_metrics as (
    select
        count(*) as records_tested,
        coalesce(sum(case when employee_id is null then 1 else 0 end), 0) as null_employee_ids,
        coalesce(sum(case when not is_valid_employment_dates then 1 else 0 end), 0)
            as invalid_employment_dates,
        coalesce(sum(case when not is_valid_employment_status then 1 else 0 end), 0)
            as invalid_employment_statuses,
        coalesce(sum(case when not is_valid_employment_type then 1 else 0 end), 0)
            as invalid_employment_types
    from {{ ref('stg_hris__employees') }}
),

department_metrics as (
    select
        count(*) as records_tested,
        coalesce(sum(case when not is_valid_record then 1 else 0 end), 0) as invalid_records
    from {{ ref('stg_hris__departments') }}
),

hire_metrics as (
    select
        count(*) as records_tested,
        coalesce(sum(case when not is_valid_record then 1 else 0 end), 0) as invalid_records
    from {{ ref('stg_hris__hires') }}
),

termination_metrics as (
    select
        count(*) as records_tested,
        coalesce(sum(case when not is_valid_record then 1 else 0 end), 0) as invalid_records
    from {{ ref('stg_hris__terminations') }}
),

checks as (
    select
        'employees.null_business_key' as check_id,
        'employees' as source_entity,
        'Employee business key is populated' as check_name,
        'critical' as severity,
        records_tested,
        null_employee_ids as failure_count
    from employee_metrics

    union all

    select
        'employees.valid_employment_dates',
        'employees',
        'Termination is not before hire date',
        'critical',
        records_tested,
        invalid_employment_dates
    from employee_metrics

    union all

    select
        'employees.valid_employment_status',
        'employees',
        'Employment status is recognized',
        'warning',
        records_tested,
        invalid_employment_statuses
    from employee_metrics

    union all

    select
        'employees.valid_employment_type',
        'employees',
        'Employment type is recognized',
        'warning',
        records_tested,
        invalid_employment_types
    from employee_metrics

    union all

    select
        'departments.valid_record',
        'departments',
        'Department key and name are populated',
        'critical',
        records_tested,
        invalid_records
    from department_metrics

    union all

    select
        'hires.valid_record',
        'hires',
        'Hire event has valid keys and a non-future date',
        'critical',
        records_tested,
        invalid_records
    from hire_metrics

    union all

    select
        'terminations.valid_record',
        'terminations',
        'Termination event has valid keys and date',
        'critical',
        records_tested,
        invalid_records
    from termination_metrics
)

select
    check_id,
    source_entity,
    check_name,
    severity,
    records_tested,
    failure_count,
    records_tested - failure_count as passed_count,
    coalesce({{ safe_divide('records_tested - failure_count', 'records_tested') }}, 1.0)
        as pass_rate,
    case
        when failure_count = 0 then 'passed'
        when severity = 'critical' then 'failed'
        else 'warning'
    end as check_status,
    cast(current_timestamp as timestamp) as evaluated_at
from checks
