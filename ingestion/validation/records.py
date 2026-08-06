"""Field-level and workforce business-rule validators."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from peoplepulse.common.models import (
    Record,
    SourceSchema,
    ValidationIssue,
    ValidationResult,
)

ValidationRule = Callable[[Record], Iterable[ValidationIssue]]


def _is_null(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _valid_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool) or str(value).lower() in {
            "true",
            "false",
            "0",
            "1",
        }
    if expected == "integer":
        try:
            int(str(value))
        except (TypeError, ValueError):
            return False
        return True
    if expected == "number":
        try:
            Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return True
    if expected == "date":
        try:
            date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return False
        return True
    if expected == "datetime":
        try:
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return False
        return True
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, (list, tuple))
    return True


def _workforce_date_rules(record: Record) -> Iterable[ValidationIssue]:
    hire_raw = record.get("hire_date")
    termination_raw = record.get("termination_date")
    try:
        hire_date = date.fromisoformat(str(hire_raw)) if not _is_null(hire_raw) else None
    except ValueError:
        hire_date = None
    try:
        termination_date = (
            date.fromisoformat(str(termination_raw)) if not _is_null(termination_raw) else None
        )
    except ValueError:
        termination_date = None
    if hire_date and termination_date and termination_date < hire_date:
        yield ValidationIssue(
            field="termination_date",
            code="TERMINATION_BEFORE_HIRE",
            message="termination_date cannot be earlier than hire_date",
        )
    status = record.get("employment_status")
    if status == "terminated" and termination_date is None:
        yield ValidationIssue(
            field="termination_date",
            code="TERMINATION_DATE_REQUIRED",
            message="terminated employees require a termination_date",
        )
    if status == "active" and termination_date is not None:
        yield ValidationIssue(
            field="employment_status",
            code="STATUS_DATE_MISMATCH",
            message="active employees cannot have a termination_date",
        )


@dataclass(frozen=True, slots=True)
class ValidationBatch:
    accepted: tuple[dict[str, Any], ...]
    rejected: tuple[tuple[dict[str, Any], ValidationResult], ...]


class RecordValidator:
    def __init__(
        self,
        schema: SourceSchema,
        *,
        rules: Iterable[ValidationRule] = (),
        known_departments: set[str] | None = None,
        as_of_date: date | None = None,
        reject_unknown_fields: bool = False,
    ) -> None:
        self.schema = schema
        self.rules = tuple(rules)
        self.known_departments = known_departments
        self.as_of_date = as_of_date
        self.reject_unknown_fields = reject_unknown_fields

    def validate(self, record: Record) -> ValidationResult:
        issues: list[ValidationIssue] = []
        field_map = self.schema.field_map
        for field_name, spec in field_map.items():
            value = record.get(field_name)
            if _is_null(value):
                if not spec.nullable:
                    issues.append(
                        ValidationIssue(
                            field=field_name,
                            code="REQUIRED",
                            message=f"{field_name} is required",
                        )
                    )
                continue
            if not _valid_type(value, spec.data_type):
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        code="INVALID_TYPE",
                        message=f"{field_name} must be {spec.data_type}",
                    )
                )
            if spec.accepted_values and value not in spec.accepted_values:
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        code="INVALID_VALUE",
                        message=f"{field_name} has an unaccepted value",
                    )
                )

        if self.reject_unknown_fields:
            for field_name in sorted(set(record) - set(field_map)):
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        code="UNKNOWN_FIELD",
                        message=f"{field_name} is not in schema version {self.schema.version}",
                    )
                )
        if "hire_date" in field_map or "termination_date" in field_map:
            issues.extend(_workforce_date_rules(record))
        if self.as_of_date is not None and not _is_null(record.get("hire_date")):
            try:
                hire_date = date.fromisoformat(str(record["hire_date"]))
            except ValueError:
                pass
            else:
                if hire_date > self.as_of_date:
                    issues.append(
                        ValidationIssue(
                            field="hire_date",
                            code="FUTURE_HIRE_DATE",
                            message="hire_date cannot be later than the batch as-of date",
                        )
                    )
        if (
            self.known_departments is not None
            and not _is_null(record.get("department_id"))
            and str(record["department_id"]) not in self.known_departments
        ):
            issues.append(
                ValidationIssue(
                    field="department_id",
                    code="UNKNOWN_DEPARTMENT",
                    message="department_id does not exist in reference data",
                )
            )
        for rule in self.rules:
            issues.extend(rule(record))
        return ValidationResult(valid=not issues, issues=tuple(issues))


def validate_record(
    record: Record,
    schema: SourceSchema,
    **validator_options: Any,
) -> ValidationResult:
    return RecordValidator(schema, **validator_options).validate(record)


def validate_batch(
    records: Iterable[Record],
    schema: SourceSchema,
    **validator_options: Any,
) -> ValidationBatch:
    validator = RecordValidator(schema, **validator_options)
    accepted: list[dict[str, Any]] = []
    rejected: list[tuple[dict[str, Any], ValidationResult]] = []
    for source_record in records:
        record = dict(source_record)
        result = validator.validate(record)
        if result.valid:
            accepted.append(record)
        else:
            rejected.append((record, result))
    return ValidationBatch(tuple(accepted), tuple(rejected))
