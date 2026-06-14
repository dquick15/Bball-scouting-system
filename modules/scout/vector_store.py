"""
modules/scout/vector_store.py
==============================
FAISS vector index with OpenAI embeddings and a local hash-based fallback.
Ported from scout_chatbot/vector_store.py — no logic changes, import paths updated.
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path

import faiss
import numpy as np
from openai import OpenAI


class ScoutVectorStore:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.index: faiss.IndexFlatIP | None = None
        self.records: list[dict[str, object]] = []
        self.embeddings: np.ndarray | None = None
        self.backend = "openai"

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    def _hash_embed_texts(self, texts: list[str], dimensions: int = 512) -> np.ndarray:
        """Deterministic local fallback — no API call required."""
        embeddings = np.zeros((len(texts), dimensions), dtype="float32")
        for row_index, text in enumerate(texts):
            tokens = re.findall(r"[a-z0-9']+", str(text).lower())
            for token in tokens:
                bucket = hash(token) % dimensions
                embeddings[row_index, bucket] += 1.0
        faiss.normalize_L2(embeddings)
        return embeddings

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        try:
            response = self.client.embeddings.create(model=self.model, input=texts)
            embeddings = np.array([item.embedding for item in response.data], dtype="float32")
            faiss.normalize_L2(embeddings)
            self.backend = "openai"
            return embeddings
        except Exception:
            self.backend = "hash"
            return self._hash_embed_texts(texts)

    # ------------------------------------------------------------------
    # Index lifecycle
    # ------------------------------------------------------------------

    def build(self, records: list[dict[str, object]]) -> None:
        self.records = records
        texts = [str(record["document"]) for record in records]
        embeddings = self._embed_texts(texts)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        self.embeddings = embeddings

    def save(self, index_path: str | Path, metadata_path: str | Path) -> None:
        if self.index is None:
            raise ValueError("Vector index has not been built.")
        faiss.write_index(self.index, str(index_path))
        with open(metadata_path, "wb") as fh:
            pickle.dump(
                {"records": self.records, "embeddings": self.embeddings, "backend": self.backend},
                fh,
            )

    def load(self, index_path: str | Path, metadata_path: str | Path) -> None:
        self.index = faiss.read_index(str(index_path))
        with open(metadata_path, "rb") as fh:
            payload = pickle.load(fh)
        self.records = payload["records"]
        self.embeddings = payload["embeddings"]
        self.backend = payload.get("backend", "openai")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def similarity_search(self, query: str, top_k: int = 6) -> list[dict[str, object]]:
        if self.index is None:
            raise ValueError("Vector index has not been built.")
        query_embedding = self._embed_texts([query])
        scores, indices = self.index.search(query_embedding, top_k)
        matches: list[dict[str, object]] = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0:
                continue
            record = dict(self.records[idx])
            record["similarity"] = float(score)
            matches.append(record)
        return matches

    def similar_players(self, player_name: str, top_k: int = 5) -> list[dict[str, object]]:
        if self.index is None or self.embeddings is None:
            raise ValueError("Vector index has not been built.")
        source_index = next(
            (i for i, r in enumerate(self.records) if str(r["Player Name"]).lower() == player_name.lower()),
            None,
        )
        if source_index is None:
            return []
        query_embedding = self.embeddings[source_index : source_index + 1]
        scores, indices = self.index.search(query_embedding, top_k + 1)
        matches: list[dict[str, object]] = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0 or idx == source_index:
                continue
            record = dict(self.records[idx])
            record["similarity"] = float(score)
            matches.append(record)
        return matches[:top_k]
