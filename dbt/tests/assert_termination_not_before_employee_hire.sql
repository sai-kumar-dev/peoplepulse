select
    termination_sk,
    employee_id,
    termination_date,
    tenure_days_at_termination
from {{ ref('fact_termination') }}
where tenure_days_at_termination < 0

