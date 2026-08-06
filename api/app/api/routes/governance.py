"""Metadata-only governance catalog, lineage, and classification routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from api.app.api.dependencies import AnalyticsServiceDependency
from api.app.schemas.common import Page
from api.app.schemas.operations import CatalogAsset, Classification, LineageEdge

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/catalog", response_model=Page[CatalogAsset])
async def catalog(
    service: AnalyticsServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    layer: Annotated[
        str | None, Query(min_length=1, max_length=32, pattern=r"^[A-Za-z_]+$")
    ] = None,
) -> Page[CatalogAsset]:
    return await service.catalog(offset=offset, limit=limit, layer=layer)


@router.get("/lineage", response_model=Page[LineageEdge])
async def lineage(
    service: AnalyticsServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    asset: Annotated[
        str | None,
        Query(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:@/-]+$"),
    ] = None,
) -> Page[LineageEdge]:
    return await service.lineage(offset=offset, limit=limit, asset=asset)


@router.get("/classifications", response_model=Page[Classification])
async def classifications(
    service: AnalyticsServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    classification: Annotated[
        str | None, Query(min_length=1, max_length=64, pattern=r"^[A-Za-z_]+$")
    ] = None,
) -> Page[Classification]:
    return await service.classifications(
        offset=offset,
        limit=limit,
        classification=classification,
    )
