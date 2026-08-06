"""Consistent Plotly chart helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import plotly.graph_objects as go
import streamlit as st

_TEAL = "#0f766e"
_NAVY = "#263a5b"
_PALETTE = ["#0f766e", "#2a9d8f", "#457b9d", "#5c6f91", "#94a3b8", "#cbd5e1"]


def _base_layout(title: str) -> dict[str, Any]:
    return {
        "title": {"text": title, "font": {"size": 16, "color": "#17233c"}},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Inter, system-ui, sans-serif", "color": "#475569"},
        "margin": {"l": 8, "r": 8, "t": 52, "b": 8},
        "hoverlabel": {"bgcolor": "#17233c", "font_color": "white"},
        "legend": {"orientation": "h", "y": -0.16},
    }


def time_series(
    points: Sequence[dict[str, Any]],
    *,
    title: str,
    value_key: str = "value",
    value_label: str = "Value",
    percent: bool = False,
) -> None:
    figure = go.Figure(
        go.Scatter(
            x=[point.get("period") for point in points],
            y=[point.get(value_key, 0) for point in points],
            mode="lines+markers",
            name=value_label,
            line={"color": _TEAL, "width": 3},
            marker={"size": 7, "color": "white", "line": {"color": _TEAL, "width": 2}},
            hovertemplate=(
                "%{x}<br>%{y:.2f}%<extra></extra>"
                if percent
                else "%{x}<br>%{y:,.0f}<extra></extra>"
            ),
        )
    )
    figure.update_layout(**_base_layout(title))
    figure.update_xaxes(showgrid=False)
    figure.update_yaxes(gridcolor="#e2e8f0", ticksuffix="%" if percent else "")
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})


def category_bars(
    points: Sequence[dict[str, Any]],
    *,
    title: str,
    horizontal: bool = False,
    percent: bool = False,
) -> None:
    categories = [str(point.get("category", "Unknown")) for point in points]
    values = [float(point.get("value", 0)) for point in points]
    trace = (
        go.Bar(
            x=values,
            y=categories,
            orientation="h",
            marker_color=_PALETTE[: len(values)],
            hovertemplate="%{y}<br>%{x:,.2f}<extra></extra>",
        )
        if horizontal
        else go.Bar(
            x=categories,
            y=values,
            marker_color=_PALETTE[: len(values)],
            hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>",
        )
    )
    figure = go.Figure(trace)
    figure.update_layout(**_base_layout(title), showlegend=False)
    figure.update_xaxes(
        gridcolor="#e2e8f0" if horizontal else None,
        showgrid=horizontal,
        ticksuffix="%" if percent and horizontal else "",
    )
    figure.update_yaxes(
        gridcolor="#e2e8f0" if not horizontal else None,
        showgrid=not horizontal,
        ticksuffix="%" if percent and not horizontal else "",
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})


def status_donut(values: dict[str, int], *, title: str) -> None:
    figure = go.Figure(
        go.Pie(
            labels=list(values),
            values=list(values.values()),
            hole=0.68,
            marker={"colors": [_TEAL, "#d97706", "#dc2626", _NAVY]},
            textinfo="label+value",
            hovertemplate="%{label}: %{value}<extra></extra>",
        )
    )
    figure.update_layout(**_base_layout(title), showlegend=False)
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
