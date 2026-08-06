"""FastAPI dependency providers and validated query filters."""

from __future__ import annotations

from datetime import date
from typing import Annotated, cast

from fastapi import Depends, Query, Request

from api.app.core.errors import ApiProblem
from api.app.repositories.analytics import AnalyticsRepository
from api.app.schemas.common import SafeDimension, WorkforceFilters
from api.app.services.admin import AdminOperationService
from api.app.services.analytics import AnalyticsService


def get_repository(request: Request) -> AnalyticsRepository:
    return cast(AnalyticsRepository, request.app.state.repository)


def get_analytics_service(
    repository: Annotated[AnalyticsRepository, Depends(get_repository)],
) -> AnalyticsService:
    return AnalyticsService(repository)


def get_admin_service(request: Request) -> AdminOperationService:
    return cast(AdminOperationService, request.app.state.admin_service)


def workforce_filters(
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    department: Annotated[SafeDimension | None, Query()] = None,
    location: Annotated[SafeDimension | None, Query()] = None,
    job_level: Annotated[SafeDimension | None, Query()] = None,
    legal_entity: Annotated[SafeDimension | None, Query()] = None,
    employment_type: Annotated[SafeDimension | None, Query()] = None,
    work_arrangement: Annotated[SafeDimension | None, Query()] = None,
) -> WorkforceFilters:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ApiProblem(
            status_code=422,
            error_code="INVALID_FILTER",
            title="Invalid date range",
            detail="start_date must be on or before end_date.",
        )
    return WorkforceFilters(
        start_date=start_date,
        end_date=end_date,
        department=department,
        location=location,
        job_level=job_level,
        legal_entity=legal_entity,
        employment_type=employment_type,
        work_arrangement=work_arrangement,
    )


AnalyticsServiceDependency = Annotated[AnalyticsService, Depends(get_analytics_service)]
AdminServiceDependency = Annotated[AdminOperationService, Depends(get_admin_service)]
WorkforceFilterDependency = Annotated[WorkforceFilters, Depends(workforce_filters)]
