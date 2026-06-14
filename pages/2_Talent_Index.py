"""
pages/2_Talent_Index.py
========================
Page 2 — Event Talent Index.
Refactored from bball_talent_index/app.py to use shared/ imports.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from shared.workbook import find_default_workbook, load_from_path, load_from_upload
from shared.filters import apply_filters
from modules.talent_index.event_scoring import (
    calculate_event_summary,
    comparison_metrics,
    get_event_detail,
)

st.set_page_config(
    page_title="Event Talent Index — AAU Scouting",
    page_icon="🏆",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_data():
    uploaded = st.sidebar.file_uploader(
        "Upload scouting export",
        type=["csv", "xlsx", "xls"],
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

def _render_overview(summary_df) -> None:
    best = summary_df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events Evaluated", int(summary_df["Event Name"].nunique()))
    c2.metric("Average Talent Index", f"{summary_df['Talent Index'].mean():.2f}")
    c3.metric("Highest-Ranked Event", str(best["Event Name"]))
    c4.metric("Top Event Grade", str(best["Grade"]))


def _render_leaderboard(summary_df) -> None:
    st.subheader("Event Rankings Leaderboard")
    fig = px.bar(
        summary_df.sort_values("Talent Index", ascending=True),
        x="Talent Index", y="Event Name",
        color="Grade", orientation="h", text="Talent Index",
        color_discrete_sequence=["#0f4c5c", "#2c7da0", "#468faf", "#89c2d9", "#d9ed92"],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(margin=dict(l=0, r=20, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        summary_df[[
            "Event Name", "Talent Index", "Grade", "Players Evaluated",
            "Average Overall Score", "Average Growth Upside",
            "Top Performers", "Most Promising Prospects", "Position Breakdown",
        ]],
        hide_index=True,
        use_container_width=True,
    )


def _render_distributions(summary_df) -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Talent Distribution")
        fig = px.histogram(summary_df, x="Talent Index", nbins=12, color_discrete_sequence=["#1d3557"])
        fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("Upside Distribution")
        fig = px.box(summary_df, y="Average Growth Upside", points="all", color_discrete_sequence=["#e76f51"])
        fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)


def _render_event_detail(df, summary_df) -> None:
    st.subheader("Event Comparison Dashboard")
    selected_events = st.multiselect(
        "Select events to compare",
        options=summary_df["Event Name"].tolist(),
        default=summary_df["Event Name"].head(min(3, len(summary_df))).tolist(),
    )
    if selected_events:
        metrics_df = comparison_metrics(summary_df, selected_events)
        fig = px.line_polar(
            metrics_df, r="Value", theta="Metric",
            color="Event Name", line_close=True,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)

    selected_event = st.selectbox("Inspect an event", options=summary_df["Event Name"].tolist())
    detail = get_event_detail(df, selected_event)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Talent Index", f"{detail['Talent Index']:.2f}")
    m2.metric("Grade", str(detail["Grade"]))
    m3.metric("Players Evaluated", int(detail["Players Evaluated"]))
    m4.metric("Elite Player Density", f"{detail['Elite Player Density']:.2f}%")

    i1, i2 = st.columns(2)
    with i1:
        st.markdown(f"**Top Performers**\n\n{detail['Top Performers']}")
        st.markdown(f"**Most Promising Prospects**\n\n{detail['Most Promising Prospects']}")
    with i2:
        st.markdown(f"**Position Breakdown**\n\n{detail['Position Breakdown']}")
        st.markdown(
            f"**Scoring Inputs**\n\n"
            f"Average Overall Score: {detail['Average Overall Score']:.2f}  \n"
            f"Average Growth Upside: {detail['Average Growth Upside']:.2f}  \n"
            f"Event Depth Score: {detail['Event Depth Score']:.2f}"
        )

    st.dataframe(
        detail["event_df"][["Player Name", "Team", "Grade", "Position", "Growth Upside", "Overall Score"]],
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("🏆 Event Talent Index")
    st.write("Evaluate basketball tournaments by talent concentration, upside, diversity, and roster depth.")

    try:
        df, source_name = _load_data()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    st.sidebar.success(f"Source: {source_name}")
    st.sidebar.header("Filters")
    grades = st.sidebar.multiselect("Grade", options=sorted(df["Grade"].unique()))
    positions = st.sidebar.multiselect("Position", options=sorted(df["Position"].unique()))
    teams = st.sidebar.multiselect("Team", options=sorted(df["Team"].unique()))

    filtered_df = apply_filters(df, teams=teams, grades=grades, positions=positions)
    if filtered_df.empty:
        st.warning("No evaluations match the selected filters.")
        st.stop()

    summary_df = calculate_event_summary(filtered_df)
    if summary_df.empty:
        st.warning("No event summaries could be calculated from the filtered data.")
        st.stop()

    _render_overview(summary_df)
    _render_leaderboard(summary_df)
    _render_distributions(summary_df)
    _render_event_detail(filtered_df, summary_df)


main()
