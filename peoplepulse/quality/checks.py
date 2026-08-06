"""Composable checks that operate on PII-opaque record mappings."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CheckStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Safe aggregate outcome; failing row payloads are deliberately excluded."""

    check_id: str
    check_name: str
    entity_name: str
    severity: Severity
    status: CheckStatus
    observed_value: float
    threshold_value: float
    safe_message: str
    measured_at: datetime

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["severity"] = self.severity.value
        value["status"] = self.status.value
        value["measured_at"] = self.measured_at.isoformat()
        return value


def _result(
    *,
    name: str,
    entity: str,
    severity: Severity,
    passed: bool,
    observed: float,
    threshold: float,
    message: str,
) -> CheckResult:
    status = (
        CheckStatus.PASS
        if passed
        else (CheckStatus.FAIL if severity is Severity.CRITICAL else CheckStatus.WARN)
    )
    return CheckResult(
        check_id=f"{name}:{uuid4().hex[:12]}",
        check_name=name,
        entity_name=entity,
        severity=severity,
        status=status,
        observed_value=observed,
        threshold_value=threshold,
        safe_message=message,
        measured_at=datetime.now(UTC),
    )


def check_not_null(
    records: Sequence[Mapping[str, Any]],
    *,
    entity: str,
    field: str,
    severity: Severity = Severity.CRITICAL,
) -> CheckResult:
    missing = sum(record.get(field) in (None, "") for record in records)
    return _result(
        name=f"not_null_{field}",
        entity=entity,
        severity=severity,
        passed=missing == 0,
        observed=float(missing),
        threshold=0.0,
        message=f"{missing} of {len(records)} records have a missing {field}.",
    )


def check_unique(
    records: Sequence[Mapping[str, Any]],
    *,
    entity: str,
    field: str,
    severity: Severity = Severity.CRITICAL,
) -> CheckResult:
    values = [record.get(field) for record in records if record.get(field) not in (None, "")]
    duplicates = sum(count - 1 for count in Counter(values).values() if count > 1)
    return _result(
        name=f"unique_{field}",
        entity=entity,
        severity=severity,
        passed=duplicates == 0,
        observed=float(duplicates),
        threshold=0.0,
        message=f"{duplicates} duplicate business keys detected in {entity}.",
    )


def check_references(
    records: Sequence[Mapping[str, Any]],
    *,
    entity: str,
    foreign_key: str,
    valid_keys: Iterable[Any],
    severity: Severity = Severity.CRITICAL,
) -> CheckResult:
    allowed = set(valid_keys)
    invalid = sum(
        record.get(foreign_key) not in allowed
        for record in records
        if record.get(foreign_key) not in (None, "")
    )
    return _result(
        name=f"relationships_{foreign_key}",
        entity=entity,
        severity=severity,
        passed=invalid == 0,
        observed=float(invalid),
        threshold=0.0,
        message=f"{invalid} records have an unknown {foreign_key}.",
    )


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def check_employment_dates(
    records: Sequence[Mapping[str, Any]],
    *,
    entity: str = "employees",
    as_of: date | None = None,
) -> CheckResult:
    today = as_of or datetime.now(UTC).date()
    invalid = 0
    for record in records:
        hire_date = _parse_date(record.get("hire_date"))
        termination_date = _parse_date(record.get("termination_date"))
        invalid_range = (
            hire_date is not None and termination_date is not None and termination_date < hire_date
        )
        if hire_date is None or hire_date > today or invalid_range:
            invalid += 1
    return _result(
        name="valid_employment_dates",
        entity=entity,
        severity=Severity.CRITICAL,
        passed=invalid == 0,
        observed=float(invalid),
        threshold=0.0,
        message=f"{invalid} records violate employment date rules.",
    )


def check_duplicate_rate(
    *,
    entity: str,
    total_count: int,
    duplicate_count: int,
    warning_threshold: float = 0.01,
) -> CheckResult:
    rate = duplicate_count / total_count if total_count else 0.0
    return _result(
        name="duplicate_rate",
        entity=entity,
        severity=Severity.WARNING,
        passed=rate <= warning_threshold,
        observed=rate,
        threshold=warning_threshold,
        message=f"Duplicate rate is {rate:.2%}; warning threshold is {warning_threshold:.2%}.",
    )


def check_volume_change(
    *,
    entity: str,
    current_count: int,
    previous_count: int,
    maximum_change: float = 0.30,
) -> CheckResult:
    change = (
        abs(current_count - previous_count) / previous_count
        if previous_count
        else (0.0 if current_count == 0 else 1.0)
    )
    return _result(
        name="volume_change",
        entity=entity,
        severity=Severity.WARNING,
        passed=change <= maximum_change,
        observed=change,
        threshold=maximum_change,
        message=f"Volume changed by {change:.2%}; warning threshold is {maximum_change:.2%}.",
    )


def check_reconciliation(
    *,
    entity: str,
    extracted_count: int,
    loaded_count: int,
    rejected_count: int,
    duplicate_count: int = 0,
) -> CheckResult:
    accounted_for = loaded_count + rejected_count + duplicate_count
    difference = extracted_count - accounted_for
    return _result(
        name="source_target_reconciliation",
        entity=entity,
        severity=Severity.CRITICAL,
        passed=difference == 0,
        observed=float(difference),
        threshold=0.0,
        message=(
            f"Extracted {extracted_count}; accounted for {accounted_for}; difference {difference}."
        ),
    )
