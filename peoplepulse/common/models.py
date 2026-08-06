"""Typed records shared by ingestion, orchestration, and observability."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

type Record = Mapping[str, Any]


def utc_now() -> datetime:
    return datetime.now(UTC)


class BatchStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    COMPLETED_WITH_REJECTIONS = "completed_with_rejections"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    data_type: str = "string"
    nullable: bool = True
    pii: bool = False
    description: str = ""
    accepted_values: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceSchema:
    entity_name: str
    fields: tuple[FieldSpec, ...]
    version: str = "1"
    business_key: tuple[str, ...] = ()

    @property
    def field_map(self) -> dict[str, FieldSpec]:
        return {item.name: item for item in self.fields}

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields)


@dataclass(frozen=True, slots=True)
class ExtractionContext:
    batch_id: str
    source_name: str
    entity_name: str
    since: Any | None = None
    limit: int | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Checkpoint:
    source_name: str
    entity_name: str
    value: Any
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class LoadContext:
    batch_id: str
    pipeline_name: str
    source_name: str
    entity_name: str
    started_at: datetime = field(default_factory=utc_now)
    checkpoint_value: str | None = None


@dataclass(slots=True)
class BatchMetadata:
    batch_id: str
    pipeline_name: str
    source_name: str
    entity_name: str
    started_at: datetime
    completed_at: datetime | None = None
    status: BatchStatus = BatchStatus.STARTED
    extracted_count: int = 0
    loaded_count: int = 0
    rejected_count: int = 0
    duplicate_count: int = 0
    checksum: str = ""
    checkpoint_value: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...] = ()

    @classmethod
    def success(cls) -> ValidationResult:
        return cls(valid=True)


@dataclass(frozen=True, slots=True)
class SchemaDrift:
    added_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    type_changes: Mapping[str, tuple[str, str]] = field(default_factory=dict)

    @property
    def detected(self) -> bool:
        return bool(self.added_fields or self.missing_fields or self.type_changes)


@dataclass(slots=True)
class DeadLetterRecord:
    dead_letter_id: str
    payload: Mapping[str, Any]
    source_identifier: str
    validation_error: str
    batch_id: str
    rejected_at: datetime = field(default_factory=utc_now)
    reprocessing_status: str = "pending"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    matched: bool
    extracted_count: int
    accounted_count: int
    difference: int
    message: str


@dataclass(frozen=True, slots=True)
class LoadResult:
    metadata: BatchMetadata
    dead_letters: tuple[DeadLetterRecord, ...] = ()
    reconciliation: ReconciliationResult | None = None
