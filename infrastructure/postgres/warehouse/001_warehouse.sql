CREATE SCHEMA IF NOT EXISTS raw_hris;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS governance;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.pipeline_batch (
    batch_id UUID PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    source_name TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    extracted_count BIGINT NOT NULL DEFAULT 0,
    loaded_count BIGINT NOT NULL DEFAULT 0,
    rejected_count BIGINT NOT NULL DEFAULT 0,
    duplicate_count BIGINT NOT NULL DEFAULT 0,
    checksum TEXT,
    checkpoint_value TEXT,
    error_code TEXT,
    error_message TEXT,
    CONSTRAINT ck_pipeline_batch_status
        CHECK (status IN ('started', 'completed', 'completed_with_warnings', 'failed'))
);

CREATE TABLE IF NOT EXISTS audit.dead_letter_record (
    rejection_id UUID PRIMARY KEY,
    batch_id UUID NOT NULL REFERENCES audit.pipeline_batch(batch_id),
    source_identifier TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    payload_encrypted_or_redacted JSONB NOT NULL,
    validation_error TEXT NOT NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reprocessing_status TEXT NOT NULL DEFAULT 'pending',
    CONSTRAINT ck_dead_letter_status
        CHECK (reprocessing_status IN ('pending', 'corrected', 'reprocessed', 'discarded'))
);

CREATE TABLE IF NOT EXISTS audit.data_quality_result (
    result_id UUID PRIMARY KEY,
    run_id UUID NOT NULL,
    check_id TEXT NOT NULL,
    check_name TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    observed_value NUMERIC,
    threshold_value NUMERIC,
    safe_message TEXT NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_quality_severity CHECK (severity IN ('info', 'warning', 'critical')),
    CONSTRAINT ck_quality_status CHECK (status IN ('pass', 'warn', 'fail'))
);

CREATE TABLE IF NOT EXISTS audit.sensitive_access_event (
    event_id UUID PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    request_id TEXT,
    outcome TEXT NOT NULL,
    CONSTRAINT ck_access_outcome CHECK (outcome IN ('allowed', 'denied'))
);

CREATE TABLE IF NOT EXISTS governance.data_catalog (
    asset_name TEXT PRIMARY KEY,
    layer TEXT NOT NULL,
    owner_role TEXT NOT NULL,
    classification TEXT NOT NULL,
    retention_days INTEGER NOT NULL,
    description TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_hris.departments (
    department_id TEXT NOT NULL,
    department_name TEXT,
    parent_department_id TEXT,
    cost_center_id TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    source_system TEXT,
    _ingested_at TIMESTAMPTZ NOT NULL,
    _batch_id UUID NOT NULL,
    PRIMARY KEY (department_id, _batch_id)
);

CREATE TABLE IF NOT EXISTS raw_hris.employees (
    employee_id TEXT NOT NULL,
    legal_entity_id TEXT,
    first_name TEXT,
    last_name TEXT,
    preferred_name TEXT,
    date_of_birth DATE,
    gender TEXT,
    email TEXT,
    phone TEXT,
    hire_date DATE,
    termination_date DATE,
    employment_status TEXT,
    employment_type TEXT,
    manager_employee_id TEXT,
    department_id TEXT,
    job_id TEXT,
    job_level TEXT,
    location_id TEXT,
    cost_center_id TEXT,
    worker_category TEXT,
    work_arrangement TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    source_system TEXT,
    _ingested_at TIMESTAMPTZ NOT NULL,
    _batch_id UUID NOT NULL,
    PRIMARY KEY (employee_id, updated_at, _batch_id)
);

CREATE TABLE IF NOT EXISTS raw_hris.hires (
    hire_event_id TEXT NOT NULL,
    employee_id TEXT,
    hire_date DATE,
    hire_type TEXT,
    department_id TEXT,
    job_id TEXT,
    location_id TEXT,
    requisition_id TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    source_system TEXT,
    _ingested_at TIMESTAMPTZ NOT NULL,
    _batch_id UUID NOT NULL,
    PRIMARY KEY (hire_event_id, _batch_id)
);

CREATE TABLE IF NOT EXISTS raw_hris.terminations (
    termination_event_id TEXT NOT NULL,
    employee_id TEXT,
    termination_date DATE,
    termination_type TEXT,
    termination_reason TEXT,
    voluntary_flag BOOLEAN,
    department_id TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    source_system TEXT,
    _ingested_at TIMESTAMPTZ NOT NULL,
    _batch_id UUID NOT NULL,
    PRIMARY KEY (termination_event_id, _batch_id)
);

CREATE INDEX IF NOT EXISTS ix_raw_employee_updated
    ON raw_hris.employees (updated_at, employee_id);
CREATE INDEX IF NOT EXISTS ix_raw_employee_department
    ON raw_hris.employees (department_id, hire_date);
CREATE INDEX IF NOT EXISTS ix_raw_hires_date
    ON raw_hris.hires (hire_date, department_id);
CREATE INDEX IF NOT EXISTS ix_raw_terminations_date
    ON raw_hris.terminations (termination_date, department_id);

INSERT INTO governance.data_catalog (
    asset_name, layer, owner_role, classification, retention_days, description
) VALUES
    ('raw_hris.employees', 'raw', 'data_engineering', 'restricted_pii', 2555,
     'Immutable HRIS employee extracts; direct analyst access is prohibited.'),
    ('core.dim_employee', 'core', 'people_analytics', 'confidential', 2555,
     'Effective-dated employee dimension with masked analytics attributes.'),
    ('marts.mart_headcount', 'mart', 'people_analytics', 'internal', 2555,
     'Aggregated monthly workforce headcount metrics.'),
    ('marts.mart_attrition', 'mart', 'people_analytics', 'internal', 2555,
     'Aggregated monthly attrition metrics.')
ON CONFLICT (asset_name) DO NOTHING;

