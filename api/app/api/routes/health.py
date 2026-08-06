"""Liveness, readiness, and dependency diagnostics."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request

from api.app.core.config import Settings
from api.app.repositories.analytics import RepositoryUnavailableError
from api.app.schemas.common import (
    DependenciesResponse,
    DependencyStatus,
    HealthResponse,
    HealthStatus,
)

router = APIRouter(prefix="/health", tags=["health"])


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("/live", response_model=HealthResponse)
async def live(request: Request) -> HealthResponse:
    settings = _settings(request)
    return HealthResponse(
        status=HealthStatus.OK,
        service=settings.service_name,
        version=settings.api_version,
    )


async def _dependency_statuses(request: Request) -> tuple[HealthStatus, list[DependencyStatus]]:
    settings = _settings(request)
    build = request.app.state.repository_build
    repository = request.app.state.repository
    dependencies: list[DependencyStatus] = []
    overall = HealthStatus.READY

    if not build.database_configured:
        dependencies.append(
            DependencyStatus(
                name="analytics_database",
                status=HealthStatus.OK,
                required=False,
                latency_ms=0,
                detail="Not configured; deterministic aggregate demo repository is active.",
            )
        )
    elif build.initialization_error:
        dependencies.append(
            DependencyStatus(
                name="analytics_database",
                status=HealthStatus.UNAVAILABLE,
                required=not settings.demo_fallback_enabled,
                detail="The configured database adapter could not be initialized.",
            )
        )
        overall = HealthStatus.DEGRADED
    else:
        try:
            latency_ms = await repository.ping()
            dependencies.append(
                DependencyStatus(
                    name="analytics_database",
                    status=HealthStatus.OK,
                    required=not settings.demo_fallback_enabled,
                    latency_ms=latency_ms,
                    detail="The configured analytics database accepted a probe.",
                )
            )
        except RepositoryUnavailableError:
            dependencies.append(
                DependencyStatus(
                    name="analytics_database",
                    status=HealthStatus.UNAVAILABLE,
                    required=not settings.demo_fallback_enabled,
                    detail="The configured analytics database did not accept a probe.",
                )
            )
            overall = (
                HealthStatus.DEGRADED
                if settings.demo_fallback_enabled
                else HealthStatus.UNAVAILABLE
            )

    dependencies.append(
        DependencyStatus(
            name="aggregate_serving",
            status=HealthStatus.OK
            if overall is not HealthStatus.UNAVAILABLE
            else HealthStatus.UNAVAILABLE,
            required=True,
            latency_ms=0,
            detail=(
                "Trusted aggregate responses are available."
                if overall is not HealthStatus.UNAVAILABLE
                else "Trusted aggregate responses are unavailable."
            ),
        )
    )
    return overall, dependencies


@router.get("/ready", response_model=HealthResponse)
async def ready(request: Request) -> HealthResponse:
    settings = _settings(request)
    status, _ = await _dependency_statuses(request)
    return HealthResponse(
        status=status,
        service=settings.service_name,
        version=settings.api_version,
    )


@router.get("/dependencies", response_model=DependenciesResponse)
async def dependencies(request: Request) -> DependenciesResponse:
    status, checks = await _dependency_statuses(request)
    return DependenciesResponse(status=status, dependencies=checks)
