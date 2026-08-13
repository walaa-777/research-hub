"""
Web search tool.

Priority: TAVILY_API_KEY (real, ranked search) -> duckduckgo-search (real, keyless)
-> synthetic demo results (no network at all). The pipeline always calls
`web_search(query)` and gets back the same `list[dict]` shape regardless of which
backend served it.
"""
from __future__ import annotations

import hashlib
import os


def _demo_results(query: str, n: int = 5) -> list[dict]:
    seed = int(hashlib.sha256(query.encode()).hexdigest()[:8], 16)
    return [
        {
            "url": f"https://example-source-{i}.org/articles/{seed % 9999}-{i}",
            "title": f"[DEMO MODE] Synthetic result {i} for '{query}'",
            "snippet": (
                f"[DEMO MODE] This is placeholder text standing in for a real web "
                f"result about '{query}'. No network call was made."
            ),
        }
        for i in range(n)
    ]


def _tavily_search(query: str, n: int) -> list[dict]:
    from tavily import TavilyClient  # imported lazily; optional dependency

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    resp = client.search(query=query, max_results=n)
    return [
        {"url": r["url"], "title": r.get("title", r["url"]), "snippet": r.get("content", "")}
        for r in resp.get("results", [])
    ]


def _duckduckgo_search(query: str, n: int) -> list[dict]:
    from duckduckgo_search import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=n))
    return [
        {"url": r["href"], "title": r.get("title", r["href"]), "snippet": r.get("body", "")}
        for r in results
    ]


def web_search(query: str, n: int = 5) -> list[dict]:
    if os.environ.get("TAVILY_API_KEY"):
        try:
            return _tavily_search(query, n)
        except Exception:
            pass
    if os.environ.get("ANTHROPIC_API_KEY"):
        # Real pipeline is on, but no Tavily key -- fall back to keyless DuckDuckGo.
        try:
            return _duckduckgo_search(query, n)
        except Exception:
            pass
    return _demo_results(query, n)
