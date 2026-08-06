"""Shared API schema primitives."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

SafeDimension = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[\w .&()/+-]+$",
    ),
]


class ApiModel(BaseModel):
    """Strict base contract used by all public API models."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DataSource(StrEnum):
    WAREHOUSE = "warehouse"
    DEMO = "demo"


class ResponseMetadata(ApiModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data_source: DataSource = DataSource.DEMO
    filters_applied: dict[str, str] = Field(default_factory=dict)
    minimum_group_size: int = 5
    suppressed_groups: int = 0


class Pagination(ApiModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=25, ge=1, le=100)


class Page[T](ApiModel):
    items: list[T]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    has_more: bool


class WorkforceFilters(ApiModel):
    """Allow-listed aggregate filters shared by workforce endpoints."""

    start_date: date | None = None
    end_date: date | None = None
    department: SafeDimension | None = None
    location: SafeDimension | None = None
    job_level: SafeDimension | None = None
    legal_entity: SafeDimension | None = None
    employment_type: SafeDimension | None = None
    work_arrangement: SafeDimension | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> WorkforceFilters:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self

    def as_safe_dict(self) -> dict[str, str]:
        values = self.model_dump(exclude_none=True, mode="json")
        return {key: str(value) for key, value in values.items()}


class TimeGrain(StrEnum):
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class TimeValue(ApiModel):
    period: date
    value: float


class CategoryValue(ApiModel):
    category: str
    value: float
    percentage: float | None = Field(default=None, ge=0, le=100)


class HealthStatus(StrEnum):
    OK = "ok"
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class HealthResponse(ApiModel):
    status: HealthStatus
    service: str
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DependencyStatus(ApiModel):
    name: str
    status: HealthStatus
    required: bool
    latency_ms: float | None = Field(default=None, ge=0)
    detail: str


class DependenciesResponse(ApiModel):
    status: HealthStatus
    dependencies: list[DependencyStatus]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"
