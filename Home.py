"""
Home.py
=======
AAU Basketball Scouting Platform — main entry point.
This file is the root of the Streamlit multi-page app.
Navigation to the four tool pages is handled by Streamlit's pages/ system.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="AAU Basketball Scouting Platform",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏀 AAU Basketball Scouting Platform")
st.write(
    "A unified scouting intelligence suite for scouts, recruiters, and coaches. "
    "Use the sidebar to navigate between the four tools."
)

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Stock Tracker")
    st.write(
        "Track player performance across events, identify risers and fallers, "
        "and visualize individual score trends over time."
    )

    st.subheader("🏆 Event Talent Index")
    st.write(
        "Score and rank basketball tournaments by talent concentration, upside, "
        "positional diversity, and roster depth using the proprietary ETI formula."
    )

with col2:
    st.subheader("📋 AI Report Generator")
    st.write(
        "Generate polished, recruiter-ready scouting reports in five writing modes "
        "using GPT-4.1-mini. Export to DOCX or PDF."
    )

    st.subheader("🤖 Scout Assistant")
    st.write(
        "Ask natural language scouting questions against the full player database. "
        "Supports age-group filters (15U/16U/17U/MS/HS), role queries (guard/wing/big), "
        "and FAISS-backed semantic retrieval."
    )

st.markdown("---")
st.info(
    "**Data:** Upload the AAU_Scouting_System.xlsx workbook from the sidebar on any page, "
    "or place it in the `aau_system/` folder and it will be loaded automatically."
)
