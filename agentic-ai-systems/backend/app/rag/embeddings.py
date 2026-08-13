"""
Local TF-IDF "embeddings" -- deliberately not calling an external embeddings API.

This keeps the RAG path fully offline (works in demo mode, works in `pytest`,
works with zero API keys) while still giving the Fact-Checker real vector
similarity search over retrieved source text. See docs/write-up.md 3.3.
"""
from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.rag.chunking import Chunk


@dataclass
class IndexedChunk:
    chunk: Chunk
    vector_row: int


class TfidfIndex:
    """A tiny in-memory vector store, rebuilt per research thread."""

    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(stop_words="english", max_features=4096)
        self._chunks: list[Chunk] = []
        self._matrix = None

    def build(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        if not chunks:
            self._matrix = None
            return
        self._matrix = self._vectorizer.fit_transform([c.text for c in chunks])

    def search(self, query: str, k: int = 5) -> list[tuple[Chunk, float]]:
        if not self._chunks or self._matrix is None:
            return []
        q_vec = self._vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self._matrix)[0]
        ranked = sorted(zip(self._chunks, sims), key=lambda pair: pair[1], reverse=True)
        return [(c, float(s)) for c, s in ranked[:k] if s > 0]
