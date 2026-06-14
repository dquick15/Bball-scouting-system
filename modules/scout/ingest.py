"""
modules/scout/ingest.py
========================
Data ingestion, normalization, and document-text construction for the scout chatbot.
Depends on shared.workbook for loading; handles SHA-256 cache keying.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pandas as pd
import streamlit as st

from shared.workbook import clean_dataframe, read_source, find_default_workbook

DEFAULT_DATA_FILES = [
    Path("aau_system/AAU_Scouting_System.xlsx"),
    Path("AAU_Scouting_System.xlsx"),
]


def prepare_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    return clean_dataframe(raw_df)


def build_document_text(record: dict[str, object]) -> str:
    parts = [
        f"Player: {record.get('Player Name', 'Unknown')}",
        f"Team: {record.get('Team', 'Unknown')}",
        f"Grade: {record.get('Grade', 'Unknown')}",
        f"Position: {record.get('Position', 'Unknown')}",
        f"Event: {record.get('Event Name', 'Unknown')}",
        f"Overall Score: {record.get('Overall Score', '')}",
        f"Growth Upside: {record.get('Growth Upside', '')}",
        f"Skill: {record.get('Skill Score', '')}",
        f"Athleticism: {record.get('Athleticism Score', '')}",
        f"Basketball IQ: {record.get('Basketball IQ Score', '')}",
        f"Competitive Traits: {record.get('Competitive Traits Score', '')}",
        f"Immediate Impact: {record.get('Immediate Impact Score', '')}",
        f"Strengths: {record.get('Strengths', '')}",
        f"Development Areas: {record.get('Development Areas', '')}",
        f"Projection: {record.get('Projection', '')}",
    ]
    return " | ".join(p for p in parts if p.split(": ", 1)[1])


def build_records(df: pd.DataFrame) -> list[dict[str, object]]:
    records = df.to_dict(orient="records")
    for record in records:
        record["document"] = build_document_text(record)
    return records


def dataframe_signature(df: pd.DataFrame) -> str:
    return sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()[:16]


@st.cache_data(show_spinner=False)
def load_chatbot_data() -> pd.DataFrame | None:
    default = find_default_workbook(["aau_system", "."])
    if default is None:
        return None
    raw = read_source(str(default))
    return clean_dataframe(raw)
