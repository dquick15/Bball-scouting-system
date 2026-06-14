"""
shared/workbook.py
==================
Single source of truth for loading and normalizing the AAU scouting workbook
across all four application modules.

The AAU_Scouting_System.xlsx workbook uses two primary sheets:
  - Player_Evaluations  — per-player per-event rows
  - Event_Log           — event metadata including date ranges

All four original apps had their own near-identical copies of this logic.
This module replaces all of them.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Master column definitions
# ---------------------------------------------------------------------------

# Full evaluation columns produced from the raw workbook (superset of all pages)
WORKBOOK_COLUMNS = [
    "Player Name",
    "Team",
    "Grade",
    "Position",
    "Strengths",
    "Development Areas",
    "Projection",
    "Event Name",
    "Event Date",
    "Overall Score",
    "Growth Upside",
    "Skill Score",
    "Athleticism Score",
    "Basketball IQ Score",
    "Competitive Traits Score",
    "Immediate Impact Score",
]

NUMERIC_COLUMNS = [
    "Overall Score",
    "Growth Upside",
    "Skill Score",
    "Athleticism Score",
    "Basketball IQ Score",
    "Competitive Traits Score",
    "Immediate Impact Score",
]

TEXT_COLUMNS = [
    "Player Name",
    "Team",
    "Grade",
    "Position",
    "Strengths",
    "Development Areas",
    "Projection",
    "Event Name",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_event_start_date(value: object) -> pd.Timestamp:
    """Parse the first date from an AAU date-range string like '04/03/2026 - 04/05/2026'."""
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    if not text:
        return pd.NaT
    return pd.to_datetime(text.split(" - ", maxsplit=1)[0].strip(), errors="coerce")


def _normalize_aau_workbook(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Join Player_Evaluations with Event_Log and return a wide flat DataFrame
    with all WORKBOOK_COLUMNS populated.
    """
    evaluations = sheets["Player_Evaluations"].copy()
    events = sheets["Event_Log"].copy()

    evaluations.columns = [str(c).strip() for c in evaluations.columns]
    events.columns = [str(c).strip() for c in events.columns]

    merged = evaluations.merge(
        events[["Event ID", "Event Name", "Date"]],
        on="Event ID",
        how="left",
    )

    notable_moments = (
        merged["Event Name"].fillna("Unknown Event").astype(str).str.strip()
        + " | "
        + merged["Date"].map(
            lambda v: str(v).split(" - ", maxsplit=1)[0] if pd.notna(v) else "Unknown Date"
        )
    )

    return pd.DataFrame(
        {
            "Player Name": merged["Player Name"],
            "Team": merged["Team"],
            "Grade": merged["Level"],
            "Position": merged["Position"],
            "Strengths": merged["Strengths"],
            "Development Areas": merged["Development Areas"],
            "Projection": merged["Projection"],
            "Event Name": merged["Event Name"],
            "Event Date": merged["Date"].map(_extract_event_start_date),
            "Overall Score": merged["Overall Grade"],
            "Growth Upside": merged["Growth Upside (1-5)"],
            "Skill Score": merged["Skill (1-5)"],
            "Athleticism Score": merged["Athleticism (1-5)"],
            "Basketball IQ Score": merged["IQ (1-5)"],
            "Competitive Traits Score": merged["Competitive Traits (1-5)"],
            "Immediate Impact Score": merged["Immediate Impact (1-5)"],
        }
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_source(source) -> pd.DataFrame:
    """
    Read a CSV or Excel upload/path and return a raw DataFrame.
    For AAU workbooks the two-sheet join is applied automatically.
    For plain spreadsheets the first sheet whose columns match is used.
    """
    source_name = getattr(source, "name", str(source))
    suffix = Path(source_name).suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(source)

    if suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(source, sheet_name=None)
        normalized = {str(k).strip(): v for k, v in sheets.items()}

        if "Player_Evaluations" in normalized and "Event_Log" in normalized:
            return _normalize_aau_workbook(normalized)

        # Fall through: any sheet that has the superset of columns
        for df in normalized.values():
            candidate = df.copy()
            candidate.columns = [str(c).strip() for c in candidate.columns]
            if all(col in candidate.columns for col in ["Player Name", "Overall Score"]):
                return candidate

    raise ValueError(
        "Unsupported file. Upload a CSV export or the AAU_Scouting_System.xlsx workbook."
    )


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise column types, fill missing text with 'Unknown', coerce numerics,
    and add any optional columns that are absent.
    Returns a sorted, clean DataFrame.
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Add optional columns that might not be in every CSV schema
    for col in WORKBOOK_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df["Event Date"] = pd.to_datetime(df["Event Date"], errors="coerce")

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in TEXT_COLUMNS:
        df[col] = df[col].fillna("Unknown").astype(str).str.strip()
        df.loc[df[col] == "", col] = "Unknown"

    df = df.dropna(subset=["Overall Score"])
    df = df[df["Player Name"] != "Unknown"].copy()
    df = df.sort_values(
        ["Player Name", "Event Date", "Event Name"]
    ).reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False)
def load_from_path(path: str) -> pd.DataFrame:
    """Cached load from a file path."""
    return clean_dataframe(read_source(path))


def load_from_upload(uploaded_file) -> pd.DataFrame:
    """Load from a Streamlit UploadedFile object (never cached, unique each run)."""
    return clean_dataframe(read_source(uploaded_file))


def find_default_workbook(search_roots: list[str] | None = None) -> Path | None:
    """
    Walk the supplied roots (or the default list) looking for an AAU workbook
    or CSV export.  Returns the first file found.
    """
    candidates: list[Path] = []
    roots = search_roots or ["aau_system", "."]
    for root in roots:
        for name in ["AAU_Scouting_System.xlsx", "scouting_export.csv"]:
            candidates.append(Path(root) / name)

    for path in candidates:
        if path.exists():
            return path

    return None
