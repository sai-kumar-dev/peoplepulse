"""Recruitment funnel and hiring outcomes."""

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
        "Talent acquisition",
        "Recruitment",
        "Hiring flow, funnel conversion, source mix, and delivery speed.",
    )
    payload = client.hiring(filters)

    columns = st.columns(5)
    columns[0].metric("Applications", format_integer(payload["applications"]))
    columns[1].metric("Offers", format_integer(payload["offers"]))
    columns[2].metric("Hires", format_integer(payload["hires"]))
    columns[3].metric("Offer acceptance", format_percent(payload["offer_acceptance_rate"]))
    columns[4].metric("Time to hire", f"{float(payload['average_time_to_hire_days']):.1f} days")

    time_series(payload["hiring_trend"], title="Monthly hires")
    left, right = st.columns(2)
    with left:
        category_bars(
            payload["recruitment_funnel"],
            title="Recruitment funnel",
            horizontal=True,
        )
    with right:
        category_bars(
            payload["by_source_channel"],
            title="Hires by source channel",
            horizontal=True,
        )

    show_source_metadata(payload)
    privacy_note()
