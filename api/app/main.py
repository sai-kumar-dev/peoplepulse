"""PeoplePulse FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app.api.routes import admin, governance, health, operations, workforce
from api.app.core.config import Settings, get_settings
from api.app.core.errors import ProblemDetail, install_exception_handlers
from api.app.core.logging import configure_logging
from api.app.db.session import build_repository
from api.app.middleware.request_context import request_context_middleware
from api.app.services.admin import AdminOperationService


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct an isolated application, allowing deterministic test settings."""

    runtime_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(
            service=runtime_settings.service_name,
            environment=runtime_settings.environment,
            level=runtime_settings.log_level,
        )
        repository_build = build_repository(runtime_settings)
        application.state.settings = runtime_settings
        application.state.repository_build = repository_build
        application.state.repository = repository_build.repository
        application.state.admin_service = AdminOperationService()
        try:
            yield
        finally:
            await repository_build.repository.close()

    application = FastAPI(
        title="PeoplePulse Analytics API",
        summary="Governed workforce aggregates and platform observability.",
        description=(
            "Typed, aggregate-only access to certified people analytics marts. "
            "Employee-level PII is intentionally absent from every analytics contract."
        ),
        version=runtime_settings.api_version,
        lifespan=lifespan,
        contact={"name": "People Data Platform"},
        license_info={"name": "MIT"},
        responses={
            400: {"model": ProblemDetail},
            401: {"model": ProblemDetail},
            403: {"model": ProblemDetail},
            404: {"model": ProblemDetail},
            422: {"model": ProblemDetail},
            500: {"model": ProblemDetail},
            503: {"model": ProblemDetail},
        },
    )
    application.dependency_overrides[get_settings] = lambda: runtime_settings
    application.middleware("http")(request_context_middleware)
    install_exception_handlers(application)

    application.include_router(health.router)
    application.include_router(workforce.router, prefix="/api/v1")
    application.include_router(operations.router, prefix="/api/v1")
    application.include_router(governance.router, prefix="/api/v1")
    application.include_router(admin.router, prefix="/api/v1")
    return application


app = create_app()
