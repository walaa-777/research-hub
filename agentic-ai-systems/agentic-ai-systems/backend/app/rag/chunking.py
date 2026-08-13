"""Simple fixed-window text chunker with overlap, used before local TF-IDF indexing."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    source_url: str
    index: int


def chunk_text(text: str, source_url: str, size: int = 800, overlap: int = 150) -> list[Chunk]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(Chunk(text=text[start:end], source_url=source_url, index=idx))
        if end == len(text):
            break
        start = end - overlap
        idx += 1
    return chunks
