"""Canonical source contracts for the initial HRIS vertical slice."""

from __future__ import annotations

from peoplepulse.common.models import FieldSpec, SourceSchema


def _field(
    name: str,
    data_type: str = "string",
    *,
    nullable: bool = True,
    pii: bool = False,
    accepted_values: tuple[str, ...] = (),
) -> FieldSpec:
    return FieldSpec(
        name=name,
        data_type=data_type,
        nullable=nullable,
        pii=pii,
        accepted_values=accepted_values,
    )


DEPARTMENT_SCHEMA = SourceSchema(
    entity_name="departments",
    business_key=("department_id",),
    fields=(
        _field("department_id", nullable=False),
        _field("department_name", nullable=False),
        _field("parent_department_id"),
        _field("cost_center_id", nullable=False),
        _field("created_at", "datetime", nullable=False),
        _field("updated_at", "datetime", nullable=False),
        _field("source_system", nullable=False),
    ),
)

EMPLOYEE_SCHEMA = SourceSchema(
    entity_name="employees",
    business_key=("employee_id",),
    fields=(
        _field("employee_id", nullable=False),
        _field("legal_entity_id", nullable=False),
        _field("first_name", nullable=False, pii=True),
        _field("last_name", nullable=False, pii=True),
        _field("preferred_name", pii=True),
        _field("date_of_birth", "date", nullable=False, pii=True),
        _field(
            "gender",
            nullable=False,
            pii=True,
            accepted_values=("female", "male", "non_binary", "not_disclosed"),
        ),
        _field("email", nullable=False, pii=True),
        _field("phone", nullable=False, pii=True),
        _field("hire_date", "date", nullable=False),
        _field("termination_date", "date"),
        _field(
            "employment_status",
            nullable=False,
            accepted_values=("active", "terminated", "leave"),
        ),
        _field(
            "employment_type",
            nullable=False,
            accepted_values=("full_time", "part_time", "contractor"),
        ),
        _field("manager_employee_id"),
        _field("department_id", nullable=False),
        _field("job_id", nullable=False),
        _field("job_level", nullable=False),
        _field("location_id", nullable=False),
        _field("cost_center_id", nullable=False),
        _field(
            "worker_category",
            nullable=False,
            accepted_values=("employee", "contingent"),
        ),
        _field(
            "work_arrangement",
            nullable=False,
            accepted_values=("onsite", "hybrid", "remote"),
        ),
        _field("created_at", "datetime", nullable=False),
        _field("updated_at", "datetime", nullable=False),
        _field("source_system", nullable=False),
    ),
)

HIRE_SCHEMA = SourceSchema(
    entity_name="hires",
    business_key=("hire_event_id",),
    fields=(
        _field("hire_event_id", nullable=False),
        _field("employee_id", nullable=False),
        _field("hire_date", "date", nullable=False),
        _field(
            "hire_type",
            nullable=False,
            accepted_values=("external", "rehire", "conversion"),
        ),
        _field("department_id", nullable=False),
        _field("job_id", nullable=False),
        _field("location_id", nullable=False),
        _field("requisition_id"),
        _field("created_at", "datetime", nullable=False),
        _field("updated_at", "datetime", nullable=False),
        _field("source_system", nullable=False),
    ),
)

TERMINATION_SCHEMA = SourceSchema(
    entity_name="terminations",
    business_key=("termination_event_id",),
    fields=(
        _field("termination_event_id", nullable=False),
        _field("employee_id", nullable=False),
        _field("termination_date", "date", nullable=False),
        _field(
            "termination_type",
            nullable=False,
            accepted_values=("voluntary", "involuntary"),
        ),
        _field("termination_reason", nullable=False),
        _field("voluntary_flag", "boolean", nullable=False),
        _field("department_id", nullable=False),
        _field("created_at", "datetime", nullable=False),
        _field("updated_at", "datetime", nullable=False),
        _field("source_system", nullable=False),
    ),
)

SCHEMAS = {
    schema.entity_name: schema
    for schema in (
        DEPARTMENT_SCHEMA,
        EMPLOYEE_SCHEMA,
        HIRE_SCHEMA,
        TERMINATION_SCHEMA,
    )
}

PII_FIELDS = frozenset(
    item.name for schema in SCHEMAS.values() for item in schema.fields if item.pii
)

__all__ = [
    "DEPARTMENT_SCHEMA",
    "EMPLOYEE_SCHEMA",
    "HIRE_SCHEMA",
    "PII_FIELDS",
    "SCHEMAS",
    "TERMINATION_SCHEMA",
]
