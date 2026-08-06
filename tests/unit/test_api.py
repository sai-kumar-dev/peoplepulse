"""Unit and contract tests for the FastAPI serving layer."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app.core.config import Settings
from api.app.core.errors import ApiProblem
from api.app.core.logging import JsonFormatter
from api.app.core.security import Principal, Role
from api.app.db.session import RepositoryBuild, _async_database_url, build_repository
from api.app.main import create_app
from api.app.repositories.analytics import (
    DemoAnalyticsRepository,
    RepositoryUnavailableError,
)
from api.app.repositories.warehouse import WarehouseAnalyticsRepository
from api.app.schemas.analytics import WorkforceSummaryResponse
from api.app.schemas.common import DataSource, WorkforceFilters
from api.app.services.admin import AdminOperationService
from api.app.services.analytics import AnalyticsService

_DIRECT_VALUE_KEYS = {
    "employee_id",
    "candidate_id",
    "first_name",
    "last_name",
    "preferred_name",
    "email",
    "phone",
    "date_of_birth",
    "base_salary",
    "bonus_paid",
}


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {
            nested_key for nested in value.values() for nested_key in _all_keys(nested)
        }
    if isinstance(value, list):
        return {nested_key for item in value for nested_key in _all_keys(item)}
    return set()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PEOPLEPULSE_DATABASE_URL", raising=False)
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=None,
        log_level="CRITICAL",
        admin_token="unit-admin-token",
        analyst_token="unit-analyst-token",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_health_endpoints_and_request_correlation(client: TestClient) -> None:
    live = client.get("/health/live", headers={"X-Request-ID": "test-request-123"})
    ready = client.get("/health/ready")
    dependencies = client.get("/health/dependencies")

    assert live.status_code == 200
    assert live.headers["X-Request-ID"] == "test-request-123"
    assert live.json()["status"] == "ok"
    assert ready.json()["status"] == "ready"
    assert dependencies.json()["dependencies"][0]["required"] is False
    assert "demo repository" in dependencies.json()["dependencies"][0]["detail"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/workforce/summary",
        "/api/v1/workforce/headcount",
        "/api/v1/workforce/attrition",
        "/api/v1/workforce/hiring",
        "/api/v1/workforce/mobility",
        "/api/v1/workforce/diversity",
        "/api/v1/workforce/compensation",
        "/api/v1/workforce/learning",
    ],
)
def test_workforce_endpoints_are_aggregate_only(client: TestClient, path: str) -> None:
    response = client.get(
        path,
        params={
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "department": "Engineering",
            "location": "Bengaluru",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["metadata"]["data_source"] == "demo"
    assert payload["metadata"]["filters_applied"]["department"] == "Engineering"
    assert _DIRECT_VALUE_KEYS.isdisjoint(_all_keys(payload))


def test_filter_validation_uses_problem_details_and_does_not_echo_input(
    client: TestClient,
) -> None:
    unsafe = "<script>alert('pii')</script>"
    response = client.get("/api/v1/workforce/headcount", params={"department": unsafe})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error_code"] == "INVALID_FILTER"
    assert unsafe not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_invalid_date_range_returns_safe_problem(client: TestClient) -> None:
    response = client.get(
        "/api/v1/workforce/attrition",
        params={"start_date": "2025-12-01", "end_date": "2025-01-01"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "INVALID_FILTER"
    assert response.json()["detail"] == "start_date must be on or before end_date."


def test_pipeline_pagination_filters_and_lookup(client: TestClient) -> None:
    definitions = client.get("/api/v1/pipelines", params={"limit": 2})
    page = client.get("/api/v1/pipelines/runs", params={"offset": 1, "limit": 2})
    filtered = client.get("/api/v1/pipelines/runs", params={"status": "succeeded", "limit": 100})
    found = client.get("/api/v1/pipelines/runs/run-ingest-20260101T010000Z")

    assert definitions.status_code == 200
    assert len(definitions.json()["items"]) == 2
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert page.json()["has_more"] is True
    assert all(item["status"] == "succeeded" for item in filtered.json()["items"])
    assert found.json()["records_loaded"] == 34_040


def test_missing_resource_and_route_are_rfc7807(client: TestClient) -> None:
    missing_run = client.get("/api/v1/pipelines/runs/run-does-not-exist")
    missing_route = client.get("/not-a-route")

    for response in (missing_run, missing_route):
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["error_code"] == "NOT_FOUND"
        assert response.json()["instance"] == response.request.url.path


def test_quality_and_governance_pages_are_paginated(client: TestClient) -> None:
    quality = client.get("/api/v1/data-quality", params={"limit": 2})
    catalog = client.get("/api/v1/governance/catalog", params={"layer": "marts"})
    lineage = client.get(
        "/api/v1/governance/lineage",
        params={"asset": "core.dim_employee"},
    )
    classifications = client.get(
        "/api/v1/governance/classifications",
        params={"classification": "direct_pii"},
    )
    quality_detail = client.get("/api/v1/data-quality/dq-comp-negative")

    assert quality.json()["total"] >= 4
    assert quality_detail.json()["status"] == "passed"
    assert len(quality.json()["items"]) == 2
    assert all(item["layer"] == "marts" for item in catalog.json()["items"])
    assert lineage.json()["total"] == 2
    assert classifications.json()["items"][0]["exposed_by_api"] is False
    # Governance exposes classification metadata, never the classified values.
    assert "personal@example.com" not in json.dumps(classifications.json())


def test_admin_routes_enforce_roles_and_are_idempotent(client: TestClient) -> None:
    payload = {"employees": 250, "months": 12, "seed": 7, "scenario": "baseline"}
    unauthenticated = client.post("/api/v1/admin/generate-data", json=payload)
    analyst = client.post(
        "/api/v1/admin/generate-data",
        json=payload,
        headers={"Authorization": "Bearer unit-analyst-token"},
    )
    first = client.post(
        "/api/v1/admin/generate-data",
        json=payload,
        headers={"Authorization": "Bearer unit-admin-token"},
    )
    repeated = client.post(
        "/api/v1/admin/generate-data",
        json=payload,
        headers={"Authorization": "Bearer unit-admin-token"},
    )

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error_code"] == "UNAUTHORIZED"
    assert analyst.status_code == 403
    assert analyst.json()["error_code"] == "FORBIDDEN"
    assert first.status_code == 202
    assert first.json()["operation_id"] == repeated.json()["operation_id"]
    assert "unit-admin-token" not in first.text


def test_all_admin_command_contracts(client: TestClient) -> None:
    headers = {"Authorization": "Bearer unit-admin-token"}
    requests = [
        (
            "/api/v1/admin/trigger-ingestion",
            {"logical_date": "2025-12-31T00:00:00Z", "idempotency_key": "demo-1"},
        ),
        (
            "/api/v1/admin/trigger-transformation",
            {"idempotency_key": "demo-2", "full_refresh": False},
        ),
        (
            "/api/v1/admin/reprocess-rejected",
            {"batch_id": "batch-42", "rejection_ids": ["reject-1", "reject-2"]},
        ),
    ]

    for path, body in requests:
        response = client.post(path, json=body, headers=headers)
        assert response.status_code == 202, response.text
        assert response.json()["status"] == "scheduled"


def test_demo_repository_is_deterministic_and_filter_aware() -> None:
    repository = DemoAnalyticsRepository(minimum_group_size=7)
    filters = WorkforceFilters(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        department="Engineering",
    )
    first = asyncio.run(repository.workforce_summary(filters))
    second = asyncio.run(repository.workforce_summary(filters))
    headcount = asyncio.run(repository.headcount(filters))

    assert first == second
    assert first.total_headcount == round(4_860 * 0.3)
    assert headcount.by_department[0].value == headcount.total_headcount
    assert first.metadata.minimum_group_size == 7
    assert first.metadata.data_source is DataSource.DEMO


def test_admin_service_idempotency_is_payload_based() -> None:
    service = AdminOperationService()
    principal = Principal(subject="test-admin", role=Role.ADMIN)

    async def exercise() -> tuple[str, str]:
        from api.app.schemas.operations import GenerateDataRequest

        first = await service.generate_data(GenerateDataRequest(employees=100, seed=42), principal)
        second = await service.generate_data(GenerateDataRequest(employees=101, seed=42), principal)
        return first.operation_id, second.operation_id

    first_id, second_id = asyncio.run(exercise())
    assert first_id != second_id


def test_repository_unavailability_maps_to_safe_503() -> None:
    class FailingRepository(DemoAnalyticsRepository):
        async def workforce_summary(self, filters: WorkforceFilters) -> WorkforceSummaryResponse:
            del filters
            raise RepositoryUnavailableError("secret database detail")

    service = AnalyticsService(FailingRepository())
    with pytest.raises(ApiProblem) as captured:
        asyncio.run(service.summary(WorkforceFilters()))

    problem = captured.value
    assert problem.status_code == 503
    assert problem.error_code == "DATABASE_UNAVAILABLE"
    assert "secret database detail" not in problem.detail


def test_warehouse_vertical_slice_maps_marts_without_pii() -> None:
    class StubWarehouseRepository(WarehouseAnalyticsRepository):
        def __init__(self) -> None:
            self.minimum_group_size = 5
            self._fallback = DemoAnalyticsRepository(minimum_group_size=5)
            self._schema_prefix = "marts."

        async def _rows(self, query: str, parameters: dict[str, object]) -> list[dict[str, Any]]:
            assert all(value != "'; drop table" for value in parameters.values())
            if "mart_workforce_summary" in query:
                return [
                    {
                        "snapshot_date": date(2025, 12, 31),
                        "total_headcount": 100,
                        "active_employees": 96,
                        "inactive_employees": 4,
                        "average_tenure_years": 3.2,
                        "hires_year_to_date": 20,
                        "terminations_year_to_date": 10,
                        "year_to_date_attrition_rate": 0.1,
                        "data_quality_score": 99.2,
                        "snapshot_loaded_at": "2026-01-01T02:00:00Z",
                    }
                ]
            if "mart_headcount" in query:
                return [
                    {
                        "snapshot_date": date(2025, 11, 30),
                        "department_name": "Engineering",
                        "location_id": "Pune",
                        "job_level": "L3",
                        "employment_type": "Full-time",
                        "headcount": 90,
                    },
                    {
                        "snapshot_date": date(2025, 12, 31),
                        "department_name": "Engineering",
                        "location_id": "Pune",
                        "job_level": "L3",
                        "employment_type": "Full-time",
                        "headcount": 96,
                    },
                    {
                        "snapshot_date": date(2025, 12, 31),
                        "department_name": "Tiny cohort",
                        "location_id": "Pune",
                        "job_level": "L5+",
                        "employment_type": "Full-time",
                        "headcount": 4,
                    },
                ]
            if "mart_attrition" in query:
                return [
                    {
                        "metric_month": date(2025, 11, 1),
                        "department_name": "Engineering",
                        "terminations": 4,
                        "voluntary_terminations": 3,
                        "involuntary_terminations": 1,
                        "average_headcount": 95,
                    },
                    {
                        "metric_month": date(2025, 12, 1),
                        "department_name": "Engineering",
                        "terminations": 5,
                        "voluntary_terminations": 4,
                        "involuntary_terminations": 1,
                        "average_headcount": 98,
                    },
                ]
            raise AssertionError("unexpected mart query")

    repository = StubWarehouseRepository()
    filters = WorkforceFilters()
    summary = asyncio.run(repository.workforce_summary(filters))
    headcount = asyncio.run(repository.headcount(filters))
    attrition = asyncio.run(repository.attrition(filters))
    hiring = asyncio.run(repository.hiring(filters))
    mobility = asyncio.run(repository.mobility(filters))
    diversity = asyncio.run(repository.diversity(filters))
    compensation = asyncio.run(repository.compensation(filters))
    learning = asyncio.run(repository.learning(filters))
    fallback_summary = asyncio.run(
        repository.workforce_summary(WorkforceFilters(legal_entity="Unsupported entity"))
    )

    assert summary.metadata.data_source is DataSource.WAREHOUSE
    assert summary.attrition_rate == 10
    assert summary.latest_refresh_time.tzinfo is not None
    assert headcount.total_headcount == 100
    assert [item.category for item in headcount.by_department] == ["Engineering"]
    assert headcount.metadata.suppressed_groups == 2
    assert attrition.terminations == 9
    assert attrition.by_type[0].category == "Voluntary"
    assert hiring.metadata.data_source is DataSource.DEMO
    assert mobility.metadata.data_source is DataSource.DEMO
    assert diversity.metadata.data_source is DataSource.DEMO
    assert compensation.metadata.data_source is DataSource.DEMO
    assert learning.metadata.data_source is DataSource.DEMO
    assert fallback_summary.metadata.data_source is DataSource.DEMO


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://user:password@db/example",
            "postgresql+asyncpg://user:password@db/example",
        ),
        (
            "postgres://user:password@db/example",
            "postgresql+asyncpg://user:password@db/example",
        ),
        (
            "postgresql+psycopg://user:password@db/example",
            "postgresql+asyncpg://user:password@db/example",
        ),
        ("sqlite:///example.db", "sqlite+aiosqlite:///example.db"),
        (
            "postgresql+asyncpg://user:password@db/example",
            "postgresql+asyncpg://user:password@db/example",
        ),
    ],
)
def test_database_urls_are_normalized_for_async_sqlalchemy(raw: str, expected: str) -> None:
    assert _async_database_url(raw) == expected


def test_repository_builder_selects_demo_warehouse_and_safe_invalid_fallback() -> None:
    demo_build = build_repository(Settings(_env_file=None, environment="test", database_url=None))
    warehouse_build = build_repository(
        Settings(
            _env_file=None,
            environment="test",
            database_url="postgresql+asyncpg://user:password@localhost/example",
        )
    )
    invalid_build = build_repository(
        Settings(
            _env_file=None,
            environment="test",
            database_url="mysql://user:password@localhost/example",
        )
    )

    assert demo_build.database_configured is False
    assert warehouse_build.database_configured is True
    assert warehouse_build.initialization_error is None
    assert invalid_build.initialization_error == "ValueError"
    asyncio.run(warehouse_build.repository.close())


def test_dependency_health_reports_initialization_and_runtime_degradation() -> None:
    invalid_settings = Settings(
        _env_file=None,
        environment="test",
        database_url="mysql://user:password@localhost/example",
        log_level="CRITICAL",
    )
    with TestClient(create_app(invalid_settings)) as invalid_client:
        initialization = invalid_client.get("/health/dependencies")
    assert initialization.json()["status"] == "degraded"
    assert initialization.json()["dependencies"][0]["status"] == "unavailable"

    class UnavailableRepository(DemoAnalyticsRepository):
        async def ping(self) -> float:
            raise RepositoryUnavailableError("private connection detail")

    local_settings = Settings(
        _env_file=None,
        environment="test",
        database_url=None,
        log_level="CRITICAL",
    )
    application = create_app(local_settings)
    with TestClient(application) as runtime_client:
        unavailable = UnavailableRepository()
        application.state.repository = unavailable
        application.state.repository_build = RepositoryBuild(
            repository=unavailable,
            database_configured=True,
        )
        runtime = runtime_client.get("/health/dependencies")

    assert runtime.json()["status"] == "degraded"
    assert runtime.json()["dependencies"][0]["detail"].startswith(
        "The configured analytics database"
    )


def test_json_formatter_allow_lists_context_and_redacts_exception_detail() -> None:
    formatter = JsonFormatter(service="peoplepulse-api", environment="test")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_complete",
        args=(),
        exc_info=None,
    )
    record.__dict__["status_code"] = 200
    record.__dict__["email"] = "must-not-appear@example.test"
    payload = json.loads(formatter.format(record))

    assert payload["service"] == "peoplepulse-api"
    assert payload["status_code"] == 200
    assert "must-not-appear" not in json.dumps(payload)

    try:
        raise ValueError("sensitive technical detail")
    except ValueError:
        record.exc_info = sys.exc_info()
    exception_payload = json.loads(formatter.format(record))
    assert exception_payload["exception_type"] == "ValueError"
    assert "sensitive technical detail" not in json.dumps(exception_payload)


def test_method_and_unexpected_errors_use_safe_problem_details() -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=None,
        log_level="CRITICAL",
    )
    application = create_app(settings)

    @application.get("/explode")
    async def explode() -> None:
        raise RuntimeError("private database password")

    with TestClient(application, raise_server_exceptions=False) as error_client:
        method = error_client.post("/health/live")
        unexpected = error_client.get("/explode")

    assert method.status_code == 405
    assert method.json()["error_code"] == "METHOD_NOT_ALLOWED"
    assert unexpected.status_code == 500
    assert unexpected.json()["error_code"] == "INTERNAL_ERROR"
    assert "private database password" not in unexpected.text
