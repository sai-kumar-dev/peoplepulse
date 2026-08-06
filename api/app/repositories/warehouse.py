"""SQLAlchemy adapter for API-safe warehouse marts.

The vertical-slice headcount, attrition, and summary marts are queried directly with
allow-listed columns and bind parameters. Expanded domains explicitly use the
configured deterministic fallback until their marts are published.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from api.app.repositories.analytics import (
    DemoAnalyticsRepository,
    RepositoryUnavailableError,
)
from api.app.schemas.analytics import (
    AttritionResponse,
    AttritionTrendPoint,
    CompensationResponse,
    DiversityResponse,
    HeadcountResponse,
    HiringResponse,
    LearningResponse,
    MobilityResponse,
    WorkforceSummaryResponse,
)
from api.app.schemas.common import (
    CategoryValue,
    DataSource,
    ResponseMetadata,
    TimeValue,
    WorkforceFilters,
)

logger = logging.getLogger(__name__)


class WarehouseAnalyticsRepository(DemoAnalyticsRepository):
    """Read typed aggregate response documents through SQLAlchemy."""

    source = DataSource.WAREHOUSE

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        schema: str,
        query_timeout_seconds: float,
        minimum_group_size: int,
        fallback: DemoAnalyticsRepository | None,
        sqlite: bool = False,
    ) -> None:
        super().__init__(minimum_group_size=minimum_group_size)
        self._engine = engine
        self._query_timeout_seconds = query_timeout_seconds
        self._fallback = fallback
        self._schema_prefix = "" if sqlite else f"{schema}."

    async def _rows(self, query: str, parameters: dict[str, object]) -> list[dict[str, Any]]:
        try:
            async with asyncio.timeout(self._query_timeout_seconds):
                async with self._engine.connect() as connection:
                    result = await connection.execute(text(query), parameters)
                    return [dict(row) for row in result.mappings().all()]
        except (SQLAlchemyError, TimeoutError) as exc:
            raise RepositoryUnavailableError("Warehouse aggregate is unavailable") from exc

    @staticmethod
    def _as_date(value: object) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise RepositoryUnavailableError("Warehouse returned an invalid date")

    @staticmethod
    def _as_datetime(value: object) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        raise RepositoryUnavailableError("Warehouse returned an invalid timestamp")

    def _metadata(
        self, filters: WorkforceFilters, *, suppressed_groups: int = 0
    ) -> ResponseMetadata:
        return ResponseMetadata(
            data_source=DataSource.WAREHOUSE,
            filters_applied=filters.as_safe_dict(),
            minimum_group_size=self.minimum_group_size,
            suppressed_groups=suppressed_groups,
        )

    def _categories(self, values: dict[str, float]) -> tuple[list[CategoryValue], int]:
        total = sum(values.values())
        visible = [
            (category, value)
            for category, value in values.items()
            if value >= self.minimum_group_size
        ]
        visible.sort(key=lambda item: (-item[1], item[0]))
        return (
            [
                CategoryValue(
                    category=category,
                    value=value,
                    percentage=round(value / total * 100, 2) if total else 0,
                )
                for category, value in visible
            ],
            len(values) - len(visible),
        )

    async def ping(self) -> float:
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            async with asyncio.timeout(self._query_timeout_seconds):
                async with self._engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, TimeoutError) as exc:
            raise RepositoryUnavailableError("Database dependency is unavailable") from exc
        return round((loop.time() - started) * 1_000, 2)

    async def _summary_from_mart(self, filters: WorkforceFilters) -> WorkforceSummaryResponse:
        if any(
            (
                filters.department,
                filters.location,
                filters.job_level,
                filters.legal_entity,
                filters.employment_type,
                filters.work_arrangement,
            )
        ):
            raise RepositoryUnavailableError(
                "The summary mart does not contain the requested dimensions"
            )
        predicates: list[str] = []
        parameters: dict[str, object] = {}
        if filters.start_date:
            predicates.append("snapshot_date >= :start_date")
            parameters["start_date"] = filters.start_date
        if filters.end_date:
            predicates.append("snapshot_date <= :end_date")
            parameters["end_date"] = filters.end_date
        where = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        rows = await self._rows(
            f"""
            SELECT
                snapshot_date,
                total_headcount,
                active_employees,
                inactive_employees,
                average_tenure_years,
                hires_year_to_date,
                terminations_year_to_date,
                year_to_date_attrition_rate,
                data_quality_score,
                snapshot_loaded_at
            FROM {self._schema_prefix}mart_workforce_summary
            {where}
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            parameters,
        )
        if not rows:
            raise RepositoryUnavailableError("The workforce summary mart is empty")
        row = rows[0]
        attrition_rate = float(row.get("year_to_date_attrition_rate") or 0)
        if attrition_rate <= 1:
            attrition_rate *= 100
        return WorkforceSummaryResponse(
            as_of_date=self._as_date(row["snapshot_date"]),
            total_headcount=int(row.get("total_headcount") or 0),
            active_employees=int(row.get("active_employees") or 0),
            inactive_employees=int(row.get("inactive_employees") or 0),
            new_hires=int(row.get("hires_year_to_date") or 0),
            terminations=int(row.get("terminations_year_to_date") or 0),
            attrition_rate=min(round(attrition_rate, 2), 100),
            # Recruitment marts are outside the initial warehouse slice. Zero values
            # are explicit and are replaced when those aggregates are published.
            open_requisitions=0,
            offer_acceptance_rate=0,
            average_tenure_years=float(row.get("average_tenure_years") or 0),
            latest_refresh_time=self._as_datetime(row["snapshot_loaded_at"]),
            data_quality_score=float(row.get("data_quality_score") or 0),
            metadata=self._metadata(filters),
        )

    async def _headcount_from_mart(self, filters: WorkforceFilters) -> HeadcountResponse:
        if filters.legal_entity:
            raise RepositoryUnavailableError("The headcount mart does not contain legal entity")
        column_filters = {
            "department_name": filters.department,
            "location_id": filters.location,
            "job_level": filters.job_level,
            "employment_type": filters.employment_type,
            "work_arrangement": filters.work_arrangement,
        }
        predicates: list[str] = []
        parameters: dict[str, object] = {}
        if filters.start_date:
            predicates.append("snapshot_date >= :start_date")
            parameters["start_date"] = filters.start_date
        if filters.end_date:
            predicates.append("snapshot_date <= :end_date")
            parameters["end_date"] = filters.end_date
        for column, value in column_filters.items():
            if value:
                parameter = f"filter_{column}"
                predicates.append(f"{column} = :{parameter}")
                parameters[parameter] = value
        where = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        rows = await self._rows(
            f"""
            SELECT
                snapshot_date,
                department_name,
                location_id,
                job_level,
                employment_type,
                headcount
            FROM {self._schema_prefix}mart_headcount
            {where}
            ORDER BY snapshot_date
            """,
            parameters,
        )
        if not rows:
            raise RepositoryUnavailableError("The headcount mart returned no rows")
        as_of = max(self._as_date(row["snapshot_date"]) for row in rows)
        current = [row for row in rows if self._as_date(row["snapshot_date"]) == as_of]
        total = sum(float(row.get("headcount") or 0) for row in current)
        trend_values: dict[date, float] = {}
        for row in rows:
            period = self._as_date(row["snapshot_date"])
            trend_values[period] = trend_values.get(period, 0) + float(row.get("headcount") or 0)

        def breakdown(column: str) -> tuple[list[CategoryValue], int]:
            values: dict[str, float] = {}
            for row in current:
                category = str(row.get(column) or "Unknown")
                values[category] = values.get(category, 0) + float(row.get("headcount") or 0)
            return self._categories(values)

        departments, suppressed_departments = breakdown("department_name")
        locations, suppressed_locations = breakdown("location_id")
        levels, suppressed_levels = breakdown("job_level")
        employment, suppressed_employment = breakdown("employment_type")
        suppressed = (
            suppressed_departments
            + suppressed_locations
            + suppressed_levels
            + suppressed_employment
        )
        return HeadcountResponse(
            as_of_date=as_of,
            total_headcount=round(total),
            trend=[
                TimeValue(period=period, value=round(value))
                for period, value in sorted(trend_values.items())
            ],
            by_department=departments,
            by_location=locations,
            by_job_level=levels,
            by_employment_type=employment,
            metadata=self._metadata(filters, suppressed_groups=suppressed),
        )

    async def _attrition_from_mart(self, filters: WorkforceFilters) -> AttritionResponse:
        if any(
            (
                filters.location,
                filters.job_level,
                filters.legal_entity,
                filters.employment_type,
                filters.work_arrangement,
            )
        ):
            raise RepositoryUnavailableError(
                "The attrition mart does not contain the requested dimensions"
            )
        predicates: list[str] = []
        parameters: dict[str, object] = {}
        if filters.start_date:
            predicates.append("metric_month >= :start_date")
            parameters["start_date"] = filters.start_date
        if filters.end_date:
            predicates.append("metric_month <= :end_date")
            parameters["end_date"] = filters.end_date
        if filters.department:
            predicates.append("department_name = :department")
            parameters["department"] = filters.department
        where = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        rows = await self._rows(
            f"""
            SELECT
                metric_month,
                department_name,
                terminations,
                voluntary_terminations,
                involuntary_terminations,
                average_headcount
            FROM {self._schema_prefix}mart_attrition
            {where}
            ORDER BY metric_month
            """,
            parameters,
        )
        if not rows:
            raise RepositoryUnavailableError("The attrition mart returned no rows")
        monthly: dict[date, dict[str, float]] = {}
        departments: dict[str, float] = {}
        voluntary = 0.0
        involuntary = 0.0
        for row in rows:
            period = self._as_date(row["metric_month"])
            aggregate = monthly.setdefault(period, {"terminations": 0, "average_headcount": 0})
            terminations = float(row.get("terminations") or 0)
            aggregate["terminations"] += terminations
            aggregate["average_headcount"] += float(row.get("average_headcount") or 0)
            department = str(row.get("department_name") or "Unknown")
            departments[department] = departments.get(department, 0) + terminations
            voluntary += float(row.get("voluntary_terminations") or 0)
            involuntary += float(row.get("involuntary_terminations") or 0)
        trend = [
            AttritionTrendPoint(
                period=period,
                terminations=round(values["terminations"]),
                average_headcount=round(values["average_headcount"], 2),
                attrition_rate=min(
                    round(
                        values["terminations"] / values["average_headcount"] * 100,
                        2,
                    )
                    if values["average_headcount"]
                    else 0,
                    100,
                ),
            )
            for period, values in sorted(monthly.items())
        ]
        total_terminations = sum(point.terminations for point in trend)
        average_headcount = (
            sum(point.average_headcount for point in trend) / len(trend) if trend else 0
        )
        by_department, suppressed = self._categories(departments)
        by_type, suppressed_type = self._categories(
            {"Voluntary": voluntary, "Involuntary": involuntary}
        )
        return AttritionResponse(
            start_date=filters.start_date or min(monthly),
            end_date=filters.end_date or max(monthly),
            terminations=total_terminations,
            attrition_rate=min(
                round(total_terminations / average_headcount * 100, 2) if average_headcount else 0,
                100,
            ),
            trend=trend,
            by_type=by_type,
            by_department=by_department,
            by_tenure_band=[],
            by_job_level=[],
            metadata=self._metadata(filters, suppressed_groups=suppressed + suppressed_type),
        )

    async def workforce_summary(self, filters: WorkforceFilters) -> WorkforceSummaryResponse:
        fallback = self._fallback
        try:
            return await self._summary_from_mart(filters)
        except RepositoryUnavailableError:
            if fallback is None:
                raise
            logger.warning(
                "warehouse_summary_fallback",
                extra={"error_code": "DATABASE_UNAVAILABLE", "status": "degraded"},
            )
            return await fallback.workforce_summary(filters)

    async def headcount(self, filters: WorkforceFilters) -> HeadcountResponse:
        fallback = self._fallback
        try:
            return await self._headcount_from_mart(filters)
        except RepositoryUnavailableError:
            if fallback is None:
                raise
            logger.warning(
                "warehouse_headcount_fallback",
                extra={"error_code": "DATABASE_UNAVAILABLE", "status": "degraded"},
            )
            return await fallback.headcount(filters)

    async def attrition(self, filters: WorkforceFilters) -> AttritionResponse:
        fallback = self._fallback
        try:
            return await self._attrition_from_mart(filters)
        except RepositoryUnavailableError:
            if fallback is None:
                raise
            logger.warning(
                "warehouse_attrition_fallback",
                extra={"error_code": "DATABASE_UNAVAILABLE", "status": "degraded"},
            )
            return await fallback.attrition(filters)

    async def hiring(self, filters: WorkforceFilters) -> HiringResponse:
        fallback = self._fallback
        if fallback is None:
            raise RepositoryUnavailableError("Hiring mart is not yet published")
        return await fallback.hiring(filters)

    async def mobility(self, filters: WorkforceFilters) -> MobilityResponse:
        fallback = self._fallback
        if fallback is None:
            raise RepositoryUnavailableError("Mobility mart is not yet published")
        return await fallback.mobility(filters)

    async def diversity(self, filters: WorkforceFilters) -> DiversityResponse:
        fallback = self._fallback
        if fallback is None:
            raise RepositoryUnavailableError("Diversity mart is not yet published")
        return await fallback.diversity(filters)

    async def compensation(self, filters: WorkforceFilters) -> CompensationResponse:
        fallback = self._fallback
        if fallback is None:
            raise RepositoryUnavailableError("Compensation mart is not yet published")
        return await fallback.compensation(filters)

    async def learning(self, filters: WorkforceFilters) -> LearningResponse:
        fallback = self._fallback
        if fallback is None:
            raise RepositoryUnavailableError("Learning mart is not yet published")
        return await fallback.learning(filters)

    async def close(self) -> None:
        await self._engine.dispose()
