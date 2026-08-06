"""Headcount trend and approved dimension breakdowns."""

from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.components.charts import category_bars, time_series
from dashboard.components.layout import (
    format_integer,
    page_header,
    privacy_note,
    show_source_metadata,
)
from dashboard.services.api_client import ApiClient


def render(client: ApiClient, filters: dict[str, Any]) -> None:
    page_header(
        "Workforce",
        "Headcount",
        "Monthly workforce scale and distribution across governed organizational dimensions.",
    )
    payload = client.headcount(filters)

    metric_col, context_col = st.columns([1, 4])
    metric_col.metric("Current headcount", format_integer(payload["total_headcount"]))
    context_col.info(f"As of {payload['as_of_date']}")

    time_series(payload["trend"], title="Monthly headcount trend")
    left, right = st.columns(2)
    with left:
        category_bars(
            payload["by_department"],
            title="Department breakdown",
            horizontal=True,
        )
        category_bars(
            payload["by_job_level"],
            title="Job-level breakdown",
        )
    with right:
        category_bars(
            payload["by_location"],
            title="Location breakdown",
            horizontal=True,
        )
        category_bars(
            payload["by_employment_type"],
            title="Employment-type breakdown",
        )

    show_source_metadata(payload)
    privacy_note()
