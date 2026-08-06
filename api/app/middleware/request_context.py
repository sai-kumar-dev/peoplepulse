"""Request correlation and aggregate-only access logging."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from api.app.core.context import reset_request_id, set_request_id

logger = logging.getLogger(__name__)
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


def _request_id(request: Request) -> str:
    candidate = request.headers.get("X-Request-ID", "")
    if _VALID_REQUEST_ID.fullmatch(candidate):
        return candidate
    return str(uuid4())


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach a request ID and emit one log event without query/body/header values."""

    request_id = _request_id(request)
    token = set_request_id(request_id)
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = round((time.perf_counter() - started) * 1_000, 2)
        logger.info(
            "api_request_completed",
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        reset_request_id(token)
