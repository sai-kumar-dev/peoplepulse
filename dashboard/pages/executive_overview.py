"""Executive KPI overview."""

from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.components.charts import status_donut
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
        "Executive overview",
        "Workforce at a glance",
        "Certified workforce, talent, and platform-health indicators for the selected scope.",
    )
    summary = client.summary(filters)

    first = st.columns(5)
    first[0].metric("Total headcount", format_integer(summary["total_headcount"]))
    first[1].metric("Active employees", format_integer(summary["active_employees"]))
    first[2].metric("New hires", format_integer(summary["new_hires"]))
    first[3].metric("Terminations", format_integer(summary["terminations"]))
    first[4].metric("Attrition rate", format_percent(summary["attrition_rate"]))

    second = st.columns(5)
    second[0].metric("Open requisitions", format_integer(summary["open_requisitions"]))
    second[1].metric("Offer acceptance", format_percent(summary["offer_acceptance_rate"]))
    second[2].metric("Average tenure", f"{float(summary['average_tenure_years']):.1f} yrs")
    second[3].metric("Data quality", format_percent(summary["data_quality_score"]))
    second[4].metric("Inactive employees", format_integer(summary["inactive_employees"]))

    pipeline_payload = client.pipeline_runs(limit=20)
    quality_payload = client.quality_checks(limit=100)
    runs = pipeline_payload.get("items", [])
    checks = quality_payload.get("items", [])

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Latest platform signals")
        latest = runs[:4]
        if latest:
            st.dataframe(
                [
                    {
                        "Pipeline": run["pipeline_id"].replace("_", " ").title(),
                        "Status": str(run["status"]).title(),
                        "Started": run["started_at"],
                        "Duration (s)": run.get("duration_seconds"),
                        "Loaded": run.get("records_loaded", 0),
                    }
                    for run in latest
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No pipeline runs are available for this scope.")
    with right:
        status_counts: dict[str, int] = {}
        for check in checks:
            status = str(check.get("status", "unknown")).title()
            status_counts[status] = status_counts.get(status, 0) + 1
        status_donut(status_counts or {"No results": 1}, title="Quality-check outcomes")

    st.caption(f"Latest certified refresh: {summary['latest_refresh_time']}")
    show_source_metadata(summary)
    privacy_note()
