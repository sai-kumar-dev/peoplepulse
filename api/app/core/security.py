"""Small local bearer-token role model for protected demo operations."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from enum import StrEnum
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from api.app.core.config import Settings, get_settings
from api.app.core.errors import ApiProblem

bearer_scheme = HTTPBearer(auto_error=False)


class Role(StrEnum):
    ANALYST = "analyst"
    ADMIN = "admin"


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str
    role: Role


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    """Resolve a configured local token without logging or echoing it."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiProblem(
            status_code=HTTPStatus.UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            title="Authentication required",
            detail="Supply a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if secrets.compare_digest(token, settings.admin_token.get_secret_value()):
        return Principal(subject="local-admin", role=Role.ADMIN)
    if secrets.compare_digest(token, settings.analyst_token.get_secret_value()):
        return Principal(subject="local-analyst", role=Role.ANALYST)
    raise ApiProblem(
        status_code=HTTPStatus.UNAUTHORIZED,
        error_code="UNAUTHORIZED",
        title="Invalid credentials",
        detail="The supplied Bearer token is not valid.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*allowed_roles: Role) -> Callable[..., Principal]:
    """Create a dependency enforcing one of the supplied roles."""

    def dependency(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
        if principal.role not in allowed_roles:
            raise ApiProblem(
                status_code=HTTPStatus.FORBIDDEN,
                error_code="FORBIDDEN",
                title="Insufficient permission",
                detail="This operation requires a different role.",
            )
        return principal

    return dependency


require_admin = require_roles(Role.ADMIN)
