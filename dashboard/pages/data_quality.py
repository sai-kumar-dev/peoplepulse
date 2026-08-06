"""Data quality scorecard and check outcomes."""

from __future__ import annotations

import streamlit as st

from dashboard.components.charts import category_bars, status_donut
from dashboard.components.layout import format_integer, page_header, privacy_note
from dashboard.services.api_client import ApiClient


def render(client: ApiClient, filters: dict[str, object]) -> None:
    del filters
    page_header(
        "Trust & controls",
        "Data quality",
        "Persisted validity, completeness, consistency, and freshness results.",
    )
    payload = client.quality_checks(limit=100)
    checks = payload.get("items", [])
    status_counts: dict[str, int] = {}
    dimension_scores: dict[str, list[float]] = {}
    for check in checks:
        status = str(check.get("status", "unknown")).title()
        status_counts[status] = status_counts.get(status, 0) + 1
        dimension = str(check.get("dimension", "other")).title()
        dimension_scores.setdefault(dimension, []).append(float(check.get("score", 0)))

    average_score = (
        sum(float(check.get("score", 0)) for check in checks) / len(checks) if checks else 0
    )
    affected = sum(int(check.get("affected_rows", 0)) for check in checks)
    critical_failures = sum(
        1
        for check in checks
        if check.get("severity") == "critical" and check.get("status") == "failed"
    )

    columns = st.columns(4)
    columns[0].metric("Quality score", f"{average_score:.1f}%")
    columns[1].metric("Checks", format_integer(len(checks)))
    columns[2].metric("Critical failures", format_integer(critical_failures))
    columns[3].metric("Affected rows", format_integer(affected))

    left, right = st.columns(2)
    with left:
        status_donut(status_counts or {"No results": 1}, title="Check outcomes")
    with right:
        category_bars(
            [
                {
                    "category": dimension,
                    "value": sum(scores) / len(scores),
                }
                for dimension, scores in dimension_scores.items()
            ],
            title="Average score by quality dimension",
            horizontal=True,
            percent=True,
        )

    st.subheader("Persisted checks")
    st.dataframe(
        [
            {
                "Check": check["check_name"],
                "Dataset": check["dataset"],
                "Dimension": str(check["dimension"]).title(),
                "Severity": str(check["severity"]).title(),
                "Status": str(check["status"]).title(),
                "Score": check["score"],
                "Checked": check["checked_at"],
                "Summary": check["safe_summary"],
            }
            for check in checks
        ],
        hide_index=True,
        use_container_width=True,
    )
    privacy_note()
