"""Stable, safe error types for APIs and data pipelines."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_SCHEMA_INVALID = "SOURCE_SCHEMA_INVALID"
    SCHEMA_DRIFT_DETECTED = "SCHEMA_DRIFT_DETECTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    LOAD_FAILED = "LOAD_FAILED"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    CHECKPOINT_FAILED = "CHECKPOINT_FAILED"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"


class PeoplePulseError(RuntimeError):
    """Pipeline error that separates a safe message from the technical cause."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool = False,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.context = context or {}
        self.__cause__ = cause

    def as_dict(self) -> dict[str, Any]:
        """Return fields safe for logs; causes and source payloads are excluded."""
        return {
            "error_code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "context": self.context,
        }
