"""
shared/filters.py
=================
Reusable sidebar filter widgets and filter application logic.
All four pages use Team / Grade / Position / Event filters.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_sidebar_filters(df: pd.DataFrame, include_event: bool = True) -> pd.DataFrame:
    """
    Render multiselect filters in the sidebar and return the filtered DataFrame.
    """
    st.sidebar.header("Filters")

    teams = st.sidebar.multiselect("Team", options=sorted(df["Team"].dropna().unique()))
    grades = st.sidebar.multiselect("Grade", options=sorted(df["Grade"].dropna().unique()))
    positions = st.sidebar.multiselect("Position", options=sorted(df["Position"].dropna().unique()))

    events: list[str] = []
    if include_event and "Event Name" in df.columns:
        events = st.sidebar.multiselect("Event", options=sorted(df["Event Name"].dropna().unique()))

    return apply_filters(df, teams=teams, grades=grades, positions=positions, events=events)


def apply_filters(
    df: pd.DataFrame,
    teams: list[str] | None = None,
    grades: list[str] | None = None,
    positions: list[str] | None = None,
    events: list[str] | None = None,
) -> pd.DataFrame:
    """Apply filter lists to a DataFrame; empty lists are treated as 'all'."""
    filtered = df.copy()
    mapping: dict[str, list[str]] = {
        "Team": teams or [],
        "Grade": grades or [],
        "Position": positions or [],
        "Event Name": events or [],
    }
    for col, values in mapping.items():
        if values and col in filtered.columns:
            filtered = filtered[filtered[col].isin(values)]

    return filtered.reset_index(drop=True)
