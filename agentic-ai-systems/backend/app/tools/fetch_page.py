"""Fetches and extracts readable text from a URL, with a keyless demo fallback."""
from __future__ import annotations

import os


def fetch_page(url: str) -> str:
    if url.startswith("https://example-source-") or not os.environ.get("ANTHROPIC_API_KEY"):
        return (
            f"[DEMO MODE] Synthetic page body for {url}. In live mode this text is "
            f"the real, cleaned article body fetched over HTTP and parsed with "
            f"BeautifulSoup, ready for the RAG chunker."
        )
    import httpx
    from bs4 import BeautifulSoup

    resp = httpx.get(url, timeout=10.0, follow_redirects=True)
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())
