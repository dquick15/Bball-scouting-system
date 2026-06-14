"""
pages/3_Report_Generator.py
============================
Page 3 — AI Basketball Scouting Report Generator.
Refactored from scouting_report_gen/app.py to use shared/ imports.
"""
from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from shared.workbook import find_default_workbook, load_from_path, load_from_upload
from shared.secrets import get_openai_api_key
from modules.report_gen.prompts import REPORT_MODES
from modules.report_gen.report_generator import (
    ScoutingReportGenerator,
    create_docx_bytes,
    create_pdf_bytes,
)

st.set_page_config(
    page_title="Report Generator — AAU Scouting",
    page_icon="📋",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_data():
    uploaded = st.sidebar.file_uploader(
        "Upload scouting export",
        type=["csv", "xlsx", "xls"],
        help="Upload the AAU workbook or a CSV scouting export.",
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
# Render helpers
# ---------------------------------------------------------------------------

def _render_profile_card(record: pd.Series) -> None:
    st.subheader("Player Profile")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Team", record["Team"])
    c2.metric("Grade", record["Grade"])
    c3.metric("Position", record["Position"])
    c4.metric("Projection", record.get("Projection", "N/A"))

    n1, n2, n3 = st.columns(3)
    n1.markdown(f"**Strengths**\n\n{record.get('Strengths', 'N/A')}")
    n2.markdown(f"**Development Areas**\n\n{record.get('Development Areas', 'N/A')}")
    # "Notable Game Moments" is derived from Event Name + Date in the shared workbook
    notable = record.get("Event Name", "N/A")
    n3.markdown(f"**Event**\n\n{notable}")


def _render_scores(record: pd.Series) -> None:
    st.subheader("Scores Visualization")
    score_data = {
        "Category": ["Skill Score", "Athleticism Score", "Basketball IQ Score", "Growth Upside"],
        "Score": [
            record.get("Skill Score", 0),
            record.get("Athleticism Score", 0),
            record.get("Basketball IQ Score", 0),
            record.get("Growth Upside", 0),
        ],
    }
    fig = px.bar(
        score_data, x="Category", y="Score", text="Score",
        color="Category",
        color_discrete_sequence=["#0f4c5c", "#e36414", "#5f0f40", "#6a994e"],
        range_y=[0, 5],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)


def _render_copy_button(report_text: str) -> None:
    escaped = json.dumps(report_text)
    components.html(
        f"""
        <div style="margin-top:0.5rem;">
          <button
            style="background:#0f4c5c;color:white;border:none;border-radius:8px;
                   padding:0.65rem 1rem;cursor:pointer;font-weight:600;"
            onclick='navigator.clipboard.writeText({escaped})
              .then(() => {{ this.innerText = "Copied ✓"; }});'
          >Copy to clipboard</button>
        </div>
        """,
        height=56,
    )


def _render_generated_report(player_name: str, mode: str, report_text: str) -> None:
    st.subheader("Generated Report")
    st.write(report_text)
    _render_copy_button(report_text)

    docx_bytes = create_docx_bytes(player_name, mode, report_text)
    pdf_bytes = create_pdf_bytes(player_name, mode, report_text)
    e1, e2 = st.columns(2)
    e1.download_button(
        "Download DOCX", data=docx_bytes,
        file_name=f"{player_name.lower().replace(' ', '_')}_{mode.lower().replace(' ', '_')}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
    e2.download_button(
        "Download PDF", data=pdf_bytes,
        file_name=f"{player_name.lower().replace(' ', '_')}_{mode.lower().replace(' ', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("📋 AI Basketball Scouting Report Generator")
    st.write("Generate polished, recruiter-ready scouting reports from player evaluation data.")

    try:
        df, source_name = _load_data()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    st.sidebar.success(f"Source: {source_name}")
    st.sidebar.caption("Set OPENAI_API_KEY in your environment or Streamlit secrets to enable generation.")

    selected_player = st.selectbox("Select a player", options=sorted(df["Player Name"].unique()))
    selected_mode = st.radio("Report mode", options=list(REPORT_MODES.keys()), horizontal=False)

    player_rows = df[df["Player Name"] == selected_player].reset_index(drop=True)
    player_record = player_rows.iloc[0]

    # Build the player_record dict expected by the generator
    record_dict = player_record.to_dict()
    # Map shared column names to generator's expected keys
    record_dict["Growth Upside Score"] = record_dict.get("Growth Upside", 0)
    record_dict["Notable Game Moments"] = (
        f"{record_dict.get('Event Name', 'N/A')} | {record_dict.get('Event Date', 'N/A')}"
    )

    left_col, right_col = st.columns([1.1, 1.2])
    with left_col:
        _render_profile_card(player_record)
    with right_col:
        _render_scores(player_record)

    api_key = get_openai_api_key()
    generator_disabled = not api_key
    if generator_disabled:
        st.info(
            "Add an OpenAI API key to generate reports. "
            "The player profile and scores remain available without it."
        )

    if st.button("Generate Scouting Report", type="primary", use_container_width=True, disabled=generator_disabled):
        try:
            generator = ScoutingReportGenerator(api_key=api_key)
            with st.spinner("Generating report..."):
                report_text = generator.generate_report(record_dict, selected_mode)
            st.session_state["rg_report"] = report_text
            st.session_state["rg_player"] = selected_player
            st.session_state["rg_mode"] = selected_mode
        except Exception as exc:
            st.error(f"Report generation failed: {exc}")

    if (
        st.session_state.get("rg_report")
        and st.session_state.get("rg_player") == selected_player
    ):
        _render_generated_report(
            player_name=st.session_state["rg_player"],
            mode=st.session_state.get("rg_mode", selected_mode),
            report_text=st.session_state["rg_report"],
        )


main()
