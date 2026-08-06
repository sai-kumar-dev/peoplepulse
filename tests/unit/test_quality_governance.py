from datetime import date
from pathlib import Path

import pytest

from peoplepulse.governance import AccessRole, mask_record
from peoplepulse.quality import (
    CheckStatus,
    QualityGateError,
    QualityRunner,
    check_duplicate_rate,
    check_employment_dates,
    check_not_null,
    check_reconciliation,
    check_references,
    check_unique,
    check_volume_change,
)


def test_core_quality_checks_cover_valid_and_invalid_records() -> None:
    records = [
        {"employee_id": "E1", "department_id": "D1", "hire_date": "2024-01-01"},
        {"employee_id": "E2", "department_id": "MISSING", "hire_date": "2024-02-01"},
    ]
    assert check_not_null(records, entity="employees", field="employee_id").status == "pass"
    assert check_unique(records, entity="employees", field="employee_id").status == "pass"
    relationship = check_references(
        records,
        entity="employees",
        foreign_key="department_id",
        valid_keys={"D1"},
    )
    assert relationship.status == "fail"
    assert relationship.observed_value == 1
    assert check_employment_dates(records, as_of=date(2026, 1, 1)).status == "pass"


def test_date_rules_and_aggregate_thresholds() -> None:
    invalid = [
        {"employee_id": "E1", "hire_date": "2027-01-01"},
        {
            "employee_id": "E2",
            "hire_date": "2025-01-02",
            "termination_date": "2025-01-01",
        },
    ]
    result = check_employment_dates(invalid, as_of=date(2026, 1, 1))
    assert result.status == CheckStatus.FAIL
    assert result.observed_value == 2
    assert (
        check_duplicate_rate(
            entity="employees", total_count=100, duplicate_count=2, warning_threshold=0.01
        ).status
        == "warn"
    )
    assert (
        check_volume_change(
            entity="employees", current_count=125, previous_count=100, maximum_change=0.30
        ).status
        == "pass"
    )
    assert (
        check_reconciliation(
            entity="employees",
            extracted_count=10,
            loaded_count=8,
            rejected_count=1,
            duplicate_count=1,
        ).status
        == "pass"
    )


def test_quality_runner_persists_before_failing(tmp_path: Path) -> None:
    result = check_reconciliation(
        entity="employees",
        extracted_count=10,
        loaded_count=8,
        rejected_count=1,
    )
    output = tmp_path / "quality.json"
    with pytest.raises(QualityGateError):
        QualityRunner(output).evaluate([result])
    assert output.exists()
    assert "source_target_reconciliation" in output.read_text(encoding="utf-8")


def test_masking_never_exposes_pii_to_analysts() -> None:
    record = {
        "employee_id": "E100",
        "first_name": "Synthetic",
        "email": "synthetic@example.test",
        "department_id": "D1",
        "base_salary": 100_000,
    }
    masked = mask_record(record, role=AccessRole.ANALYST)
    assert masked["first_name"] == "***"
    assert masked["email"] == "***@example.test"
    assert masked["employee_id"].startswith("person_")
    assert masked["base_salary"] == "[restricted]"
    assert masked["department_id"] == "D1"
    assert mask_record(record, role=AccessRole.HR_RESTRICTED) == record
