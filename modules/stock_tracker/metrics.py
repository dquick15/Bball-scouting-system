"""
modules/stock_tracker/metrics.py
=================================
Stock-movement calculations for the Player Stock Tracker page.
Unchanged logic from player_stock_tracker/metrics.py — now importable
from a single shared location.
"""
from __future__ import annotations

import pandas as pd


STOCK_UP_THRESHOLD = 0.5
STOCK_DOWN_THRESHOLD = -0.5


def latest_player_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.sort_values(["Player Name", "Event Date", "Event Name"])
    latest = ordered.groupby("Player Name", as_index=False).tail(1)
    return latest.sort_values("Overall Score", ascending=False).reset_index(drop=True)


def get_dashboard_overview(df: pd.DataFrame) -> dict[str, float | int]:
    latest = latest_player_snapshot(df)
    return {
        "total_players": int(df["Player Name"].nunique()),
        "total_events": int(df["Event Name"].nunique()),
        "average_player_score": round(float(latest["Overall Score"].mean()), 2) if not latest.empty else 0.0,
    }


def get_top_players(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    latest = latest_player_snapshot(df)
    columns = ["Player Name", "Team", "Grade", "Position", "Event Name", "Overall Score"]
    return latest[columns].head(limit).reset_index(drop=True)


def stock_label(stock_change: float) -> str:
    if stock_change >= STOCK_UP_THRESHOLD:
        return "Stock Up"
    if stock_change <= STOCK_DOWN_THRESHOLD:
        return "Stock Down"
    return "Stable"


def stock_movement_for_player(player_df: pd.DataFrame) -> dict[str, float | str]:
    ordered = player_df.sort_values(["Event Date", "Event Name"]).reset_index(drop=True)
    first_score = float(ordered.iloc[0]["Overall Score"])
    last_score = float(ordered.iloc[-1]["Overall Score"])
    movement = round(last_score - first_score, 2)
    return {
        "starting_score": round(first_score, 2),
        "current_score": round(last_score, 2),
        "stock_movement": movement,
        "stock_label": stock_label(movement),
    }


def player_stock_summary(df: pd.DataFrame) -> pd.DataFrame:
    summaries: list[dict[str, object]] = []

    for player_name, player_df in df.groupby("Player Name"):
        ordered = player_df.sort_values(["Event Date", "Event Name"]).reset_index(drop=True)
        movement = float(ordered.iloc[-1]["Overall Score"] - ordered.iloc[0]["Overall Score"])
        latest = ordered.iloc[-1]
        summaries.append(
            {
                "Player Name": player_name,
                "Team": latest["Team"],
                "Grade": latest["Grade"],
                "Position": latest["Position"],
                "Current Overall Score": round(float(latest["Overall Score"]), 2),
                "Stock Movement": round(movement, 2),
                "Stock Label": stock_label(movement),
            }
        )

    summary_df = pd.DataFrame(summaries)
    if summary_df.empty:
        return summary_df

    return summary_df.sort_values("Stock Movement", ascending=False).reset_index(drop=True)


def get_top_risers(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    return player_stock_summary(df).head(limit).reset_index(drop=True)


def get_top_fallers(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    return player_stock_summary(df).sort_values("Stock Movement", ascending=True).head(limit).reset_index(drop=True)
