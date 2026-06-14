"""
modules/scout/chatbot.py
=========================
RAG-powered Basketball Scout Assistant with:
 - Structured intent parsing (age groups, role/position filters, stock/upside/top queries)
 - OpenAI answer generation with graceful fallback
 - Pro-analyst formatted fallback answers

Enhanced from scout_chatbot/chatbot.py:
 - Age-group detection: 15U / 16U / 17U / MS / HS
 - Role/position detection: guard, point guard, combo guard, wing, forward, big, center
 - Pro-analyst tone in _fallback_answer()
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from openai import OpenAI

from modules.scout.ingest import build_records, dataframe_signature
from modules.scout.vector_store import ScoutVectorStore


INDEX_DIR = Path("aau_system/.vector_cache")
INDEX_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Grade / role mapping tables
# ---------------------------------------------------------------------------

_AGE_GROUP_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\b15u\b", re.IGNORECASE), ["15U", "MS"]),
    (re.compile(r"\b16u\b", re.IGNORECASE), ["16U", "HS"]),
    (re.compile(r"\b17u\b", re.IGNORECASE), ["17U", "HS"]),
    (re.compile(r"\b18u\b", re.IGNORECASE), ["18U", "HS"]),
    (re.compile(r"\b\bms\b\b", re.IGNORECASE), ["MS"]),
    (re.compile(r"\b\bhs\b\b", re.IGNORECASE), ["HS"]),
    (re.compile(r"\bmiddle.?school\b", re.IGNORECASE), ["MS"]),
    (re.compile(r"\bhigh.?school\b", re.IGNORECASE), ["HS"]),
]

_ROLE_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\bpoint\s+guard\b", re.IGNORECASE), ["PG"]),
    (re.compile(r"\bcombo\s+guard\b", re.IGNORECASE), ["PG", "SG"]),
    (re.compile(r"\b\bpg\b\b", re.IGNORECASE), ["PG"]),
    (re.compile(r"\b\bsg\b\b", re.IGNORECASE), ["SG"]),
    (re.compile(r"\b\bsf\b\b", re.IGNORECASE), ["SF"]),
    (re.compile(r"\b\bpf\b\b", re.IGNORECASE), ["PF"]),
    (re.compile(r"\b\bc\b\b", re.IGNORECASE), ["C"]),
    (re.compile(r"\bguard\b", re.IGNORECASE), ["PG", "SG"]),
    (re.compile(r"\bwing\b", re.IGNORECASE), ["SG", "SF"]),
    (re.compile(r"\bforward\b", re.IGNORECASE), ["SF", "PF"]),
    (re.compile(r"\bbig\b", re.IGNORECASE), ["PF", "C"]),
    (re.compile(r"\bcenter\b", re.IGNORECASE), ["C"]),
    (re.compile(r"\bpower\s+forward\b", re.IGNORECASE), ["PF"]),
    (re.compile(r"\bsmall\s+forward\b", re.IGNORECASE), ["SF"]),
    (re.compile(r"\bshoot\w*\s+guard\b", re.IGNORECASE), ["SG"]),
]


def _extract_age_group_filter(question: str) -> list[str]:
    """Return a list of Grade values implied by age-group language in the question."""
    grades: list[str] = []
    for pattern, values in _AGE_GROUP_PATTERNS:
        if pattern.search(question):
            grades.extend(values)
    return list(dict.fromkeys(grades))  # deduplicated, insertion-order


def _extract_role_filter(question: str) -> list[str]:
    """Return a list of Position values implied by role language in the question."""
    positions: list[str] = []
    for pattern, values in _ROLE_PATTERNS:
        if pattern.search(question):
            positions.extend(values)
    return list(dict.fromkeys(positions))


def _apply_prefilters(question: str, df: pd.DataFrame) -> pd.DataFrame:
    """Narrow the DataFrame based on age-group and role mentions in the question."""
    age_grades = _extract_age_group_filter(question)
    role_positions = _extract_role_filter(question)

    filtered = df.copy()
    if age_grades and "Grade" in filtered.columns:
        filtered = filtered[filtered["Grade"].isin(age_grades)]
    if role_positions and "Position" in filtered.columns:
        filtered = filtered[filtered["Position"].isin(role_positions)]

    # If filtering wiped the DataFrame, fall back to full set to avoid empty answers
    return filtered if not filtered.empty else df


# ---------------------------------------------------------------------------
# Main assistant class
# ---------------------------------------------------------------------------

class BasketballScoutAssistant:
    def __init__(
        self,
        api_key: str,
        chat_model: str = "gpt-4.1-mini",
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self.client = OpenAI(api_key=api_key)
        self.chat_model = chat_model
        self.vector_store = ScoutVectorStore(api_key=api_key, model=embedding_model)

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def ensure_index(self, df: pd.DataFrame) -> None:
        signature = dataframe_signature(df)
        index_path = INDEX_DIR / f"{signature}.faiss"
        metadata_path = INDEX_DIR / f"{signature}.pkl"

        if index_path.exists() and metadata_path.exists():
            self.vector_store.load(index_path, metadata_path)
            return

        records = build_records(df)
        self.vector_store.build(records)
        self.vector_store.save(index_path, metadata_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer_question(self, question: str, df: pd.DataFrame) -> dict[str, object]:
        scoped_df = _apply_prefilters(question, df)
        intents = self._structured_intents(question, scoped_df)
        retrieved_records = self.vector_store.similarity_search(question, top_k=6)
        response_text = self._generate_answer(question, intents, retrieved_records)
        return {
            "answer": response_text,
            "retrieved_records": retrieved_records,
            "insights": intents,
            "retrieval_backend": self.vector_store.backend,
        }

    def player_profile(self, player_name: str, df: pd.DataFrame) -> dict[str, object] | None:
        player_df = df[df["Player Name"] == player_name].sort_values(["Event Date", "Event Name"])
        if player_df.empty:
            return None
        latest = player_df.iloc[-1].to_dict()
        earliest = player_df.iloc[0].to_dict()
        return {
            "player": latest,
            "history": player_df,
            "improvement": round(float(latest["Overall Score"] - earliest["Overall Score"]), 2),
        }

    def event_summary(self, event_name: str, df: pd.DataFrame) -> dict[str, object] | None:
        event_df = df[df["Event Name"] == event_name].copy()
        if event_df.empty:
            return None
        return {
            "event_name": event_name,
            "player_count": int(event_df["Player Name"].nunique()),
            "average_score": round(float(event_df["Overall Score"].mean()), 2),
            "top_players": event_df.sort_values("Overall Score", ascending=False).head(5),
            "upside_players": event_df.sort_values(
                ["Growth Upside", "Overall Score"], ascending=False
            ).head(5),
            "positions": event_df["Position"].value_counts().to_dict(),
        }

    def prospect_rankings(
        self, df: pd.DataFrame, metric: str = "Overall Score", top_k: int = 10
    ) -> pd.DataFrame:
        columns = ["Player Name", "Team", "Grade", "Position", "Event Name", metric]
        return df.sort_values(metric, ascending=False)[columns].head(top_k).reset_index(drop=True)

    def similar_players(self, player_name: str) -> list[dict[str, object]]:
        return self.vector_store.similar_players(player_name, top_k=5)

    # ------------------------------------------------------------------
    # Intent extraction
    # ------------------------------------------------------------------

    def _structured_intents(self, question: str, df: pd.DataFrame) -> dict[str, object]:
        lowered = question.lower()
        insights: dict[str, object] = {}

        if any(kw in lowered for kw in ["improved", "season", "stock", "rising", "riser"]):
            groups = []
            for player_name, pdf in df.groupby("Player Name"):
                ordered = pdf.sort_values(["Event Date", "Event Name"])
                improvement = float(ordered.iloc[-1]["Overall Score"] - ordered.iloc[0]["Overall Score"])
                groups.append(
                    {
                        "Player Name": player_name,
                        "Improvement": round(improvement, 2),
                        "Current Score": round(float(ordered.iloc[-1]["Overall Score"]), 2),
                        "Team": ordered.iloc[-1]["Team"],
                        "Grade": ordered.iloc[-1]["Grade"],
                        "Position": ordered.iloc[-1]["Position"],
                    }
                )
            insights["most_improved"] = pd.DataFrame(groups).sort_values(
                ["Improvement", "Current Score"], ascending=[False, False]
            ).head(10)

        if any(kw in lowered for kw in ["upside", "ceiling", "potential", "prospect"]):
            upside_df = df.dropna(subset=["Growth Upside"]).sort_values(
                ["Growth Upside", "Overall Score"], ascending=False
            )
            insights["highest_upside"] = upside_df[
                ["Player Name", "Team", "Grade", "Position", "Event Name", "Growth Upside", "Overall Score"]
            ].head(10)

        if any(kw in lowered for kw in ["top", "best", "ranked", "rankings", "elite"]):
            insights["top_players"] = df[
                ["Player Name", "Team", "Grade", "Position", "Event Name", "Overall Score"]
            ].sort_values("Overall Score", ascending=False).head(10)

        player_match = re.search(r"similar to ([a-zA-Z .'-]+)", question, flags=re.IGNORECASE)
        if player_match:
            insights["similar_players"] = self.similar_players(player_match.group(1).strip())

        return insights

    # ------------------------------------------------------------------
    # Answer generation
    # ------------------------------------------------------------------

    def _generate_answer(
        self,
        question: str,
        structured_insights: dict[str, object],
        retrieved_records: list[dict[str, object]],
    ) -> str:
        serialized_records = [
            {
                "Player Name": r["Player Name"],
                "Team": r["Team"],
                "Grade": r["Grade"],
                "Position": r["Position"],
                "Event Name": r["Event Name"],
                "Event Date": str(r["Event Date"]),
                "Overall Score": r["Overall Score"],
                "Growth Upside": r.get("Growth Upside"),
                "Strengths": r["Strengths"],
                "Development Areas": r["Development Areas"],
                "Projection": r["Projection"],
                "Similarity": round(float(r["similarity"]), 4),
            }
            for r in retrieved_records
        ]

        structured_sections: list[str] = []
        for label, value in structured_insights.items():
            if isinstance(value, pd.DataFrame):
                structured_sections.append(f"{label}:\n{value.to_string(index=False)}")
            else:
                structured_sections.append(f"{label}: {value}")

        system_prompt = (
            "You are an expert basketball scouting analyst with 15+ years evaluating youth and high-school talent. "
            "Answer only from the provided scouting context. "
            "Be concise, specific, and analytical. "
            "Use basketball evaluation language: floors, ceilings, translatable skills, role projection, effort traits. "
            "When ranking players, briefly justify each inclusion. "
            "If data is insufficient for a definitive answer, state what context is missing."
        )
        structured_block = "\n\n".join(structured_sections) if structured_sections else "None"
        user_prompt = (
            f"Scout's question:\n{question}\n\n"
            f"Pre-filtered structured data:\n{structured_block}\n\n"
            f"Retrieved scouting records:\n{serialized_records}"
        )

        try:
            response = self.client.responses.create(
                model=self.chat_model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
                ],
                max_output_tokens=700,
            )
            return response.output_text.strip()
        except Exception:
            return self._fallback_answer(question, structured_insights, retrieved_records)

    # ------------------------------------------------------------------
    # Pro-analyst fallback (no API required)
    # ------------------------------------------------------------------

    def _fallback_answer(
        self,
        question: str,
        structured_insights: dict[str, object],
        retrieved_records: list[dict[str, object]],
    ) -> str:
        """
        Deterministic, pro-analyst formatted answer from structured data.
        Used when OpenAI API is unavailable or quota is exhausted.
        """
        lowered = question.lower()

        if "most_improved" in structured_insights:
            df = structured_insights["most_improved"].head(5)
            lines = [
                f"**{r['Player Name']}** ({r['Grade']} {r['Position']}, {r['Team']}) — "
                f"stock movement: {r['Improvement']:+.2f} pts | current rating: {r['Current Score']:.2f}. "
                f"{'Trending up sharply — evaluate for role expansion.' if r['Improvement'] >= 0.5 else 'Steady positive trend — worth continued monitoring.'}"
                for r in df.to_dict(orient="records")
            ]
            return (
                "**Most Improved Players — Current Evaluation Cycle**\n\n"
                + "\n".join(f"{i+1}. {line}" for i, line in enumerate(lines))
                + "\n\n_Note: Movement calculated first-to-last event in the current filter set._"
            )

        if "highest_upside" in structured_insights and any(
            kw in lowered for kw in ["upside", "ceiling", "potential", "prospect"]
        ):
            df = structured_insights["highest_upside"].head(5)
            lines = [
                f"**{r['Player Name']}** ({r['Grade']} {r['Position']}, {r['Team']}) — "
                f"Growth Upside: {r['Growth Upside']:.2f} | Overall: {r['Overall Score']:.2f}. "
                f"{'High-ceiling prospect; production may trail projectable tools.' if r['Growth Upside'] >= 4.0 else 'Solid developmental upside; track skill refinement.'}"
                for r in df.to_dict(orient="records")
            ]
            return (
                "**Highest-Ceiling Prospects — Growth Upside Rankings**\n\n"
                + "\n".join(f"{i+1}. {line}" for i, line in enumerate(lines))
                + "\n\n_Upside ratings reflect projectable tools and developmental trajectory, not current output._"
            )

        if "top_players" in structured_insights and any(
            kw in lowered for kw in ["top", "best", "ranked", "elite", "guard", "forward", "wing", "big", "center"]
        ):
            df = structured_insights["top_players"].head(5)
            lines = [
                f"**{r['Player Name']}** ({r['Grade']} {r['Position']}, {r['Team']}) — "
                f"Overall: {r['Overall Score']:.2f} at {r['Event Name']}."
                for r in df.to_dict(orient="records")
            ]
            return (
                "**Top-Rated Players — Current Evaluation Set**\n\n"
                + "\n".join(f"{i+1}. {line}" for i, line in enumerate(lines))
                + "\n\n_Rankings reflect the most recent event score for each player in the current filter._"
            )

        if "similar_players" in structured_insights and structured_insights["similar_players"]:
            players = structured_insights["similar_players"][:5]
            lines = [
                f"**{r['Player Name']}** ({r.get('Grade', '—')} {r.get('Position', '—')}, {r.get('Team', '—')}) — "
                f"profile similarity: {r['similarity']:.3f}. "
                f"Overall: {float(r.get('Overall Score', 0)):.2f}."
                for r in players
            ]
            return (
                "**Comparable Player Profiles**\n\n"
                + "\n".join(f"{i+1}. {line}" for i, line in enumerate(lines))
                + "\n\n_Similarity is computed from scouting profile embeddings — positional role and skill signature are primary factors._"
            )

        if retrieved_records:
            top = retrieved_records[:5]
            lines = [
                f"**{r['Player Name']}** ({r.get('Grade', '—')} {r.get('Position', '—')}, {r.get('Team', '—')}) — "
                f"Overall: {float(r.get('Overall Score', 0)):.2f} | "
                f"Strengths: {r.get('Strengths', 'N/A')} | "
                f"Projection: {r.get('Projection', 'N/A')}."
                for r in top
            ]
            return (
                "**Closest Scouting Matches**\n\n"
                + "\n".join(f"{i+1}. {line}" for i, line in enumerate(lines))
                + "\n\n_Results retrieved via vector similarity from the scouting database. AI synthesis unavailable — showing raw context._"
            )

        return (
            "No matching scouting context was found for that query within the current filter set. "
            "Try broadening your filters or rephrasing the question."
        )
