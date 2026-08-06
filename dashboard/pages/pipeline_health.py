"""Operational pipeline status."""

from __future__ import annotations

import streamlit as st

from dashboard.components.charts import status_donut
from dashboard.components.layout import format_integer, page_header, privacy_note
from dashboard.services.api_client import ApiClient


def render(client: ApiClient, filters: dict[str, object]) -> None:
    del filters
    page_header(
        "Platform operations",
        "Pipeline health",
        "Recent orchestration outcomes, throughput, rejects, and retry signals.",
    )
    payload = client.pipeline_runs(limit=100)
    runs = payload.get("items", [])

    status_counts: dict[str, int] = {}
    for run in runs:
        status = str(run.get("status", "unknown")).title()
        status_counts[status] = status_counts.get(status, 0) + 1
    succeeded = status_counts.get("Succeeded", 0)
    rejected = sum(int(run.get("records_rejected", 0)) for run in runs)
    loaded = sum(int(run.get("records_loaded", 0)) for run in runs)

    columns = st.columns(4)
    columns[0].metric("Runs", format_integer(len(runs)))
    columns[1].metric("Succeeded", format_integer(succeeded))
    columns[2].metric("Records loaded", format_integer(loaded))
    columns[3].metric("Records rejected", format_integer(rejected))

    left, right = st.columns([1, 2.4])
    with left:
        status_donut(status_counts or {"No results": 1}, title="Run outcomes")
    with right:
        st.subheader("Recent runs")
        st.dataframe(
            [
                {
                    "Run ID": run["run_id"],
                    "Pipeline": run["pipeline_id"],
                    "Status": str(run["status"]).title(),
                    "Started": run["started_at"],
                    "Duration (s)": run.get("duration_seconds"),
                    "Loaded": run.get("records_loaded", 0),
                    "Rejected": run.get("records_rejected", 0),
                    "Retries": run.get("retry_count", 0),
                    "Error code": run.get("error_code"),
                }
                for run in runs
            ],
            hide_index=True,
            use_container_width=True,
        )
    st.caption(f"Showing {len(runs)} of {payload.get('total', len(runs))} recent runs.")
    privacy_note()
