"""RFC 7807-style errors and exception handlers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.app.core.context import current_request_id

logger = logging.getLogger(__name__)


class ProblemDetail(BaseModel):
    """Machine-readable, PII-safe API problem response."""

    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    instance: str
    error_code: str
    request_id: str | None = None
    retryable: bool = False


class ApiProblem(Exception):
    """Expected application error mapped to a problem-details document."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        title: str,
        detail: str,
        retryable: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(title)
        self.status_code = status_code
        self.error_code = error_code
        self.title = title
        self.detail = detail
        self.retryable = retryable
        self.headers = headers


def _problem_response(
    request: Request,
    *,
    status_code: int,
    error_code: str,
    title: str,
    detail: str,
    retryable: bool = False,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    problem = ProblemDetail(
        type=f"https://peoplepulse.local/problems/{error_code.lower().replace('_', '-')}",
        title=title,
        status=status_code,
        detail=detail,
        instance=request.url.path,
        error_code=error_code,
        request_id=current_request_id(),
        retryable=retryable,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
        headers=headers,
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Attach consistent handlers without exposing submitted values or stack traces."""

    @app.exception_handler(ApiProblem)
    async def api_problem_handler(request: Request, exc: ApiProblem) -> JSONResponse:
        logger.warning(
            "api_problem",
            extra={"error_code": exc.error_code, "status_code": exc.status_code},
        )
        return _problem_response(
            request,
            status_code=exc.status_code,
            error_code=exc.error_code,
            title=exc.title,
            detail=exc.detail,
            retryable=exc.retryable,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_problem_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = sorted(
            {
                ".".join(str(part) for part in error.get("loc", ()) if part != "query")
                for error in exc.errors()
            }
        )
        safe_fields = ", ".join(field for field in fields if field) or "request"
        return _problem_response(
            request,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            error_code="INVALID_FILTER",
            title="Request validation failed",
            detail=f"Invalid or missing value for: {safe_fields}.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_problem_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        try:
            title = HTTPStatus(exc.status_code).phrase
        except ValueError:
            title = "HTTP error"
        error_code = {
            int(HTTPStatus.NOT_FOUND): "NOT_FOUND",
            int(HTTPStatus.METHOD_NOT_ALLOWED): "METHOD_NOT_ALLOWED",
        }.get(exc.status_code, "HTTP_ERROR")
        return _problem_response(
            request,
            status_code=exc.status_code,
            error_code=error_code,
            title=title,
            detail=title,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_problem_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_api_error",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"error_code": "INTERNAL_ERROR", "status_code": 500},
        )
        return _problem_response(
            request,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_ERROR",
            title="Unexpected service error",
            detail="The service could not complete the request.",
            retryable=False,
        )
