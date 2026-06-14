"""
pages/4_Scout_Assistant.py
===========================
Page 4 — Basketball Scout Assistant (RAG chatbot).
Refactored from scout_chatbot/app.py to use shared/ and modules/scout imports.
Enhanced query parsing (age groups + roles) and pro-analyst fallback from modules/scout/chatbot.py.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from shared.workbook import find_default_workbook, load_from_path, load_from_upload
from shared.filters import apply_filters
from shared.secrets import get_openai_api_key
from modules.scout.chatbot import BasketballScoutAssistant
from modules.scout.ingest import build_records, dataframe_signature

st.set_page_config(
    page_title="Scout Assistant — AAU Scouting",
    page_icon="🤖",
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
# Cached resource helpers
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _get_assistant(api_key: str) -> BasketballScoutAssistant:
    return BasketballScoutAssistant(api_key=api_key)


# ---------------------------------------------------------------------------
# Render functions
# ---------------------------------------------------------------------------

def _render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")
    teams = st.sidebar.multiselect("Team", options=sorted(df["Team"].unique()))
    grades = st.sidebar.multiselect("Grade", options=sorted(df["Grade"].unique()))
    positions = st.sidebar.multiselect("Position", options=sorted(df["Position"].unique()))
    events = st.sidebar.multiselect("Event", options=sorted(df["Event Name"].unique()))
    return apply_filters(df, teams=teams, grades=grades, positions=positions, events=events)


def _render_quick_tools(assistant: BasketballScoutAssistant, df: pd.DataFrame) -> None:
    tab1, tab2, tab3 = st.tabs(["Player Lookup", "Event Summary", "Prospect Rankings"])

    with tab1:
        player_name = st.selectbox("Player profile", options=sorted(df["Player Name"].unique()))
        profile = assistant.player_profile(player_name, df)
        if profile is not None:
            player = profile["player"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Team", player["Team"])
            c2.metric("Grade", player["Grade"])
            c3.metric("Position", player["Position"])
            c4.metric("Score Change", f"{profile['improvement']:+.2f}")
            st.markdown(f"**Strengths**\n\n{player.get('Strengths', 'N/A')}")
            st.markdown(f"**Development Areas**\n\n{player.get('Development Areas', 'N/A')}")
            st.markdown(f"**Projection**\n\n{player.get('Projection', 'N/A')}")

            trend = px.line(
                profile["history"], x="Event Date", y="Overall Score",
                markers=True, title=f"Overall Score Trend: {player_name}",
                hover_data=["Event Name"],
            )
            trend.update_layout(margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(trend, use_container_width=True)

    with tab2:
        event_name = st.selectbox("Event summary", options=sorted(df["Event Name"].unique()))
        summary = assistant.event_summary(event_name, df)
        if summary is not None:
            c1, c2 = st.columns(2)
            c1.metric("Players Evaluated", summary["player_count"])
            c2.metric("Average Overall Score", f"{summary['average_score']:.2f}")
            st.markdown("**Top performers**")
            st.dataframe(
                summary["top_players"][["Player Name", "Team", "Position", "Overall Score"]],
                hide_index=True, use_container_width=True,
            )
            st.markdown("**Most promising prospects**")
            st.dataframe(
                summary["upside_players"][["Player Name", "Team", "Position", "Growth Upside", "Overall Score"]],
                hide_index=True, use_container_width=True,
            )

    with tab3:
        metric = st.selectbox("Ranking metric", options=["Overall Score", "Growth Upside"])
        rankings = assistant.prospect_rankings(df, metric=metric, top_k=15)
        st.dataframe(rankings, hide_index=True, use_container_width=True)


def _render_similar_players(assistant: BasketballScoutAssistant, df: pd.DataFrame) -> None:
    st.subheader("Similar Player Search")
    selected = st.selectbox(
        "Find similar players", options=sorted(df["Player Name"].unique()), key="similar-player"
    )
    if st.button("Find Similar Players", use_container_width=True):
        matches = assistant.similar_players(selected)
        if matches:
            match_df = pd.DataFrame(matches)
            display_cols = [c for c in ["Player Name", "Team", "Grade", "Position", "Event Name", "Overall Score", "similarity"] if c in match_df.columns]
            st.dataframe(match_df[display_cols], hide_index=True, use_container_width=True)
        else:
            st.info("No similar players were found for the selected player.")


def _render_chat(assistant: BasketballScoutAssistant, df: pd.DataFrame) -> None:
    st.subheader("Scout Chat")
    st.caption(
        "Ask about players, events, rankings, upside, or improvement trends. "
        "Supports age-group queries (15U, 16U, 17U, MS, HS) and role filters (guard, wing, forward, big)."
    )

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask a scouting question…")
    if not prompt:
        return

    st.session_state["chat_history"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching scouting records…"):
            result = assistant.answer_question(prompt, df)
        st.markdown(result["answer"])

        with st.expander("Retrieved scouting context"):
            records = result.get("retrieved_records", [])
            if records:
                rdf = pd.DataFrame(records)
                cols = [c for c in ["Player Name", "Team", "Grade", "Position", "Event Name", "Overall Score", "similarity"] if c in rdf.columns]
                st.dataframe(rdf[cols], hide_index=True, use_container_width=True)

    st.session_state["chat_history"].append({"role": "assistant", "content": result["answer"]})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("🤖 Basketball Scout Assistant")
    st.write(
        "Ask scouting questions across players, events, rankings, and development trends. "
        "Powered by a FAISS vector knowledge base with OpenAI semantic search and a "
        "local hash-embedding fallback."
    )

    try:
        df, source_name = _load_data()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    filtered_df = _render_sidebar_filters(df)
    if filtered_df.empty:
        st.warning("No scouting records match the selected filters.")
        st.stop()

    st.sidebar.success(f"Source: {source_name}")

    api_key = get_openai_api_key()
    if not api_key:
        st.error("OPENAI_API_KEY is not set. Configure it in your environment or Streamlit secrets.")
        st.stop()

    assistant = _get_assistant(api_key)

    with st.spinner("Building vector knowledge base…"):
        assistant.ensure_index(filtered_df)

    if assistant.vector_store.backend != "openai":
        st.warning(
            "OpenAI embeddings were unavailable — using local FAISS hash-embedding fallback. "
            "Answers remain data-grounded; semantic quality improves when API quota is restored."
        )

    _render_quick_tools(assistant, filtered_df)
    _render_similar_players(assistant, filtered_df)
    _render_chat(assistant, filtered_df)


main()
