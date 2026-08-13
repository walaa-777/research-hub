"""Search worker: turns the query (or a follow-up query after rejections) into Sources."""
from __future__ import annotations

from app.state import ResearchState, Source
from app.tools.web_search import web_search


def run_search(state: ResearchState) -> ResearchState:
    query = state.query
    if state.rejected_sources and not state.accepted_sources:
        # Previous pass yielded nothing usable -- broaden/refine instead of repeating verbatim.
        query = f"{state.query} (authoritative primary source)"

    results = web_search(query, n=6)
    seen = {s.url for s in state.sources}
    for r in results:
        if r["url"] in seen:
            continue
        state.sources.append(Source(url=r["url"], title=r["title"], snippet=r["snippet"]))
        seen.add(r["url"])

    state.log("search", "search_complete", query=query, found=len(results))
    return state
