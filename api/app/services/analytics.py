"""Thin service layer enforcing safe repository error mapping."""

from __future__ import annotations

from http import HTTPStatus

from api.app.core.errors import ApiProblem
from api.app.repositories.analytics import (
    AnalyticsRepository,
    RepositoryUnavailableError,
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
from api.app.schemas.common import Page, WorkforceFilters
from api.app.schemas.operations import (
    CatalogAsset,
    Classification,
    DataQualityCheck,
    LineageEdge,
    PipelineDefinition,
    PipelineRun,
)


class AnalyticsService:
    """Coordinate aggregate reads while keeping transport concerns out of repositories."""

    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    @staticmethod
    def _database_problem() -> ApiProblem:
        return ApiProblem(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            error_code="DATABASE_UNAVAILABLE",
            title="Analytics dependency unavailable",
            detail="Trusted aggregate data is temporarily unavailable.",
            retryable=True,
        )

    async def summary(self, filters: WorkforceFilters) -> WorkforceSummaryResponse:
        try:
            return await self.repository.workforce_summary(filters)
        except RepositoryUnavailableError as exc:
            raise self._database_problem() from exc

    async def headcount(self, filters: WorkforceFilters) -> HeadcountResponse:
        try:
            return await self.repository.headcount(filters)
        except RepositoryUnavailableError as exc:
            raise self._database_problem() from exc

    async def attrition(self, filters: WorkforceFilters) -> AttritionResponse:
        try:
            return await self.repository.attrition(filters)
        except RepositoryUnavailableError as exc:
            raise self._database_problem() from exc

    async def hiring(self, filters: WorkforceFilters) -> HiringResponse:
        try:
            return await self.repository.hiring(filters)
        except RepositoryUnavailableError as exc:
            raise self._database_problem() from exc

    async def mobility(self, filters: WorkforceFilters) -> MobilityResponse:
        try:
            return await self.repository.mobility(filters)
        except RepositoryUnavailableError as exc:
            raise self._database_problem() from exc

    async def diversity(self, filters: WorkforceFilters) -> DiversityResponse:
        try:
            return await self.repository.diversity(filters)
        except RepositoryUnavailableError as exc:
            raise self._database_problem() from exc

    async def compensation(self, filters: WorkforceFilters) -> CompensationResponse:
        try:
            return await self.repository.compensation(filters)
        except RepositoryUnavailableError as exc:
            raise self._database_problem() from exc

    async def learning(self, filters: WorkforceFilters) -> LearningResponse:
        try:
            return await self.repository.learning(filters)
        except RepositoryUnavailableError as exc:
            raise self._database_problem() from exc

    async def pipelines(self, *, offset: int, limit: int) -> Page[PipelineDefinition]:
        return await self.repository.pipelines(offset=offset, limit=limit)

    async def pipeline_runs(
        self,
        *,
        offset: int,
        limit: int,
        pipeline_id: str | None,
        status: str | None,
    ) -> Page[PipelineRun]:
        return await self.repository.pipeline_runs(
            offset=offset,
            limit=limit,
            pipeline_id=pipeline_id,
            status=status,
        )

    async def pipeline_run(self, run_id: str) -> PipelineRun:
        run = await self.repository.pipeline_run(run_id)
        if run is None:
            raise ApiProblem(
                status_code=HTTPStatus.NOT_FOUND,
                error_code="NOT_FOUND",
                title="Pipeline run not found",
                detail="No pipeline run exists for the supplied identifier.",
            )
        return run

    async def quality_checks(
        self, *, offset: int, limit: int, status: str | None
    ) -> Page[DataQualityCheck]:
        return await self.repository.quality_checks(offset=offset, limit=limit, status=status)

    async def quality_check(self, check_id: str) -> DataQualityCheck:
        check = await self.repository.quality_check(check_id)
        if check is None:
            raise ApiProblem(
                status_code=HTTPStatus.NOT_FOUND,
                error_code="NOT_FOUND",
                title="Data-quality check not found",
                detail="No data-quality check exists for the supplied identifier.",
            )
        return check

    async def catalog(self, *, offset: int, limit: int, layer: str | None) -> Page[CatalogAsset]:
        return await self.repository.catalog(offset=offset, limit=limit, layer=layer)

    async def lineage(self, *, offset: int, limit: int, asset: str | None) -> Page[LineageEdge]:
        return await self.repository.lineage(offset=offset, limit=limit, asset=asset)

    async def classifications(
        self, *, offset: int, limit: int, classification: str | None
    ) -> Page[Classification]:
        return await self.repository.classifications(
            offset=offset, limit=limit, classification=classification
        )
