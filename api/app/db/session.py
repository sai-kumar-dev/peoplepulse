"""Async SQLAlchemy engine construction and repository selection."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from api.app.core.config import Settings
from api.app.repositories.analytics import AnalyticsRepository, DemoAnalyticsRepository
from api.app.repositories.warehouse import WarehouseAnalyticsRepository


@dataclass(frozen=True)
class RepositoryBuild:
    repository: AnalyticsRepository
    database_configured: bool
    initialization_error: str | None = None


def _async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://") or url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    raise ValueError("Only PostgreSQL and SQLite async database URLs are supported")


def create_engine(settings: Settings) -> AsyncEngine:
    """Create a bounded async engine without opening a connection."""

    if not settings.database_url:
        raise ValueError("database_url is not configured")
    url = _async_database_url(settings.database_url)
    common: dict[str, object] = {
        "pool_pre_ping": True,
        "echo": False,
    }
    if not url.startswith("sqlite+"):
        common.update(
            {
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_pool_size,
                "pool_recycle": 1_800,
            }
        )
    return create_async_engine(url, **common)


def build_repository(settings: Settings) -> RepositoryBuild:
    """Prefer configured warehouse aggregates and retain a deterministic fallback."""

    demo = DemoAnalyticsRepository(minimum_group_size=settings.minimum_reportable_group_size)
    if not settings.database_url:
        return RepositoryBuild(repository=demo, database_configured=False)
    try:
        engine = create_engine(settings)
        repository = WarehouseAnalyticsRepository(
            engine=engine,
            schema=settings.warehouse_schema,
            query_timeout_seconds=settings.query_timeout_seconds,
            minimum_group_size=settings.minimum_reportable_group_size,
            fallback=demo if settings.demo_fallback_enabled else None,
            sqlite=settings.database_url.startswith("sqlite"),
        )
        return RepositoryBuild(repository=repository, database_configured=True)
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        if not settings.demo_fallback_enabled:
            raise
        return RepositoryBuild(
            repository=demo,
            database_configured=True,
            initialization_error=type(exc).__name__,
        )
