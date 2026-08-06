"""Governance catalog, lineage, and classification views."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from dashboard.components.layout import page_header, privacy_note
from dashboard.services.api_client import ApiClient


def _lineage_chart(edges: list[dict[str, object]]) -> None:
    assets: list[str] = []
    for edge in edges:
        for key in ("source_asset", "target_asset"):
            asset = str(edge[key])
            if asset not in assets:
                assets.append(asset)
    index = {asset: position for position, asset in enumerate(assets)}
    palette = ["#0f766e", "#2a9d8f", "#457b9d", "#263a5b"]
    figure = go.Figure(
        go.Sankey(
            arrangement="snap",
            node={
                "label": assets,
                "pad": 18,
                "thickness": 16,
                "color": [palette[position % len(palette)] for position in range(len(assets))],
            },
            link={
                "source": [index[str(edge["source_asset"])] for edge in edges],
                "target": [index[str(edge["target_asset"])] for edge in edges],
                "value": [1 for _ in edges],
                "label": [str(edge["transformation"]) for edge in edges],
                "color": "rgba(15,118,110,.2)",
            },
        )
    )
    figure.update_layout(
        height=420,
        margin={"l": 8, "r": 8, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, sans-serif", "color": "#17233c"},
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})


def render(client: ApiClient, filters: dict[str, object]) -> None:
    del filters
    page_header(
        "Trust & controls",
        "Governance",
        "Certified assets, transformation lineage, sensitivity labels, and API exposure.",
    )
    catalog = client.catalog(limit=100).get("items", [])
    lineage = client.lineage(limit=100).get("items", [])
    classifications = client.classifications(limit=100).get("items", [])

    tab_catalog, tab_lineage, tab_classifications = st.tabs(
        ["Data catalog", "Lineage", "Classifications"]
    )
    with tab_catalog:
        st.dataframe(
            [
                {
                    "Asset": item["asset_id"],
                    "Name": item["name"],
                    "Layer": str(item["layer"]).title(),
                    "Owner": item["owner"],
                    "Classification": item["classification"],
                    "Refresh": item["refresh_frequency"],
                    "Documented": item["documented"],
                    "Description": item["description"],
                }
                for item in catalog
            ],
            hide_index=True,
            use_container_width=True,
        )
    with tab_lineage:
        if lineage:
            _lineage_chart(lineage)
            with st.expander("Transformation details"):
                st.dataframe(lineage, hide_index=True, use_container_width=True)
        else:
            st.info("No lineage edges are published.")
    with tab_classifications:
        st.dataframe(
            [
                {
                    "Asset": item["asset"],
                    "Column": item["column_name"],
                    "Classification": item["classification"],
                    "Handling": item["handling"],
                    "Exposed by API": item["exposed_by_api"],
                }
                for item in classifications
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "Column names document controls; the dashboard never requests or renders "
            "employee-level values."
        )
    privacy_note()
