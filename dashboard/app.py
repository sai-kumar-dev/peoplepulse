"""PeoplePulse Streamlit entry point."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

from dashboard.components.layout import inject_theme, render_sidebar_filters
from dashboard.pages import (
    attrition,
    data_quality,
    executive_overview,
    governance,
    headcount,
    pipeline_health,
    recruitment,
)
from dashboard.services.api_client import ApiClient, DashboardApiError

st.set_page_config(
    page_title="PeoplePulse | Workforce intelligence",
    page_icon="P",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()

PageRenderer = Callable[[ApiClient, dict[str, Any]], None]
PAGES: dict[str, PageRenderer] = {
    "Executive overview": executive_overview.render,
    "Headcount": headcount.render,
    "Attrition": attrition.render,
    "Recruitment": recruitment.render,
    "Pipeline health": pipeline_health.render,
    "Data quality": data_quality.render,
    "Governance": governance.render,
}
WORKFORCE_PAGES = {
    "Executive overview",
    "Headcount",
    "Attrition",
    "Recruitment",
}


def main() -> None:
    st.sidebar.markdown(
        """
        <div class="pp-kicker">PeoplePulse</div>
        <div style="font-size:1.2rem;font-weight:720;color:#17233c;margin-bottom:.9rem">
          Workforce intelligence
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected = st.sidebar.radio("Navigate", list(PAGES), label_visibility="collapsed")
    client = ApiClient()

    try:
        health = client.health()
        status = str(health.get("status", "unknown"))
        if status in {"ok", "ready"}:
            st.sidebar.success("Analytics API ready")
        elif status == "degraded":
            st.sidebar.warning("Analytics API in fallback mode")
        else:
            st.sidebar.error("Analytics API unavailable")
    except DashboardApiError:
        st.sidebar.error("Analytics API unavailable")

    filters = render_sidebar_filters() if selected in WORKFORCE_PAGES else {}
    st.sidebar.divider()
    st.sidebar.caption(
        "Aggregate analytics only | no names, personal contacts, dates of birth, "
        "or employee-level compensation."
    )

    try:
        PAGES[selected](client, filters)
    except DashboardApiError as exc:
        st.error(str(exc))
        st.info("Start the FastAPI service or verify PEOPLEPULSE_API_URL, then refresh this page.")


if __name__ == "__main__":
    main()
