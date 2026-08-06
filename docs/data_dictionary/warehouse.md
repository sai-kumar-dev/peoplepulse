# Warehouse data dictionary

All technical timestamps are UTC. Business dates remain date-valued and are
interpreted in the employing legal entity's reporting calendar where required.

## Raw layer

| Asset | Grain | Owner | Classification | Important columns |
|---|---|---|---|---|
| `raw_hris.departments` | One source department version per batch | Data engineering | Internal | `department_id`, `department_name`, `parent_department_id`, `_batch_id`, `_ingested_at` |
| `raw_hris.employees` | One source employee version per batch/update | Data engineering | Restricted PII | `employee_id`, lifecycle/dimension keys, names/contact/DOB, `updated_at`, `_batch_id` |
| `raw_hris.hires` | One hire/rehire event per batch | Data engineering | Confidential | `hire_event_id`, `employee_id`, `hire_date`, `hire_type`, organizational keys |
| `raw_hris.terminations` | One termination event per batch | Data engineering | Confidential | `termination_event_id`, `employee_id`, `termination_date`, `termination_type`, `voluntary_flag` |

`_batch_id` links to `audit.pipeline_batch`; `_ingested_at` measures technical
freshness. Raw names, email, phone, birth date, and identifiers are never
analyst-facing.

## Core dimensions

| Asset | Grain | Owner | Classification | Description |
|---|---|---|---|---|
| `core.dim_employee` | One effective-dated version of an employee | People analytics engineering | Confidential | SCD2 organizational/employment history |
| `core.dim_department` | One department business key | People analytics engineering | Internal | Conformed department attributes |

### `core.dim_employee`

| Column | Meaning | Sensitivity / caveat |
|---|---|---|
| `employee_sk` | Deterministic warehouse surrogate key | Confidential; not a source identifier |
| `employee_id` | HRIS business key | Confidential; restricted views should tokenize/exclude |
| `department_id` | Effective department assignment | Internal |
| `manager_employee_id` | Effective manager business key | Confidential |
| `job_id`, `job_level` | Effective role and level | Confidential at employee grain |
| `location_id` | Effective work location | Confidential at employee grain |
| `employment_status` | Effective active/inactive status | Confidential at employee grain |
| `valid_from` | Inclusive business-effective start | Required |
| `valid_to` | Exclusive business-effective end, null/current sentinel for current | Use half-open point-in-time predicates |
| `is_current` | True for the only open version | Tested for one current row per business key |
| `record_hash` | Hash of tracked SCD attributes | Not an anonymization of the row |
| `loaded_at` | Technical UTC model timestamp | Freshness only |
| `source_system` | Originating system | Currently `hris` |

Tracked attributes are department, manager, job, job level, location, and
employment status. Source contact fields are deliberately absent from analytics
marts.

## Core facts

| Asset | Grain | Owner | Classification | Additive measures |
|---|---|---|---|---|
| `core.fact_hire` | One hire or rehire event | People analytics | Confidential | `hire_count` |
| `core.fact_termination` | One termination event | People analytics | Confidential | `termination_count`, `voluntary_termination_count` |
| `core.fact_employee_snapshot` | One employee per snapshot month | People analytics | Confidential | `headcount`, `active_count` |

Facts resolve the dimension version effective on the event/snapshot date.
Unknown or late dimensions use a documented unknown key and are repaired on a
subsequent run.

## Analytics marts

| Asset | Grain | Refresh | Owner | Classification | Definition |
|---|---|---|---|---|---|
| `marts.mart_headcount` | Month × department × location × level × employment type | Daily | People analytics | Internal | Month-end active headcount and hires |
| `marts.mart_attrition` | Month × department × termination type | Daily | People analytics | Internal | Terminations and attrition rate |
| `marts.mart_workforce_summary` | Latest published month | Daily | People analytics | Internal | Executive KPI row |
| `marts.mart_data_quality_summary` | Quality run/status/severity | Per pipeline | Data engineering | Internal | Passed, warned, failed check counts |
| `marts.mart_pipeline_health` | Pipeline run | Per pipeline | Data engineering | Internal | Status, counts, freshness, duration |

Headcount is the number of active employees at month end. Attrition rate uses
terminations divided by average opening/closing headcount for the reporting
window; consumers must not sum rates across dimensions. If a denominator is
zero, the rate is null rather than infinity.

## Audit and governance

| Asset | Grain | Retention | Classification |
|---|---|---|---|
| `audit.pipeline_batch` | One entity load within a pipeline batch | 400 days | Internal |
| `audit.dead_letter_record` | One rejected source record | 90 days pending, policy review thereafter | Restricted PII |
| `audit.data_quality_result` | One check result per run | 400 days | Internal |
| `audit.sensitive_access_event` | One access decision | 400 days | Confidential |
| `governance.data_catalog` | One governed asset | Current + audit history | Internal |

