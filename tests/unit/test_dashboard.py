"""Unit tests for the cached dashboard query/privacy layer."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from dashboard.services.api_client import (
    ApiClient,
    DashboardApiError,
    _normalize_params,
    assert_aggregate_only,
)


def test_privacy_guard_accepts_aggregate_metrics() -> None:
    assert_aggregate_only(
        {
            "total_headcount": 100,
            "median_base_salary": 1_000_000,
            "items": [{"category": "Engineering", "value": 30}],
        }
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "synthetic@example.test"},
        {"items": [{"employee_id": "E-1"}]},
        {"nested": {"base_salary": 100_000}},
        {"raw_payload": {"arbitrary": "value"}},
    ],
)
def test_privacy_guard_rejects_employee_level_fields(payload: object) -> None:
    with pytest.raises(DashboardApiError, match="privacy guard"):
        assert_aggregate_only(payload)


def test_api_client_serializes_filters_and_checks_payload() -> None:
    observed: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "total_headcount": 42,
                "metadata": {"data_source": "demo"},
            },
        )

    client = ApiClient(
        base_url="http://peoplepulse.test",
        transport=httpx.MockTransport(handler),
    )
    payload = client.headcount(
        {
            "start_date": date(2025, 1, 1),
            "department": "Engineering",
            "location": None,
        }
    )

    assert payload["total_headcount"] == 42
    assert observed == {
        "department": "Engineering",
        "start_date": "2025-01-01",
    }


def test_api_client_rejects_pii_from_upstream() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"total_headcount": 1, "items": [{"email": "bad@example.test"}]},
        )
    )
    client = ApiClient(base_url="http://peoplepulse.test", transport=transport)

    with pytest.raises(DashboardApiError, match=r"\$\.items\[0\]\.email"):
        client.summary({})


def test_api_problem_detail_becomes_safe_dashboard_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            503,
            json={
                "error_code": "DATABASE_UNAVAILABLE",
                "detail": "Trusted aggregate data is temporarily unavailable.",
            },
        )
    )
    client = ApiClient(base_url="http://peoplepulse.test", transport=transport)

    with pytest.raises(DashboardApiError, match="Trusted aggregate data"):
        client.summary({})


def test_network_failure_becomes_actionable_dashboard_error() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = ApiClient(
        base_url="http://peoplepulse.test",
        transport=httpx.MockTransport(fail),
    )
    with pytest.raises(DashboardApiError, match="not reachable"):
        client.health()


@pytest.mark.parametrize(
    "base_url",
    ["file:///tmp/api", "localhost:8000", "javascript:alert(1)", ""],
)
def test_api_client_requires_absolute_http_url(base_url: str) -> None:
    with pytest.raises(ValueError, match=r"HTTP\(S\)"):
        ApiClient(base_url=base_url)


def test_filter_normalization_is_stable_and_omits_empty_values() -> None:
    assert _normalize_params(
        {
            "location": None,
            "department": "People",
            "start_date": date(2025, 2, 1),
            "empty": "",
        }
    ) == (("department", "People"), ("start_date", "2025-02-01"))
