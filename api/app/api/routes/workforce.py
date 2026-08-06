"""Aggregate-only workforce analytics routes."""

from __future__ import annotations

from fastapi import APIRouter

from api.app.api.dependencies import (
    AnalyticsServiceDependency,
    WorkforceFilterDependency,
)
from api.app.schemas.analytics import (
    AttritionResponse,
    CompensationResponse,
    DiversityResponse,
    HeadcountResponse,
    HiringResponse,
    LearningResponse,
    MobilityResponse,
    WorkforceSummaryResponse,
)

router = APIRouter(prefix="/workforce", tags=["workforce"])


@router.get(
    "/summary",
    response_model=WorkforceSummaryResponse,
    summary="Certified workforce KPI summary",
)
async def workforce_summary(
    service: AnalyticsServiceDependency,
    filters: WorkforceFilterDependency,
) -> WorkforceSummaryResponse:
    return await service.summary(filters)


@router.get("/headcount", response_model=HeadcountResponse)
async def headcount(
    service: AnalyticsServiceDependency,
    filters: WorkforceFilterDependency,
) -> HeadcountResponse:
    return await service.headcount(filters)


@router.get("/attrition", response_model=AttritionResponse)
async def attrition(
    service: AnalyticsServiceDependency,
    filters: WorkforceFilterDependency,
) -> AttritionResponse:
    return await service.attrition(filters)


@router.get("/hiring", response_model=HiringResponse)
async def hiring(
    service: AnalyticsServiceDependency,
    filters: WorkforceFilterDependency,
) -> HiringResponse:
    return await service.hiring(filters)


@router.get("/mobility", response_model=MobilityResponse)
async def mobility(
    service: AnalyticsServiceDependency,
    filters: WorkforceFilterDependency,
) -> MobilityResponse:
    return await service.mobility(filters)


@router.get("/diversity", response_model=DiversityResponse)
async def diversity(
    service: AnalyticsServiceDependency,
    filters: WorkforceFilterDependency,
) -> DiversityResponse:
    return await service.diversity(filters)


@router.get("/compensation", response_model=CompensationResponse)
async def compensation(
    service: AnalyticsServiceDependency,
    filters: WorkforceFilterDependency,
) -> CompensationResponse:
    return await service.compensation(filters)


@router.get("/learning", response_model=LearningResponse)
async def learning(
    service: AnalyticsServiceDependency,
    filters: WorkforceFilterDependency,
) -> LearningResponse:
    return await service.learning(filters)
