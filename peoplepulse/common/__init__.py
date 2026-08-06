"""Shared, dependency-free contracts used across PeoplePulse."""

from peoplepulse.common.errors import ErrorCode, PeoplePulseError
from peoplepulse.common.hashing import canonical_json, checksum_records, record_hash
from peoplepulse.common.models import (
    BatchMetadata,
    BatchStatus,
    Checkpoint,
    DeadLetterRecord,
    ExtractionContext,
    FieldSpec,
    LoadContext,
    LoadResult,
    ReconciliationResult,
    Record,
    SchemaDrift,
    SourceSchema,
    ValidationIssue,
    ValidationResult,
    utc_now,
)

__all__ = [
    "BatchMetadata",
    "BatchStatus",
    "Checkpoint",
    "DeadLetterRecord",
    "ErrorCode",
    "ExtractionContext",
    "FieldSpec",
    "LoadContext",
    "LoadResult",
    "PeoplePulseError",
    "ReconciliationResult",
    "Record",
    "SchemaDrift",
    "SourceSchema",
    "ValidationIssue",
    "ValidationResult",
    "canonical_json",
    "checksum_records",
    "record_hash",
    "utc_now",
]
