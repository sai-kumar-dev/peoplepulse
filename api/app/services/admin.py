"""Idempotent local simulation of privileged operational commands."""

from __future__ import annotations

import asyncio
import hashlib
import json

from api.app.core.security import Principal
from api.app.schemas.operations import (
    AdminOperationResponse,
    GenerateDataRequest,
    ReprocessRejectedRequest,
    TriggerPipelineRequest,
)


class AdminOperationService:
    """Record accepted commands without directly coupling HTTP to Airflow or generators."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._operations: dict[str, AdminOperationResponse] = {}

    @staticmethod
    def _operation_id(operation: str, payload: dict[str, object]) -> str:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode()
        digest = hashlib.sha256(operation.encode() + b":" + encoded).hexdigest()[:20]
        return f"op-{digest}"

    async def _accept(
        self,
        *,
        operation: str,
        payload: dict[str, object],
        principal: Principal,
        message: str,
    ) -> AdminOperationResponse:
        operation_id = self._operation_id(operation, payload)
        async with self._lock:
            existing = self._operations.get(operation_id)
            if existing is not None:
                return existing
            response = AdminOperationResponse(
                operation_id=operation_id,
                operation=operation,
                status="scheduled",
                requested_by_role=principal.role,
                message=message,
            )
            self._operations[operation_id] = response
            return response

    async def generate_data(
        self, request: GenerateDataRequest, principal: Principal
    ) -> AdminOperationResponse:
        return await self._accept(
            operation="generate-data",
            payload=request.model_dump(mode="json"),
            principal=principal,
            message="Synthetic data generation was accepted for local orchestration.",
        )

    async def trigger_ingestion(
        self, request: TriggerPipelineRequest, principal: Principal
    ) -> AdminOperationResponse:
        return await self._accept(
            operation="trigger-ingestion",
            payload=request.model_dump(mode="json"),
            principal=principal,
            message="The ingestion trigger was accepted.",
        )

    async def trigger_transformation(
        self, request: TriggerPipelineRequest, principal: Principal
    ) -> AdminOperationResponse:
        return await self._accept(
            operation="trigger-transformation",
            payload=request.model_dump(mode="json"),
            principal=principal,
            message="The transformation trigger was accepted.",
        )

    async def reprocess_rejected(
        self, request: ReprocessRejectedRequest, principal: Principal
    ) -> AdminOperationResponse:
        return await self._accept(
            operation="reprocess-rejected",
            payload=request.model_dump(mode="json"),
            principal=principal,
            message="Rejected-record identifiers were accepted for controlled reprocessing.",
        )
