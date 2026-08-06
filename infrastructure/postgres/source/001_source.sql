CREATE SCHEMA IF NOT EXISTS hris;

CREATE TABLE IF NOT EXISTS hris.departments (
    department_id TEXT PRIMARY KEY,
    department_name TEXT NOT NULL,
    parent_department_id TEXT,
    cost_center_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    source_system TEXT NOT NULL DEFAULT 'hris'
);

CREATE TABLE IF NOT EXISTS hris.employees (
    employee_id TEXT PRIMARY KEY,
    legal_entity_id TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    preferred_name TEXT,
    date_of_birth DATE NOT NULL,
    gender TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    hire_date DATE NOT NULL,
    termination_date DATE,
    employment_status TEXT NOT NULL,
    employment_type TEXT NOT NULL,
    manager_employee_id TEXT,
    department_id TEXT,
    job_id TEXT NOT NULL,
    job_level TEXT NOT NULL,
    location_id TEXT NOT NULL,
    cost_center_id TEXT NOT NULL,
    worker_category TEXT NOT NULL,
    work_arrangement TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    source_system TEXT NOT NULL DEFAULT 'hris'
);

CREATE INDEX IF NOT EXISTS ix_source_employee_updated
    ON hris.employees (updated_at, employee_id);
CREATE INDEX IF NOT EXISTS ix_source_employee_department
    ON hris.employees (department_id);

