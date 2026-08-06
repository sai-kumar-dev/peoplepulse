"""Role-protected simulated operational commands."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from api.app.api.dependencies import AdminServiceDependency
from api.app.core.security import Principal, require_admin
from api.app.schemas.operations import (
    AdminOperationResponse,
    GenerateDataRequest,
    ReprocessRejectedRequest,
    TriggerPipelineRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])
AdminPrincipal = Annotated[Principal, Depends(require_admin)]


@router.post(
    "/generate-data",
    response_model=AdminOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_data(
    request: GenerateDataRequest,
    service: AdminServiceDependency,
    principal: AdminPrincipal,
) -> AdminOperationResponse:
    return await service.generate_data(request, principal)


@router.post(
    "/trigger-ingestion",
    response_model=AdminOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_ingestion(
    request: TriggerPipelineRequest,
    service: AdminServiceDependency,
    principal: AdminPrincipal,
) -> AdminOperationResponse:
    return await service.trigger_ingestion(request, principal)


@router.post(
    "/trigger-transformation",
    response_model=AdminOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_transformation(
    request: TriggerPipelineRequest,
    service: AdminServiceDependency,
    principal: AdminPrincipal,
) -> AdminOperationResponse:
    return await service.trigger_transformation(request, principal)


@router.post(
    "/reprocess-rejected",
    response_model=AdminOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_rejected(
    request: ReprocessRejectedRequest,
    service: AdminServiceDependency,
    principal: AdminPrincipal,
) -> AdminOperationResponse:
    return await service.reprocess_rejected(request, principal)
