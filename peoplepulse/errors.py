"""Stable, PII-safe error taxonomy shared by services and pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_SCHEMA_INVALID = "SOURCE_SCHEMA_INVALID"
    SCHEMA_DRIFT_DETECTED = "SCHEMA_DRIFT_DETECTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    LOAD_FAILED = "LOAD_FAILED"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    TRANSFORMATION_FAILED = "TRANSFORMATION_FAILED"
    DATA_QUALITY_FAILED = "DATA_QUALITY_FAILED"
    CHECKPOINT_FAILED = "CHECKPOINT_FAILED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_FILTER = "INVALID_FILTER"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"


@dataclass(slots=True)
class PeoplePulseError(Exception):
    """A safe operational error that can cross a service boundary."""

    code: ErrorCode
    summary: str
    detail: str
    retryable: bool = False
    run_id: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.summary}"

    def to_problem(self, *, request_id: str, status: int) -> dict[str, object]:
        """Return RFC 7807-compatible fields without exposing a root payload."""
        return {
            "type": f"https://peoplepulse.local/problems/{self.code.lower()}",
            "title": self.summary,
            "status": status,
            "detail": self.detail,
            "code": self.code,
            "request_id": request_id,
            "retryable": self.retryable,
            "run_id": self.run_id,
        }
