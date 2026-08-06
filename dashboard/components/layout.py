"""Shared dashboard layout, filters, and display helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st


def inject_theme() -> None:
    """Apply a restrained enterprise theme without external assets."""

    st.markdown(
        """
        <style>
          :root {
            --pp-ink: #17233c;
            --pp-muted: #64748b;
            --pp-teal: #0f766e;
            --pp-line: #e2e8f0;
            --pp-panel: #f8fafc;
          }
          [data-testid="stAppViewContainer"] {
            background:
              radial-gradient(circle at 100% 0%, rgba(15,118,110,.08), transparent 28rem),
              #ffffff;
          }
          [data-testid="stSidebar"] {
            border-right: 1px solid var(--pp-line);
            background: #f8fafc;
          }
          .pp-kicker {
            color: var(--pp-teal);
            font-size: .72rem;
            font-weight: 750;
            letter-spacing: .14em;
            text-transform: uppercase;
            margin-bottom: .35rem;
          }
          .pp-title {
            color: var(--pp-ink);
            font-size: 2rem;
            font-weight: 720;
            letter-spacing: -.035em;
            line-height: 1.05;
            margin: 0;
          }
          .pp-subtitle {
            color: var(--pp-muted);
            font-size: .95rem;
            margin: .45rem 0 1.3rem;
          }
          .pp-note {
            background: var(--pp-panel);
            border: 1px solid var(--pp-line);
            border-left: 3px solid var(--pp-teal);
            border-radius: .45rem;
            color: #475569;
            font-size: .82rem;
            padding: .7rem .9rem;
          }
          [data-testid="stMetric"] {
            background: rgba(255,255,255,.92);
            border: 1px solid var(--pp-line);
            border-radius: .7rem;
            padding: .8rem 1rem;
            box-shadow: 0 2px 8px rgba(15,23,42,.035);
          }
          [data-testid="stMetricLabel"] { color: var(--pp-muted); }
          [data-testid="stMetricValue"] { color: var(--pp-ink); }
          footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="pp-kicker">{kicker}</div>
        <h1 class="pp-title">{title}</h1>
        <p class="pp-subtitle">{subtitle}</p>
        """,
        unsafe_allow_html=True,
    )


def privacy_note() -> None:
    st.markdown(
        """
        <div class="pp-note">
          Aggregate view only | direct identifiers are blocked | small groups follow
          the configured suppression threshold.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_filters() -> dict[str, Any]:
    """Return only allow-listed workforce dimensions."""

    st.sidebar.markdown("### Reporting scope")
    start_date = st.sidebar.date_input("From", value=date(2025, 1, 1), key="filter_start")
    end_date = st.sidebar.date_input("To", value=date(2025, 12, 31), key="filter_end")
    department = st.sidebar.selectbox(
        "Department",
        ["All", "Engineering", "Sales", "Operations", "Finance", "People", "Marketing"],
    )
    location = st.sidebar.selectbox("Location", ["All", "Bengaluru", "Pune", "Hyderabad", "Remote"])
    job_level = st.sidebar.selectbox("Job level", ["All", "L1", "L2", "L3", "L4", "L5+"])
    employment_type = st.sidebar.selectbox(
        "Employment type", ["All", "Full-time", "Part-time", "Contract"]
    )
    work_arrangement = st.sidebar.selectbox(
        "Work arrangement", ["All", "Hybrid", "Onsite", "Remote"]
    )
    if start_date > end_date:
        st.sidebar.error("The start date must be on or before the end date.")
        start_date = end_date
    return {
        "start_date": start_date,
        "end_date": end_date,
        "department": None if department == "All" else department,
        "location": None if location == "All" else location,
        "job_level": None if job_level == "All" else job_level,
        "employment_type": None if employment_type == "All" else employment_type,
        "work_arrangement": None if work_arrangement == "All" else work_arrangement,
    }


def show_source_metadata(payload: dict[str, Any]) -> None:
    metadata = payload.get("metadata", {})
    source = str(metadata.get("data_source", "unknown")).title()
    generated = str(metadata.get("generated_at", "unknown"))
    minimum = metadata.get("minimum_group_size", "-")
    st.caption(f"Source: {source} | Generated: {generated} | Minimum reportable group: {minimum}")


def format_integer(value: Any) -> str:
    return f"{int(value or 0):,}"


def format_percent(value: Any) -> str:
    return f"{float(value or 0):.1f}%"
