"""Analytics repository contract and deterministic local implementation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol

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
    Page,
    ResponseMetadata,
    TimeValue,
    WorkforceFilters,
)
from api.app.schemas.operations import (
    CatalogAsset,
    Classification,
    DataQualityCheck,
    LineageEdge,
    PipelineDefinition,
    PipelineRun,
)


class RepositoryUnavailableError(RuntimeError):
    """Raised when a configured repository cannot safely serve a result."""


class AnalyticsRepository(Protocol):
    """Storage-independent aggregate analytics interface."""

    source: DataSource

    async def ping(self) -> float: ...

    async def workforce_summary(self, filters: WorkforceFilters) -> WorkforceSummaryResponse: ...

    async def headcount(self, filters: WorkforceFilters) -> HeadcountResponse: ...

    async def attrition(self, filters: WorkforceFilters) -> AttritionResponse: ...

    async def hiring(self, filters: WorkforceFilters) -> HiringResponse: ...

    async def mobility(self, filters: WorkforceFilters) -> MobilityResponse: ...

    async def diversity(self, filters: WorkforceFilters) -> DiversityResponse: ...

    async def compensation(self, filters: WorkforceFilters) -> CompensationResponse: ...

    async def learning(self, filters: WorkforceFilters) -> LearningResponse: ...

    async def pipelines(self, *, offset: int, limit: int) -> Page[PipelineDefinition]: ...

    async def pipeline_runs(
        self,
        *,
        offset: int,
        limit: int,
        pipeline_id: str | None,
        status: str | None,
    ) -> Page[PipelineRun]: ...

    async def pipeline_run(self, run_id: str) -> PipelineRun | None: ...

    async def quality_checks(
        self, *, offset: int, limit: int, status: str | None
    ) -> Page[DataQualityCheck]: ...

    async def quality_check(self, check_id: str) -> DataQualityCheck | None: ...

    async def catalog(
        self, *, offset: int, limit: int, layer: str | None
    ) -> Page[CatalogAsset]: ...

    async def lineage(self, *, offset: int, limit: int, asset: str | None) -> Page[LineageEdge]: ...

    async def classifications(
        self, *, offset: int, limit: int, classification: str | None
    ) -> Page[Classification]: ...

    async def close(self) -> None: ...


def _page[T](items: list[T], *, offset: int, limit: int) -> Page[T]:
    selected = items[offset : offset + limit]
    return Page[T](
        items=selected,
        total=len(items),
        offset=offset,
        limit=limit,
        has_more=offset + len(selected) < len(items),
    )


class DemoAnalyticsRepository:
    """Deterministic aggregate data for local demos and dependency-free tests."""

    source = DataSource.DEMO
    _AS_OF = date(2025, 12, 31)
    _REFRESH = datetime(2026, 1, 1, 2, 15, tzinfo=UTC)

    def __init__(self, *, minimum_group_size: int = 5) -> None:
        self.minimum_group_size = minimum_group_size

    def _metadata(
        self, filters: WorkforceFilters, *, suppressed_groups: int = 0
    ) -> ResponseMetadata:
        return ResponseMetadata(
            generated_at=self._REFRESH,
            data_source=self.source,
            filters_applied=filters.as_safe_dict(),
            minimum_group_size=self.minimum_group_size,
            suppressed_groups=suppressed_groups,
        )

    @staticmethod
    def _date_range(filters: WorkforceFilters) -> tuple[date, date]:
        return (
            filters.start_date or date(2025, 1, 1),
            filters.end_date or DemoAnalyticsRepository._AS_OF,
        )

    @staticmethod
    def _percentages(values: list[tuple[str, float]]) -> list[CategoryValue]:
        total = sum(value for _, value in values)
        return [
            CategoryValue(
                category=category,
                value=value,
                percentage=round((value / total * 100), 2) if total else 0,
            )
            for category, value in values
        ]

    @staticmethod
    def _select_dimension(
        values: list[tuple[str, float]], selected: str | None
    ) -> list[tuple[str, float]]:
        if selected is None:
            return values
        return [
            (category, value)
            for category, value in values
            if category.casefold() == selected.casefold()
        ]

    @staticmethod
    def _scale(filters: WorkforceFilters, *, exclude: frozenset[str] = frozenset()) -> float:
        mappings: tuple[tuple[str, str | None, dict[str, float]], ...] = (
            (
                "department",
                filters.department,
                {
                    "engineering": 0.3,
                    "sales": 0.22,
                    "operations": 0.18,
                    "finance": 0.11,
                    "people": 0.1,
                    "marketing": 0.09,
                },
            ),
            (
                "location",
                filters.location,
                {
                    "bengaluru": 0.35,
                    "pune": 0.24,
                    "hyderabad": 0.22,
                    "remote": 0.19,
                },
            ),
            (
                "job_level",
                filters.job_level,
                {
                    "l1": 0.16,
                    "l2": 0.28,
                    "l3": 0.26,
                    "l4": 0.18,
                    "l5+": 0.12,
                },
            ),
            (
                "employment_type",
                filters.employment_type,
                {"full-time": 0.88, "part-time": 0.05, "contract": 0.07},
            ),
            (
                "work_arrangement",
                filters.work_arrangement,
                {"hybrid": 0.51, "onsite": 0.29, "remote": 0.2},
            ),
        )
        scale = 1.0
        for dimension, selected, mapping in mappings:
            if selected is not None and dimension not in exclude:
                scale *= mapping.get(selected.casefold(), 0.0)
        if filters.legal_entity is not None and "legal_entity" not in exclude:
            scale *= 0.72 if filters.legal_entity.casefold() == "peoplepulse india" else 0.0
        return scale

    async def ping(self) -> float:
        return 0.0

    async def workforce_summary(self, filters: WorkforceFilters) -> WorkforceSummaryResponse:
        scale = self._scale(filters)
        headcount = round(4_860 * scale)
        return WorkforceSummaryResponse(
            as_of_date=filters.end_date or self._AS_OF,
            total_headcount=headcount,
            active_employees=headcount,
            inactive_employees=round(312 * scale),
            new_hires=round(742 * scale),
            terminations=round(516 * scale),
            attrition_rate=10.62 if headcount else 0,
            open_requisitions=round(184 * scale),
            offer_acceptance_rate=83.4 if headcount else 0,
            average_tenure_years=4.3 if headcount else 0,
            latest_refresh_time=self._REFRESH,
            data_quality_score=98.6,
            metadata=self._metadata(filters),
        )

    async def headcount(self, filters: WorkforceFilters) -> HeadcountResponse:
        scale = self._scale(filters)
        total = round(4_860 * scale)
        trend_values = [
            (date(2025, 1, 1), 4_510),
            (date(2025, 2, 1), 4_536),
            (date(2025, 3, 1), 4_568),
            (date(2025, 4, 1), 4_601),
            (date(2025, 5, 1), 4_638),
            (date(2025, 6, 1), 4_672),
            (date(2025, 7, 1), 4_701),
            (date(2025, 8, 1), 4_733),
            (date(2025, 9, 1), 4_761),
            (date(2025, 10, 1), 4_798),
            (date(2025, 11, 1), 4_832),
            (date(2025, 12, 1), 4_860),
        ]
        start, end = self._date_range(filters)
        trend = [
            TimeValue(period=period, value=round(value * scale))
            for period, value in trend_values
            if start <= period <= end
        ]
        departments = self._select_dimension(
            [
                ("Engineering", 1_458),
                ("Sales", 1_069),
                ("Operations", 875),
                ("Finance", 535),
                ("People", 486),
                ("Marketing", 437),
            ],
            filters.department,
        )
        locations = self._select_dimension(
            [
                ("Bengaluru", 1_701),
                ("Pune", 1_166),
                ("Hyderabad", 1_069),
                ("Remote", 924),
            ],
            filters.location,
        )
        levels = self._select_dimension(
            [("L1", 778), ("L2", 1_361), ("L3", 1_264), ("L4", 875), ("L5+", 582)],
            filters.job_level,
        )
        employment = self._select_dimension(
            [("Full-time", 4_277), ("Part-time", 243), ("Contract", 340)],
            filters.employment_type,
        )
        return HeadcountResponse(
            as_of_date=filters.end_date or self._AS_OF,
            total_headcount=total,
            trend=trend,
            by_department=self._percentages(
                [
                    (
                        name,
                        round(value * self._scale(filters, exclude=frozenset({"department"}))),
                    )
                    for name, value in departments
                ]
            ),
            by_location=self._percentages(
                [
                    (
                        name,
                        round(value * self._scale(filters, exclude=frozenset({"location"}))),
                    )
                    for name, value in locations
                ]
            ),
            by_job_level=self._percentages(
                [
                    (
                        name,
                        round(value * self._scale(filters, exclude=frozenset({"job_level"}))),
                    )
                    for name, value in levels
                ]
            ),
            by_employment_type=self._percentages(
                [
                    (
                        name,
                        round(value * self._scale(filters, exclude=frozenset({"employment_type"}))),
                    )
                    for name, value in employment
                ]
            ),
            metadata=self._metadata(filters),
        )

    async def attrition(self, filters: WorkforceFilters) -> AttritionResponse:
        start, end = self._date_range(filters)
        scale = self._scale(filters)
        points = [
            (date(2025, month, 1), value)
            for month, value in enumerate([39, 42, 46, 43, 41, 45, 48, 44, 47, 40, 39, 42], start=1)
        ]
        trend = [
            AttritionTrendPoint(
                period=period,
                terminations=round(terms * scale),
                average_headcount=round((4_480 + period.month * 31) * scale, 1),
                attrition_rate=round((terms / (4_480 + period.month * 31) * 100), 2)
                if scale
                else 0,
            )
            for period, terms in points
            if start <= period <= end
        ]
        terminations = sum(point.terminations for point in trend)
        return AttritionResponse(
            start_date=start,
            end_date=end,
            terminations=terminations,
            attrition_rate=10.62 if scale else 0,
            trend=trend,
            by_type=self._percentages(
                [
                    ("Voluntary", round(361 * scale)),
                    ("Involuntary", round(155 * scale)),
                ]
            ),
            by_department=self._percentages(
                [
                    ("Sales", round(141 * scale)),
                    ("Engineering", round(135 * scale)),
                    ("Operations", round(104 * scale)),
                    ("Marketing", round(51 * scale)),
                    ("Finance", round(47 * scale)),
                    ("People", round(38 * scale)),
                ]
            ),
            by_tenure_band=self._percentages(
                [
                    ("< 1 year", round(166 * scale)),
                    ("1-3 years", round(194 * scale)),
                    ("3-5 years", round(91 * scale)),
                    ("5+ years", round(65 * scale)),
                ]
            ),
            by_job_level=self._percentages(
                [
                    ("L1", round(113 * scale)),
                    ("L2", round(171 * scale)),
                    ("L3", round(129 * scale)),
                    ("L4", round(72 * scale)),
                    ("L5+", round(31 * scale)),
                ]
            ),
            metadata=self._metadata(filters),
        )

    async def hiring(self, filters: WorkforceFilters) -> HiringResponse:
        start, end = self._date_range(filters)
        scale = self._scale(filters)
        hires = round(742 * scale)
        return HiringResponse(
            start_date=start,
            end_date=end,
            applications=round(12_480 * scale),
            offers=round(890 * scale),
            hires=hires,
            open_requisitions=round(184 * scale),
            offer_acceptance_rate=83.4 if scale else 0,
            average_time_to_hire_days=31.7 if scale else 0,
            hiring_trend=[
                TimeValue(
                    period=date(2025, month, 1),
                    value=round(value * scale),
                )
                for month, value in enumerate(
                    [54, 58, 63, 65, 66, 61, 68, 64, 59, 62, 60, 62], start=1
                )
                if start <= date(2025, month, 1) <= end
            ],
            recruitment_funnel=self._percentages(
                [
                    ("Applications", round(12_480 * scale)),
                    ("Screened", round(5_420 * scale)),
                    ("Interviewed", round(2_310 * scale)),
                    ("Offers", round(890 * scale)),
                    ("Accepted", hires),
                ]
            ),
            by_source_channel=self._percentages(
                [
                    ("Referral", round(241 * scale)),
                    ("Job board", round(207 * scale)),
                    ("Careers site", round(178 * scale)),
                    ("Agency", round(68 * scale)),
                    ("Campus", round(48 * scale)),
                ]
            ),
            metadata=self._metadata(filters),
        )

    async def mobility(self, filters: WorkforceFilters) -> MobilityResponse:
        start, end = self._date_range(filters)
        scale = self._scale(filters)
        return MobilityResponse(
            start_date=start,
            end_date=end,
            employee_movements=round(684 * scale),
            promotions=round(392 * scale),
            transfers=round(292 * scale),
            promotion_rate=8.07 if scale else 0,
            movement_trend=[
                TimeValue(period=date(2025, month, 1), value=round(value * scale))
                for month, value in enumerate(
                    [46, 49, 71, 48, 52, 74, 50, 53, 79, 55, 48, 79], start=1
                )
                if start <= date(2025, month, 1) <= end
            ],
            by_movement_type=self._percentages(
                [
                    ("Promotion", round(392 * scale)),
                    ("Lateral transfer", round(221 * scale)),
                    ("Location transfer", round(71 * scale)),
                ]
            ),
            by_department=self._percentages(
                [
                    ("Engineering", round(226 * scale)),
                    ("Sales", round(151 * scale)),
                    ("Operations", round(123 * scale)),
                    ("Finance", round(70 * scale)),
                    ("People", round(62 * scale)),
                    ("Marketing", round(52 * scale)),
                ]
            ),
            metadata=self._metadata(filters),
        )

    async def diversity(self, filters: WorkforceFilters) -> DiversityResponse:
        scale = self._scale(filters)
        headcount = round(4_860 * scale)
        return DiversityResponse(
            as_of_date=filters.end_date or self._AS_OF,
            reportable_headcount=headcount,
            gender_representation=self._percentages(
                [
                    ("Women", round(2_333 * scale)),
                    ("Men", round(2_381 * scale)),
                    ("Non-binary / self-described", round(97 * scale)),
                    ("Not disclosed", round(49 * scale)),
                ]
            ),
            workforce_by_job_level=self._percentages(
                [
                    ("L1", round(778 * scale)),
                    ("L2", round(1_361 * scale)),
                    ("L3", round(1_264 * scale)),
                    ("L4", round(875 * scale)),
                    ("L5+", round(582 * scale)),
                ]
            ),
            workforce_by_location=self._percentages(
                [
                    ("Bengaluru", round(1_701 * scale)),
                    ("Pune", round(1_166 * scale)),
                    ("Hyderabad", round(1_069 * scale)),
                    ("Remote", round(924 * scale)),
                ]
            ),
            suppressed_groups=0,
            metadata=self._metadata(filters),
        )

    async def compensation(self, filters: WorkforceFilters) -> CompensationResponse:
        scale = self._scale(filters)
        return CompensationResponse(
            as_of_date=filters.end_date or self._AS_OF,
            currency="INR",
            reportable_headcount=round(4_812 * scale),
            median_base_salary=1_680_000 if scale else 0,
            average_base_salary=1_842_500 if scale else 0,
            pay_distribution=self._percentages(
                [
                    ("< ₹1M", round(816 * scale)),
                    ("₹1M-₹2M", round(2_358 * scale)),
                    ("₹2M-₹3M", round(1_107 * scale)),
                    ("₹3M+", round(531 * scale)),
                ]
            ),
            by_job_level=[
                CategoryValue(category="L1", value=780_000),
                CategoryValue(category="L2", value=1_250_000),
                CategoryValue(category="L3", value=1_780_000),
                CategoryValue(category="L4", value=2_550_000),
                CategoryValue(category="L5+", value=3_840_000),
            ]
            if scale
            else [],
            compa_ratio_by_department=[
                CategoryValue(category="Engineering", value=1.04),
                CategoryValue(category="Sales", value=1.01),
                CategoryValue(category="Operations", value=0.99),
                CategoryValue(category="Finance", value=1.02),
                CategoryValue(category="People", value=0.98),
                CategoryValue(category="Marketing", value=1.0),
            ]
            if scale
            else [],
            suppressed_groups=0,
            metadata=self._metadata(filters),
        )

    async def learning(self, filters: WorkforceFilters) -> LearningResponse:
        start, end = self._date_range(filters)
        scale = self._scale(filters)
        return LearningResponse(
            start_date=start,
            end_date=end,
            enrollments=round(14_260 * scale),
            completions=round(12_495 * scale),
            completion_rate=87.62 if scale else 0,
            total_learning_hours=round(58_340 * scale, 1),
            average_learning_hours=12.0 if scale else 0,
            completion_trend=[
                TimeValue(period=date(2025, month, 1), value=round(value * scale))
                for month, value in enumerate(
                    [840, 910, 1060, 980, 1040, 1120, 970, 1010, 1180, 1090, 1140, 1155],
                    start=1,
                )
                if start <= date(2025, month, 1) <= end
            ],
            by_course_category=self._percentages(
                [
                    ("Technical", round(4_730 * scale)),
                    ("Leadership", round(2_810 * scale)),
                    ("Compliance", round(3_920 * scale)),
                    ("Professional skills", round(1_035 * scale)),
                ]
            ),
            metadata=self._metadata(filters),
        )

    @staticmethod
    def _pipeline_definitions() -> list[PipelineDefinition]:
        return [
            PipelineDefinition(
                pipeline_id="people_data_ingestion",
                display_name="People data ingestion",
                schedule="0 1 * * *",
                owner="people-data-platform",
                enabled=True,
                last_run_status="succeeded",
            ),
            PipelineDefinition(
                pipeline_id="people_data_transformation",
                display_name="People data transformation",
                schedule="0 2 * * *",
                owner="analytics-engineering",
                enabled=True,
                last_run_status="succeeded",
            ),
            PipelineDefinition(
                pipeline_id="people_data_quality",
                display_name="People data quality",
                schedule="30 2 * * *",
                owner="data-governance",
                enabled=True,
                last_run_status="degraded",
            ),
            PipelineDefinition(
                pipeline_id="people_data_end_to_end",
                display_name="End-to-end publication",
                schedule="0 0 * * 1",
                owner="people-data-platform",
                enabled=True,
                last_run_status="succeeded",
            ),
        ]

    @staticmethod
    def _runs() -> list[PipelineRun]:
        return [
            PipelineRun(
                run_id="run-e2e-20260101T000000Z",
                pipeline_id="people_data_end_to_end",
                started_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
                completed_at=datetime(2026, 1, 1, 0, 18, 42, tzinfo=UTC),
                status="succeeded",
                duration_seconds=1122,
                records_loaded=128_420,
                records_rejected=17,
            ),
            PipelineRun(
                run_id="run-quality-20260101T023000Z",
                pipeline_id="people_data_quality",
                started_at=datetime(2026, 1, 1, 2, 30, tzinfo=UTC),
                completed_at=datetime(2026, 1, 1, 2, 34, 6, tzinfo=UTC),
                status="degraded",
                duration_seconds=246,
                records_loaded=0,
                records_rejected=0,
                error_code="QUALITY_WARNING",
                error_summary="One non-critical freshness threshold was exceeded.",
            ),
            PipelineRun(
                run_id="run-transform-20260101T020000Z",
                pipeline_id="people_data_transformation",
                started_at=datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
                completed_at=datetime(2026, 1, 1, 2, 14, 37, tzinfo=UTC),
                status="succeeded",
                duration_seconds=877,
                records_loaded=94_380,
            ),
            PipelineRun(
                run_id="run-ingest-20260101T010000Z",
                pipeline_id="people_data_ingestion",
                started_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
                completed_at=datetime(2026, 1, 1, 1, 8, 14, tzinfo=UTC),
                status="succeeded",
                duration_seconds=494,
                records_loaded=34_040,
                records_rejected=17,
            ),
        ]

    @staticmethod
    def _quality() -> list[DataQualityCheck]:
        checked_at = datetime(2026, 1, 1, 2, 34, tzinfo=UTC)
        return [
            DataQualityCheck(
                check_id="dq-dim-employee-current",
                check_name="One current employee dimension record",
                dataset="core.dim_employee",
                dimension="consistency",
                severity="critical",
                status="passed",
                score=100,
                checked_at=checked_at,
                affected_rows=0,
                safe_summary="Every business key has at most one current record.",
            ),
            DataQualityCheck(
                check_id="dq-comp-negative",
                check_name="Non-negative compensation",
                dataset="core.fact_compensation",
                dimension="validity",
                severity="critical",
                status="passed",
                score=100,
                checked_at=checked_at,
                affected_rows=0,
                safe_summary="No negative compensation facts were published.",
            ),
            DataQualityCheck(
                check_id="dq-lms-freshness",
                check_name="Learning data freshness",
                dataset="marts.mart_learning",
                dimension="freshness",
                severity="warning",
                status="warning",
                score=91,
                checked_at=checked_at,
                affected_rows=0,
                safe_summary="The source is outside its warning freshness target.",
            ),
            DataQualityCheck(
                check_id="dq-employee-reconciliation",
                check_name="Employee count reconciliation",
                dataset="raw.hris_employees",
                dimension="completeness",
                severity="critical",
                status="passed",
                score=100,
                checked_at=checked_at,
                affected_rows=0,
                safe_summary="Accepted and rejected counts reconcile to the source count.",
            ),
        ]

    async def pipelines(self, *, offset: int, limit: int) -> Page[PipelineDefinition]:
        return _page(self._pipeline_definitions(), offset=offset, limit=limit)

    async def pipeline_runs(
        self,
        *,
        offset: int,
        limit: int,
        pipeline_id: str | None,
        status: str | None,
    ) -> Page[PipelineRun]:
        values = self._runs()
        if pipeline_id:
            values = [item for item in values if item.pipeline_id == pipeline_id]
        if status:
            values = [item for item in values if item.status == status]
        return _page(values, offset=offset, limit=limit)

    async def pipeline_run(self, run_id: str) -> PipelineRun | None:
        return next((item for item in self._runs() if item.run_id == run_id), None)

    async def quality_checks(
        self, *, offset: int, limit: int, status: str | None
    ) -> Page[DataQualityCheck]:
        values = self._quality()
        if status:
            values = [item for item in values if item.status == status]
        return _page(values, offset=offset, limit=limit)

    async def quality_check(self, check_id: str) -> DataQualityCheck | None:
        return next((item for item in self._quality() if item.check_id == check_id), None)

    @staticmethod
    def _catalog_assets() -> list[CatalogAsset]:
        return [
            CatalogAsset(
                asset_id="marts.mart_workforce_summary",
                name="Workforce summary",
                layer="marts",
                asset_type="table",
                owner="people-analytics",
                description="Certified current workforce KPIs.",
                classification="internal",
                refresh_frequency="daily",
                documented=True,
            ),
            CatalogAsset(
                asset_id="marts.mart_headcount",
                name="Headcount",
                layer="marts",
                asset_type="table",
                owner="people-analytics",
                description="Monthly aggregate headcount by approved dimensions.",
                classification="internal",
                refresh_frequency="daily",
                documented=True,
            ),
            CatalogAsset(
                asset_id="core.dim_employee",
                name="Employee dimension",
                layer="core",
                asset_type="table",
                owner="people-data-platform",
                description="Effective-dated employee state with protected identifiers.",
                classification="restricted",
                refresh_frequency="daily",
                documented=True,
            ),
            CatalogAsset(
                asset_id="raw.hris_employees",
                name="HRIS employee landing",
                layer="raw",
                asset_type="table",
                owner="people-data-platform",
                description="Access-restricted immutable HRIS landing data.",
                classification="highly_restricted",
                refresh_frequency="daily",
                documented=True,
            ),
        ]

    @staticmethod
    def _lineage_edges() -> list[LineageEdge]:
        return [
            LineageEdge(
                source_asset="raw.hris_employees",
                target_asset="staging.stg_hris__employees",
                transformation="standardize_and_deduplicate",
            ),
            LineageEdge(
                source_asset="staging.stg_hris__employees",
                target_asset="core.dim_employee",
                transformation="scd_type_2_merge",
            ),
            LineageEdge(
                source_asset="core.dim_employee",
                target_asset="marts.mart_headcount",
                transformation="monthly_aggregate",
            ),
            LineageEdge(
                source_asset="marts.mart_headcount",
                target_asset="marts.mart_workforce_summary",
                transformation="certified_kpi_rollup",
            ),
        ]

    @staticmethod
    def _classifications() -> list[Classification]:
        return [
            Classification(
                asset="core.dim_employee",
                column_name="employee_id",
                classification="confidential_identifier",
                handling="tokenized; restricted role only",
                exposed_by_api=False,
            ),
            Classification(
                asset="raw.hris_employees",
                column_name="email",
                classification="direct_pii",
                handling="masked; raw access audited",
                exposed_by_api=False,
            ),
            Classification(
                asset="raw.hris_employees",
                column_name="date_of_birth",
                classification="sensitive_pii",
                handling="masked; retained by policy",
                exposed_by_api=False,
            ),
            Classification(
                asset="marts.mart_headcount",
                column_name="headcount",
                classification="internal_aggregate",
                handling="minimum group-size suppression",
                exposed_by_api=True,
            ),
        ]

    async def catalog(self, *, offset: int, limit: int, layer: str | None) -> Page[CatalogAsset]:
        values = self._catalog_assets()
        if layer:
            values = [item for item in values if item.layer.casefold() == layer.casefold()]
        return _page(values, offset=offset, limit=limit)

    async def lineage(self, *, offset: int, limit: int, asset: str | None) -> Page[LineageEdge]:
        values = self._lineage_edges()
        if asset:
            values = [item for item in values if asset in {item.source_asset, item.target_asset}]
        return _page(values, offset=offset, limit=limit)

    async def classifications(
        self, *, offset: int, limit: int, classification: str | None
    ) -> Page[Classification]:
        values = self._classifications()
        if classification:
            values = [
                item
                for item in values
                if item.classification.casefold() == classification.casefold()
            ]
        return _page(values, offset=offset, limit=limit)

    async def close(self) -> None:
        return None
