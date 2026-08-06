"""Pipeline, data-quality, governance, and admin API contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints

from api.app.schemas.common import ApiModel

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:@/-]+$",
    ),
]


class PipelineStatus(StrEnum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"


class PipelineDefinition(ApiModel):
    pipeline_id: Identifier
    display_name: str
    schedule: str
    owner: str
    enabled: bool
    last_run_status: PipelineStatus | None = None


class PipelineRun(ApiModel):
    run_id: Identifier
    pipeline_id: Identifier
    started_at: datetime
    completed_at: datetime | None = None
    status: PipelineStatus
    duration_seconds: float | None = Field(default=None, ge=0)
    records_loaded: int = Field(default=0, ge=0)
    records_rejected: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_summary: str | None = None


class QualitySeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class QualityStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class DataQualityCheck(ApiModel):
    check_id: Identifier
    check_name: str
    dataset: str
    dimension: str
    severity: QualitySeverity
    status: QualityStatus
    score: float = Field(ge=0, le=100)
    checked_at: datetime
    affected_rows: int = Field(ge=0)
    safe_summary: str


class CatalogAsset(ApiModel):
    asset_id: Identifier
    name: str
    layer: str
    asset_type: str
    owner: str
    description: str
    classification: str
    refresh_frequency: str
    documented: bool


class LineageEdge(ApiModel):
    source_asset: Identifier
    target_asset: Identifier
    transformation: str


class Classification(ApiModel):
    asset: Identifier
    column_name: Identifier
    classification: str
    handling: str
    exposed_by_api: bool


class GenerateDataRequest(ApiModel):
    employees: int = Field(default=1_000, ge=10, le=100_000)
    months: int = Field(default=24, ge=1, le=120)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    scenario: str = Field(default="baseline", min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")


class TriggerPipelineRequest(ApiModel):
    logical_date: datetime | None = None
    idempotency_key: Identifier | None = None
    full_refresh: bool = False


class ReprocessRejectedRequest(ApiModel):
    batch_id: Identifier
    rejection_ids: list[Identifier] = Field(min_length=1, max_length=100)


class AdminOperationResponse(ApiModel):
    operation_id: Identifier
    operation: str
    status: PipelineStatus
    accepted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    requested_by_role: str
    message: str
