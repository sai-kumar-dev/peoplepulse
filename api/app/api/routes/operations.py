"""Pipeline execution and data-quality observability routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from api.app.api.dependencies import AnalyticsServiceDependency
from api.app.schemas.common import Page
from api.app.schemas.operations import (
    DataQualityCheck,
    PipelineDefinition,
    PipelineRun,
    PipelineStatus,
    QualityStatus,
)

router = APIRouter(tags=["operations"])
SafeIdentifierPath = Annotated[
    str,
    Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:@/-]+$"),
]


@router.get("/pipelines", response_model=Page[PipelineDefinition])
async def pipelines(
    service: AnalyticsServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[PipelineDefinition]:
    return await service.pipelines(offset=offset, limit=limit)


@router.get("/pipelines/runs", response_model=Page[PipelineRun])
async def pipeline_runs(
    service: AnalyticsServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    pipeline_id: Annotated[
        str | None,
        Query(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:@/-]+$"),
    ] = None,
    status: Annotated[PipelineStatus | None, Query()] = None,
) -> Page[PipelineRun]:
    return await service.pipeline_runs(
        offset=offset,
        limit=limit,
        pipeline_id=pipeline_id,
        status=status.value if status else None,
    )


@router.get("/pipelines/runs/{run_id}", response_model=PipelineRun)
async def pipeline_run(
    service: AnalyticsServiceDependency, run_id: SafeIdentifierPath
) -> PipelineRun:
    return await service.pipeline_run(run_id)


@router.get("/data-quality", response_model=Page[DataQualityCheck])
async def quality_checks(
    service: AnalyticsServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    status: Annotated[QualityStatus | None, Query()] = None,
) -> Page[DataQualityCheck]:
    return await service.quality_checks(
        offset=offset,
        limit=limit,
        status=status.value if status else None,
    )


@router.get("/data-quality/{check_id}", response_model=DataQualityCheck)
async def quality_check(
    service: AnalyticsServiceDependency, check_id: SafeIdentifierPath
) -> DataQualityCheck:
    return await service.quality_check(check_id)
