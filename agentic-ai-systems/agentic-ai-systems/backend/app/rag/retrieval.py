"""Ties chunking + the TF-IDF index together into a single build/query interface."""
from __future__ import annotations

from app.rag.chunking import chunk_text
from app.rag.embeddings import TfidfIndex
from app.state import Source


def build_index(sources: list[Source]) -> TfidfIndex:
    index = TfidfIndex()
    chunks = []
    for s in sources:
        text = s.fetched_text or s.snippet
        chunks.extend(chunk_text(text, s.url))
    index.build(chunks)
    return index


def retrieve_evidence(index: TfidfIndex, claim: str, k: int = 3):
    """Returns [(chunk, score), ...] most relevant to `claim`, best first."""
    return index.search(claim, k=k)
