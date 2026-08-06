"""Data-quality checks and execution policy."""

from peoplepulse.quality.checks import (
    CheckResult,
    CheckStatus,
    Severity,
    check_duplicate_rate,
    check_employment_dates,
    check_not_null,
    check_reconciliation,
    check_references,
    check_unique,
    check_volume_change,
)
from peoplepulse.quality.runner import QualityGateError, QualityRunner

__all__ = [
    "CheckResult",
    "CheckStatus",
    "QualityGateError",
    "QualityRunner",
    "Severity",
    "check_duplicate_rate",
    "check_employment_dates",
    "check_not_null",
    "check_reconciliation",
    "check_references",
    "check_unique",
    "check_volume_change",
]
