"""
LangSmith wiring (opt-in via LANGCHAIN_API_KEY / LANGCHAIN_TRACING_V2) plus a
small local helper for pulling a concrete finding out of a run's trace without
needing the LangSmith UI -- used by notebook/demo.ipynb to produce the
"captures a trace finding" step mentioned in the README.
"""
from __future__ import annotations

import os

from app.state import ResearchState


def tracing_enabled() -> bool:
    return bool(os.environ.get("LANGCHAIN_API_KEY")) and os.environ.get(
        "LANGCHAIN_TRACING_V2", "false"
    ).lower() == "true"


def configure_tracing() -> None:
    """Call once at process startup (server.py does this). No-op if unconfigured."""
    if tracing_enabled():
        os.environ.setdefault("LANGCHAIN_PROJECT", "research-hub")
        # langchain-core reads LANGCHAIN_TRACING_V2 / LANGCHAIN_API_KEY / LANGCHAIN_PROJECT
        # directly from the environment; nothing else to do here.


def find_trace_insight(state: ResearchState) -> str:
    """
    Local (non-LangSmith) trace analysis: walks state.trace and reports the most
    expensive or most retried step. This is the "local trace-finding helper"
    referenced in the README architecture table.
    """
    retries = [e for e in state.trace if e.get("event") == "retry"]
    fallbacks = [e for e in state.trace if e.get("event") == "fallback_triggered"]
    revisions = state.revision_count

    if fallbacks:
        agent = fallbacks[0]["agent"]
        return f"Trace finding: '{agent}' triggered a fallback ({len(fallbacks)}x)."
    if retries:
        agent = retries[0]["agent"]
        return f"Trace finding: '{agent}' needed {len(retries)} retries before succeeding."
    if revisions:
        return f"Trace finding: report needed {revisions} revision round(s) before approval."
    return "Trace finding: pipeline completed cleanly on the first pass, no retries or revisions."
