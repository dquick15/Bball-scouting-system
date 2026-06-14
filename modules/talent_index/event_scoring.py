"""
modules/talent_index/event_scoring.py
=======================================
Event Talent Index calculation.
Ported from bball_talent_index/event_scoring.py — no logic changes.

ETI formula (0-100):
  avg_overall/5*100 * 0.30
  + avg_upside/5*100 * 0.20
  + elite_density      * 0.20   (% players with Overall >= 4.25)
  + positional_div     * 0.10   (normalised Shannon entropy)
  + team_div           * 0.10
  + depth_score        * 0.10
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


ELITE_SCORE_THRESHOLD = 4.25


def _normalized_entropy(series: pd.Series) -> float:
    counts = series.value_counts(normalize=True)
    if counts.empty or len(counts) == 1:
        return 0.0
    entropy = -(counts * np.log2(counts)).sum()
    max_entropy = math.log2(len(counts))
    return float(entropy / max_entropy) if max_entropy else 0.0


def _event_depth_score(event_df: pd.DataFrame) -> float:
    overall = event_df["Overall Score"].dropna()
    upside = event_df["Growth Upside"].dropna()
    if overall.empty or upside.empty:
        return 0.0
    return round(
        0.45 * (float(overall.median()) / 5 * 100)
        + 0.35 * (float(overall.quantile(0.35)) / 5 * 100)
        + 0.20 * (float(upside.quantile(0.65)) / 5 * 100),
        2,
    )


def _grade_from_index(value: float) -> str:
    thresholds = [(95, "A+"), (90, "A"), (85, "A-"), (80, "B+"), (75, "B"),
                  (70, "B-"), (65, "C+"), (60, "C"), (55, "C-"), (50, "D")]
    for threshold, grade in thresholds:
        if value >= threshold:
            return grade
    return "F"


def calculate_event_summary(df: pd.DataFrame) -> pd.DataFrame:
    summaries: list[dict[str, object]] = []

    for event_name, event_df in df.groupby("Event Name"):
        player_count = int(event_df["Player Name"].nunique())
        avg_overall = float(event_df["Overall Score"].mean())
        avg_upside = float(event_df["Growth Upside"].mean())
        elite_density = float((event_df["Overall Score"] >= ELITE_SCORE_THRESHOLD).mean()) * 100
        positional_diversity = _normalized_entropy(event_df["Position"]) * 100
        team_diversity = _normalized_entropy(event_df["Team"]) * 100
        depth_score = _event_depth_score(event_df)

        talent_index = round(
            (avg_overall / 5 * 100) * 0.30
            + (avg_upside / 5 * 100) * 0.20
            + elite_density * 0.20
            + positional_diversity * 0.10
            + team_diversity * 0.10
            + depth_score * 0.10,
            2,
        )

        top_performers = (
            event_df.sort_values("Overall Score", ascending=False).head(3)["Player Name"].tolist()
        )
        promising_prospects = (
            event_df.sort_values(["Growth Upside", "Overall Score"], ascending=False)
            .head(3)["Player Name"]
            .tolist()
        )
        position_breakdown = event_df["Position"].value_counts().to_dict()

        summaries.append(
            {
                "Event Name": event_name,
                "Event Date": event_df["Event Date"].min(),
                "Talent Index": talent_index,
                "Grade": _grade_from_index(talent_index),
                "Players Evaluated": player_count,
                "Average Overall Score": round(avg_overall, 2),
                "Average Growth Upside": round(avg_upside, 2),
                "Elite Player Density": round(elite_density, 2),
                "Positional Diversity Score": round(positional_diversity, 2),
                "Team Diversity Score": round(team_diversity, 2),
                "Event Depth Score": round(depth_score, 2),
                "Top Performers": ", ".join(top_performers),
                "Most Promising Prospects": ", ".join(promising_prospects),
                "Position Breakdown": ", ".join(
                    f"{pos}: {cnt}" for pos, cnt in position_breakdown.items()
                ),
            }
        )

    summary_df = pd.DataFrame(summaries)
    if summary_df.empty:
        return summary_df
    return summary_df.sort_values(
        ["Talent Index", "Players Evaluated"], ascending=[False, False]
    ).reset_index(drop=True)


def get_event_detail(df: pd.DataFrame, event_name: str) -> dict[str, object]:
    event_df = df[df["Event Name"] == event_name].copy()
    summary = calculate_event_summary(event_df).iloc[0].to_dict()
    summary["event_df"] = event_df.sort_values(
        ["Overall Score", "Growth Upside"], ascending=False
    ).reset_index(drop=True)
    return summary


def comparison_metrics(summary_df: pd.DataFrame, event_names: list[str]) -> pd.DataFrame:
    metrics = [
        "Talent Index",
        "Average Overall Score",
        "Average Growth Upside",
        "Elite Player Density",
        "Positional Diversity Score",
        "Team Diversity Score",
        "Event Depth Score",
    ]
    filtered = summary_df[summary_df["Event Name"].isin(event_names)]
    return filtered.melt(
        id_vars=["Event Name"], value_vars=metrics, var_name="Metric", value_name="Value"
    ).reset_index(drop=True)
