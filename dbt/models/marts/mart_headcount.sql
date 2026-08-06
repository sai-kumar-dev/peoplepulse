with snapshot_records as (
    select *
    from {{ ref('fact_employee_snapshot') }}
),

department as (
    select
        department_sk,
        department_name
    from {{ ref('dim_department') }}
)

select
    snapshot_records.snapshot_date,
    snapshot_records.department_sk,
    department.department_name,
    coalesce(snapshot_records.location_id, '__UNKNOWN__') as location_id,
    coalesce(snapshot_records.job_level, 'unknown') as job_level,
    coalesce(snapshot_records.employment_type, 'unknown') as employment_type,
    coalesce(snapshot_records.work_arrangement, 'unknown') as work_arrangement,
    sum(snapshot_records.headcount_count) as headcount,
    sum(snapshot_records.active_employee_count) as active_employees,
    sum(snapshot_records.leave_employee_count) as employees_on_leave,
    sum(snapshot_records.inactive_employee_count) as inactive_employees,
    count(distinct case
        when snapshot_records.headcount_count = 1 then snapshot_records.employee_id
    end) as distinct_employees,
    {{ safe_divide(
        "sum(case when snapshot_records.headcount_count = 1
            then snapshot_records.tenure_days else 0 end)",
        "sum(snapshot_records.headcount_count)"
    ) }} / 365.25 as average_tenure_years,
    max(snapshot_records.loaded_at) as refreshed_at
from snapshot_records
left join department
    on snapshot_records.department_sk = department.department_sk
group by
    snapshot_records.snapshot_date,
    snapshot_records.department_sk,
    department.department_name,
    coalesce(snapshot_records.location_id, '__UNKNOWN__'),
    coalesce(snapshot_records.job_level, 'unknown'),
    coalesce(snapshot_records.employment_type, 'unknown'),
    coalesce(snapshot_records.work_arrangement, 'unknown')

