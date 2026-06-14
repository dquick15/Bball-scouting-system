"""
pages/1_Stock_Tracker.py
=========================
Page 1 — Basketball Scouting Stock Tracker Dashboard.
Refactored from player_stock_tracker/dashboard.py to use shared/ imports.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from shared.workbook import (
    clean_dataframe,
    find_default_workbook,
    load_from_path,
    load_from_upload,
)
from shared.filters import apply_filters
from modules.stock_tracker.metrics import (
    get_dashboard_overview,
    get_top_fallers,
    get_top_players,
    get_top_risers,
    stock_movement_for_player,
)

st.set_page_config(
    page_title="Stock Tracker — AAU Scouting",
    page_icon="📈",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_data():
    uploaded = st.sidebar.file_uploader(
        "Upload scouting export",
        type=["csv", "xlsx", "xls"],
        help="Upload the AAU_Scouting_System.xlsx workbook or a CSV export.",
    )
    if uploaded is not None:
        return load_from_upload(uploaded), uploaded.name

    default = find_default_workbook(["aau_system", "."])
    if default:
        return load_from_path(str(default)), default.name

    raise FileNotFoundError(
        "No data file found. Upload a scouting export or place AAU_Scouting_System.xlsx "
        "in the aau_system folder."
    )


# ---------------------------------------------------------------------------
# Render functions
# ---------------------------------------------------------------------------

def _render_metric_cards(df) -> None:
    overview = get_dashboard_overview(df)
    top = get_top_players(df)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Players Tracked", overview["total_players"])
    c2.metric("Total Events Tracked", overview["total_events"])
    c3.metric("Average Player Score", f"{overview['average_player_score']:.2f}")

    st.subheader("Top 10 Highest-Rated Players")
    st.dataframe(top, use_container_width=True, hide_index=True)


def _render_overview_charts(df) -> None:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Top Risers")
        risers = get_top_risers(df)
        if risers.empty:
            st.info("Not enough data to calculate stock movement.")
        else:
            fig = px.bar(
                risers.sort_values("Stock Movement", ascending=True),
                x="Stock Movement", y="Player Name",
                color="Stock Label", orientation="h", text="Stock Movement",
                color_discrete_map={"Stock Up": "#1f7a1f", "Stable": "#b58900", "Stock Down": "#b22222"},
            )
            fig.update_traces(texttemplate="%{text:+.2f}", textposition="outside")
            fig.update_layout(margin=dict(l=0, r=20, t=20, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Top Fallers")
        fallers = get_top_fallers(df)
        if fallers.empty:
            st.info("Not enough data to calculate stock movement.")
        else:
            fig = px.bar(
                fallers.sort_values("Stock Movement", ascending=False),
                x="Stock Movement", y="Player Name",
                color="Stock Label", orientation="h", text="Stock Movement",
                color_discrete_map={"Stock Up": "#1f7a1f", "Stable": "#b58900", "Stock Down": "#b22222"},
            )
            fig.update_traces(texttemplate="%{text:+.2f}", textposition="outside")
            fig.update_layout(margin=dict(l=0, r=20, t=20, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Overall Score Distribution")
    hist = px.histogram(df, x="Overall Score", nbins=20, color_discrete_sequence=["#1f4e79"], opacity=0.85)
    hist.update_layout(bargap=0.08, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(hist, use_container_width=True)


def _render_player_trend(df) -> None:
    st.subheader("Player Trend Analysis")
    player_name = st.selectbox("Select a player", options=sorted(df["Player Name"].unique()))
    player_df = df[df["Player Name"] == player_name].sort_values(["Event Date", "Event Name"])

    summary = stock_movement_for_player(player_df)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Starting Score", f"{summary['starting_score']:.2f}")
    m2.metric("Current Score", f"{summary['current_score']:.2f}")
    m3.metric("Stock Movement", f"{summary['stock_movement']:+.2f}")
    m4.metric("Stock Label", str(summary["stock_label"]))

    c1, c2 = st.columns(2)
    with c1:
        fig = px.line(
            player_df, x="Event Date", y="Overall Score",
            color_discrete_sequence=["#0d3b66"], markers=True,
            hover_data=["Event Name", "Team", "Grade", "Position"],
            title=f"Overall Score Trend: {player_name}",
        )
        fig.update_layout(margin=dict(l=0, r=0, t=60, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.line(
            player_df, x="Event Date", y="Growth Upside",
            color_discrete_sequence=["#ee964b"], markers=True,
            hover_data=["Event Name", "Team", "Grade", "Position"],
            title=f"Growth Upside Trend: {player_name}",
        )
        fig.update_layout(margin=dict(l=0, r=0, t=60, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.caption("Stock movement = latest Overall Score minus earliest Overall Score in the active filter context.")


def _render_sidebar_filters(df):
    st.sidebar.header("Filters")
    teams = st.sidebar.multiselect("Team", options=sorted(df["Team"].dropna().unique()))
    grades = st.sidebar.multiselect("Grade", options=sorted(df["Grade"].dropna().unique()))
    positions = st.sidebar.multiselect("Position", options=sorted(df["Position"].dropna().unique()))
    events = st.sidebar.multiselect("Event", options=sorted(df["Event Name"].dropna().unique()))
    return apply_filters(df, teams=teams, grades=grades, positions=positions, events=events)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("📈 Basketball Scouting Stock Tracker")
    st.write("Track player performance, identify stock movement, and compare evaluation trends across events.")

    try:
        base_df, source_name = _load_data()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    st.sidebar.success(f"Source: {source_name}")
    filtered_df = _render_sidebar_filters(base_df)

    if filtered_df.empty:
        st.warning("No records match the selected filters.")
        st.stop()

    _render_metric_cards(filtered_df)
    _render_overview_charts(filtered_df)
    _render_player_trend(filtered_df)


main()
