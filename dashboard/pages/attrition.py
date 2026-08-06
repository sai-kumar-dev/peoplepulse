"""Attrition trends and cohort-safe breakdowns."""

from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.components.charts import category_bars, time_series
from dashboard.components.layout import (
    format_integer,
    format_percent,
    page_header,
    privacy_note,
    show_source_metadata,
)
from dashboard.services.api_client import ApiClient


def render(client: ApiClient, filters: dict[str, Any]) -> None:
    page_header(
        "Workforce",
        "Attrition",
        "Rolling workforce exits, separation type, and organizational hot spots.",
    )
    payload = client.attrition(filters)

    columns = st.columns(3)
    columns[0].metric("Terminations", format_integer(payload["terminations"]))
    columns[1].metric("Attrition rate", format_percent(payload["attrition_rate"]))
    columns[2].metric("Reporting period", f"{payload['start_date']} to {payload['end_date']}")

    time_series(
        payload["trend"],
        title="Monthly attrition rate",
        value_key="attrition_rate",
        value_label="Attrition rate",
        percent=True,
    )
    left, right = st.columns(2)
    with left:
        category_bars(payload["by_type"], title="Voluntary vs involuntary")
        category_bars(
            payload["by_tenure_band"],
            title="Terminations by tenure band",
            horizontal=True,
        )
    with right:
        category_bars(
            payload["by_department"],
            title="Terminations by department",
            horizontal=True,
        )
        category_bars(payload["by_job_level"], title="Terminations by job level")

    st.caption(
        "Manager-level slices are intentionally omitted from the executive view "
        "unless every cohort meets the reportability threshold."
    )
    show_source_metadata(payload)
    privacy_note()
