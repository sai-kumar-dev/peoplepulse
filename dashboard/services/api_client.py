"""Cached, PII-defensive client for the PeoplePulse aggregate API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import streamlit as st

_BLOCKED_VALUE_KEYS = frozenset(
    {
        "employee_id",
        "candidate_id",
        "application_id",
        "first_name",
        "last_name",
        "preferred_name",
        "legal_name",
        "email",
        "phone",
        "date_of_birth",
        "birth_date",
        "base_salary",
        "bonus_paid",
        "raw_payload",
    }
)


class DashboardApiError(RuntimeError):
    """Safe user-facing API access failure."""


def assert_aggregate_only(value: Any, *, path: str = "$") -> None:
    """Reject direct identifiers and raw PII by key before dashboard rendering."""

    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = str(raw_key).casefold()
            if key in _BLOCKED_VALUE_KEYS:
                raise DashboardApiError(f"Aggregate privacy guard rejected field at {path}.{key}.")
            assert_aggregate_only(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            assert_aggregate_only(nested, path=f"{path}[{index}]")


def _normalize_params(params: Mapping[str, Any] | None) -> tuple[tuple[str, str], ...]:
    if not params:
        return ()
    normalized: list[tuple[str, str]] = []
    for key, value in sorted(params.items()):
        if value is None or value == "":
            continue
        normalized.append((key, value.isoformat() if isinstance(value, date) else str(value)))
    return tuple(normalized)


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("PeoplePulse API URL must be an absolute HTTP(S) URL")
    return base_url.rstrip("/")


def _request_json(
    *,
    base_url: str,
    path: str,
    params: tuple[tuple[str, str], ...],
    timeout_seconds: float,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    if not path.startswith("/") or ".." in path:
        raise DashboardApiError("The dashboard attempted an invalid API path.")
    try:
        with httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
            headers={
                "Accept": "application/json",
                "X-Request-ID": f"dashboard-{uuid4()}",
                "User-Agent": "peoplepulse-dashboard/1.0",
            },
        ) as client:
            response = client.get(path, params=params)
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise DashboardApiError(
            "The analytics API is not reachable. Confirm that the API service is running."
        ) from exc

    if response.is_error:
        detail = "The analytics API could not complete this request."
        try:
            problem = response.json()
            if isinstance(problem, dict) and isinstance(problem.get("detail"), str):
                detail = problem["detail"]
        except ValueError:
            pass
        raise DashboardApiError(f"{detail} (HTTP {response.status_code})")

    try:
        payload = response.json()
    except ValueError as exc:
        raise DashboardApiError("The analytics API returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise DashboardApiError("The analytics API returned an unexpected payload.")
    assert_aggregate_only(payload)
    return payload


@st.cache_data(ttl=60, show_spinner=False, max_entries=256)
def _cached_request_json(
    base_url: str,
    path: str,
    params: tuple[tuple[str, str], ...],
    timeout_seconds: float,
) -> dict[str, Any]:
    return _request_json(
        base_url=base_url,
        path=path,
        params=params,
        timeout_seconds=timeout_seconds,
    )


class ApiClient:
    """Small synchronous client suitable for Streamlit's execution model."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 8.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = _validate_base_url(
            base_url
            if base_url is not None
            else os.getenv(
                "PEOPLEPULSE_API_URL",
                os.getenv("PEOPLEPULSE_API_BASE_URL", "http://localhost:8000"),
            )
        )
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        normalized = _normalize_params(params)
        if self._transport is not None:
            return _request_json(
                base_url=self.base_url,
                path=path,
                params=normalized,
                timeout_seconds=self.timeout_seconds,
                transport=self._transport,
            )
        return _cached_request_json(
            self.base_url,
            path,
            normalized,
            self.timeout_seconds,
        )

    def health(self) -> dict[str, Any]:
        return self.get("/health/ready")

    def summary(self, filters: Mapping[str, Any]) -> dict[str, Any]:
        return self.get("/api/v1/workforce/summary", filters)

    def headcount(self, filters: Mapping[str, Any]) -> dict[str, Any]:
        return self.get("/api/v1/workforce/headcount", filters)

    def attrition(self, filters: Mapping[str, Any]) -> dict[str, Any]:
        return self.get("/api/v1/workforce/attrition", filters)

    def hiring(self, filters: Mapping[str, Any]) -> dict[str, Any]:
        return self.get("/api/v1/workforce/hiring", filters)

    def pipeline_runs(self, *, limit: int = 25) -> dict[str, Any]:
        return self.get("/api/v1/pipelines/runs", {"limit": limit})

    def quality_checks(self, *, limit: int = 100) -> dict[str, Any]:
        return self.get("/api/v1/data-quality", {"limit": limit})

    def catalog(self, *, limit: int = 100) -> dict[str, Any]:
        return self.get("/api/v1/governance/catalog", {"limit": limit})

    def lineage(self, *, limit: int = 100) -> dict[str, Any]:
        return self.get("/api/v1/governance/lineage", {"limit": limit})

    def classifications(self, *, limit: int = 100) -> dict[str, Any]:
        return self.get("/api/v1/governance/classifications", {"limit": limit})
