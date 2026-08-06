select
    employee_snapshot_sk,
    employee_id,
    snapshot_date,
    hire_date,
    termination_date,
    employment_status,
    headcount_count
from {{ ref('fact_employee_snapshot') }}
where headcount_count = 1
    and (
        hire_date > snapshot_date
        or termination_date <= snapshot_date
        or employment_status not in ('active', 'leave')
    )

