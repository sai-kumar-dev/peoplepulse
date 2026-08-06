from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from peoplepulse.errors import ErrorCode, PeoplePulseError
from peoplepulse.governance import AccessRole, mask_record
from peoplepulse.observability import metrics
from peoplepulse.quality import (
    CheckStatus,
    QualityRunner,
    Severity,
    check_duplicate_rate,
    check_employment_dates,
    check_not_null,
    check_reconciliation,
    check_unique,
    check_volume_change,
)
from peoplepulse.quality.cli import main as quality_main


def _write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_platform_error_is_safe_and_rfc7807_compatible() -> None:
    error = PeoplePulseError(
        code=ErrorCode.SOURCE_UNAVAILABLE,
        summary="Source unavailable",
        detail="The configured source did not respond.",
        retryable=True,
        run_id="run-safe-1",
    )
    assert str(error) == "SOURCE_UNAVAILABLE: Source unavailable"
    problem = error.to_problem(request_id="request-safe-1", status=503)
    assert problem == {
        "type": "https://peoplepulse.local/problems/source_unavailable",
        "title": "Source unavailable",
        "status": 503,
        "detail": "The configured source did not respond.",
        "code": ErrorCode.SOURCE_UNAVAILABLE,
        "request_id": "request-safe-1",
        "retryable": True,
        "run_id": "run-safe-1",
    }


def test_quality_edge_cases_do_not_divide_by_zero_or_leak_rows(tmp_path: Path) -> None:
    missing = check_not_null(
        [{"employee_id": None}, {"employee_id": ""}],
        entity="employees",
        field="employee_id",
        severity=Severity.WARNING,
    )
    assert missing.status is CheckStatus.WARN
    assert missing.observed_value == 2
    assert (
        check_unique(
            [{"employee_id": "E1"}, {"employee_id": "E1"}, {"employee_id": ""}],
            entity="employees",
            field="employee_id",
        ).observed_value
        == 1
    )
    assert (
        check_duplicate_rate(
            entity="employees",
            total_count=0,
            duplicate_count=0,
        ).status
        is CheckStatus.PASS
    )
    assert (
        check_volume_change(
            entity="employees",
            current_count=0,
            previous_count=0,
        ).observed_value
        == 0
    )
    assert (
        check_volume_change(
            entity="employees",
            current_count=1,
            previous_count=0,
        ).status
        is CheckStatus.WARN
    )
    assert (
        check_reconciliation(
            entity="employees",
            extracted_count=1,
            loaded_count=0,
            rejected_count=0,
        ).status
        is CheckStatus.FAIL
    )

    invalid_dates = check_employment_dates(
        [
            {"hire_date": "not-a-date"},
            {"hire_date": date(2024, 1, 1), "termination_date": "bad-date"},
        ],
        as_of=date(2025, 1, 1),
    )
    assert invalid_dates.observed_value == 1

    output = tmp_path / "non-blocking-quality.json"
    results = QualityRunner(output, run_id="quality-safe-1").evaluate(
        [missing],
        fail_on_critical=False,
    )
    assert results == [missing]
    assert json.loads(output.read_text(encoding="utf-8"))["run_id"] == "quality-safe-1"


def test_quality_cli_passes_clean_source_and_can_persist_allowed_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _write_csv(
        source / "departments.csv",
        [{"department_id": "D1", "department_name": "Engineering"}],
        ["department_id", "department_name"],
    )
    _write_csv(
        source / "employees.csv",
        [
            {
                "employee_id": "E1",
                "department_id": "D1",
                "hire_date": "2024-01-01",
                "termination_date": "",
            }
        ],
        ["employee_id", "department_id", "hire_date", "termination_date"],
    )
    clean_output = tmp_path / "clean.json"
    assert quality_main(["--input-dir", str(source), "--output", str(clean_output)]) == 0
    assert "Quality results written" in capsys.readouterr().out

    _write_csv(
        source / "employees.csv",
        [
            {
                "employee_id": "",
                "department_id": "UNKNOWN",
                "hire_date": "not-a-date",
                "termination_date": "",
            }
        ],
        ["employee_id", "department_id", "hire_date", "termination_date"],
    )
    failed_output = tmp_path / "failed.json"
    assert quality_main(["--input-dir", str(source), "--output", str(failed_output)]) == 1
    assert "Critical data-quality checks failed" in capsys.readouterr().out
    allowed_output = tmp_path / "allowed.json"
    assert (
        quality_main(
            [
                "--input-dir",
                str(source),
                "--output",
                str(allowed_output),
                "--allow-critical",
            ]
        )
        == 0
    )


def test_masking_edge_cases_and_metrics_are_available() -> None:
    masked = mask_record(
        {
            "employee_id": None,
            "email": "invalid-without-domain",
            "first_name": None,
            "department_id": "D1",
        },
        role=AccessRole.EXECUTIVE,
    )
    assert masked == {
        "employee_id": None,
        "email": "***",
        "first_name": None,
        "department_id": "D1",
    }
    metrics.PIPELINE_RUNS.labels(pipeline="test", status="passed").inc()
    metrics.RECORDS_EXTRACTED.labels(source="test", entity="employees").inc(2)
    metrics.RECORDS_LOADED.labels(source="test", entity="employees").inc(2)
    metrics.RECORDS_REJECTED.labels(
        source="test", entity="employees", error_code="VALIDATION_FAILED"
    ).inc()
    metrics.QUALITY_FAILURES.labels(check_name="test", severity="warning").inc()
    metrics.API_REQUESTS.labels(method="GET", route="/test", status="200").inc()
    with metrics.PIPELINE_DURATION.labels(pipeline="test").time():
        pass
    with metrics.API_DURATION.labels(method="GET", route="/test").time():
        pass
