with termination_versions as (
    select
        term.termination_event_id,
        term.employee_id,
        term.termination_date,
        term.termination_type,
        term.termination_reason,
        term.is_voluntary,
        coalesce(term.department_id, employee.department_id) as department_id,
        employee.hire_date,
        employee.job_id,
        employee.job_level,
        employee.location_id,
        employee.employment_type,
        term.source_system,
        term.ingested_at,
        term.batch_id,
        term.source_record_hash,
        term.is_valid_record,
        row_number() over (
            partition by term.termination_event_id
            order by employee.valid_from desc nulls last
        ) as employee_version_rank
    from {{ ref('stg_hris__terminations') }} as term
    left join {{ ref('int_employee_history') }} as employee
        on term.employee_id = employee.employee_id
        and cast(term.termination_date as timestamp) >= employee.valid_from
        and (
            employee.valid_to is null
            or cast(term.termination_date as timestamp) < employee.valid_to
        )
)

select
    termination_event_id,
    employee_id,
    termination_date,
    termination_type,
    termination_reason,
    is_voluntary,
    department_id,
    hire_date,
    job_id,
    job_level,
    location_id,
    employment_type,
    case
        when hire_date is not null and termination_date >= hire_date
            then {{ datediff_days('hire_date', 'termination_date') }}
        else null
    end as tenure_days_at_termination,
    source_system,
    ingested_at,
    batch_id,
    source_record_hash,
    is_valid_record
from termination_versions
where employee_version_rank = 1

