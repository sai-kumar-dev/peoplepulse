select
    department_sk,
    department_id,
    parent_department_id
from {{ ref('dim_department') }}
where department_id = parent_department_id
    and department_id <> '__UNKNOWN__'

